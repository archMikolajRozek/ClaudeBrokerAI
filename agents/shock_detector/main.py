"""
Shock Detector Agent - Complete Implementation
Wykrywa anomalie rynkowe (price shocks, volume spikes) przy użyciu z-score.
"""

import asyncio
import os
import sys
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Deque
from collections import deque, defaultdict
import math
import uuid

import redis.asyncio as redis
from dotenv import load_dotenv

# Add packages to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../packages'))
from common.schemas import (
    MarketCandleMessage,
    MarketShockEvent,
    StreamNames
)
from common.redis_utils import publish_message, create_consumer_group, deserialize_message


load_dotenv()


class StatisticalAnalyzer:
    """Analiza statystyczna dla detekcji anomalii"""

    def __init__(self, window_size: int = 20):
        """
        Args:
            window_size: Rozmiar sliding window dla obliczania statystyk
        """
        self.window_size = window_size

    def calculate_zscore(self, values: List[float]) -> Optional[float]:
        """
        Oblicz z-score dla ostatniej wartości

        Returns:
            z-score (ile std od średniej) lub None jeśli za mało danych
        """
        if len(values) < 2:
            return None

        # Oblicz mean i std dla wszystkich oprócz ostatniej wartości
        historical = values[:-1]
        current = values[-1]

        mean = sum(historical) / len(historical)

        # Std dev
        variance = sum((x - mean) ** 2 for x in historical) / len(historical)
        std = math.sqrt(variance)

        if std == 0:
            return 0.0

        z_score = (current - mean) / std
        return z_score

    def calculate_percentile(self, values: List[float], value: float) -> float:
        """
        Oblicz percentyl dla danej wartości

        Returns:
            Percentyl 0-100
        """
        if len(values) == 0:
            return 50.0

        below = sum(1 for v in values if v < value)
        percentile = (below / len(values)) * 100

        return percentile


class ShockDetector:
    """Detektor anomalii rynkowych"""

    def __init__(
        self,
        window_size: int = 20,
        zscore_threshold: float = 2.0,
        volume_percentile_threshold: float = 80.0
    ):
        """
        Args:
            window_size: Rozmiar sliding window
            zscore_threshold: Threshold dla z-score (np. 2.0 = 2 std)
            volume_percentile_threshold: Threshold dla volume (np. 80 = 80th percentile)
        """
        self.window_size = window_size
        self.zscore_threshold = zscore_threshold
        self.volume_percentile_threshold = volume_percentile_threshold

        # Sliding windows per ticker
        self.returns_windows: Dict[str, Deque[float]] = defaultdict(
            lambda: deque(maxlen=window_size)
        )
        self.volume_windows: Dict[str, Deque[int]] = defaultdict(
            lambda: deque(maxlen=window_size)
        )
        self.price_history: Dict[str, Optional[float]] = {}  # Last close price

        self.analyzer = StatisticalAnalyzer(window_size)

        print(f"[ShockDetector] Initialized with:")
        print(f"  Window size: {window_size}")
        print(f"  Z-score threshold: {zscore_threshold}")
        print(f"  Volume percentile threshold: {volume_percentile_threshold}")

    def process_candle(self, candle: MarketCandleMessage) -> Optional[MarketShockEvent]:
        """
        Przetwórz świecę i sprawdź czy jest anomalia

        Returns:
            MarketShockEvent jeśli wykryto anomalię, None otherwise
        """
        ticker = candle.ticker

        # Oblicz returns jeśli mamy poprzednią cenę
        if self.price_history.get(ticker) is not None:
            prev_close = self.price_history[ticker]
            returns = (candle.close - prev_close) / prev_close
        else:
            returns = 0.0

        # Update price history
        self.price_history[ticker] = candle.close

        # Dodaj do windows
        self.returns_windows[ticker].append(returns)
        self.volume_windows[ticker].append(candle.volume)

        # Sprawdź czy mamy wystarczająco danych
        if len(self.returns_windows[ticker]) < self.window_size:
            return None  # Zbieramy dane

        # Oblicz z-score dla returns
        returns_list = list(self.returns_windows[ticker])
        z_score = self.analyzer.calculate_zscore(returns_list)

        if z_score is None:
            return None

        # Oblicz percentyl dla volume
        volume_list = list(self.volume_windows[ticker])
        volume_percentile = self.analyzer.calculate_percentile(
            volume_list[:-1],  # Historical
            candle.volume      # Current
        )

        # Sprawdź czy jest anomalia
        shock_type = None
        severity = 0.0

        # 1. Price shock (based on z-score)
        if abs(z_score) > self.zscore_threshold:
            if z_score > 0:
                shock_type = "PRICE_SPIKE"
            else:
                shock_type = "PRICE_DROP"

            # Severity based on z-score (capped at 3 std = 1.0)
            severity = min(abs(z_score) / 3.0, 1.0)

        # 2. Volume spike
        if volume_percentile > self.volume_percentile_threshold:
            if shock_type is None:
                shock_type = "VOLUME_SPIKE"
                severity = (volume_percentile - self.volume_percentile_threshold) / (100 - self.volume_percentile_threshold)
            else:
                # Combined shock - increase severity
                severity = min(severity * 1.2, 1.0)

        # Jeśli wykryto anomalię, zwróć event
        if shock_type:
            return MarketShockEvent(
                ticker=ticker,
                shock_type=shock_type,
                detected_at=datetime.now(timezone.utc).isoformat(),
                price=candle.close,
                z_score=z_score,
                volume_percentile=volume_percentile,
                returns=returns * 100,  # Convert to percentage
                severity=severity
            )

        return None


class ShockDetectorAgent:
    """Agent wykrywający anomalie rynkowe"""

    def __init__(self):
        self.redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
        self.redis_client = None
        self.input_stream = StreamNames.MARKET_CANDLES
        self.output_stream = StreamNames.MARKET_SHOCKS
        self.consumer_group = "shock_detector_group"
        self.consumer_name = "shock_detector_consumer_1"
        self.agent_name = "shock_detector"

        # Shock detector z konfiguracją
        window_size = int(os.getenv("SHOCK_WINDOW_SIZE", "20"))
        zscore_threshold = float(os.getenv("SHOCK_ZSCORE_THRESHOLD", "2.0"))
        volume_percentile = float(os.getenv("SHOCK_VOLUME_PERCENTILE", "80.0"))

        self.detector = ShockDetector(
            window_size=window_size,
            zscore_threshold=zscore_threshold,
            volume_percentile_threshold=volume_percentile
        )

    async def connect(self):
        """Połącz z Redis"""
        self.redis_client = await redis.from_url(
            self.redis_url,
            decode_responses=True
        )

        # Utwórz consumer group
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
            print(f"[{self.agent_name}] Disconnected from Redis")

    async def process_candle(self, message_id: str, message_data: Dict[str, str]):
        """Przetwórz świecę i sprawdź anomalie"""
        try:
            stream_msg = deserialize_message(message_data)
            candle = MarketCandleMessage(**stream_msg.data)

            # Wykryj anomalie
            shock_event = self.detector.process_candle(candle)

            if shock_event:
                # Publikuj do market_shocks stream
                await publish_message(
                    self.redis_client,
                    self.output_stream,
                    self.agent_name,
                    shock_event.model_dump(),
                    message_type="MarketShockEvent"
                )

                print(f"[{self.agent_name}] 🚨 SHOCK DETECTED: {shock_event.shock_type} "
                      f"{shock_event.ticker} @ ${shock_event.price:.2f} | "
                      f"z-score={shock_event.z_score:.2f}, "
                      f"volume_pct={shock_event.volume_percentile:.1f}%, "
                      f"severity={shock_event.severity:.2f}")

            # ACK
            await self.redis_client.xack(
                self.input_stream,
                self.consumer_group,
                message_id
            )

        except Exception as e:
            print(f"[{self.agent_name}] ❌ Error processing {message_id}: {e}")
            import traceback
            traceback.print_exc()

    async def run(self):
        """Główna pętla agenta - event listener"""
        await self.connect()

        try:
            print(f"[{self.agent_name}] 🚀 Starting event loop...")

            processed_count = 0

            while True:
                # Czytaj ze strumienia
                messages = await self.redis_client.xreadgroup(
                    self.consumer_group,
                    self.consumer_name,
                    {self.input_stream: ">"},
                    count=10,
                    block=5000
                )

                if messages:
                    for stream_name, stream_messages in messages:
                        for message_id, message_data in stream_messages:
                            await self.process_candle(message_id, message_data)
                            processed_count += 1

                    if processed_count % 100 == 0:
                        print(f"[{self.agent_name}] Processed {processed_count} candles")

                await asyncio.sleep(0.1)

        except KeyboardInterrupt:
            print(f"\n[{self.agent_name}] 🛑 Shutting down...")
        except Exception as e:
            print(f"[{self.agent_name}] ❌ Fatal error: {e}")
            import traceback
            traceback.print_exc()
        finally:
            await self.disconnect()


async def main():
    """Entry point"""
    agent = ShockDetectorAgent()
    await agent.run()


if __name__ == "__main__":
    asyncio.run(main())
