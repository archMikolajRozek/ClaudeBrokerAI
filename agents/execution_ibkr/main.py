"""
Execution Agent IBKR - Interactive Brokers Integration
Wykonuje zatwierdzone zlecenia handlowe przez Interactive Brokers TWS API.

Uses ib_insync library for async TWS API integration.
Supports paper trading and live trading accounts.
"""

import asyncio
import os
import sys
from datetime import datetime, timezone
from typing import Dict, Any, Optional
import uuid

import redis.asyncio as redis
from ib_insync import IB, Stock, MarketOrder, LimitOrder, Order, util
from dotenv import load_dotenv

# Add packages to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../packages'))
from common.schemas import ApprovedTrade, ExecutedOrder, StreamNames
from common.redis_utils import publish_message, create_consumer_group, deserialize_message


load_dotenv()


class IBKRBroker:
    """
    Interactive Brokers integration using ib_insync

    Documentation:
    - https://ib-insync.readthedocs.io/
    - https://interactivebrokers.github.io/tws-api/
    """

    def __init__(self, host: str, port: int, client_id: int):
        """
        Args:
            host: IB Gateway host (e.g., 'ib-gateway' in Docker or 'localhost')
            port: IB Gateway port (4002 for paper trading, 4001 for live)
            client_id: Unique client ID (0-32)
        """
        self.host = host
        self.port = port
        self.client_id = client_id
        self.ib = IB()
        self.connected = False

        print(f"[IBKRBroker] Initialized with host={host}, port={port}, client_id={client_id}")

    async def connect(self, max_retries: int = 5, delay: int = 10):
        """
        Connect to IB Gateway with retry logic

        Args:
            max_retries: Maximum number of connection attempts
            delay: Seconds to wait between retries

        Note:
            IB Gateway needs ~10 seconds after login before API port is ready
        """
        for attempt in range(max_retries):
            try:
                print(f"[IBKRBroker] Connection attempt {attempt + 1}/{max_retries}...")
                # Timeout 20s (default is 2s which is too short for IB Gateway startup)
                await self.ib.connectAsync(self.host, self.port, clientId=self.client_id, timeout=20)
                self.connected = True
                print(f"[IBKRBroker] ✓ Connected to IB Gateway at {self.host}:{self.port}")

                # Get account info
                accounts = self.ib.managedAccounts()
                print(f"[IBKRBroker] Available accounts: {accounts}")

                return True
            except Exception as e:
                if attempt < max_retries - 1:
                    print(f"[IBKRBroker] Connection failed: {e}")
                    print(f"[IBKRBroker] Retrying in {delay} seconds... (IB Gateway may still be starting)")
                    await asyncio.sleep(delay)
                else:
                    print(f"[IBKRBroker] ✗ Connection failed after {max_retries} attempts: {e}")
                    self.connected = False
                    return False

    async def disconnect(self):
        """Disconnect from IB Gateway"""
        if self.connected:
            self.ib.disconnect()
            self.connected = False
            print(f"[IBKRBroker] Disconnected from IB Gateway")

    async def place_order(
        self,
        ticker: str,
        side: str,
        quantity: int,
        entry_price: float,
        order_type: str = "MKT"
    ) -> Dict[str, Any]:
        """
        Place order through IBKR API

        Args:
            ticker: Stock symbol (e.g., AAPL)
            side: BUY or SELL
            quantity: Number of shares
            entry_price: Target price (used for LIMIT orders)
            order_type: MKT (market) or LMT (limit)

        Returns:
            Dict with keys: order_id, executed_price, status, commission, slippage
        """
        if not self.connected:
            raise RuntimeError("Not connected to IB Gateway. Call connect() first.")

        try:
            # Create contract (US stocks)
            contract = Stock(ticker, 'SMART', 'USD')

            # Qualify contract (get full details from IBKR)
            await self.ib.qualifyContractsAsync(contract)

            # Create order
            if order_type == "MKT":
                order = MarketOrder(side, quantity)
            elif order_type == "LMT":
                order = LimitOrder(side, quantity, entry_price)
            else:
                raise ValueError(f"Unsupported order type: {order_type}")

            print(f"[IBKRBroker] Placing order: {side} {quantity} {ticker} @ {order_type}")

            # Place order
            trade = self.ib.placeOrder(contract, order)

            # Wait for fill (with timeout)
            await asyncio.sleep(1)  # Give order time to process

            # Get order status
            status = trade.orderStatus.status
            filled_qty = trade.orderStatus.filled
            avg_fill_price = trade.orderStatus.avgFillPrice

            # Calculate commission (IBKR charges per share, typically $0.0035/share for US stocks)
            commission = filled_qty * 0.0035 if filled_qty > 0 else 0.0

            # Calculate slippage
            slippage = abs(avg_fill_price - entry_price) if avg_fill_price > 0 else 0.0

            result = {
                "order_id": str(trade.order.orderId),
                "executed_price": avg_fill_price if avg_fill_price > 0 else entry_price,
                "status": status,  # e.g., "Filled", "Submitted", "Cancelled"
                "filled_quantity": filled_qty,
                "commission": commission,
                "slippage": slippage,
                "perm_id": trade.order.permId,  # Permanent order ID
            }

            print(f"[IBKRBroker] ✓ Order result: {result}")
            return result

        except Exception as e:
            print(f"[IBKRBroker] ✗ Order failed: {e}")
            import traceback
            traceback.print_exc()

            # Return failed order
            return {
                "order_id": str(uuid.uuid4()),
                "executed_price": 0.0,
                "status": "FAILED",
                "filled_quantity": 0,
                "commission": 0.0,
                "slippage": 0.0,
                "error": str(e)
            }

    async def get_account_info(self) -> Dict[str, Any]:
        """Get account balance and buying power"""
        if not self.connected:
            return {}

        try:
            account_values = self.ib.accountValues()

            # Extract key values
            net_liquidation = 0.0
            available_funds = 0.0
            buying_power = 0.0
            cash_balance = 0.0

            for value in account_values:
                if value.tag == 'NetLiquidation':
                    net_liquidation = float(value.value)
                elif value.tag == 'AvailableFunds':
                    available_funds = float(value.value)
                elif value.tag == 'BuyingPower':
                    buying_power = float(value.value)
                elif value.tag == 'CashBalance':
                    cash_balance = float(value.value)

            return {
                "net_liquidation": net_liquidation,
                "available_funds": available_funds,
                "buying_power": buying_power,
                "cash_balance": cash_balance,
            }
        except Exception as e:
            print(f"[IBKRBroker] Error getting account info: {e}")
            return {}

    async def get_positions(self) -> list[Dict[str, Any]]:
        """
        Get all current positions from IBKR account

        Returns:
            List of positions with ticker, quantity, avg_cost, market_value
        """
        if not self.connected:
            return []

        try:
            positions = self.ib.positions()

            result = []
            for position in positions:
                # Extract stock symbol
                ticker = position.contract.symbol

                result.append({
                    "ticker": ticker,
                    "quantity": position.position,  # Positive for long, negative for short
                    "avg_cost": position.avgCost,
                    "market_value": position.marketValue,
                    "unrealized_pnl": position.unrealizedPNL,
                })

            return result
        except Exception as e:
            print(f"[IBKRBroker] Error getting positions: {e}")
            return []


class ExecutionAgentIBKR:
    """
    Execution Agent dla Interactive Brokers

    Konsumuje `approved_trades` stream i wykonuje zlecenia przez IBKR API.
    Publikuje wyniki do `executed_orders` stream.
    """

    def __init__(self):
        self.redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
        self.redis_client: Optional[redis.Redis] = None

        # IBKR Configuration
        self.ibkr_host = os.getenv("IBKR_HOST", "ib-gateway")
        self.ibkr_port = int(os.getenv("IBKR_PORT", "4002"))  # 4002 = paper, 4001 = live
        self.ibkr_client_id = int(os.getenv("IBKR_CLIENT_ID", "1"))

        # Broker
        self.broker = IBKRBroker(
            host=self.ibkr_host,
            port=self.ibkr_port,
            client_id=self.ibkr_client_id
        )

        # Consumer group
        self.consumer_group = "execution_ibkr_group"
        self.consumer_name = f"execution_ibkr_{uuid.uuid4().hex[:8]}"

        print(f"[execution_ibkr] Initialized")
        print(f"[execution_ibkr]   IBKR: {self.ibkr_host}:{self.ibkr_port}")
        print(f"[execution_ibkr]   Consumer: {self.consumer_name}")

    async def sync_with_ibkr(self):
        """
        Synchronize Redis state with actual IBKR account state

        Compares positions and account info between Redis and IBKR,
        logs any discrepancies to help detect manual trades or errors.
        """
        try:
            # Get IBKR account info
            account_info = await self.broker.get_account_info()
            if account_info:
                print(f"\n[execution_ibkr] === IBKR Account Sync ===")
                print(f"[execution_ibkr] Net Liquidation: ${account_info.get('net_liquidation', 0):,.2f}")
                print(f"[execution_ibkr] Cash Balance: ${account_info.get('cash_balance', 0):,.2f}")
                print(f"[execution_ibkr] Buying Power: ${account_info.get('buying_power', 0):,.2f}")

            # Get IBKR positions
            ibkr_positions = await self.broker.get_positions()
            if ibkr_positions:
                print(f"[execution_ibkr] Open Positions ({len(ibkr_positions)}):")
                for pos in ibkr_positions:
                    pnl_sign = "+" if pos['unrealized_pnl'] >= 0 else ""
                    print(f"[execution_ibkr]   {pos['ticker']}: {pos['quantity']} shares @ ${pos['avg_cost']:.2f} "
                          f"(P&L: {pnl_sign}${pos['unrealized_pnl']:.2f})")
            else:
                print(f"[execution_ibkr] No open positions")

            print(f"[execution_ibkr] ========================\n")

            # TODO: Compare with Redis state (portfolio_agent positions)
            # This would require fetching current positions from Redis and comparing
            # For now, we just log IBKR state as source of truth

        except Exception as e:
            print(f"[execution_ibkr] Error syncing with IBKR: {e}")
            import traceback
            traceback.print_exc()

    async def connect_redis(self):
        """Connect to Redis"""
        self.redis_client = redis.from_url(self.redis_url, decode_responses=True)
        await self.redis_client.ping()
        print(f"[execution_ibkr] ✓ Connected to Redis at {self.redis_url}")

        # Create consumer group
        try:
            await self.redis_client.xgroup_create(
                StreamNames.APPROVED_TRADES,
                self.consumer_group,
                id='0',
                mkstream=True
            )
            print(f"[execution_ibkr] ✓ Created consumer group '{self.consumer_group}'")
        except redis.ResponseError as e:
            if "BUSYGROUP" in str(e):
                print(f"[execution_ibkr] Consumer group already exists")
            else:
                raise

    async def process_approved_trade(self, trade_data: Dict[str, Any]):
        """
        Process single approved trade

        Args:
            trade_data: Approved trade from risk agent
        """
        try:
            # Parse approved trade
            approved = ApprovedTrade(**trade_data)

            print(f"\n[execution_ibkr] === Processing Approved Trade ===")
            print(f"[execution_ibkr]   Ticker: {approved.ticker}")
            print(f"[execution_ibkr]   Side: {approved.side}")
            print(f"[execution_ibkr]   Quantity: {approved.quantity}")
            print(f"[execution_ibkr]   Entry: ${approved.entry_price:.2f}")
            print(f"[execution_ibkr]   Stop Loss: ${approved.stop_loss:.2f}")
            print(f"[execution_ibkr]   Take Profit: ${approved.take_profit:.2f}")

            # Execute order through IBKR
            result = await self.broker.place_order(
                ticker=approved.ticker,
                side=approved.side,
                quantity=approved.quantity,
                entry_price=approved.entry_price,
                order_type="MKT"  # Market order for immediate execution
            )

            # Create executed order
            executed = ExecutedOrder(
                ticker=approved.ticker,
                side=approved.side,
                quantity=result["filled_quantity"] if result["status"] != "FAILED" else 0,
                entry_price=result["executed_price"],
                entry_time=datetime.now(timezone.utc).isoformat(),
                stop_loss=approved.stop_loss,
                take_profit=approved.take_profit,
                order_id=result["order_id"],
                status=result["status"],  # FILLED, PARTIAL, FAILED
                commission=result["commission"],
                slippage=result["slippage"]
            )

            # Publish to executed_orders stream
            await publish_message(
                self.redis_client,
                StreamNames.EXECUTED_ORDERS,
                executed.model_dump()
            )

            status_emoji = "✓" if result["status"] in ["Filled", "FILLED"] else "✗"
            print(f"[execution_ibkr] {status_emoji} Order executed: {result['status']}")
            print(f"[execution_ibkr]   Order ID: {result['order_id']}")
            print(f"[execution_ibkr]   Executed: {result['filled_quantity']} @ ${result['executed_price']:.2f}")
            print(f"[execution_ibkr]   Commission: ${result['commission']:.2f}")
            print(f"[execution_ibkr]   Slippage: ${result['slippage']:.2f}")

        except Exception as e:
            print(f"[execution_ibkr] ✗ Error processing trade: {e}")
            import traceback
            traceback.print_exc()

    async def run(self):
        """Main agent loop"""
        await self.connect_redis()

        # Wait for IB Gateway to fully start (it needs ~20-30s after container start)
        print("[execution_ibkr] Waiting 30 seconds for IB Gateway to fully initialize...")
        await asyncio.sleep(30)

        # Connect to IBKR
        connected = await self.broker.connect()
        if not connected:
            print("[execution_ibkr] ✗ Failed to connect to IB Gateway. Exiting.")
            print("[execution_ibkr] Make sure IB Gateway is running and configured:")
            print("[execution_ibkr]   - Paper trading: port 4002")
            print("[execution_ibkr]   - Enable API connections in TWS/Gateway settings")
            return

        # Get account info
        account_info = await self.broker.get_account_info()
        if account_info:
            print(f"[execution_ibkr] Account Info:")
            print(f"[execution_ibkr]   Net Liquidation: ${account_info.get('net_liquidation', 0):,.2f}")
            print(f"[execution_ibkr]   Buying Power: ${account_info.get('buying_power', 0):,.2f}")

        print(f"\n[execution_ibkr] 🚀 Listening for approved trades...")

        # Track last sync time
        last_sync_time = datetime.now(timezone.utc)
        sync_interval_seconds = 300  # 5 minutes

        try:
            while True:
                # Read from approved_trades stream
                messages = await self.redis_client.xreadgroup(
                    self.consumer_group,
                    self.consumer_name,
                    {StreamNames.APPROVED_TRADES: '>'},
                    count=1,
                    block=5000  # 5 second timeout
                )

                # Periodic sync with IBKR (every 5 minutes)
                current_time = datetime.now(timezone.utc)
                if (current_time - last_sync_time).total_seconds() >= sync_interval_seconds:
                    await self.sync_with_ibkr()
                    last_sync_time = current_time

                if not messages:
                    continue

                for stream_name, stream_messages in messages:
                    for message_id, message_data in stream_messages:
                        # Deserialize
                        trade_data = deserialize_message(message_data)

                        # Process trade
                        await self.process_approved_trade(trade_data)

                        # Acknowledge message
                        await self.redis_client.xack(
                            StreamNames.APPROVED_TRADES,
                            self.consumer_group,
                            message_id
                        )

        except KeyboardInterrupt:
            print("\n[execution_ibkr] Shutting down...")
        finally:
            await self.broker.disconnect()
            if self.redis_client:
                await self.redis_client.aclose()


if __name__ == "__main__":
    agent = ExecutionAgentIBKR()
    asyncio.run(agent.run())
