"""
Momentum Agent - Technical Analysis
Oblicza wskaźniki techniczne (RSI, MACD, momentum) z candles i generuje momentum_score.

OPIS:
Agent słucha strumienia market_candles, zbiera historię dla każdego ticker'a,
oblicza wskaźniki techniczne używając packages/common/tech.py,
i publikuje MarketMomentumMessage z momentum_score [-1, 1].

ARCHITEKTURA:
Input: market_candles stream (MarketCandleMessage)
Processing:
  1. Zbieraj sliding window candles (50 bars)
  2. Oblicz RSI, MACD, ROC
  3. Kombinuj w jeden momentum_score
Output: market_momentum stream (MarketMomentumMessage)

MOMENTUM SCORE:
-1.0 = Strong bearish (silna spadkowa tendencja)
 0.0 = Neutral (brak wyraźnego trendu)
+1.0 = Strong bullish (silna wzrostowa tendencja)
"""

import asyncio
import os
import sys
from datetime import datetime, timezone
from typing import Dict, List, Optional
from collections import defaultdict, deque

import redis.asyncio as redis
from dotenv import load_dotenv

# Dodaj packages do path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../packages'))
from common.schemas import MarketCandleMessage, MarketMomentumMessage, StreamNames
from common.redis_utils import publish_message, create_consumer_group, deserialize_message
from common.tech import momentum_score as calculate_momentum_score

load_dotenv()


# ============================================================================
# CANDLE WINDOW MANAGER
# ============================================================================

class CandleWindowManager:
    """
    Zarządza sliding window candles dla każdego ticker'a

    ZADANIA:
    - Przechowuje ostatnie N candles per ticker
    - Dostarcza listę cen do obliczenia wskaźników
    - Auto-trimming (usuwa stare candles)

    STRUKTURA DANYCH:
    {
        "AAPL": deque([candle1, candle2, ..., candleN], maxlen=50),
        "MSFT": deque([...]),
        ...
    }
    """

    def __init__(self, window_size: int = 50):
        """
        Args:
            window_size: Ile świec przechowywać (domyślnie 50)
        """
        self.window_size = window_size

        # Sliding windows per ticker
        # Format: {ticker: deque([MarketCandleMessage, ...])}
        self.candles: Dict[str, deque] = defaultdict(
            lambda: deque(maxlen=self.window_size)
        )

    def add_candle(self, ticker: str, candle: MarketCandleMessage):
        """
        Dodaj nową świecę do window

        Args:
            ticker: Symbol akcji
            candle: MarketCandleMessage z market_data agent
        """
        self.candles[ticker].append(candle)

    def get_close_prices(self, ticker: str) -> List[float]:
        """
        Pobierz listę cen zamknięcia dla ticker'a

        Args:
            ticker: Symbol akcji

        Returns:
            Lista close prices (najstarsza → najnowsza)
        """
        if ticker not in self.candles:
            return []

        return [candle.close for candle in self.candles[ticker]]

    def get_highs(self, ticker: str) -> List[float]:
        """Pobierz listę high prices"""
        if ticker not in self.candles:
            return []
        return [candle.high for candle in self.candles[ticker]]

    def get_lows(self, ticker: str) -> List[float]:
        """Pobierz listę low prices"""
        if ticker not in self.candles:
            return []
        return [candle.low for candle in self.candles[ticker]]

    def get_volumes(self, ticker: str) -> List[int]:
        """Pobierz listę volumes"""
        if ticker not in self.candles:
            return []
        return [candle.volume for candle in self.candles[ticker]]

    def has_enough_data(self, ticker: str, min_periods: int = 30) -> bool:
        """
        Sprawdź czy mamy wystarczająco danych do obliczenia wskaźników

        Args:
            ticker: Symbol akcji
            min_periods: Minimum wymaganych świec

        Returns:
            True jeśli >= min_periods
        """
        return len(self.candles.get(ticker, [])) >= min_periods

    def get_candle_count(self, ticker: str) -> int:
        """Zwróć liczbę świec dla ticker'a"""
        return len(self.candles.get(ticker, []))


# ============================================================================
# MOMENTUM AGENT
# ============================================================================

class MomentumAgent:
    """
    Agent obliczający momentum z technical indicators

    FUNKCJONALNOŚĆ:
    1. Konsumuje market_candles stream
    2. Zbiera sliding window (50 bars) dla każdego ticker'a
    3. Oblicza RSI, MACD, ROC używając tech.py
    4. Generuje momentum_score [-1, 1]
    5. Publikuje do market_momentum stream

    KONFIGURACJA (z .env):
    - MOMENTUM_WINDOW_SIZE: Ile świec przechowywać (default 50)
    - MOMENTUM_RSI_PERIOD: Okres RSI (default 14)
    - MOMENTUM_MACD_FAST/SLOW/SIGNAL: Parametry MACD
    """

    def __init__(self):
        # Redis connection
        self.redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
        self.redis_client = None

        # Stream names
        self.input_stream = StreamNames.MARKET_CANDLES
        self.output_stream = StreamNames.MARKET_MOMENTUM

        # Consumer group
        self.consumer_group = "momentum_group"
        self.consumer_name = "momentum_consumer_1"

        # Agent metadata
        self.agent_name = "momentum"

        # Konfiguracja z .env
        self.window_size = int(os.getenv("MOMENTUM_WINDOW_SIZE", "50"))
        self.rsi_period = int(os.getenv("MOMENTUM_RSI_PERIOD", "14"))
        self.macd_fast = int(os.getenv("MOMENTUM_MACD_FAST", "12"))
        self.macd_slow = int(os.getenv("MOMENTUM_MACD_SLOW", "26"))
        self.macd_signal = int(os.getenv("MOMENTUM_MACD_SIGNAL", "9"))

        # Candle window manager
        self.candle_manager = CandleWindowManager(window_size=self.window_size)

        # Stats
        self.processed_count = 0
        self.signals_generated = 0

        print(f"[{self.agent_name}] Initialized")
        print(f"  Window size: {self.window_size} bars")
        print(f"  RSI period: {self.rsi_period}")
        print(f"  MACD: {self.macd_fast}/{self.macd_slow}/{self.macd_signal}")

    async def connect(self):
        """Połącz z Redis i utwórz consumer group"""
        self.redis_client = await redis.from_url(
            self.redis_url,
            decode_responses=True
        )

        # Utwórz consumer group dla input stream
        await create_consumer_group(
            self.redis_client,
            self.input_stream,
            self.consumer_group,
            start_id="0"
        )

        print(f"[{self.agent_name}] ✓ Connected to Redis")
        print(f"[{self.agent_name}] Listening on: {self.input_stream}")

    async def disconnect(self):
        """Rozłącz z Redis"""
        if self.redis_client:
            await self.redis_client.close()
        print(f"[{self.agent_name}] Disconnected")

    async def process_candle(self, message_id: str, message_data: Dict[str, str]):
        """
        Przetwórz nową świecę z market_candles stream

        FLOW:
        1. Deserializuj MarketCandleMessage
        2. Dodaj do sliding window
        3. Sprawdź czy mamy wystarczająco danych
        4. Oblicz momentum_score
        5. Publikuj do market_momentum stream

        Args:
            message_id: Redis stream message ID
            message_data: Surowe dane z Redis
        """
        try:
            # Deserializuj message
            stream_msg = deserialize_message(message_data)
            candle = MarketCandleMessage(**stream_msg.data)

            # Dodaj do window
            self.candle_manager.add_candle(candle.ticker, candle)

            self.processed_count += 1

            # Sprawdź czy mamy wystarczająco danych
            # Potrzebujemy min. MACD_slow + MACD_signal (np. 26+9=35)
            min_required = self.macd_slow + self.macd_signal

            if not self.candle_manager.has_enough_data(candle.ticker, min_required):
                # Za mało danych, pomiń
                await self.redis_client.xack(
                    self.input_stream,
                    self.consumer_group,
                    message_id
                )
                return

            # Oblicz momentum score
            await self.calculate_and_publish_momentum(candle.ticker)

            # ACK message
            await self.redis_client.xack(
                self.input_stream,
                self.consumer_group,
                message_id
            )

        except Exception as e:
            print(f"[{self.agent_name}] ✗ Error processing candle: {e}")
            import traceback
            traceback.print_exc()

    async def calculate_and_publish_momentum(self, ticker: str):
        """
        Oblicz momentum score i publikuj

        Args:
            ticker: Symbol akcji
        """
        try:
            # Pobierz ceny z window
            prices = self.candle_manager.get_close_prices(ticker)

            if len(prices) < self.macd_slow + self.macd_signal:
                return  # Za mało danych

            # Oblicz momentum score używając tech.py
            score = calculate_momentum_score(
                prices=prices,
                rsi_period=self.rsi_period,
                macd_fast=self.macd_fast,
                macd_slow=self.macd_slow,
                macd_signal=self.macd_signal,
                roc_period=20  # Rate of change period
            )

            if score is None:
                return  # Błąd w kalkulacji

            # Pobierz ostatnią cenę dla metadata
            last_price = prices[-1]

            # Utwórz MarketMomentumMessage
            momentum_msg = MarketMomentumMessage(
                ticker=ticker,
                momentum_score=score,
                timestamp=datetime.now(timezone.utc).isoformat(),
                price=last_price,
                metadata={
                    "candles_used": len(prices),
                    "rsi_period": self.rsi_period,
                    "macd_config": f"{self.macd_fast}/{self.macd_slow}/{self.macd_signal}"
                }
            )

            # Publikuj do Redis
            await publish_message(
                self.redis_client,
                self.output_stream,
                self.agent_name,
                momentum_msg.dict(),
                message_type="MarketMomentum"
            )

            self.signals_generated += 1

            # Log (nie każdego, żeby nie spamować)
            if self.signals_generated % 10 == 0 or abs(score) > 0.7:
                direction = "📈 BULLISH" if score > 0.6 else "📉 BEARISH" if score < -0.6 else "➡️ NEUTRAL"
                print(
                    f"[{self.agent_name}] {ticker}: "
                    f"momentum={score:+.3f} {direction} "
                    f"(price=${last_price:.2f}, {len(prices)} bars)"
                )

        except Exception as e:
            print(f"[{self.agent_name}] ✗ Error calculating momentum for {ticker}: {e}")
            import traceback
            traceback.print_exc()

    async def run(self):
        """
        Główna pętla agenta

        FLOW:
        1. Połącz z Redis
        2. Nasłuchuj market_candles stream (consumer group)
        3. Dla każdej świecy:
           - Dodaj do window
           - Jeśli wystarczająco danych → oblicz momentum
           - Publikuj do market_momentum
        4. Loop forever
        """
        await self.connect()

        try:
            print(f"[{self.agent_name}] 🚀 Starting momentum calculation loop...")

            while True:
                # Czytaj ze strumienia (consumer group)
                messages = await self.redis_client.xreadgroup(
                    self.consumer_group,
                    self.consumer_name,
                    {self.input_stream: ">"},  # > = nowe wiadomości
                    count=10,
                    block=5000  # 5 sec timeout
                )

                if messages:
                    for stream_name, stream_messages in messages:
                        for message_id, message_data in stream_messages:
                            await self.process_candle(message_id, message_data)

                # Stats co jakiś czas
                if self.processed_count > 0 and self.processed_count % 100 == 0:
                    print(
                        f"[{self.agent_name}] Stats: "
                        f"Processed {self.processed_count} candles, "
                        f"Generated {self.signals_generated} momentum signals"
                    )

                await asyncio.sleep(0.1)

        except KeyboardInterrupt:
            print(f"\n[{self.agent_name}] 🛑 Shutting down...")
        except Exception as e:
            print(f"[{self.agent_name}] ✗ Fatal error: {e}")
            import traceback
            traceback.print_exc()
        finally:
            await self.disconnect()


# ============================================================================
# MAIN ENTRY POINT
# ============================================================================

async def main():
    """
    Entry point - uruchom momentum agent

    WYMAGANIA:
    - Redis running
    - market_data agent running (publikuje do market_candles)
    - MOMENTUM_* env vars w .env (opcjonalne, są defaulty)

    URUCHOMIENIE:
    python main.py
    """
    agent = MomentumAgent()
    await agent.run()


if __name__ == "__main__":
    asyncio.run(main())
