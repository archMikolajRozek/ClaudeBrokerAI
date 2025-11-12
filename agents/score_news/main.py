"""
Score News Agent - Complete Implementation
Konsumuje newsy z Redis Streams i oblicza adjusted impact z decay factor.
"""

import asyncio
import os
import sys
import math
from datetime import datetime, timezone
from typing import Dict, Any, Optional
import json

import redis.asyncio as redis
from dotenv import load_dotenv
from dateutil import parser as date_parser

# Add packages to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../packages'))
from common.schemas import NewsIngestedMessage, NewsScoredMessage, StreamNames
from common.redis_utils import publish_message, create_consumer_group, deserialize_message


load_dotenv()


class NewsScorer:
    """Kalkulacja score z decay factor"""

    def __init__(self, tau_hours: float = 24.0):
        """
        Args:
            tau_hours: Parametr decay - half-life w godzinach
                      Po tau godzinach, decay_factor = exp(-1) ≈ 0.368
        """
        self.tau_hours = tau_hours
        self.tau_seconds = tau_hours * 3600

    def calculate_decay_factor(self, news_datetime: str, current_datetime: datetime) -> float:
        """
        Oblicz decay factor: exp(-Δt / tau)

        Args:
            news_datetime: ISO datetime newsa
            current_datetime: Aktualny czas

        Returns:
            decay_factor w zakresie (0, 1]
        """
        try:
            # Parse news datetime
            news_dt = date_parser.isoparse(news_datetime)

            # Ensure both datetimes are timezone-aware
            if news_dt.tzinfo is None:
                news_dt = news_dt.replace(tzinfo=timezone.utc)
            if current_datetime.tzinfo is None:
                current_datetime = current_datetime.replace(tzinfo=timezone.utc)

            # Calculate time difference in seconds
            delta_t = (current_datetime - news_dt).total_seconds()

            # Ensure delta_t is non-negative
            delta_t = max(0, delta_t)

            # Calculate decay factor: exp(-Δt / tau)
            decay_factor = math.exp(-delta_t / self.tau_seconds)

            return min(1.0, max(0.0, decay_factor))

        except Exception as e:
            print(f"[score_news] Error calculating decay factor: {e}")
            return 1.0  # Default to no decay on error

    def calculate_adjusted_impact(
        self,
        sentiment: float,
        impact: float,
        decay_factor: float
    ) -> float:
        """
        Oblicz adjusted impact: sentiment * impact * decay_factor

        Args:
            sentiment: Sentyment od -1 do 1
            impact: Impact od 0 do 1
            decay_factor: Decay od 0 do 1

        Returns:
            adjusted_impact (może być ujemny jeśli sentiment < 0)
        """
        return sentiment * impact * decay_factor

    def score_news(
        self,
        news: NewsIngestedMessage,
        current_time: Optional[datetime] = None
    ) -> NewsScoredMessage:
        """
        Oblicz pełny score dla newsa

        Args:
            news: Znormalizowany news z ingest_news
            current_time: Czas obliczenia (domyślnie teraz)

        Returns:
            NewsScoredMessage ze score i metadata
        """
        if current_time is None:
            current_time = datetime.now(timezone.utc)

        # Calculate decay factor
        decay_factor = self.calculate_decay_factor(news.datetime, current_time)

        # Calculate adjusted impact
        score = self.calculate_adjusted_impact(
            news.sentiment,
            news.impact,
            decay_factor
        )

        return NewsScoredMessage(
            ticker=news.ticker,
            score=score,
            timestamp=current_time.isoformat(),
            decay_factor=decay_factor,
            relevance=news.relevance,
            original_sentiment=news.sentiment,
            original_impact=news.impact,
            news_datetime=news.datetime,
            headline=news.headline
        )


class ScoreNewsAgent:
    """Agent scorujący newsy z decay factor"""

    def __init__(self):
        self.redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
        self.redis_client = None
        self.input_stream = StreamNames.NEWS_INGESTED
        self.output_stream = StreamNames.NEWS_SCORED
        self.consumer_group = "score_news_group"
        self.consumer_name = "score_news_consumer_1"
        self.agent_name = "score_news"

        # News scorer z konfiguracją
        tau_hours = float(os.getenv("NEWS_DECAY_TAU_HOURS", "24.0"))
        self.scorer = NewsScorer(tau_hours=tau_hours)

        print(f"[{self.agent_name}] Initialized with tau={tau_hours}h")

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
            start_id="0"  # Process from beginning
        )

        print(f"[{self.agent_name}] ✓ Connected to Redis")
        print(f"[{self.agent_name}] Listening on stream: {self.input_stream}")

    async def disconnect(self):
        """Rozłącz z Redis"""
        if self.redis_client:
            await self.redis_client.close()
            print(f"[{self.agent_name}] Disconnected from Redis")

    async def process_message(self, message_id: str, message_data: Dict[str, str]):
        """Przetwórz pojedynczą wiadomość"""
        try:
            # Deserialize message
            stream_msg = deserialize_message(message_data)

            # Parse NewsIngestedMessage
            news = NewsIngestedMessage(**stream_msg.data)

            # Calculate score with decay factor
            scored = self.scorer.score_news(news)

            # Publish to output stream
            await publish_message(
                self.redis_client,
                self.output_stream,
                self.agent_name,
                scored.model_dump(),
                message_type="NewsScoredMessage"
            )

            # Acknowledge message
            await self.redis_client.xack(
                self.input_stream,
                self.consumer_group,
                message_id
            )

            # Log
            print(f"[{self.agent_name}] ✓ Scored: {scored.ticker} - "
                  f"score={scored.score:.4f} "
                  f"(sentiment={scored.original_sentiment:.2f}, "
                  f"impact={scored.original_impact:.2f}, "
                  f"decay={scored.decay_factor:.4f})")

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
                            processed_count += 1

                    print(f"[{self.agent_name}] Processed {processed_count} messages total")

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
    agent = ScoreNewsAgent()
    await agent.run()


if __name__ == "__main__":
    asyncio.run(main())
