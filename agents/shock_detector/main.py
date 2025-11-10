"""
Shock Detector Agent - Main Event Loop
Monitoruje rynek pod kątem nagłych anomalii i wyzwala alerty.
"""

import asyncio
import os
from datetime import datetime
from typing import Dict, Any, List
import redis.asyncio as redis


class ShockDetectorAgent:
    def __init__(self):
        self.redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
        self.redis_client = None
        self.input_stream = "market:data"
        self.output_stream = "alerts:shocks"
        self.consumer_group = "shock_detector_group"
        self.consumer_name = "shock_detector_consumer_1"
        self.agent_name = "shock_detector"

        # Shock detection parameters
        self.price_threshold = 0.05  # 5% price change
        self.volume_threshold = 3.0  # 3x average volume
        self.historical_data: Dict[str, List[float]] = {}

    async def connect(self):
        """Połącz z Redis"""
        self.redis_client = await redis.from_url(self.redis_url, decode_responses=True)

        try:
            await self.redis_client.xgroup_create(
                self.input_stream, self.consumer_group, id="0", mkstream=True
            )
        except redis.ResponseError as e:
            if "BUSYGROUP" not in str(e):
                raise

        print(f"[{self.agent_name}] Connected to Redis")

    async def disconnect(self):
        """Rozłącz z Redis"""
        if self.redis_client:
            await self.redis_client.close()

    async def detect_shock(self, market_data: Dict[str, Any]) -> Dict[str, Any]:
        """Wykryj anomalie rynkowe (placeholder)"""
        # TODO: Implementacja zaawansowanej detekcji:
        # - Statistical anomaly detection
        # - Machine Learning models
        # - Pattern recognition
        # - Correlation breaks

        ticker = market_data.get("ticker")
        price = market_data.get("price", 0)
        volume = market_data.get("volume", 0)
        change_pct = abs(market_data.get("change_pct", 0))

        shock_detected = False
        shock_type = None
        shock_severity = 0.0

        # Prosty algorytm detekcji
        if change_pct > self.price_threshold * 100:
            shock_detected = True
            shock_type = "PRICE_SHOCK"
            shock_severity = change_pct / 100

        # TODO: Volume spike detection
        # TODO: Correlation breaks
        # TODO: Volatility spikes

        if shock_detected:
            return {
                "ticker": ticker,
                "shock_type": shock_type,
                "severity": shock_severity,
                "price": price,
                "change_pct": change_pct,
                "volume": volume,
                "detected_at": datetime.now().isoformat(),
                "message": f"{shock_type} detected for {ticker}: {change_pct:.2f}% change"
            }

        return None

    async def process_message(self, message_id: str, message_data: Dict[str, str]):
        """Przetwórz dane rynkowe i wykryj shocki"""
        try:
            market_data = eval(message_data.get("data", "{}"))

            # Wykryj anomalie
            shock = await self.detect_shock(market_data)

            # Jeśli wykryto shock, publikuj alert
            if shock:
                await self.redis_client.xadd(
                    self.output_stream,
                    {
                        "agent": self.agent_name,
                        "timestamp": datetime.now().isoformat(),
                        "data": str(shock)
                    }
                )
                print(f"[{self.agent_name}] 🚨 SHOCK DETECTED: {shock['message']}")

            await self.redis_client.xack(self.input_stream, self.consumer_group, message_id)

        except Exception as e:
            print(f"[{self.agent_name}] Error processing {message_id}: {e}")

    async def run(self):
        """Główna pętla agenta - event listener"""
        await self.connect()

        try:
            print(f"[{self.agent_name}] Starting event loop...")

            while True:
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
                            await self.process_message(message_id, message_data)

                await asyncio.sleep(0.1)

        except KeyboardInterrupt:
            print(f"[{self.agent_name}] Shutting down...")
        finally:
            await self.disconnect()


async def main():
    """Entry point"""
    agent = ShockDetectorAgent()
    await agent.run()


if __name__ == "__main__":
    asyncio.run(main())
