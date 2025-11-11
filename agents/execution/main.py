"""
Execution Agent - Complete Implementation
Wykonuje zatwierdzone zlecenia handlowe przez Alpaca API.
"""

import asyncio
import os
import sys
from datetime import datetime, timezone
from typing import Dict, Any, Optional
import uuid
import random

import redis.asyncio as redis
import aiohttp
from dotenv import load_dotenv

# Add packages to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../packages'))
from common.schemas import ApprovedTrade, ExecutedOrder, StreamNames
from common.redis_utils import publish_message, create_consumer_group, deserialize_message


load_dotenv()


class AlpacaBroker:
    """
    Prawdziwa integracja z Alpaca Trading API

    Dokumentacja: https://alpaca.markets/docs/api-references/trading-api/
    """

    def __init__(self, api_key: str, api_secret: str, base_url: str):
        """
        Args:
            api_key: Alpaca API key
            api_secret: Alpaca API secret
            base_url: Base URL (paper: https://paper-api.alpaca.markets)
        """
        self.api_key = api_key
        self.api_secret = api_secret
        self.base_url = base_url.rstrip('/')

        # Headers dla autentykacji
        self.headers = {
            "APCA-API-KEY-ID": self.api_key,
            "APCA-API-SECRET-KEY": self.api_secret,
            "Content-Type": "application/json"
        }

        print(f"[AlpacaBroker] Initialized with base_url={base_url}")

    async def place_order(
        self,
        ticker: str,
        side: str,
        quantity: int,
        entry_price: float
    ) -> Dict[str, Any]:
        """
        Złóż zlecenie przez Alpaca API

        Args:
            ticker: Symbol akcji (np. AAPL)
            side: BUY lub SELL
            quantity: Liczba akcji
            entry_price: Cena docelowa (używamy jako limit price)

        Returns:
            Dict z kluczami: order_id, executed_price, status, commission, slippage
        """
        url = f"{self.base_url}/v2/orders"

        # Payload dla Alpaca
        # Używamy MARKET order dla natychmiastowego wykonania
        # Możesz zmienić na LIMIT order używając entry_price jako limit
        payload = {
            "symbol": ticker,
            "qty": quantity,
            "side": side.lower(),  # buy/sell (lowercase w Alpaca)
            "type": "market",  # market, limit, stop, stop_limit
            "time_in_force": "day"  # day, gtc, ioc, fok
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    url,
                    headers=self.headers,
                    json=payload,
                    timeout=10
                ) as response:

                    if response.status != 200:
                        text = await response.text()
                        print(f"[AlpacaBroker] ✗ Order failed: HTTP {response.status}")
                        print(f"[AlpacaBroker]   URL: {url}")
                        print(f"[AlpacaBroker]   Payload: {payload}")
                        print(f"[AlpacaBroker]   Response: {text}")

                        # Jeśli 404, prawdopodobnie rynek zamknięty lub nieprawidłowy ticker
                        if response.status == 404:
                            print(f"[AlpacaBroker]   💡 Hint: Rynek może być zamknięty (NYSE: 9:30-16:00 EST) lub ticker nieprawidłowy")

                        return {
                            "order_id": f"FAILED_{uuid.uuid4().hex[:8].upper()}",
                            "executed_price": entry_price,
                            "status": "REJECTED",
                            "commission": 0.0,
                            "slippage": 0.0,
                            "error": text
                        }

                    order_data = await response.json()

                    # Alpaca response format:
                    # {
                    #   "id": "order_uuid",
                    #   "status": "accepted", "pending_new", "filled", etc.
                    #   "filled_avg_price": "150.25",
                    #   "qty": "10",
                    #   ...
                    # }

                    order_id = order_data.get("id", "UNKNOWN")
                    status_raw = order_data.get("status", "unknown")
                    filled_price = order_data.get("filled_avg_price")

                    # Map Alpaca status do naszego formatu
                    if status_raw in ["filled", "partially_filled"]:
                        status = "FILLED" if status_raw == "filled" else "PARTIAL"
                        executed_price = float(filled_price) if filled_price else entry_price
                    else:
                        # pending_new, accepted, new
                        status = "PENDING"
                        executed_price = entry_price  # Nieznana jeszcze

                    # Alpaca nie pobiera prowizji na paper trading
                    # Na live trading: $0 commission dla akcji
                    commission = 0.0

                    slippage = executed_price - entry_price if filled_price else 0.0

                    print(f"[AlpacaBroker] ✓ Order {order_id} status={status} price=${executed_price:.2f}")

                    return {
                        "order_id": order_id,
                        "executed_price": executed_price,
                        "status": status,
                        "commission": commission,
                        "slippage": slippage
                    }

        except asyncio.TimeoutError:
            print(f"[AlpacaBroker] ✗ Timeout placing order for {ticker}")
            return {
                "order_id": f"TIMEOUT_{uuid.uuid4().hex[:8].upper()}",
                "executed_price": entry_price,
                "status": "REJECTED",
                "commission": 0.0,
                "slippage": 0.0,
                "error": "Timeout"
            }
        except Exception as e:
            print(f"[AlpacaBroker] ✗ Error placing order: {e}")
            return {
                "order_id": f"ERROR_{uuid.uuid4().hex[:8].upper()}",
                "executed_price": entry_price,
                "status": "REJECTED",
                "commission": 0.0,
                "slippage": 0.0,
                "error": str(e)
            }


class MockBroker:
    """Fallback mock broker dla testów bez API keys"""

    def __init__(self):
        print("[MockBroker] Using simulated orders (no real API)")

    async def place_order(
        self,
        ticker: str,
        side: str,
        quantity: int,
        entry_price: float
    ) -> Dict[str, Any]:
        """Symulacja zlecenia"""
        await asyncio.sleep(0.2)

        slippage_pct = random.uniform(0, 0.002)
        if side == "BUY":
            executed_price = entry_price * (1 + slippage_pct)
        else:
            executed_price = entry_price * (1 - slippage_pct)

        status = "FILLED" if random.random() > 0.05 else "PARTIAL"

        return {
            "order_id": f"MOCK_{uuid.uuid4().hex[:8].upper()}",
            "executed_price": executed_price,
            "status": status,
            "commission": quantity * 0.005,
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

        # Broker API - wybierz Alpaca lub Mock
        alpaca_key = os.getenv("ALPACA_API_KEY")
        alpaca_secret = os.getenv("ALPACA_API_SECRET")
        alpaca_url = os.getenv("ALPACA_BASE_URL", "https://paper-api.alpaca.markets")

        if alpaca_key and alpaca_secret and alpaca_key != "your-alpaca-api-key":
            # Użyj prawdziwego Alpaca API
            self.broker = AlpacaBroker(alpaca_key, alpaca_secret, alpaca_url)
            print(f"[execution] Using REAL Alpaca API (paper trading)")
        else:
            # Fallback: Mock broker
            self.broker = MockBroker()
            print(f"[execution] ⚠️  No Alpaca credentials, using MOCK broker")

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
