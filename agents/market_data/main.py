"""
Market Data Agent - Real-Time Implementation
Pobiera dane rynkowe z Polygon.io lub Alpaca w czasie rzeczywistym.

OPIS:
Agent odpowiada za streaming danych rynkowych (ceny, wolumen, świece 1-min)
z zewnętrznego API i publikowanie ich do Redis Streams.

ŹRÓDŁA DANYCH:
- Polygon.io: Websocket real-time (preferowane)
- Alpaca: Websocket real-time (backup)
- REST fallback: Dla testów bez websocket

ARCHITEKTURA:
1. Łączy się z API brokera/dostawcy danych
2. Subskrybuje ticker'y z watchlist
3. Odbiera 1-min bars w czasie rzeczywistym
4. Normalizuje do MarketCandleMessage
5. Publikuje do Redis stream: market_candles
"""

import asyncio
import os
import sys
import json
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from collections import defaultdict

import redis.asyncio as redis
import websockets
import aiohttp
from dotenv import load_dotenv

# Dodaj packages do path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../packages'))
from common.schemas import MarketCandleMessage, StreamNames
from common.redis_utils import publish_message

load_dotenv()


# ============================================================================
# POLYGON.IO WEBSOCKET CLIENT
# ============================================================================

class PolygonWebsocketClient:
    """
    Klient websocket dla Polygon.io - streaming real-time stock data

    UŻYCIE:
    - Wymaga POLYGON_API_KEY w .env
    - Łączy się z wss://socket.polygon.io/stocks
    - Subskrybuje ticker'y i odbiera aggregate bars (1-min candles)

    KOSZTY:
    - Free tier: 5 połączeń/min, delayed data (15 min delay)
    - Starter ($99/mo): Real-time, unlimited tickers
    """

    def __init__(self, api_key: str, on_bar_callback):
        """
        Args:
            api_key: Polygon.io API key
            on_bar_callback: Async function wywoływana dla każdej nowej świecy
                            callback(ticker, bar_data) -> None
        """
        self.api_key = api_key
        self.on_bar_callback = on_bar_callback

        # URL websocket Polygon.io
        self.ws_url = "wss://socket.polygon.io/stocks"

        # WebSocket connection (będzie set w connect())
        self.ws = None

        # Status połączenia
        self.connected = False

        # Lista subskrybowanych ticker'ów
        self.subscribed_tickers = []

    async def connect(self):
        """Nawiąż połączenie websocket z Polygon.io"""
        try:
            # Połącz się z websocket
            self.ws = await websockets.connect(self.ws_url)
            print(f"[PolygonWS] Connected to {self.ws_url}")

            # Autoryzacja - wyślij API key
            auth_message = {
                "action": "auth",
                "params": self.api_key
            }
            await self.ws.send(json.dumps(auth_message))

            # Czekaj na potwierdzenie autoryzacji
            response = await self.ws.recv()
            response_data = json.loads(response)

            if response_data[0].get("status") == "auth_success":
                print("[PolygonWS] ✓ Authentication successful")
                self.connected = True
            else:
                print(f"[PolygonWS] ✗ Authentication failed: {response_data}")
                self.connected = False

        except Exception as e:
            print(f"[PolygonWS] ✗ Connection error: {e}")
            self.connected = False

    async def subscribe(self, tickers: List[str]):
        """
        Subskrybuj ticker'y dla 1-min aggregate bars

        Args:
            tickers: Lista symboli akcji, np. ["AAPL", "MSFT", "GOOGL"]
        """
        if not self.connected:
            print("[PolygonWS] Not connected, cannot subscribe")
            return

        # Format: "AM.{ticker}" gdzie AM = Aggregate Minute (1-min bars)
        # Alternatywy: "A.{ticker}" = second bars, "T.{ticker}" = trades
        subscription_channels = [f"AM.{ticker}" for ticker in tickers]

        # Wyślij subskrypcję
        subscribe_message = {
            "action": "subscribe",
            "params": ",".join(subscription_channels)
        }

        await self.ws.send(json.dumps(subscribe_message))
        self.subscribed_tickers = tickers

        print(f"[PolygonWS] Subscribed to {len(tickers)} tickers: {tickers}")

    async def listen(self):
        """
        Główna pętla nasłuchująca - odbiera wiadomości z websocket
        i wywołuje callback dla każdej świecy
        """
        if not self.connected:
            print("[PolygonWS] Not connected, cannot listen")
            return

        try:
            # Nieskończona pętla odbierająca wiadomości
            async for message in self.ws:
                # Parse JSON
                data = json.loads(message)

                # Polygon wysyła array wiadomości
                for item in data:
                    # Sprawdź typ wiadomości
                    event_type = item.get("ev")  # ev = event type

                    # AM = Aggregate Minute (1-min bar)
                    if event_type == "AM":
                        # Wywołaj callback z przetworzonymi danymi
                        await self.process_bar(item)

        except websockets.exceptions.ConnectionClosed:
            print("[PolygonWS] Connection closed")
            self.connected = False
        except Exception as e:
            print(f"[PolygonWS] Error in listen loop: {e}")
            self.connected = False

    async def process_bar(self, bar_data: Dict[str, Any]):
        """
        Przetwórz odebraną świecę z Polygon.io i wywołaj callback

        Format Polygon AM message:
        {
            "ev": "AM",          # Event type
            "sym": "AAPL",       # Symbol (ticker)
            "v": 12345,          # Volume
            "av": 123456789,     # Accumulated volume (total for day)
            "op": 150.25,        # Open price
            "vw": 150.50,        # Volume weighted average price
            "o": 150.25,         # Open (same as op)
            "c": 151.00,         # Close price
            "h": 151.50,         # High price
            "l": 150.00,         # Low price
            "a": 150.45,         # VWAP
            "s": 1635174000000,  # Start timestamp (ms)
            "e": 1635174060000   # End timestamp (ms)
        }
        """
        try:
            ticker = bar_data.get("sym")  # Symbol

            # Konwertuj timestamp (milisekundy) do datetime
            timestamp_ms = bar_data.get("e")  # End timestamp
            timestamp = datetime.fromtimestamp(timestamp_ms / 1000.0, tz=timezone.utc)

            # Wywołaj callback z danymi
            await self.on_bar_callback(ticker, {
                "open": bar_data.get("o"),
                "high": bar_data.get("h"),
                "low": bar_data.get("l"),
                "close": bar_data.get("c"),
                "volume": bar_data.get("v"),
                "timestamp": timestamp.isoformat()
            })

        except Exception as e:
            print(f"[PolygonWS] Error processing bar: {e}")

    async def close(self):
        """Zamknij połączenie websocket"""
        if self.ws:
            await self.ws.close()
            self.connected = False
            print("[PolygonWS] Connection closed")


# ============================================================================
# ALPACA WEBSOCKET CLIENT (BACKUP)
# ============================================================================

class AlpacaWebsocketClient:
    """
    Klient websocket dla Alpaca - backup dla Polygon.io

    UŻYCIE:
    - Wymaga ALPACA_API_KEY i ALPACA_API_SECRET w .env
    - Łączy się z wss://stream.data.alpaca.markets/v2/iex (IEX data)
    - Lub wss://stream.data.alpaca.markets/v2/sip (SIP data - płatne)

    KOSZTY:
    - Free: IEX data (tylko IEX exchange, ~2% market volume)
    - Unlimited ($99/mo): SIP consolidated (all exchanges)
    """

    def __init__(self, api_key: str, api_secret: str, on_bar_callback):
        """
        Args:
            api_key: Alpaca API key
            api_secret: Alpaca API secret
            on_bar_callback: Async function dla każdej świecy
        """
        self.api_key = api_key
        self.api_secret = api_secret
        self.on_bar_callback = on_bar_callback

        # URL websocket - IEX (free) lub SIP (paid)
        # IEX: tylko dane z IEX exchange (mniejszy wolumen, ale wystarczający)
        # SIP: konsolidowane dane ze wszystkich giełd
        self.ws_url = "wss://stream.data.alpaca.markets/v2/iex"

        self.ws = None
        self.connected = False
        self.subscribed_tickers = []

    async def connect(self):
        """Nawiąż połączenie z Alpaca websocket"""
        try:
            self.ws = await websockets.connect(self.ws_url)
            print(f"[AlpacaWS] Connected to {self.ws_url}")

            # Autoryzacja
            auth_message = {
                "action": "auth",
                "key": self.api_key,
                "secret": self.api_secret
            }
            await self.ws.send(json.dumps(auth_message))

            # Czekaj na odpowiedź
            response = await self.ws.recv()
            response_data = json.loads(response)

            # Sprawdź status
            for msg in response_data:
                if msg.get("T") == "success" and msg.get("msg") == "authenticated":
                    print("[AlpacaWS] ✓ Authentication successful")
                    self.connected = True
                    return

            print(f"[AlpacaWS] ✗ Authentication failed: {response_data}")
            self.connected = False

        except Exception as e:
            print(f"[AlpacaWS] ✗ Connection error: {e}")
            self.connected = False

    async def subscribe(self, tickers: List[str]):
        """
        Subskrybuj ticker'y dla 1-min bars

        Args:
            tickers: Lista symboli, np. ["AAPL", "MSFT"]
        """
        if not self.connected:
            print("[AlpacaWS] Not connected, cannot subscribe")
            return

        # Alpaca format: subskrybuj "bars" (1-min aggregate)
        subscribe_message = {
            "action": "subscribe",
            "bars": tickers  # bars = 1-min candles
        }

        await self.ws.send(json.dumps(subscribe_message))
        self.subscribed_tickers = tickers

        print(f"[AlpacaWS] Subscribed to {len(tickers)} tickers: {tickers}")

    async def listen(self):
        """Nasłuchuj wiadomości z Alpaca websocket"""
        if not self.connected:
            print("[AlpacaWS] Not connected, cannot listen")
            return

        try:
            async for message in self.ws:
                data = json.loads(message)

                # Alpaca wysyła array wiadomości
                for item in data:
                    # Sprawdź typ: "b" = bar (1-min candle)
                    msg_type = item.get("T")

                    if msg_type == "b":
                        await self.process_bar(item)

        except websockets.exceptions.ConnectionClosed:
            print("[AlpacaWS] Connection closed")
            self.connected = False
        except Exception as e:
            print(f"[AlpacaWS] Error in listen loop: {e}")
            self.connected = False

    async def process_bar(self, bar_data: Dict[str, Any]):
        """
        Przetwórz świecę z Alpaca

        Format Alpaca bar message:
        {
            "T": "b",            # Type = bar
            "S": "AAPL",         # Symbol
            "o": 150.25,         # Open
            "h": 151.50,         # High
            "l": 150.00,         # Low
            "c": 151.00,         # Close
            "v": 12345,          # Volume
            "t": "2021-11-01T14:30:00Z",  # Timestamp (ISO format)
            "n": 100,            # Number of trades
            "vw": 150.50         # VWAP
        }
        """
        try:
            ticker = bar_data.get("S")

            # Timestamp już w ISO format
            timestamp = bar_data.get("t")

            await self.on_bar_callback(ticker, {
                "open": bar_data.get("o"),
                "high": bar_data.get("h"),
                "low": bar_data.get("l"),
                "close": bar_data.get("c"),
                "volume": bar_data.get("v"),
                "timestamp": timestamp
            })

        except Exception as e:
            print(f"[AlpacaWS] Error processing bar: {e}")

    async def close(self):
        """Zamknij połączenie"""
        if self.ws:
            await self.ws.close()
            self.connected = False
            print("[AlpacaWS] Connection closed")


# ============================================================================
# MARKET DATA AGENT - GŁÓWNY AGENT
# ============================================================================

class MarketDataAgent:
    """
    Agent danych rynkowych - zarządza websocket connections i publikuje do Redis

    FUNKCJONALNOŚĆ:
    1. Łączy się z wybranym dostawcą (Polygon lub Alpaca)
    2. Subskrybuje ticker'y z watchlist
    3. Odbiera real-time 1-min bars
    4. Konwertuje do MarketCandleMessage
    5. Publikuje do Redis stream: market_candles
    6. Oblicza returns (log(close/prev_close))

    KONFIGURACJA:
    - MARKET_DATA_PROVIDER: polygon lub alpaca
    - WATCHLIST: lista ticker'ów (comma-separated)
    - API keys w .env
    """

    def __init__(self):
        # Redis connection
        self.redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
        self.redis_client = None

        # Stream name dla publikacji
        self.output_stream = StreamNames.MARKET_CANDLES

        # Agent metadata
        self.agent_name = "market_data"

        # Konfiguracja z .env
        self.provider = os.getenv("MARKET_DATA_PROVIDER", "polygon").lower()

        # Watchlist - ticker'y do monitorowania
        watchlist_str = os.getenv("WATCHLIST", "AAPL,MSFT,GOOGL,AMZN,TSLA")
        self.watchlist = [ticker.strip() for ticker in watchlist_str.split(",")]

        # Websocket client (będzie set w connect())
        self.ws_client = None

        # Cache ostatnich cen (dla obliczenia returns)
        # Format: {ticker: last_close_price}
        self.last_close_prices = {}

        print(f"[{self.agent_name}] Initialized")
        print(f"  Provider: {self.provider}")
        print(f"  Watchlist: {self.watchlist}")

    async def connect_redis(self):
        """Połącz się z Redis"""
        self.redis_client = await redis.from_url(
            self.redis_url,
            decode_responses=True
        )
        print(f"[{self.agent_name}] ✓ Connected to Redis")

    async def connect_market_data(self):
        """
        Połącz się z wybranym dostawcą danych rynkowych

        Tworzy websocket client (Polygon lub Alpaca) i łączy się z API
        """
        if self.provider == "polygon":
            # Polygon.io
            api_key = os.getenv("POLYGON_API_KEY")

            if not api_key or api_key == "your-polygon-key":
                raise ValueError(
                    "POLYGON_API_KEY not set! "
                    "Get free key at https://polygon.io/"
                )

            # Utwórz client z callback
            self.ws_client = PolygonWebsocketClient(
                api_key=api_key,
                on_bar_callback=self.on_new_bar
            )

        elif self.provider == "alpaca":
            # Alpaca
            api_key = os.getenv("ALPACA_API_KEY")
            api_secret = os.getenv("ALPACA_API_SECRET")

            if not api_key or api_key == "your-alpaca-api-key":
                raise ValueError(
                    "ALPACA_API_KEY not set! "
                    "Get free key at https://alpaca.markets/"
                )

            self.ws_client = AlpacaWebsocketClient(
                api_key=api_key,
                api_secret=api_secret,
                on_bar_callback=self.on_new_bar
            )

        else:
            raise ValueError(f"Unknown provider: {self.provider}")

        # Połącz się z websocket
        await self.ws_client.connect()

        # Subskrybuj watchlist
        await self.ws_client.subscribe(self.watchlist)

    async def on_new_bar(self, ticker: str, bar_data: Dict[str, Any]):
        """
        Callback wywoływany przez websocket client dla każdej nowej świecy

        ZADANIA:
        1. Oblicz returns (% zmiana względem poprzedniej świecy)
        2. Utwórz MarketCandleMessage
        3. Publikuj do Redis stream: market_candles

        Args:
            ticker: Symbol akcji (np. "AAPL")
            bar_data: Dict z kluczami: open, high, low, close, volume, timestamp
        """
        try:
            # Pobierz dane ze świecy
            open_price = float(bar_data["open"])
            high_price = float(bar_data["high"])
            low_price = float(bar_data["low"])
            close_price = float(bar_data["close"])
            volume = int(bar_data["volume"])
            timestamp = bar_data["timestamp"]

            # Oblicz returns (log returns = ln(close/prev_close))
            # Używamy log returns bo są addytywne i lepsze dla volatility
            returns = None
            if ticker in self.last_close_prices:
                prev_close = self.last_close_prices[ticker]

                if prev_close > 0:  # Zabezpieczenie przed dzieleniem przez 0
                    import math
                    returns = math.log(close_price / prev_close)

            # Zapamiętaj close dla następnej świecy
            self.last_close_prices[ticker] = close_price

            # Utwórz message schema
            candle_msg = MarketCandleMessage(
                ticker=ticker,
                open=open_price,
                high=high_price,
                low=low_price,
                close=close_price,
                volume=volume,
                timestamp=timestamp,
                returns=returns
            )

            # Publikuj do Redis
            await publish_message(
                self.redis_client,
                self.output_stream,
                self.agent_name,
                candle_msg.dict(),
                message_type="MarketCandle"
            )

            # Log (nie każdej świecy, żeby nie spamować - co 10)
            # Możesz usunąć to % 10 jeśli chcesz widzieć wszystkie
            if volume % 10 == 0 or returns is not None and abs(returns) > 0.02:  # >2% move
                print(
                    f"[{self.agent_name}] {ticker}: "
                    f"${close_price:.2f} "
                    f"({returns*100:.2f}% return) "
                    f"vol={volume:,}"
                )

        except Exception as e:
            print(f"[{self.agent_name}] ✗ Error processing bar for {ticker}: {e}")
            import traceback
            traceback.print_exc()

    async def run(self):
        """
        Główna pętla agenta

        FLOW:
        1. Połącz się z Redis
        2. Połącz się z market data provider (websocket)
        3. Nasłuchuj wiadomości (infinite loop w ws_client.listen())
        4. Dla każdej świecy → on_new_bar() → publikuj do Redis
        """
        try:
            # Krok 1: Połącz z Redis
            await self.connect_redis()

            # Krok 2: Połącz z market data provider
            await self.connect_market_data()

            print(f"[{self.agent_name}] 🚀 Starting real-time market data stream...")
            print(f"[{self.agent_name}] Streaming {len(self.watchlist)} tickers")

            # Krok 3: Nasłuchuj (infinite loop)
            await self.ws_client.listen()

        except KeyboardInterrupt:
            print(f"\n[{self.agent_name}] 🛑 Shutting down...")
        except Exception as e:
            print(f"[{self.agent_name}] ✗ Fatal error: {e}")
            import traceback
            traceback.print_exc()
        finally:
            # Cleanup
            if self.ws_client:
                await self.ws_client.close()

            if self.redis_client:
                await self.redis_client.close()

            print(f"[{self.agent_name}] Disconnected")


# ============================================================================
# MAIN ENTRY POINT
# ============================================================================

async def main():
    """
    Entry point - uruchom market data agent

    WYMAGANIA:
    - Redis running na localhost:6379 (lub REDIS_URL w .env)
    - POLYGON_API_KEY lub ALPACA_API_KEY w .env
    - WATCHLIST w .env (lista ticker'ów)

    URUCHOMIENIE:
    python main.py
    """
    agent = MarketDataAgent()
    await agent.run()


if __name__ == "__main__":
    # Uruchom async main
    asyncio.run(main())
