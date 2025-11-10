"""
Strategy Agent - Main Event Loop
Konsumuje dane rynkowe i wiadomości, generuje sygnały handlowe.
"""

import asyncio
import os
from datetime import datetime
from typing import Dict, Any, Optional
import redis.asyncio as redis


class StrategyAgent:
    def __init__(self):
        self.redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
        self.redis_client = None
        self.input_streams = ["market:data", "news:scored"]
        self.output_stream = "signals:trading"
        self.consumer_group = "strategy_group"
        self.consumer_name = "strategy_consumer_1"
        self.agent_name = "strategy"

    async def connect(self):
        """Połącz z Redis"""
        self.redis_client = await redis.from_url(self.redis_url, decode_responses=True)

        # Utwórz consumer groups
        for stream in self.input_streams:
            try:
                await self.redis_client.xgroup_create(
                    stream, self.consumer_group, id="0", mkstream=True
                )
            except redis.ResponseError as e:
                if "BUSYGROUP" not in str(e):
                    raise

        print(f"[{self.agent_name}] Connected to Redis")

    async def disconnect(self):
        """Rozłącz z Redis"""
        if self.redis_client:
            await self.redis_client.close()

    async def generate_signal(self, market_data: Dict[str, Any], news_data: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
        """Generuj sygnał handlowy (placeholder)"""
        # TODO: Implementacja strategii (techniczna analiza + sentyment)

        # Przykładowa prosta strategia
        if market_data.get("indicators", {}).get("rsi", 50) > 70:
            signal_type = "SELL"
            confidence = 0.6
        elif market_data.get("indicators", {}).get("rsi", 50) < 30:
            signal_type = "BUY"
            confidence = 0.6
        else:
            return None  # Brak sygnału

        return {
            "ticker": market_data.get("ticker"),
            "signal": signal_type,
            "confidence": confidence,
            "price": market_data.get("price"),
            "quantity": 10,  # TODO: Position sizing
            "reason": "RSI-based signal",
            "timestamp": datetime.now().isoformat()
        }

    async def process_message(self, stream_name: str, message_id: str, message_data: Dict[str, str]):
        """Przetwórz wiadomość ze strumienia"""
        try:
            data = eval(message_data.get("data", "{}"))

            signal = None
            if stream_name == "market:data":
                signal = await self.generate_signal(data)

            # Jeśli wygenerowano sygnał, publikuj
            if signal:
                await self.redis_client.xadd(
                    self.output_stream,
                    {
                        "agent": self.agent_name,
                        "timestamp": datetime.now().isoformat(),
                        "data": str(signal)
                    }
                )
                print(f"[{self.agent_name}] Generated signal: {signal['signal']} {signal['ticker']}")

            # Acknowledge
            await self.redis_client.xack(stream_name, self.consumer_group, message_id)

        except Exception as e:
            print(f"[{self.agent_name}] Error processing {message_id}: {e}")

    async def run(self):
        """Główna pętla agenta - event listener"""
        await self.connect()

        try:
            print(f"[{self.agent_name}] Starting event loop...")

            while True:
                # Czytaj z wielu strumieni
                streams = {stream: ">" for stream in self.input_streams}
                messages = await self.redis_client.xreadgroup(
                    self.consumer_group,
                    self.consumer_name,
                    streams,
                    count=10,
                    block=5000
                )

                if messages:
                    for stream_name, stream_messages in messages:
                        for message_id, message_data in stream_messages:
                            await self.process_message(stream_name, message_id, message_data)

                await asyncio.sleep(0.1)

        except KeyboardInterrupt:
            print(f"[{self.agent_name}] Shutting down...")
        finally:
            await self.disconnect()


async def main():
    """Entry point"""
    agent = StrategyAgent()
    await agent.run()


if __name__ == "__main__":
    asyncio.run(main())
