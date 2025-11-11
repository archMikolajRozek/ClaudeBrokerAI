"""
Market Data Agent - Finazon.io Integration
Pobiera dane z Finazon.io REST API (trial: AAPL, TSLA, GOOG)

LIMITY TRIAL:
- 5 API requests/min
- Dostępne tickery: AAPL, TSLA, GOOG
- Interval: 1m, 5m, 1h, 1d (użyjemy 1m)

STRATEGIA:
- Polling co 60 sekund dla 3 tickerów
- 3 req/min (bezpiecznie poniżej limitu 5 req/min)
"""

import asyncio
import os
import sys
import time
from datetime import datetime, timezone
from typing import Dict, List, Optional

import aiohttp
import redis.asyncio as redis
from dotenv import load_dotenv

# Dodaj packages do path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../packages'))
from common.schemas import MarketCandleMessage, StreamNames
from common.redis_utils import publish_message

load_dotenv()


class FinazonClient:
    """
    REST API client dla Finazon.io

    ENDPOINTS:
    - /finazon/us_stocks_essential/time_series - świece OHLCV
    - /finazon/us_stocks_essential/price - pojedyncza cena
    - /finazon/us_stocks_essential/ticker_snapshot - snapshot z multiple data

    TRIAL LIMITS:
    - 5 req/min dla time_series
    - 10 req/min dla price
    - Dostępne tickery: AAPL, TSLA, GOOG
    """

    def __init__(self, api_key: str):
        """
        Args:
            api_key: Finazon API key
        """
        self.api_key = api_key
        self.base_url = "https://api.finazon.io/latest"

        # Track request times dla rate limiting
        self.request_times = []
        self.max_requests_per_minute = 5

    async def _check_rate_limit(self):
        """
        Sprawdź czy nie przekraczamy limitu 5 req/min
        Jeśli tak, poczekaj
        """
        now = time.time()

        # Usuń requesty starsze niż 60 sekund
        self.request_times = [t for t in self.request_times if now - t < 60]

        # Jeśli mamy >= 5 requestów w ostatniej minucie, czekaj
        if len(self.request_times) >= self.max_requests_per_minute:
            oldest_request = min(self.request_times)
            wait_time = 60 - (now - oldest_request)
            if wait_time > 0:
                print(f"[FinazonAPI] Rate limit reached, waiting {wait_time:.1f}s...")
                await asyncio.sleep(wait_time + 0.5)  # +0.5s buffer

        # Zapisz czas tego requesta
        self.request_times.append(time.time())

    async def get_latest_candle(self, ticker: str, interval: str = "1m") -> Optional[Dict]:
        """
        Pobierz ostatnią świecę dla tickera

        Args:
            ticker: Symbol akcji (AAPL, TSLA, GOOG na trial)
            interval: Interval świecy (1m, 5m, 1h, 1d)

        Returns:
            Dict z kluczami: t (timestamp), o, h, l, c, v
            lub None jeśli błąd
        """
        await self._check_rate_limit()

        url = f"{self.base_url}/finazon/us_stocks_essential/time_series"
        params = {
            "ticker": ticker,
            "interval": interval,
            "page_size": 1,  # Tylko ostatnia świeca
            "order": "desc",  # Najpierw najnowsze
            "apikey": self.api_key
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params, timeout=10) as response:
                    if response.status != 200:
                        text = await response.text()
                        print(f"[FinazonAPI] ✗ HTTP {response.status} for {ticker}: {text}")
                        return None

                    data = await response.json()

                    # Format odpowiedzi: {"data": [{"t": ..., "o": ..., "h": ..., "l": ..., "c": ..., "v": ...}]}
                    if not data.get("data"):
                        print(f"[FinazonAPI] ⚠️  No data for {ticker}")
                        return None

                    candle = data["data"][0]
                    print(f"[FinazonAPI] ✓ {ticker}: close=${candle['c']:.2f} vol={candle['v']:,}")
                    return candle

        except asyncio.TimeoutError:
            print(f"[FinazonAPI] ✗ Timeout fetching {ticker}")
            return None
        except Exception as e:
            print(f"[FinazonAPI] ✗ Error fetching {ticker}: {e}")
            return None

    async def get_current_price(self, ticker: str) -> Optional[float]:
        """
        Pobierz aktualną cenę tickera (prostszy endpoint, 10 req/min)

        Args:
            ticker: Symbol akcji

        Returns:
            Cena jako float lub None
        """
        url = f"{self.base_url}/finazon/us_stocks_essential/price"
        params = {
            "ticker": ticker,
            "apikey": self.api_key
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params, timeout=10) as response:
                    if response.status != 200:
                        return None

                    data = await response.json()
                    # Format: {"p": 184.95}
                    return data.get("p")

        except Exception as e:
            print(f"[FinazonAPI] ✗ Error fetching price for {ticker}: {e}")
            return None


class MarketDataFinazonAgent:
    """
    Agent pobierający dane z Finazon.io i publikujący do Redis

    FLOW:
    1. Co 60 sekund pobierz świece dla AAPL, TSLA, GOOG
    2. Normalizuj do MarketCandleMessage
    3. Publikuj do Redis stream: market_candles
    """

    def __init__(self):
        # Redis connection
        self.redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
        self.redis_client = None

        # Finazon API
        self.finazon_api_key = os.getenv("FINAZON_API_KEY")
        if not self.finazon_api_key:
            raise ValueError("FINAZON_API_KEY not set in environment")

        self.finazon = FinazonClient(self.finazon_api_key)

        # Watchlist (TRIAL: tylko AAPL, TSLA, GOOG dostępne)
        watchlist_str = os.getenv("WATCHLIST", "AAPL,TSLA,GOOG")
        self.watchlist = [t.strip() for t in watchlist_str.split(",")]

        # Filter tylko dostępne na trial
        trial_tickers = {"AAPL", "TSLA", "GOOG"}
        self.watchlist = [t for t in self.watchlist if t in trial_tickers]

        # Polling interval (seconds)
        self.poll_interval = int(os.getenv("MARKET_DATA_UPDATE_INTERVAL", "60"))

        print(f"[market_data_finazon] Initialized")
        print(f"  API: Finazon.io (trial)")
        print(f"  Watchlist: {self.watchlist}")
        print(f"  Poll interval: {self.poll_interval}s")
        print(f"  Rate limit: 5 req/min")

    async def connect_redis(self):
        """Połącz się z Redis"""
        self.redis_client = redis.from_url(self.redis_url, decode_responses=True)
        # Test connection
        await self.redis_client.ping()
        print(f"[market_data_finazon] ✓ Connected to Redis")

    async def publish_candle(self, ticker: str, candle_data: Dict):
        """
        Publikuj świecę do Redis stream

        Args:
            ticker: Symbol akcji
            candle_data: Dict z kluczami t, o, h, l, c, v
        """
        # Konwertuj timestamp Unix (seconds) na ISO string
        timestamp = datetime.fromtimestamp(candle_data["t"], tz=timezone.utc).isoformat()

        # Utwórz message
        message = MarketCandleMessage(
            ticker=ticker,
            timestamp=timestamp,
            open=float(candle_data["o"]),
            high=float(candle_data["h"]),
            low=float(candle_data["l"]),
            close=float(candle_data["c"]),
            volume=int(candle_data["v"]),
            provider="finazon"
        )

        # Publikuj do Redis
        await publish_message(
            self.redis_client,
            StreamNames.MARKET_CANDLES,
            message.model_dump()  # Pydantic 2.x: model_dump() zamiast dict()
        )

        print(f"[market_data_finazon] ✓ Published: {ticker} @ {timestamp} | ${message.close:.2f}")

    async def fetch_and_publish_all(self):
        """
        Pobierz świece dla wszystkich tickerów z watchlist i opublikuj
        """
        print(f"\n[market_data_finazon] === Fetching {len(self.watchlist)} tickers ===")

        for ticker in self.watchlist:
            candle = await self.finazon.get_latest_candle(ticker, interval="1m")

            if candle:
                await self.publish_candle(ticker, candle)
            else:
                print(f"[market_data_finazon] ⚠️  Skipping {ticker} (no data)")

            # Małe opóźnienie między tickerami (rate limiting)
            await asyncio.sleep(1)

    async def run(self):
        """Główna pętla agenta"""
        await self.connect_redis()

        print(f"[market_data_finazon] 🚀 Starting polling loop (every {self.poll_interval}s)...")

        iteration = 0
        while True:
            try:
                iteration += 1
                print(f"\n[market_data_finazon] === Iteration {iteration} ===")

                await self.fetch_and_publish_all()

                print(f"[market_data_finazon] Sleeping {self.poll_interval}s...")
                await asyncio.sleep(self.poll_interval)

            except KeyboardInterrupt:
                print("\n[market_data_finazon] Shutting down...")
                break
            except Exception as e:
                print(f"[market_data_finazon] ✗ Error in main loop: {e}")
                await asyncio.sleep(10)  # Wait before retry


if __name__ == "__main__":
    agent = MarketDataFinazonAgent()
    asyncio.run(agent.run())
