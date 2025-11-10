"""
API Application - FastAPI REST API
Udostępnia endpointy do zarządzania portfelem, sygnałami i monitoringu.
"""

import os
from datetime import datetime
from typing import List, Dict, Any
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import redis.asyncio as redis


app = FastAPI(
    title="AI Portfolio Manager API",
    description="REST API for AI-powered portfolio management",
    version="0.1.0"
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # TODO: Configure properly
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Redis connection
redis_client = None


# Models
class Signal(BaseModel):
    ticker: str
    signal: str
    confidence: float
    price: float
    quantity: int
    timestamp: str


class Position(BaseModel):
    ticker: str
    quantity: int
    avg_price: float
    current_price: float
    pnl: float


class PortfolioStats(BaseModel):
    total_value: float
    cash: float
    positions_value: float
    pnl: float
    pnl_pct: float


# Startup/Shutdown
@app.on_event("startup")
async def startup_event():
    global redis_client
    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
    redis_client = await redis.from_url(redis_url, decode_responses=True)
    print("[API] Connected to Redis")


@app.on_event("shutdown")
async def shutdown_event():
    if redis_client:
        await redis_client.close()
    print("[API] Disconnected from Redis")


# Routes
@app.get("/")
async def root():
    """Health check"""
    return {
        "status": "ok",
        "service": "AI Portfolio Manager API",
        "timestamp": datetime.now().isoformat()
    }


@app.get("/api/v1/signals", response_model=List[Signal])
async def get_signals(limit: int = 10):
    """Pobierz najnowsze sygnały handlowe"""
    try:
        # TODO: Pobierz z Redis Stream
        signals = [
            {
                "ticker": "AAPL",
                "signal": "BUY",
                "confidence": 0.75,
                "price": 150.00,
                "quantity": 10,
                "timestamp": datetime.now().isoformat()
            }
        ]
        return signals
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/portfolio", response_model=PortfolioStats)
async def get_portfolio():
    """Pobierz statystyki portfela"""
    try:
        # TODO: Oblicz z Redis/bazy danych
        return {
            "total_value": 100000.0,
            "cash": 50000.0,
            "positions_value": 50000.0,
            "pnl": 5000.0,
            "pnl_pct": 5.0
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/positions", response_model=List[Position])
async def get_positions():
    """Pobierz aktywne pozycje"""
    try:
        # TODO: Pobierz z bazy danych
        positions = [
            {
                "ticker": "AAPL",
                "quantity": 10,
                "avg_price": 145.00,
                "current_price": 150.00,
                "pnl": 50.0
            }
        ]
        return positions
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/alerts")
async def get_alerts(limit: int = 10):
    """Pobierz alerty o anomaliach rynkowych"""
    try:
        # TODO: Pobierz z Redis Stream (shock_detector)
        return []
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
