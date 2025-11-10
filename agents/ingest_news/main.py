"""
Ingest News Agent - Main Event Loop
Pobiera wiadomości finansowe i publikuje je do Redis Streams.
"""

import asyncio
import os
from datetime import datetime
from typing import Dict, Any
import redis.asyncio as redis


class IngestNewsAgent:
    def __init__(self):
        self.redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
        self.redis_client = None
        self.stream_name = "news:raw"
        self.agent_name = "ingest_news"

    async def connect(self):
        """Połącz z Redis"""
        self.redis_client = await redis.from_url(self.redis_url, decode_responses=True)
        print(f"[{self.agent_name}] Connected to Redis")

    async def disconnect(self):
        """Rozłącz z Redis"""
        if self.redis_client:
            await self.redis_client.close()

    async def fetch_news(self) -> list[Dict[str, Any]]:
        """Pobierz wiadomości z zewnętrznych źródeł (placeholder)"""
        # TODO: Implementacja pobierania z RSS, News API, etc.
        return [{
            "title": "Example news article",
            "content": "This is a placeholder news article",
            "source": "example.com",
            "url": "https://example.com/article",
            "published_at": datetime.now().isoformat(),
            "tickers": ["AAPL", "MSFT"]
        }]

    async def publish_news(self, news_items: list[Dict[str, Any]]):
        """Publikuj wiadomości do Redis Stream"""
        for item in news_items:
            message_id = await self.redis_client.xadd(
                self.stream_name,
                {
                    "agent": self.agent_name,
                    "timestamp": datetime.now().isoformat(),
                    "data": str(item)  # TODO: Use proper JSON serialization
                }
            )
            print(f"[{self.agent_name}] Published news: {message_id}")

    async def run(self):
        """Główna pętla agenta"""
        await self.connect()

        try:
            print(f"[{self.agent_name}] Starting event loop...")

            while True:
                # Pobierz wiadomości
                news_items = await self.fetch_news()

                # Publikuj do strumienia
                if news_items:
                    await self.publish_news(news_items)

                # Czekaj przed następnym cyklem
                await asyncio.sleep(60)  # Co minutę

        except KeyboardInterrupt:
            print(f"[{self.agent_name}] Shutting down...")
        finally:
            await self.disconnect()


async def main():
    """Entry point"""
    agent = IngestNewsAgent()
    await agent.run()


if __name__ == "__main__":
    asyncio.run(main())
