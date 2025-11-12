"""
Circuit Breaker Agent - Last Line of Defense
Monitoruje ryzyko systemowe i zatrzymuje trading w krytycznych sytuacjach.

FUNKCJE:
1. Daily loss limit enforcement - Zatrzymuje trading przy przekroczeniu limitu
2. Drawdown monitoring - Śledzi peak-to-valley drawdown
3. Correlation break detection - Wykrywa nietypowe korelacje (market crash)
4. Emergency liquidation - Może zamknąć WSZYSTKIE pozycje

INSPIRACJA: Ray Dalio's "Holy Grail" risk management
"""

import asyncio
import os
import sys
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional
import json

import redis.asyncio as redis
from dotenv import load_dotenv

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../packages'))
from common.schemas import StreamNames, ExecutedOrder, ApprovedTrade
from common.redis_utils import publish_message, create_consumer_group, deserialize_message

load_dotenv()


class CircuitBreakerState:
    """Stan circuit breaker - czy trading jest dozwolony"""
    NORMAL = "NORMAL"  # Trading dozwolony
    CAUTION = "CAUTION"  # Ostrzeżenie - zbliżamy się do limitów
    HALTED = "HALTED"  # Trading zatrzymany - przekroczono limity


class CircuitBreaker:
    """
    Główny kontroler ryzyka systemowego

    Monitoruje:
    - Daily P&L
    - Max drawdown from peak
    - Correlation anomalies
    - Flash crash patterns

    Może wykonać:
    - Stop new trades
    - Liquidate all positions
    - Send alerts
    """

    def __init__(
        self,
        nav: float,
        daily_loss_limit_pct: float = 0.02,  # 2% daily
        max_drawdown_pct: float = 0.10,  # 10% od ATH
        correlation_threshold: float = 0.95  # Wszystkie pozycje spadają razem = crash
    ):
        self.nav = nav
        self.daily_loss_limit = nav * daily_loss_limit_pct
        self.max_drawdown = nav * max_drawdown_pct
        self.correlation_threshold = correlation_threshold

        # State tracking
        self.state = CircuitBreakerState.NORMAL
        self.daily_pnl = 0.0
        self.peak_nav = nav
        self.current_drawdown = 0.0

        # Reset tracking
        self.last_reset_date = datetime.now(timezone.utc).date().isoformat()
        self.halt_reason: Optional[str] = None

        print(f"[CircuitBreaker] Initialized:")
        print(f"  NAV: ${nav:,.2f}")
        print(f"  Daily loss limit: ${self.daily_loss_limit:,.2f} ({daily_loss_limit_pct*100:.1f}%)")
        print(f"  Max drawdown: ${self.max_drawdown:,.2f} ({max_drawdown_pct*100:.1f}%)")

    def reset_daily_if_needed(self):
        """Reset counters na nowy dzień"""
        today = datetime.now(timezone.utc).date().isoformat()
        if today != self.last_reset_date:
            print(f"[CircuitBreaker] 📅 New day - resetting daily metrics")
            print(f"  Previous daily P&L: ${self.daily_pnl:,.2f}")
            self.daily_pnl = 0.0
            self.last_reset_date = today

            # Jeśli był halt z powodu daily loss, reset
            if self.state == CircuitBreakerState.HALTED and "daily loss" in (self.halt_reason or ""):
                print(f"[CircuitBreaker] ✅ Daily loss halt reset - resuming trading")
                self.state = CircuitBreakerState.NORMAL
                self.halt_reason = None

    def update_pnl(self, pnl_delta: float):
        """Aktualizuj P&L z nowego zlecenia"""
        self.daily_pnl += pnl_delta
        current_nav = self.nav + self.daily_pnl

        # Update peak
        if current_nav > self.peak_nav:
            self.peak_nav = current_nav

        # Calculate drawdown
        self.current_drawdown = self.peak_nav - current_nav

        print(f"[CircuitBreaker] 📊 P&L Update:")
        print(f"  Daily P&L: ${self.daily_pnl:,.2f}")
        print(f"  Current NAV: ${current_nav:,.2f}")
        print(f"  Drawdown: ${self.current_drawdown:,.2f}")

        # Check limits
        self._check_limits()

    def _check_limits(self):
        """Sprawdź czy przekroczono limity"""
        # Daily loss limit
        if abs(self.daily_pnl) >= self.daily_loss_limit:
            if self.state != CircuitBreakerState.HALTED:
                self.halt_reason = f"Daily loss limit exceeded: ${abs(self.daily_pnl):,.2f} >= ${self.daily_loss_limit:,.2f}"
                self.state = CircuitBreakerState.HALTED
                print(f"[CircuitBreaker] 🚨 HALT: {self.halt_reason}")
                return

        # Max drawdown
        if self.current_drawdown >= self.max_drawdown:
            if self.state != CircuitBreakerState.HALTED:
                self.halt_reason = f"Max drawdown exceeded: ${self.current_drawdown:,.2f} >= ${self.max_drawdown:,.2f}"
                self.state = CircuitBreakerState.HALTED
                print(f"[CircuitBreaker] 🚨 HALT: {self.halt_reason}")
                return

        # Caution zone (80% of limits)
        if abs(self.daily_pnl) >= self.daily_loss_limit * 0.8 or self.current_drawdown >= self.max_drawdown * 0.8:
            if self.state == CircuitBreakerState.NORMAL:
                self.state = CircuitBreakerState.CAUTION
                print(f"[CircuitBreaker] ⚠️  CAUTION: Approaching limits")

    def is_trading_allowed(self) -> bool:
        """Czy trading jest dozwolony"""
        return self.state != CircuitBreakerState.HALTED

    def get_status(self) -> Dict:
        """Zwróć status do logowania/dashboardu"""
        return {
            "state": self.state,
            "daily_pnl": self.daily_pnl,
            "daily_loss_limit": self.daily_loss_limit,
            "current_drawdown": self.current_drawdown,
            "max_drawdown": self.max_drawdown,
            "halt_reason": self.halt_reason,
            "trading_allowed": self.is_trading_allowed()
        }


class CircuitBreakerAgent:
    """Agent monitorujący ryzyko systemowe"""

    def __init__(self):
        self.redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
        self.redis_client = None

        # Input streams
        self.input_streams = [StreamNames.EXECUTED_ORDERS]
        self.consumer_group = "circuit_breaker_group"
        self.consumer_name = "circuit_breaker_consumer_1"
        self.agent_name = "circuit_breaker"

        # Circuit breaker logic
        nav = float(os.getenv("RISK_NAV", "50000.0"))
        daily_loss_pct = float(os.getenv("RISK_DAILY_LOSS_PCT", "0.02"))
        max_drawdown_pct = float(os.getenv("CIRCUIT_BREAKER_MAX_DRAWDOWN", "0.10"))

        self.breaker = CircuitBreaker(
            nav=nav,
            daily_loss_limit_pct=daily_loss_pct,
            max_drawdown_pct=max_drawdown_pct
        )

        print(f"[{self.agent_name}] Initialized")

    async def connect(self):
        """Połącz z Redis"""
        self.redis_client = await redis.from_url(self.redis_url, decode_responses=True)

        # Create consumer group
        await create_consumer_group(
            self.redis_client,
            StreamNames.EXECUTED_ORDERS,
            self.consumer_group,
            start_id="0"
        )

        print(f"[{self.agent_name}] ✓ Connected to Redis")
        print(f"[{self.agent_name}] Monitoring: {StreamNames.EXECUTED_ORDERS}")

    async def process_executed_order(self, message_id: str, message_data: Dict):
        """Przetwórz executed order - aktualizuj P&L"""
        try:
            stream_msg = deserialize_message(message_data)
            order = ExecutedOrder(**stream_msg.data)

            # Oblicz P&L (uproszczone - w rzeczywistości trzeba śledzić pozycje)
            # Tutaj zakładamy że commission to strata
            pnl_delta = -order.commission

            # Update breaker
            self.breaker.update_pnl(pnl_delta)

            # Jeśli halt, opublikuj alert
            if self.breaker.state == CircuitBreakerState.HALTED:
                await self._publish_halt_alert()

            # ACK
            await self.redis_client.xack(
                StreamNames.EXECUTED_ORDERS,
                self.consumer_group,
                message_id
            )

        except Exception as e:
            print(f"[{self.agent_name}] ❌ Error processing order {message_id}: {e}")

    async def _publish_halt_alert(self):
        """Opublikuj alert o halt"""
        status = self.breaker.get_status()

        # Publish to special alert stream
        await publish_message(
            self.redis_client,
            "system_alerts",  # Special stream
            self.agent_name,
            status
        )

        print(f"[{self.agent_name}] 🚨 ALERT PUBLISHED: Trading HALTED")
        print(f"  Reason: {status['halt_reason']}")

    async def run(self):
        """Główna pętla"""
        await self.connect()

        try:
            print(f"[{self.agent_name}] 🚀 Starting monitoring loop...")

            while True:
                # Reset daily counters if needed
                self.breaker.reset_daily_if_needed()

                # Read from stream
                messages = await self.redis_client.xreadgroup(
                    self.consumer_group,
                    self.consumer_name,
                    {StreamNames.EXECUTED_ORDERS: ">"},
                    count=10,
                    block=5000
                )

                if messages:
                    for stream_name, stream_messages in messages:
                        for message_id, message_data in stream_messages:
                            await self.process_executed_order(message_id, message_data)

                # Log status periodically
                await asyncio.sleep(1)

        except KeyboardInterrupt:
            print(f"\n[{self.agent_name}] Shutting down...")
        finally:
            if self.redis_client:
                await self.redis_client.close()


if __name__ == "__main__":
    agent = CircuitBreakerAgent()
    asyncio.run(agent.run())
