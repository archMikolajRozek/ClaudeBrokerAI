"""
Execution Agent - Main Event Loop
Wykonuje zatwierdzone zlecenia handlowe na brokerze.
"""

import asyncio
import os
from datetime import datetime
from typing import Dict, Any
import redis.asyncio as redis


class ExecutionAgent:
    def __init__(self):
        self.redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
        self.redis_client = None
        self.input_stream = "signals:approved"
        self.output_stream = "executions:completed"
        self.consumer_group = "execution_group"
        self.consumer_name = "execution_consumer_1"
        self.agent_name = "execution"

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

    async def execute_trade(self, signal: Dict[str, Any]) -> Dict[str, Any]:
        """Wykonaj transakcję na brokerze (placeholder)"""
        # TODO: Implementacja z Alpaca, Interactive Brokers, TD Ameritrade API

        # Symulacja wykonania
        await asyncio.sleep(0.5)  # Simulate API call

        return {
            "order_id": f"ORD_{datetime.now().timestamp()}",
            "ticker": signal.get("ticker"),
            "signal": signal.get("signal"),
            "quantity": signal.get("adjusted_quantity", signal.get("quantity")),
            "executed_price": signal.get("price"),
            "status": "FILLED",  # FILLED, PARTIAL, REJECTED, PENDING
            "executed_at": datetime.now().isoformat(),
            "commission": 0.0,
            "slippage": 0.0
        }

    async def process_message(self, message_id: str, message_data: Dict[str, str]):
        """Przetwórz zatwierdzone zlecenie"""
        try:
            signal = eval(message_data.get("data", "{}"))

            # Wykonaj transakcję
            execution = await self.execute_trade(signal)

            # Publikuj wynik
            await self.redis_client.xadd(
                self.output_stream,
                {
                    "agent": self.agent_name,
                    "timestamp": datetime.now().isoformat(),
                    "data": str(execution)
                }
            )

            print(f"[{self.agent_name}] Executed: {execution['signal']} {execution['quantity']} {execution['ticker']} @ ${execution['executed_price']}")

            await self.redis_client.xack(self.input_stream, self.consumer_group, message_id)

        except Exception as e:
            print(f"[{self.agent_name}] Error executing {message_id}: {e}")

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
    agent = ExecutionAgent()
    await agent.run()


if __name__ == "__main__":
    asyncio.run(main())
