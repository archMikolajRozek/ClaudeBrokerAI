"""
Risk Agent - Complete Implementation
Ocenia ryzyko trade proposals i zatwierdza/odrzuca według NAV i limitów.
"""

import asyncio
import os
import sys
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional, List
from collections import defaultdict
import json

import redis.asyncio as redis
from dotenv import load_dotenv

# Add packages to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../packages'))
from common.schemas import (
    TradeProposal,
    ApprovedTrade,
    RejectedTrade,
    StreamNames
)
from common.redis_utils import publish_message, create_consumer_group, deserialize_message


load_dotenv()


class RiskManager:
    """Manager ryzyka z walidacją NAV i limitów"""

    def __init__(
        self,
        nav: float = 10000.0,
        max_risk_per_trade_pct: float = 0.005,  # 0.5%
        max_positions: int = 5,
        daily_loss_limit_pct: float = 0.02  # 2%
    ):
        """
        Args:
            nav: Net Asset Value (kapitał do dyspozycji)
            max_risk_per_trade_pct: Max ryzyko per trade jako % NAV
            max_positions: Max liczba jednoczesnych pozycji
            daily_loss_limit_pct: Max dzienna strata jako % NAV
        """
        self.nav = nav
        self.max_risk_per_trade_pct = max_risk_per_trade_pct
        self.max_positions = max_positions
        self.daily_loss_limit_pct = daily_loss_limit_pct

        # Tracking
        self.current_positions: Dict[str, ApprovedTrade] = {}
        self.daily_pnl: float = 0.0
        self.daily_pnl_date: str = datetime.now(timezone.utc).date().isoformat()

        print(f"[RiskManager] Initialized with:")
        print(f"  NAV: ${nav:,.2f}")
        print(f"  Max risk/trade: {max_risk_per_trade_pct*100:.2f}%")
        print(f"  Max positions: {max_positions}")
        print(f"  Daily loss limit: {daily_loss_limit_pct*100:.2f}%")

    def reset_daily_pnl_if_needed(self):
        """Reset daily P&L jeśli nowy dzień"""
        today = datetime.now(timezone.utc).date().isoformat()
        if today != self.daily_pnl_date:
            print(f"[RiskManager] New day - resetting daily P&L (was ${self.daily_pnl:.2f})")
            self.daily_pnl = 0.0
            self.daily_pnl_date = today

    def calculate_position_size(
        self,
        entry: float,
        stop: float,
        side: str
    ) -> tuple[int, float, float]:
        """
        Oblicz rozmiar pozycji na podstawie ryzyka

        Returns:
            (quantity, risk_amount, risk_pct)
        """
        # Oblicz ryzyko per share
        risk_per_share = abs(entry - stop)

        if risk_per_share == 0:
            return 0, 0.0, 0.0

        # Maksymalna kwota ryzyka
        max_risk_amount = self.nav * self.max_risk_per_trade_pct

        # Quantity = max_risk / risk_per_share
        quantity = int(max_risk_amount / risk_per_share)

        # Rzeczywiste ryzyko
        actual_risk_amount = quantity * risk_per_share
        actual_risk_pct = actual_risk_amount / self.nav

        return quantity, actual_risk_amount, actual_risk_pct

    def validate_trade(self, proposal: TradeProposal) -> tuple[bool, str, Optional[dict]]:
        """
        Waliduj trade proposal

        Returns:
            (approved, reason, trade_data)
        """
        self.reset_daily_pnl_if_needed()

        # 1. Sprawdź daily loss limit
        daily_loss_limit = self.nav * self.daily_loss_limit_pct
        if self.daily_pnl < -daily_loss_limit:
            return False, f"Daily loss limit reached: ${self.daily_pnl:.2f} < -${daily_loss_limit:.2f}", None

        # 2. Sprawdź max positions
        if len(self.current_positions) >= self.max_positions:
            return False, f"Max positions limit: {len(self.current_positions)}/{self.max_positions}", None

        # 3. Sprawdź czy już mamy pozycję na tym tickerze
        if proposal.ticker in self.current_positions:
            return False, f"Already have position on {proposal.ticker}", None

        # 4. Oblicz position size
        quantity, risk_amount, risk_pct = self.calculate_position_size(
            proposal.entry,
            proposal.stop,
            proposal.side
        )

        # 5. Sprawdź czy quantity > 0
        if quantity == 0:
            return False, f"Calculated quantity is 0 (risk too small or stop too tight)", None

        # 6. Sprawdź czy entry > 0
        if proposal.entry <= 0:
            return False, f"Invalid entry price: ${proposal.entry}", None

        # 7. Sprawdź position value (musi być < NAV)
        position_value = quantity * proposal.entry
        if position_value > self.nav:
            return False, f"Position value ${position_value:.2f} exceeds NAV ${self.nav:.2f}", None

        # ✅ Zatwierdzony
        trade_data = {
            "quantity": quantity,
            "risk_amount": risk_amount,
            "risk_pct": risk_pct,
            "position_value": position_value
        }

        return True, f"Approved: {quantity} shares, risk=${risk_amount:.2f} ({risk_pct*100:.3f}% NAV)", trade_data

    def add_position(self, trade: ApprovedTrade):
        """Dodaj pozycję do trackingu"""
        self.current_positions[trade.ticker] = trade
        print(f"[RiskManager] Added position: {trade.ticker} ({len(self.current_positions)}/{self.max_positions})")

    def remove_position(self, ticker: str):
        """Usuń pozycję z trackingu"""
        if ticker in self.current_positions:
            del self.current_positions[ticker]
            print(f"[RiskManager] Removed position: {ticker} ({len(self.current_positions)}/{self.max_positions})")


class RiskAgent:
    """Agent zarządzania ryzykiem"""

    def __init__(self):
        self.redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
        self.redis_client = None
        self.input_stream = StreamNames.TRADE_PROPOSALS
        self.approved_stream = StreamNames.APPROVED_TRADES
        self.rejected_stream = StreamNames.REJECTED_TRADES
        self.consumer_group = "risk_group"
        self.consumer_name = "risk_consumer_1"
        self.agent_name = "risk"

        # Risk manager z konfiguracją
        nav = float(os.getenv("RISK_NAV", "10000.0"))
        max_risk_pct = float(os.getenv("RISK_MAX_PER_TRADE_PCT", "0.005"))  # 0.5%
        max_positions = int(os.getenv("RISK_MAX_POSITIONS", "5"))
        daily_loss_pct = float(os.getenv("RISK_DAILY_LOSS_PCT", "0.02"))  # 2%

        self.risk_manager = RiskManager(
            nav=nav,
            max_risk_per_trade_pct=max_risk_pct,
            max_positions=max_positions,
            daily_loss_limit_pct=daily_loss_pct
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

    async def process_trade_proposal(self, message_id: str, message_data: Dict[str, str]):
        """Przetwórz trade proposal"""
        try:
            stream_msg = deserialize_message(message_data)
            proposal = TradeProposal(**stream_msg.data)

            print(f"\n[{self.agent_name}] Evaluating: {proposal.side} {proposal.ticker} @ ${proposal.entry:.2f}")

            # Waliduj ryzyko
            approved, reason, trade_data = self.risk_manager.validate_trade(proposal)

            if approved:
                # Stwórz ApprovedTrade
                approved_trade = ApprovedTrade(
                    ticker=proposal.ticker,
                    side=proposal.side,
                    entry=proposal.entry,
                    stop=proposal.stop,
                    take_profit=proposal.take_profit,
                    quantity=trade_data["quantity"],
                    risk_amount=trade_data["risk_amount"],
                    risk_pct=trade_data["risk_pct"],
                    rationale=proposal.rationale,
                    timestamp=proposal.timestamp,
                    approved_at=datetime.now(timezone.utc).isoformat()
                )

                # Dodaj do trackingu
                self.risk_manager.add_position(approved_trade)

                # Publikuj do approved stream
                await publish_message(
                    self.redis_client,
                    self.approved_stream,
                    self.agent_name,
                    approved_trade.dict(),
                    message_type="ApprovedTrade"
                )

                print(f"[{self.agent_name}] ✅ APPROVED: {reason}")

            else:
                # Stwórz RejectedTrade
                rejected_trade = RejectedTrade(
                    ticker=proposal.ticker,
                    side=proposal.side,
                    entry=proposal.entry,
                    rejection_reason=reason,
                    timestamp=proposal.timestamp,
                    rejected_at=datetime.now(timezone.utc).isoformat()
                )

                # Publikuj do rejected stream
                await publish_message(
                    self.redis_client,
                    self.rejected_stream,
                    self.agent_name,
                    rejected_trade.dict(),
                    message_type="RejectedTrade"
                )

                print(f"[{self.agent_name}] ❌ REJECTED: {reason}")

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
                            await self.process_trade_proposal(message_id, message_data)
                            processed_count += 1

                    if processed_count % 10 == 0:
                        print(f"[{self.agent_name}] Processed {processed_count} proposals")

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
    agent = RiskAgent()
    await agent.run()


if __name__ == "__main__":
    asyncio.run(main())
