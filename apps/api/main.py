"""
FastAPI Backend for AI Portfolio Manager
Provides REST API for trade proposals, approvals, and execution monitoring.
"""

import asyncio
import os
import sys
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import redis.asyncio as redis
from dotenv import load_dotenv

# Add packages to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../packages'))
from common.schemas import TradeProposal, ApprovedTrade, ExecutedOrder, StreamNames
from common.redis_utils import publish_message, deserialize_message

load_dotenv()


# ============================================================================
# Pydantic Models for API
# ============================================================================

class ProposalResponse(BaseModel):
    """Trade proposal response model"""
    proposal_id: str
    ticker: str
    side: str
    quantity: int
    entry: float
    stop: float
    take_profit: float
    combined_score: float
    news_score: float
    momentum_score: float
    proposed_at: str
    status: str = "PENDING"


class ApprovalRequest(BaseModel):
    """Trade approval request"""
    approved: bool
    reason: Optional[str] = None


class ExecutedOrderResponse(BaseModel):
    """Executed order response model"""
    order_id: str
    ticker: str
    side: str
    quantity: int
    entry_price: float
    executed_price: float
    stop: Optional[float]
    take_profit: Optional[float]
    status: str
    executed_at: str
    commission: float
    slippage: float


class RiskSummaryResponse(BaseModel):
    """Risk summary for portfolio"""
    total_positions: int
    active_trades: List[str]
    total_exposure: float
    available_capacity: int
    daily_pnl: float
    nav: float


class StatsResponse(BaseModel):
    """General statistics"""
    total_proposals: int
    pending_proposals: int
    approved_today: int
    rejected_today: int
    executed_today: int
    total_executed: int


# ============================================================================
# Redis Client Manager
# ============================================================================

class RedisManager:
    """Manages Redis connection and operations"""

    def __init__(self):
        self.redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
        self.client: Optional[redis.Redis] = None
        self.proposals_cache: Dict[str, ProposalResponse] = {}
        self.executed_cache: List[ExecutedOrderResponse] = []

    async def connect(self):
        """Connect to Redis"""
        self.client = await redis.from_url(
            self.redis_url,
            decode_responses=True
        )
        print(f"[API] ✓ Connected to Redis: {self.redis_url}")

    async def disconnect(self):
        """Disconnect from Redis"""
        if self.client:
            await self.client.close()
            print("[API] Disconnected from Redis")

    async def fetch_proposals(self, limit: int = 100) -> List[ProposalResponse]:
        """Fetch trade proposals from Redis stream"""
        try:
            # Read last N messages from trade_proposals stream
            messages = await self.client.xrevrange(
                StreamNames.TRADE_PROPOSALS,
                count=limit
            )

            proposals = []
            for message_id, message_data in messages:
                try:
                    stream_msg = deserialize_message(message_data)
                    proposal = TradeProposal(**stream_msg.data)

                    # Convert to response model
                    proposals.append(ProposalResponse(
                        proposal_id=message_id,
                        ticker=proposal.ticker,
                        side=proposal.side,
                        quantity=proposal.quantity,
                        entry=proposal.entry,
                        stop=proposal.stop,
                        take_profit=proposal.take_profit,
                        combined_score=proposal.combined_score,
                        news_score=proposal.news_score,
                        momentum_score=proposal.momentum_score,
                        proposed_at=proposal.proposed_at,
                        status="PENDING"
                    ))
                except Exception as e:
                    print(f"[API] Error parsing proposal {message_id}: {e}")
                    continue

            # Update cache
            self.proposals_cache = {p.proposal_id: p for p in proposals}

            return proposals

        except Exception as e:
            print(f"[API] Error fetching proposals: {e}")
            return []

    async def approve_trade(self, proposal_id: str) -> bool:
        """
        Approve a trade proposal and publish to approved_trades stream

        Returns:
            True if successful, False otherwise
        """
        try:
            # Get proposal from cache or fetch
            if proposal_id not in self.proposals_cache:
                await self.fetch_proposals()

            if proposal_id not in self.proposals_cache:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Proposal {proposal_id} not found"
                )

            proposal = self.proposals_cache[proposal_id]

            # Create ApprovedTrade
            approved_trade = ApprovedTrade(
                ticker=proposal.ticker,
                side=proposal.side,
                quantity=proposal.quantity,
                entry=proposal.entry,
                stop=proposal.stop,
                take_profit=proposal.take_profit,
                approved_at=datetime.now(timezone.utc).isoformat()
            )

            # Publish to approved_trades stream
            await publish_message(
                self.client,
                StreamNames.APPROVED_TRADES,
                "api",
                approved_trade.dict(),
                message_type="ApprovedTrade"
            )

            # Update status in cache
            proposal.status = "APPROVED"

            print(f"[API] ✅ Approved trade: {proposal.ticker} {proposal.side} {proposal.quantity}")

            return True

        except HTTPException:
            raise
        except Exception as e:
            print(f"[API] Error approving trade {proposal_id}: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to approve trade: {str(e)}"
            )

    async def fetch_executed_orders(self, limit: int = 100) -> List[ExecutedOrderResponse]:
        """Fetch executed orders from Redis stream"""
        try:
            # Read last N messages from executed_orders stream
            messages = await self.client.xrevrange(
                StreamNames.EXECUTED_ORDERS,
                count=limit
            )

            executed = []
            for message_id, message_data in messages:
                try:
                    stream_msg = deserialize_message(message_data)
                    order = ExecutedOrder(**stream_msg.data)

                    # Convert to response model
                    executed.append(ExecutedOrderResponse(
                        order_id=order.order_id,
                        ticker=order.ticker,
                        side=order.side,
                        quantity=order.quantity,
                        entry_price=order.entry_price,
                        executed_price=order.executed_price,
                        stop=order.stop,
                        take_profit=order.take_profit,
                        status=order.status,
                        executed_at=order.executed_at,
                        commission=order.commission,
                        slippage=order.slippage
                    ))
                except Exception as e:
                    print(f"[API] Error parsing order {message_id}: {e}")
                    continue

            # Update cache
            self.executed_cache = executed

            return executed

        except Exception as e:
            print(f"[API] Error fetching executed orders: {e}")
            return []

    async def get_risk_summary(self) -> RiskSummaryResponse:
        """Get current risk summary"""
        try:
            # Fetch current executed orders
            executed = await self.fetch_executed_orders()

            # Calculate active positions (FILLED orders)
            active_trades = [
                f"{o.ticker} {o.side} {o.quantity}@{o.executed_price:.2f}"
                for o in executed if o.status == "FILLED"
            ]

            total_positions = len(active_trades)

            # Calculate total exposure (sum of position values)
            total_exposure = sum(
                o.quantity * o.executed_price
                for o in executed if o.status == "FILLED"
            )

            # Get NAV from env
            nav = float(os.getenv("RISK_NAV", "10000.0"))
            max_positions = int(os.getenv("RISK_MAX_POSITIONS", "5"))

            # Calculate daily P&L (simplified - would need position tracking)
            daily_pnl = -sum(o.commission + abs(o.slippage * o.quantity) for o in executed)

            return RiskSummaryResponse(
                total_positions=total_positions,
                active_trades=active_trades[:10],  # Show top 10
                total_exposure=total_exposure,
                available_capacity=max_positions - total_positions,
                daily_pnl=daily_pnl,
                nav=nav
            )

        except Exception as e:
            print(f"[API] Error getting risk summary: {e}")
            return RiskSummaryResponse(
                total_positions=0,
                active_trades=[],
                total_exposure=0.0,
                available_capacity=5,
                daily_pnl=0.0,
                nav=10000.0
            )


# ============================================================================
# FastAPI App Setup
# ============================================================================

# Global Redis manager
redis_manager = RedisManager()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup/shutdown"""
    # Startup
    await redis_manager.connect()
    yield
    # Shutdown
    await redis_manager.disconnect()


app = FastAPI(
    title="AI Portfolio Manager API",
    description="REST API for managing trade proposals and monitoring executions",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify exact origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================================
# API Endpoints
# ============================================================================

@app.get("/", tags=["Health"])
async def root():
    """Health check endpoint"""
    return {
        "status": "ok",
        "service": "AI Portfolio Manager API",
        "version": "1.0.0"
    }


@app.get("/proposals", response_model=List[ProposalResponse], tags=["Trading"])
async def get_proposals(limit: int = 100):
    """
    Get list of trade proposals from Redis stream

    Args:
        limit: Maximum number of proposals to return (default: 100)

    Returns:
        List of trade proposals
    """
    proposals = await redis_manager.fetch_proposals(limit=limit)
    return proposals


@app.post("/approve/{proposal_id}", tags=["Trading"])
async def approve_trade(proposal_id: str, approval: ApprovalRequest):
    """
    Approve or reject a trade proposal

    Args:
        proposal_id: The proposal ID from Redis stream
        approval: Approval request with approved flag

    Returns:
        Success message
    """
    if not approval.approved:
        # For rejection, we just return success (no action needed)
        return {
            "status": "rejected",
            "proposal_id": proposal_id,
            "reason": approval.reason or "Rejected by user"
        }

    # Approve the trade
    success = await redis_manager.approve_trade(proposal_id)

    if success:
        return {
            "status": "approved",
            "proposal_id": proposal_id,
            "message": "Trade approved and sent to execution"
        }
    else:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to approve trade"
        )


@app.get("/executed", response_model=List[ExecutedOrderResponse], tags=["Trading"])
async def get_executed_orders(limit: int = 100):
    """
    Get list of executed orders from Redis stream

    Args:
        limit: Maximum number of orders to return (default: 100)

    Returns:
        List of executed orders
    """
    executed = await redis_manager.fetch_executed_orders(limit=limit)
    return executed


@app.get("/risk-summary", response_model=RiskSummaryResponse, tags=["Risk"])
async def get_risk_summary():
    """
    Get current risk summary for the portfolio

    Returns:
        Risk summary with positions, exposure, and P&L
    """
    summary = await redis_manager.get_risk_summary()
    return summary


@app.get("/stats", response_model=StatsResponse, tags=["Statistics"])
async def get_stats():
    """
    Get general statistics about trading activity

    Returns:
        Statistics including counts of proposals and executions
    """
    proposals = await redis_manager.fetch_proposals()
    executed = await redis_manager.fetch_executed_orders()

    # Count by status
    pending = sum(1 for p in proposals if p.status == "PENDING")
    approved = sum(1 for p in proposals if p.status == "APPROVED")

    return StatsResponse(
        total_proposals=len(proposals),
        pending_proposals=pending,
        approved_today=approved,  # Simplified - would need date filtering
        rejected_today=0,  # Not tracked yet
        executed_today=len(executed),  # Simplified
        total_executed=len(executed)
    )


# ============================================================================
# Main Entry Point
# ============================================================================

if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("API_PORT", "8000"))
    host = os.getenv("API_HOST", "0.0.0.0")

    print(f"[API] Starting FastAPI server on {host}:{port}")

    uvicorn.run(
        "main:app",
        host=host,
        port=port,
        reload=True,
        log_level="info"
    )
