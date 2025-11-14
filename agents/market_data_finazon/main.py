"""
Market Data Agent - Finazon.io Integration (US Stocks Essential Plan)
Pobiera dane real-time dla wszystkich US stocks z Finazon.io

LIMITY US STOCKS ESSENTIAL:
- /tickers: 20 API requests/min
- /price: 10 API requests/min
- /time_series: 5 API requests/min
- /ticker_snapshot: 2 API requests/min
- /api_usage: 20 API requests/min

STRATEGIA:
- Przy starcie: pobierz listę wszystkich tickerów (cache do pliku)
- Filtruj: top 100-200 tickerów by volume, min price $5, main exchanges
- Polling co 60s dla filtered tickers
- Używaj /time_series endpoint (5 req/min limit)
"""

import asyncio
import os
import sys
import time
import json
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional
from pathlib import Path

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
    REST API client dla Finazon.io US Stocks Essential Plan

    ENDPOINTS (dokumentacja):
    - /finazon/us_stocks_essential/tickers - lista tickerów (20 req/min)
    - /finazon/us_stocks_essential/price - aktualna cena (10 req/min)
    - /finazon/us_stocks_essential/time_series - świece OHLCV (5 req/min)
    - /finazon/us_stocks_essential/ticker_snapshot - comprehensive snapshot (2 req/min)
    - /finazon/us_stocks_essential/api_usage - sprawdź zużycie API (20 req/min)

    RATE LIMITING:
    - Automatyczne czekanie gdy osiągniemy limit
    - Tracking osobnych limitów per endpoint
    """

    def __init__(self, api_key: str):
        """
        Args:
            api_key: Finazon API key (z panelu Finazon.io)
        """
        self.api_key = api_key
        self.base_url = "https://api.finazon.io/latest"

        # Track request times PER ENDPOINT dla rate limiting
        self.request_times = {
            "tickers": [],        # 20 req/min
            "price": [],          # 10 req/min
            "time_series": [],    # 5 req/min
            "snapshot": [],       # 2 req/min
            "usage": []           # 20 req/min
        }

        self.rate_limits = {
            "tickers": 20,
            "price": 10,
            "time_series": 5,
            "snapshot": 2,
            "usage": 20
        }

    async def _check_rate_limit(self, endpoint: str):
        """
        Sprawdź czy nie przekraczamy limitu dla danego endpointu
        Jeśli tak, poczekaj

        Args:
            endpoint: Nazwa endpointu (tickers, price, time_series, snapshot, usage)
        """
        now = time.time()
        limit = self.rate_limits.get(endpoint, 5)

        # Usuń requesty starsze niż 60 sekund
        self.request_times[endpoint] = [
            t for t in self.request_times[endpoint] if now - t < 60
        ]

        # Jeśli mamy >= limit requestów w ostatniej minucie, czekaj
        if len(self.request_times[endpoint]) >= limit:
            oldest_request = min(self.request_times[endpoint])
            wait_time = 60 - (now - oldest_request)
            if wait_time > 0:
                print(f"[FinazonAPI] ⏳ Rate limit reached for {endpoint} ({limit} req/min), waiting {wait_time:.1f}s...")
                await asyncio.sleep(wait_time + 0.5)  # +0.5s buffer

        # Zapisz czas tego requesta
        self.request_times[endpoint].append(time.time())

    async def get_all_tickers(self, page_size: int = 1000) -> List[Dict]:
        """
        Pobierz pełną listę US stock tickerów

        UWAGA: To może zająć kilka minut jeśli jest > 1000 tickerów (paginacja)

        Args:
            page_size: Ile tickerów na stronę (max 1000)

        Returns:
            Lista dict z kluczami: ticker, security, asset_type, currency, mic, cik, etc.
        """
        await self._check_rate_limit("tickers")

        url = f"{self.base_url}/finazon/us_stocks_essential/tickers"
        params = {
            "page_size": page_size,
            "page": 0,
            "apikey": self.api_key
        }

        all_tickers = []
        page = 0

        try:
            async with aiohttp.ClientSession() as session:
                while True:
                    params["page"] = page

                    async with session.get(url, params=params, timeout=30) as response:
                        if response.status != 200:
                            text = await response.text()
                            print(f"[FinazonAPI] ✗ HTTP {response.status} for tickers: {text}")
                            break

                        data = await response.json()
                        tickers = data.get("data", [])

                        if not tickers:
                            break

                        all_tickers.extend(tickers)
                        print(f"[FinazonAPI] ✓ Fetched page {page}: {len(tickers)} tickers (total: {len(all_tickers)})")

                        # Check if there's more pages
                        meta = data.get("meta", {})
                        pagination = meta.get("pagination", {})

                        # Jeśli otrzymaliśmy mniej niż page_size, to była ostatnia strona
                        if len(tickers) < page_size:
                            break

                        page += 1

                        # Rate limit protection - wait between pages
                        if page > 0:
                            await asyncio.sleep(3)  # 20 req/min = 3s per request

            print(f"[FinazonAPI] ✓ Total tickers fetched: {len(all_tickers)}")
            return all_tickers

        except Exception as e:
            print(f"[FinazonAPI] ✗ Error fetching tickers: {e}")
            return []

    async def get_latest_candle(self, ticker: str, interval: str = "1m") -> Optional[Dict]:
        """
        Pobierz ostatnią świecę dla tickera

        Args:
            ticker: Symbol akcji (np. AAPL, TSLA, MSFT)
            interval: Interval świecy (1m, 5m, 1h, 1d)

        Returns:
            Dict z kluczami: t (timestamp), o, h, l, c, v
            lub None jeśli błąd
        """
        await self._check_rate_limit("time_series")

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
                        # Don't spam errors - market may be closed
                        if response.status != 404:
                            print(f"[FinazonAPI] ✗ HTTP {response.status} for {ticker}: {text[:100]}")
                        return None

                    data = await response.json()

                    # Format odpowiedzi: {"data": [{"t": ..., "o": ..., "h": ..., "l": ..., "c": ..., "v": ...}]}
                    if not data.get("data"):
                        return None

                    candle = data["data"][0]
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
        await self._check_rate_limit("price")

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

        except Exception:
            return None

    async def get_ticker_snapshot(self, ticker: str) -> Optional[Dict]:
        """
        Pobierz comprehensive snapshot dla tickera
        Zawiera: 1d, 1m, 52w, changes, last trade, prev day

        UWAGA: Limit 2 req/min dla tego endpointu!

        Args:
            ticker: Symbol akcji

        Returns:
            Dict z kluczami: 1d, 1m, 52w, ch, lt, p1d
            lub None jeśli błąd
        """
        await self._check_rate_limit("snapshot")

        url = f"{self.base_url}/finazon/us_stocks_essential/ticker_snapshot"
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
                    return data

        except Exception as e:
            print(f"[FinazonAPI] ✗ Error fetching snapshot for {ticker}: {e}")
            return None


class MarketDataFinazonAgent:
    """
    Agent pobierający dane real-time z Finazon.io US Stocks Essential

    FLOW:
    1. Przy starcie: pobierz listę wszystkich US tickerów (cache do pliku)
    2. Filtruj tickery: min price, main exchanges, asset type
    3. Co 60 sekund pobierz świece dla top tickerów
    4. Normalizuj do MarketCandleMessage
    5. Publikuj do Redis stream: market_candles

    PARAMETRY (.env):
    - MAX_TICKERS=100 - ile max tickerów monitorować
    - MIN_STOCK_PRICE=5.0 - min cena akcji (unikaj penny stocks)
    - EXCHANGES=NYSE,NASDAQ - filtrowanie po giełdach
    - MARKET_DATA_UPDATE_INTERVAL=60 - polling interval (sekund)
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

        # Parametry filtrowania
        self.max_tickers = int(os.getenv("MAX_TICKERS", "100"))
        self.min_price = float(os.getenv("MIN_STOCK_PRICE", "5.0"))

        # Exchanges (NYSE, NASDAQ, AMEX, etc.)
        exchanges_str = os.getenv("EXCHANGES", "XNYS,XNAS")  # XNYS=NYSE, XNAS=NASDAQ
        self.allowed_exchanges = [e.strip().lower() for e in exchanges_str.split(",")]

        # Polling interval (seconds)
        self.poll_interval = int(os.getenv("MARKET_DATA_UPDATE_INTERVAL", "60"))

        # Cache file dla tickerów (żeby nie pobierać za każdym razem)
        self.cache_dir = Path(__file__).parent / "cache"
        self.cache_dir.mkdir(exist_ok=True)
        self.tickers_cache_file = self.cache_dir / "tickers_cache.json"

        # Watchlist (będzie wypełniony po fetch_tickers)
        self.watchlist = []

        print(f"[market_data_finazon] Initialized (US Stocks Essential)")
        print(f"  API: Finazon.io")
        print(f"  Max tickers: {self.max_tickers}")
        print(f"  Min price: ${self.min_price}")
        print(f"  Exchanges: {self.allowed_exchanges}")
        print(f"  Poll interval: {self.poll_interval}s")
        print(f"  Cache: {self.tickers_cache_file}")

    def filter_tickers(self, all_tickers: List[Dict]) -> List[str]:
        """
        Filtruj tickery według kryteriów:
        - asset_type = COMMON_STOCK (nie ETFy, preferowane, etc.)
        - mic (exchange) in allowed_exchanges
        - Deduplikacja (niektóre tickery mogą być listed na wielu giełdach)

        Args:
            all_tickers: Lista dict z Finazon API

        Returns:
            Lista ticker symbols (sorted alfabetycznie)
        """
        filtered = []
        seen_tickers = set()

        # Debug counters
        rejected_asset_type = 0
        rejected_exchange = 0
        rejected_format = 0
        rejected_duplicate = 0

        # Sample first 5 rejected tickers for debugging
        debug_samples = []

        for item in all_tickers:
            ticker = item.get("ticker")
            asset_type = item.get("asset_type", "")
            mic = item.get("mic", "").lower()

            # Skip if no ticker
            if not ticker:
                continue

            # Skip jeśli już widziany (deduplication)
            if ticker in seen_tickers:
                rejected_duplicate += 1
                continue

            # Filter 1: allowed exchanges FIRST (most important)
            if self.allowed_exchanges and mic not in self.allowed_exchanges:
                rejected_exchange += 1
                if len(debug_samples) < 5:
                    debug_samples.append(f"{ticker} (type={asset_type}, mic={mic})")
                continue

            # Filter 2: Format - skip penny stock tickers (zazwyczaj < 4 chars lub zawierają '.')
            # NYSE/NASDAQ tickers są usually 1-5 chars bez kropki
            if len(ticker) > 5 or "." in ticker:
                rejected_format += 1
                if len(debug_samples) < 5:
                    debug_samples.append(f"{ticker} (type={asset_type}, mic={mic})")
                continue

            # Filter 3: Blacklist certain asset types (ETFs, warrants, etc.)
            # Only reject known non-stock types, accept everything else
            blacklisted_types = ["EXCHANGE_TRADED_FUND", "WARRANT", "RIGHT", "UNIT", "INDEX"]
            if asset_type in blacklisted_types:
                rejected_asset_type += 1
                if len(debug_samples) < 5:
                    debug_samples.append(f"{ticker} (type={asset_type}, mic={mic})")
                continue

            filtered.append(ticker)
            seen_tickers.add(ticker)

        # Sort alfabetycznie
        filtered.sort()

        print(f"[market_data_finazon] Filtered: {len(filtered)} tickers from {len(all_tickers)} total")
        if len(filtered) == 0:
            print(f"[market_data_finazon] DEBUG - Rejection reasons:")
            print(f"[market_data_finazon]   Asset type: {rejected_asset_type}")
            print(f"[market_data_finazon]   Exchange: {rejected_exchange}")
            print(f"[market_data_finazon]   Format: {rejected_format}")
            print(f"[market_data_finazon]   Duplicate: {rejected_duplicate}")
            if debug_samples:
                print(f"[market_data_finazon] Sample rejected tickers:")
                for sample in debug_samples:
                    print(f"[market_data_finazon]   - {sample}")
        return filtered

    async def load_or_fetch_tickers(self) -> List[str]:
        """
        Załaduj tickery z cache lub pobierz z API jeśli cache stary/nie istnieje

        Cache validity: 24h (tickery zmieniają się rzadko)

        Returns:
            Lista ticker symbols
        """
        # Sprawdź czy cache istnieje i jest świeży (< 24h)
        if self.tickers_cache_file.exists():
            cache_age = time.time() - self.tickers_cache_file.stat().st_mtime
            cache_valid_seconds = 24 * 3600  # 24h

            if cache_age < cache_valid_seconds:
                print(f"[market_data_finazon] Loading tickers from cache (age: {cache_age/3600:.1f}h)...")
                with open(self.tickers_cache_file, 'r') as f:
                    cached_data = json.load(f)
                    tickers = cached_data.get("tickers", [])

                    if tickers:
                        print(f"[market_data_finazon] ✓ Loaded {len(tickers)} tickers from cache")
                        return tickers[:self.max_tickers]

        # Cache nie istnieje lub stary - pobierz z API
        print(f"[market_data_finazon] Cache miss or expired - fetching from API...")
        print(f"[market_data_finazon] ⏳ This may take 1-2 minutes (pagination)...")

        all_tickers = await self.finazon.get_all_tickers(page_size=1000)

        if not all_tickers:
            print(f"[market_data_finazon] ✗ Failed to fetch tickers from API")
            return []

        # Filtruj tickery
        filtered_tickers = self.filter_tickers(all_tickers)

        # Zapisz do cache
        cache_data = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "total_tickers": len(all_tickers),
            "filtered_tickers": len(filtered_tickers),
            "tickers": filtered_tickers
        }

        with open(self.tickers_cache_file, 'w') as f:
            json.dump(cache_data, f, indent=2)

        print(f"[market_data_finazon] ✓ Cached {len(filtered_tickers)} tickers to {self.tickers_cache_file}")

        # Return top MAX_TICKERS
        return filtered_tickers[:self.max_tickers]

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
            "market_data_finazon",  # agent_name
            message.model_dump()     # Pydantic 2.x: model_dump() zamiast dict()
        )

        # Compact logging (don't spam for 100+ tickers)
        # print(f"[market_data_finazon] ✓ {ticker} @ ${message.close:.2f}")

    async def fetch_and_publish_all(self):
        """
        Pobierz świece dla wszystkich tickerów z watchlist i opublikuj

        UWAGA: Rate limit /time_series = 5 req/min
        Dla 100 tickerów = 100 requests = 20 minut pełnego cyklu

        OPTYMALIZACJA:
        - Batch processing: po 5 tickerów, wait 60s
        - Lub: użyj większego poll_interval (np. 5 min)
        """
        print(f"\n[market_data_finazon] === Fetching {len(self.watchlist)} tickers ===")

        batch_size = 5  # 5 req/min limit
        successful = 0
        failed = 0

        for i, ticker in enumerate(self.watchlist):
            candle = await self.finazon.get_latest_candle(ticker, interval="1m")

            if candle:
                await self.publish_candle(ticker, candle)
                successful += 1
            else:
                failed += 1

            # Rate limiting: po 5 tickerach, wait 60s (jeśli nie ostatni batch)
            if (i + 1) % batch_size == 0 and (i + 1) < len(self.watchlist):
                remaining = len(self.watchlist) - (i + 1)
                print(f"[market_data_finazon] Processed {i+1}/{len(self.watchlist)} | OK: {successful}, FAIL: {failed} | Remaining: {remaining}")
                print(f"[market_data_finazon] ⏳ Rate limit pause (60s)...")
                await asyncio.sleep(60)

        print(f"[market_data_finazon] ✓ Cycle complete: {successful} OK, {failed} FAIL")

    async def run(self):
        """Główna pętla agenta"""
        await self.connect_redis()

        # Pobierz/załaduj tickery
        print(f"\n[market_data_finazon] === Initializing watchlist ===")
        self.watchlist = await self.load_or_fetch_tickers()

        if not self.watchlist:
            print(f"[market_data_finazon] ✗ No tickers available - exiting")
            return

        print(f"[market_data_finazon] ✓ Watchlist ready: {len(self.watchlist)} tickers")
        print(f"[market_data_finazon]   First 10: {self.watchlist[:10]}")
        print(f"[market_data_finazon]   Last 10: {self.watchlist[-10:]}")

        # INFO o czasie cyklu
        expected_cycle_time = (len(self.watchlist) / 5) * 60  # 5 req/min
        print(f"\n[market_data_finazon] ⚠️  IMPORTANT:")
        print(f"   Rate limit: 5 req/min for /time_series")
        print(f"   Tickers: {len(self.watchlist)}")
        print(f"   Expected cycle time: ~{expected_cycle_time/60:.1f} minutes")
        print(f"   Recommendation: Consider increasing MARKET_DATA_UPDATE_INTERVAL or reducing MAX_TICKERS")

        print(f"\n[market_data_finazon] 🚀 Starting polling loop (every {self.poll_interval}s)...")

        iteration = 0
        while True:
            try:
                iteration += 1
                print(f"\n[market_data_finazon] === Iteration {iteration} @ {datetime.now().strftime('%H:%M:%S')} ===")

                await self.fetch_and_publish_all()

                print(f"[market_data_finazon] Sleeping {self.poll_interval}s...")
                await asyncio.sleep(self.poll_interval)

            except KeyboardInterrupt:
                print("\n[market_data_finazon] Shutting down...")
                break
            except Exception as e:
                print(f"[market_data_finazon] ✗ Error in main loop: {e}")
                import traceback
                traceback.print_exc()
                await asyncio.sleep(60)  # Wait before retry


if __name__ == "__main__":
    agent = MarketDataFinazonAgent()
    asyncio.run(agent.run())
