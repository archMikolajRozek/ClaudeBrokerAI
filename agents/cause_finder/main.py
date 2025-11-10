"""
Cause Finder Agent - Complete Implementation
Przypisuje przyczyny dla shock events poprzez przeszukiwanie newsów.
"""

import asyncio
import os
import sys
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional, Tuple
import uuid

import redis.asyncio as redis
from dotenv import load_dotenv
from dateutil import parser as date_parser

# Add packages to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../packages'))
from common.schemas import (
    MarketShockEvent,
    NewsIngestedMessage,
    CauseAttribution,
    StreamNames
)
from common.redis_utils import publish_message, create_consumer_group, deserialize_message
from common.database import ImpactMemoryDB


load_dotenv()


class NewsFetcher:
    """Fetch newsów z Redis dla danego tickera i okna czasowego"""

    def __init__(self, redis_client: redis.Redis):
        self.redis_client = redis_client

    async def fetch_recent_news(
        self,
        ticker: str,
        time_window_minutes: int = 30
    ) -> List[NewsIngestedMessage]:
        """
        Pobierz newsy dla tickera z ostatnich N minut

        Args:
            ticker: Symbol akcji
            time_window_minutes: Okno czasowe wstecz

        Returns:
            Lista newsów
        """
        try:
            # Pobierz ostatnie 100 wiadomości z news_ingested stream
            messages = await self.redis_client.xrevrange(
                StreamNames.NEWS_INGESTED,
                count=100
            )

            recent_news = []
            cutoff_time = datetime.now(timezone.utc) - timedelta(minutes=time_window_minutes)

            for message_id, message_data in messages:
                try:
                    stream_msg = deserialize_message(message_data)
                    news = NewsIngestedMessage(**stream_msg.data)

                    # Sprawdź ticker
                    if news.ticker != ticker:
                        continue

                    # Sprawdź czas
                    news_time = date_parser.isoparse(news.datetime)
                    if news_time.tzinfo is None:
                        news_time = news_time.replace(tzinfo=timezone.utc)

                    if news_time >= cutoff_time:
                        recent_news.append(news)

                except Exception as e:
                    continue

            return recent_news

        except Exception as e:
            print(f"[NewsFetcher] Error fetching news: {e}")
            return []


class CauseAttributor:
    """Przypisywanie przyczyn dla shock events"""

    def __init__(self):
        pass

    def calculate_similarity(self, news: NewsIngestedMessage, shock: MarketShockEvent) -> float:
        """
        Oblicz similarity między newsem a shockiem (prosty keyword matching)

        Returns:
            Similarity score 0-1
        """
        # Prosty keyword matching dla MVP
        # TODO: Zamienić na proper similarity (embeddings, semantic search)

        shock_keywords = {
            "PRICE_SPIKE": ["surge", "jump", "spike", "rally", "soar", "gain", "up", "rise"],
            "PRICE_DROP": ["drop", "fall", "crash", "plunge", "decline", "down", "sink"],
            "VOLUME_SPIKE": ["volume", "trading", "activity", "buying", "selling"]
        }

        keywords = shock_keywords.get(shock.shock_type, [])

        text = (news.headline + " " + news.body).lower()

        # Count keyword matches
        matches = sum(1 for keyword in keywords if keyword in text)

        # Bonus for high impact/relevance news
        base_similarity = min(matches / len(keywords), 1.0) if keywords else 0.0

        # Weighted by news sentiment alignment
        sentiment_alignment = 0.0
        if shock.shock_type == "PRICE_SPIKE" and news.sentiment > 0:
            sentiment_alignment = news.sentiment
        elif shock.shock_type == "PRICE_DROP" and news.sentiment < 0:
            sentiment_alignment = abs(news.sentiment)

        # Combined similarity
        similarity = (base_similarity * 0.5) + (sentiment_alignment * 0.3) + (news.impact * 0.2)

        return min(similarity, 1.0)

    def attribute_cause(
        self,
        shock: MarketShockEvent,
        recent_news: List[NewsIngestedMessage]
    ) -> Optional[CauseAttribution]:
        """
        Przypisz przyczynę dla shock event

        Returns:
            CauseAttribution lub None jeśli nie znaleziono przyczyny
        """
        if not recent_news:
            # No news found - technical cause
            return self._create_technical_attribution(shock)

        # Oblicz similarity dla każdego newsa
        candidates = []
        shock_time = date_parser.isoparse(shock.detected_at)
        if shock_time.tzinfo is None:
            shock_time = shock_time.replace(tzinfo=timezone.utc)

        for news in recent_news:
            similarity = self.calculate_similarity(news, shock)

            if similarity > 0.3:  # Threshold
                news_time = date_parser.isoparse(news.datetime)
                if news_time.tzinfo is None:
                    news_time = news_time.replace(tzinfo=timezone.utc)

                time_delta = (shock_time - news_time).total_seconds() / 60.0  # minutes

                candidates.append({
                    "news": news,
                    "similarity": similarity,
                    "time_delta": time_delta
                })

        if not candidates:
            return self._create_technical_attribution(shock)

        # Wybierz najlepszego kandydata (najwyższy similarity, najbliższy czas)
        best = max(candidates, key=lambda x: x["similarity"] - (x["time_delta"] / 100.0))

        # Confidence based on similarity i time proximity
        confidence = best["similarity"] * (1.0 - min(best["time_delta"] / 30.0, 0.5))

        return CauseAttribution(
            event_id=f"EVT_{uuid.uuid4().hex[:8].upper()}",
            ticker=shock.ticker,
            shock_type=shock.shock_type,
            shock_detected_at=shock.detected_at,
            cause_type="NEWS",
            cause_text=best["news"].headline,
            cause_source=best["news"].source,
            confidence=confidence,
            impact_strength=best["news"].impact,
            time_delta_minutes=best["time_delta"],
            attributed_at=datetime.now(timezone.utc).isoformat()
        )

    def _create_technical_attribution(self, shock: MarketShockEvent) -> CauseAttribution:
        """Stwórz attribution dla technical cause (brak newsów)"""
        return CauseAttribution(
            event_id=f"EVT_{uuid.uuid4().hex[:8].upper()}",
            ticker=shock.ticker,
            shock_type=shock.shock_type,
            shock_detected_at=shock.detected_at,
            cause_type="TECHNICAL",
            cause_text=f"No news found. Likely technical/algorithmic move with z-score={shock.z_score:.2f}",
            cause_source=None,
            confidence=0.3,  # Low confidence for technical
            impact_strength=shock.severity,
            time_delta_minutes=0.0,
            attributed_at=datetime.now(timezone.utc).isoformat()
        )


class CauseFinderAgent:
    """Agent znajdujący przyczyny dla shock events"""

    def __init__(self):
        self.redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
        self.redis_client = None
        self.input_stream = StreamNames.MARKET_SHOCKS
        self.consumer_group = "cause_finder_group"
        self.consumer_name = "cause_finder_consumer_1"
        self.agent_name = "cause_finder"

        # Database
        db_path = os.getenv("IMPACT_MEMORY_DB", "impact_memory.db")
        self.db = ImpactMemoryDB(db_path)

        # News fetcher
        self.news_fetcher = None  # Will be initialized in connect()

        # Cause attributor
        self.attributor = CauseAttributor()

        # Config
        self.time_window_minutes = int(os.getenv("CAUSE_FINDER_TIME_WINDOW", "30"))

        print(f"[{self.agent_name}] Initialized with:")
        print(f"  Time window: {self.time_window_minutes} minutes")
        print(f"  Database: {db_path}")

    async def connect(self):
        """Połącz z Redis i inicjalizuj"""
        self.redis_client = await redis.from_url(
            self.redis_url,
            decode_responses=True
        )

        # Initialize news fetcher
        self.news_fetcher = NewsFetcher(self.redis_client)

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
        """Rozłącz z Redis i zamknij bazę"""
        if self.redis_client:
            await self.redis_client.close()
        self.db.close()
        print(f"[{self.agent_name}] Disconnected")

    async def process_shock_event(self, message_id: str, message_data: Dict[str, str]):
        """Przetwórz shock event i znajdź przyczynę"""
        try:
            stream_msg = deserialize_message(message_data)
            shock = MarketShockEvent(**stream_msg.data)

            print(f"\n[{self.agent_name}] Processing shock: {shock.shock_type} {shock.ticker} @ ${shock.price:.2f}")

            # Pobierz recent news
            recent_news = await self.news_fetcher.fetch_recent_news(
                shock.ticker,
                self.time_window_minutes
            )

            print(f"[{self.agent_name}] Found {len(recent_news)} news in last {self.time_window_minutes}min")

            # Przypisz przyczynę
            attribution = self.attributor.attribute_cause(shock, recent_news)

            if attribution:
                # Zapisz do bazy
                self.db.insert_attribution(
                    event_id=attribution.event_id,
                    ticker=attribution.ticker,
                    shock_type=attribution.shock_type,
                    shock_detected_at=attribution.shock_detected_at,
                    shock_price=shock.price,
                    shock_z_score=shock.z_score,
                    shock_volume_percentile=shock.volume_percentile,
                    shock_severity=shock.severity,
                    cause_type=attribution.cause_type,
                    cause_text=attribution.cause_text,
                    cause_source=attribution.cause_source,
                    confidence=attribution.confidence,
                    impact_strength=attribution.impact_strength,
                    time_delta_minutes=attribution.time_delta_minutes,
                    attributed_at=attribution.attributed_at
                )

                print(f"[{self.agent_name}] ✅ ATTRIBUTED: {attribution.cause_type} | "
                      f"confidence={attribution.confidence:.2f} | "
                      f"cause='{attribution.cause_text[:60]}...'")

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
                            await self.process_shock_event(message_id, message_data)
                            processed_count += 1

                    print(f"[{self.agent_name}] Total processed: {processed_count}")

                # Print database stats periodically
                if processed_count > 0 and processed_count % 10 == 0:
                    stats = self.db.get_statistics()
                    print(f"[{self.agent_name}] DB Stats: {stats['total_records']} records, "
                          f"avg confidence={stats['avg_confidence']:.2f}")

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
    agent = CauseFinderAgent()
    await agent.run()


if __name__ == "__main__":
    asyncio.run(main())
