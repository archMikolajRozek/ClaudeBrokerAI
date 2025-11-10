"""
Score News Agent - Main Event Loop
Konsumuje wiadomości z Redis Streams i ocenia ich sentyment/wpływ.
"""

import asyncio
import os
from datetime import datetime
from typing import Dict, Any, Optional
import redis.asyncio as redis


class ScoreNewsAgent:
    def __init__(self):
        self.redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
        self.redis_client = None
        self.input_stream = "news:raw"
        self.output_stream = "news:scored"
        self.consumer_group = "score_news_group"
        self.consumer_name = "score_news_consumer_1"
        self.agent_name = "score_news"

    async def connect(self):
        """Połącz z Redis"""
        self.redis_client = await redis.from_url(self.redis_url, decode_responses=True)

        # Utwórz consumer group jeśli nie istnieje
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

    async def score_news(self, news_data: Dict[str, Any]) -> Dict[str, Any]:
        """Oceń sentyment wiadomości (placeholder)"""
        # TODO: Implementacja z użyciem AI/NLP (OpenAI, Anthropic, HuggingFace)
        return {
            **news_data,
            "sentiment_score": 0.5,  # -1 do 1
            "impact_score": 0.3,     # 0 do 1
            "confidence": 0.7,        # 0 do 1
            "scored_at": datetime.now().isoformat()
        }

    async def process_message(self, message_id: str, message_data: Dict[str, str]):
        """Przetwórz pojedynczą wiadomość"""
        try:
            # Parse message data (TODO: proper JSON deserialization)
            news_data = eval(message_data.get("data", "{}"))

            # Score the news
            scored_data = await self.score_news(news_data)

            # Publish to output stream
            await self.redis_client.xadd(
                self.output_stream,
                {
                    "agent": self.agent_name,
                    "timestamp": datetime.now().isoformat(),
                    "data": str(scored_data)
                }
            )

            # Acknowledge message
            await self.redis_client.xack(self.input_stream, self.consumer_group, message_id)
            print(f"[{self.agent_name}] Processed and scored: {message_id}")

        except Exception as e:
            print(f"[{self.agent_name}] Error processing {message_id}: {e}")

    async def run(self):
        """Główna pętla agenta - event listener"""
        await self.connect()

        try:
            print(f"[{self.agent_name}] Starting event loop...")

            while True:
                # Czytaj z strumienia (blocking z timeout)
                messages = await self.redis_client.xreadgroup(
                    self.consumer_group,
                    self.consumer_name,
                    {self.input_stream: ">"},
                    count=10,
                    block=5000  # 5 sekund
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
    agent = ScoreNewsAgent()
    await agent.run()


if __name__ == "__main__":
    asyncio.run(main())
