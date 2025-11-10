"""
Market Data Agent - Main Event Loop
Pobiera dane rynkowe i publikuje je do Redis Streams.
"""

import asyncio
import os
from datetime import datetime
from typing import Dict, Any, List
import redis.asyncio as redis


class MarketDataAgent:
    def __init__(self):
        self.redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
        self.redis_client = None
        self.stream_name = "market:data"
        self.agent_name = "market_data"
        self.watchlist = ["AAPL", "MSFT", "GOOGL", "AMZN", "NVDA"]  # TODO: Dynamic watchlist

    async def connect(self):
        """Połącz z Redis"""
        self.redis_client = await redis.from_url(self.redis_url, decode_responses=True)
        print(f"[{self.agent_name}] Connected to Redis")

    async def disconnect(self):
        """Rozłącz z Redis"""
        if self.redis_client:
            await self.redis_client.close()

    async def fetch_market_data(self, ticker: str) -> Dict[str, Any]:
        """Pobierz dane rynkowe dla symbolu (placeholder)"""
        # TODO: Implementacja z Alpha Vantage, Yahoo Finance, IEX Cloud, Polygon.io
        return {
            "ticker": ticker,
            "price": 150.00,
            "volume": 1000000,
            "change_pct": 1.5,
            "high": 152.00,
            "low": 148.00,
            "open": 149.00,
            "timestamp": datetime.now().isoformat(),
            "indicators": {
                "rsi": 55.0,
                "macd": 1.2,
                "sma_20": 148.5,
                "sma_50": 145.0
            }
        }

    async def publish_market_data(self, market_data: Dict[str, Any]):
        """Publikuj dane rynkowe do Redis Stream"""
        message_id = await self.redis_client.xadd(
            self.stream_name,
            {
                "agent": self.agent_name,
                "timestamp": datetime.now().isoformat(),
                "data": str(market_data)
            }
        )
        print(f"[{self.agent_name}] Published market data: {market_data['ticker']}")

    async def run(self):
        """Główna pętla agenta"""
        await self.connect()

        try:
            print(f"[{self.agent_name}] Starting event loop...")

            while True:
                # Pobierz dane dla każdego symbolu na watchlist
                for ticker in self.watchlist:
                    market_data = await self.fetch_market_data(ticker)
                    await self.publish_market_data(market_data)

                # Czekaj przed następnym cyklem
                await asyncio.sleep(30)  # Co 30 sekund

        except KeyboardInterrupt:
            print(f"[{self.agent_name}] Shutting down...")
        finally:
            await self.disconnect()


async def main():
    """Entry point"""
    agent = MarketDataAgent()
    await agent.run()


if __name__ == "__main__":
    asyncio.run(main())
