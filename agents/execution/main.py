"""
Execution Agent - Complete Implementation
Wykonuje zatwierdzone zlecenia handlowe (placeholder API).
"""

import asyncio
import os
import sys
from datetime import datetime, timezone
from typing import Dict, Any
import uuid
import random

import redis.asyncio as redis
from dotenv import load_dotenv

# Add packages to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../packages'))
from common.schemas import ApprovedTrade, ExecutedOrder, StreamNames
from common.redis_utils import publish_message, create_consumer_group, deserialize_message


load_dotenv()


class BrokerAPI:
    """Placeholder broker API"""

    def __init__(self, mode: str = "paper"):
        self.mode = mode
        print(f"[BrokerAPI] Initialized in {mode} mode")

    async def place_order(
        self,
        ticker: str,
        side: str,
        quantity: int,
        entry_price: float
    ) -> Dict[str, Any]:
        """
        Wyślij zlecenie do brokera (placeholder)

        Returns:
            Order execution result
        """
        # Symulacja opóźnienia API
        await asyncio.sleep(0.2)

        # Placeholder: Losowa symulacja wykonania
        # W rzeczywistości - integracja z Alpaca, IB, etc.

        # Symuluj slippage (0-0.2%)
        slippage_pct = random.uniform(0, 0.002)
        if side == "BUY":
            executed_price = entry_price * (1 + slippage_pct)
        else:
            executed_price = entry_price * (1 - slippage_pct)

        # Symuluj status (95% filled, 5% partial)
        status = "FILLED" if random.random() > 0.05 else "PARTIAL"

        return {
            "order_id": f"ORD_{uuid.uuid4().hex[:8].upper()}",
            "executed_price": executed_price,
            "status": status,
            "commission": quantity * 0.005,  # $0.005 per share
            "slippage": executed_price - entry_price
        }


class ExecutionAgent:
    """Agent wykonujący zlecenia"""

    def __init__(self):
        self.redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
        self.redis_client = None
        self.input_stream = StreamNames.APPROVED_TRADES
        self.output_stream = StreamNames.EXECUTED_ORDERS
        self.consumer_group = "execution_group"
        self.consumer_name = "execution_consumer_1"
        self.agent_name = "execution"

        # Broker API
        mode = os.getenv("TRADING_MODE", "paper")
        self.broker = BrokerAPI(mode=mode)

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

    async def execute_trade(self, trade: ApprovedTrade):
        """Wykonaj trade na brokerze"""
        print(f"\n[{self.agent_name}] Executing: {trade.side} {trade.quantity} {trade.ticker} @ ${trade.entry:.2f}")

        try:
            # Wyślij zlecenie do brokera
            result = await self.broker.place_order(
                ticker=trade.ticker,
                side=trade.side,
                quantity=trade.quantity,
                entry_price=trade.entry
            )

            # Stwórz ExecutedOrder
            executed_order = ExecutedOrder(
                order_id=result["order_id"],
                ticker=trade.ticker,
                side=trade.side,
                quantity=trade.quantity,
                entry_price=trade.entry,
                executed_price=result["executed_price"],
                stop=trade.stop,
                take_profit=trade.take_profit,
                status=result["status"],
                executed_at=datetime.now(timezone.utc).isoformat(),
                commission=result["commission"],
                slippage=result["slippage"]
            )

            # Publikuj do executed_orders stream
            await publish_message(
                self.redis_client,
                self.output_stream,
                self.agent_name,
                executed_order.dict(),
                message_type="ExecutedOrder"
            )

            print(f"[{self.agent_name}] ✅ {result['status']}: {result['order_id']} "
                  f"@ ${result['executed_price']:.2f} "
                  f"(slippage: ${result['slippage']:.4f}, commission: ${result['commission']:.2f})")

            return executed_order

        except Exception as e:
            print(f"[{self.agent_name}] ❌ Execution failed: {e}")
            # TODO: Publish failure to error stream
            raise

    async def process_approved_trade(self, message_id: str, message_data: Dict[str, str]):
        """Przetwórz zatwierdzone zlecenie"""
        try:
            stream_msg = deserialize_message(message_data)
            trade = ApprovedTrade(**stream_msg.data)

            # Wykonaj trade
            await self.execute_trade(trade)

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

            executed_count = 0

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
                            await self.process_approved_trade(message_id, message_data)
                            executed_count += 1

                    print(f"[{self.agent_name}] Total executed: {executed_count}")

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
    agent = ExecutionAgent()
    await agent.run()


if __name__ == "__main__":
    asyncio.run(main())
