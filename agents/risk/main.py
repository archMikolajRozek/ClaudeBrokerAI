"""
Risk Agent - Main Event Loop
Ocenia ryzyko sygnałów handlowych i zatwierdza/odrzuca transakcje.
"""

import asyncio
import os
from datetime import datetime
from typing import Dict, Any
import redis.asyncio as redis


class RiskAgent:
    def __init__(self):
        self.redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
        self.redis_client = None
        self.input_stream = "signals:trading"
        self.output_stream = "signals:approved"
        self.consumer_group = "risk_group"
        self.consumer_name = "risk_consumer_1"
        self.agent_name = "risk"

        # Risk parameters
        self.max_position_size = 10000  # USD
        self.max_portfolio_risk = 0.02  # 2% max risk
        self.current_exposure = 0.0

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

    async def assess_risk(self, signal: Dict[str, Any]) -> Dict[str, Any]:
        """Oceń ryzyko sygnału (placeholder)"""
        # TODO: Implementacja zaawansowanej oceny ryzyka
        # - VaR (Value at Risk)
        # - Position sizing
        # - Correlation analysis
        # - Diversification checks

        position_value = signal.get("price", 0) * signal.get("quantity", 0)

        # Prosta walidacja
        approved = True
        reason = "Signal approved"

        if position_value > self.max_position_size:
            approved = False
            reason = f"Position size ${position_value} exceeds max ${self.max_position_size}"

        if self.current_exposure > self.max_portfolio_risk:
            approved = False
            reason = f"Portfolio risk {self.current_exposure:.2%} exceeds max {self.max_portfolio_risk:.2%}"

        return {
            **signal,
            "risk_approved": approved,
            "risk_reason": reason,
            "risk_score": 0.3,  # 0-1
            "adjusted_quantity": signal.get("quantity", 0),
            "assessed_at": datetime.now().isoformat()
        }

    async def process_message(self, message_id: str, message_data: Dict[str, str]):
        """Przetwórz sygnał handlowy"""
        try:
            signal = eval(message_data.get("data", "{}"))

            # Oceń ryzyko
            assessed_signal = await self.assess_risk(signal)

            # Publikuj tylko zatwierdzone sygnały
            if assessed_signal["risk_approved"]:
                await self.redis_client.xadd(
                    self.output_stream,
                    {
                        "agent": self.agent_name,
                        "timestamp": datetime.now().isoformat(),
                        "data": str(assessed_signal)
                    }
                )
                print(f"[{self.agent_name}] Approved: {signal['signal']} {signal['ticker']}")
            else:
                print(f"[{self.agent_name}] Rejected: {assessed_signal['risk_reason']}")

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
    agent = RiskAgent()
    await agent.run()


if __name__ == "__main__":
    asyncio.run(main())
