"""
Ingest News Agent - Main Event Loop
Pobiera wiadomości finansowe, normalizuje je i publikuje do Redis Streams.
"""

import asyncio
import os
import random
from datetime import datetime, timedelta
from typing import List, Dict, Any
import redis.asyncio as redis
import json

# Import schemas z packages/common
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
from packages.common.schemas import IngestedNewsMessage, StreamNames
from packages.common.redis_utils import publish_message


class NewsSource:
    """Placeholder dla źródła newsów - można podłączyć API NewsAPI, RSS itp."""

    def __init__(self):
        self.tickers = ["AAPL", "MSFT", "GOOGL", "AMZN", "TSLA", "META", "NVDA"]

    async def fetch_raw_news(self) -> List[Dict[str, Any]]:
        """
        Pobiera surowe newsy z zewnętrznych źródeł.

        PLACEHOLDER: W produkcji użyć prawdziwego API:
        - NewsAPI (newsapi.org)
        - Alpha Vantage News & Sentiments
        - Financial RSS feeds
        - Twitter/X API dla trendów
        """
        # Symulacja newsów
        news_items = []

        for _ in range(random.randint(1, 3)):
            ticker = random.choice(self.tickers)

            # Symulowane nagłówki
            headlines = [
                f"{ticker} announces quarterly earnings beat expectations",
                f"{ticker} stock surges on positive analyst upgrade",
                f"{ticker} faces regulatory challenges in Europe",
                f"{ticker} unveils new product lineup",
                f"CEO of {ticker} discusses future growth strategy",
                f"{ticker} reports decline in quarterly revenue",
            ]

            headline = random.choice(headlines)

            # Symulowana treść
            body = f"Lorem ipsum dolor sit amet, consectetur adipiscing elit. {headline}. " \
                   f"Sed do eiusmod tempor incididunt ut labore et dolore magna aliqua. " \
                   f"Market analysts are closely watching {ticker} performance."

            # Symulowana data (losowy czas w ostatnich 24h)
            time_offset = random.randint(0, 24 * 60)  # minuty
            published_at = datetime.now() - timedelta(minutes=time_offset)

            news_items.append({
                "ticker": ticker,
                "headline": headline,
                "body": body,
                "published_at": published_at.isoformat(),
                "source": "NewsAPI_Placeholder",
                "url": f"https://example.com/news/{ticker.lower()}/{random.randint(1000, 9999)}"
            })

        return news_items

    async def analyze_sentiment(self, headline: str, body: str) -> Dict[str, float]:
        """
        Analiza sentymentu, impact i relevance.

        PLACEHOLDER: W produkcji użyć:
        - OpenAI GPT-4 / Claude dla analizy sentymentu
        - FinBERT (model NLP dla finansów)
        - Własny model wytrenowany na danych finansowych
        """
        # Prosta heurystyka (placeholder)
        text = (headline + " " + body).lower()

        # Sentyment
        positive_words = ["beat", "surge", "positive", "growth", "unveils", "announces"]
        negative_words = ["decline", "challenges", "faces", "drop", "loss", "miss"]

        pos_count = sum(1 for word in positive_words if word in text)
        neg_count = sum(1 for word in negative_words if word in text)

        if pos_count > neg_count:
            sentiment = random.uniform(0.3, 0.9)
        elif neg_count > pos_count:
            sentiment = random.uniform(-0.9, -0.3)
        else:
            sentiment = random.uniform(-0.2, 0.2)

        # Impact - losowy z wagą
        impact = random.uniform(0.3, 0.8)

        # Relevance - w tym przypadku zawsze wysoka (news jest już dla konkretnego tickera)
        relevance = random.uniform(0.7, 1.0)

        return {
            "sentiment": round(sentiment, 3),
            "impact": round(impact, 3),
            "relevance": round(relevance, 3)
        }


class IngestNewsAgent:
    def __init__(self):
        self.redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
        self.redis_client = None
        self.stream_name = StreamNames.NEWS_INGESTED
        self.agent_name = "ingest_news"
        self.news_source = NewsSource()
        self.fetch_interval = int(os.getenv("INGEST_INTERVAL", "60"))  # sekundy

    async def connect(self):
        """Połącz z Redis"""
        self.redis_client = await redis.from_url(
            self.redis_url,
            decode_responses=True,
            encoding="utf-8"
        )
        print(f"[{self.agent_name}] ✓ Connected to Redis at {self.redis_url}")
        print(f"[{self.agent_name}] Publishing to stream: {self.stream_name}")

    async def disconnect(self):
        """Rozłącz z Redis"""
        if self.redis_client:
            await self.redis_client.close()
            print(f"[{self.agent_name}] Disconnected from Redis")

    async def normalize_and_publish(self, raw_news: Dict[str, Any]):
        """
        Normalizuje surowy news do formatu IngestedNewsMessage i publikuje.
        """
        try:
            # Analizuj sentyment
            analysis = await self.news_source.analyze_sentiment(
                raw_news["headline"],
                raw_news["body"]
            )

            # Utwórz znormalizowany obiekt
            news_message = IngestedNewsMessage(
                ticker=raw_news["ticker"],
                datetime=raw_news["published_at"],
                headline=raw_news["headline"],
                body=raw_news["body"],
                sentiment=analysis["sentiment"],
                impact=analysis["impact"],
                relevance=analysis["relevance"],
                source=raw_news.get("source"),
                url=raw_news.get("url"),
                metadata={
                    "ingested_at": datetime.now().isoformat(),
                    "agent_version": "1.0"
                }
            )

            # Publikuj do Redis Stream
            message_id = await publish_message(
                redis_client=self.redis_client,
                stream_name=self.stream_name,
                agent_name=self.agent_name,
                data=news_message.model_dump(),
                message_type="IngestedNewsMessage"
            )

            print(f"[{self.agent_name}] ✓ Published news for {news_message.ticker}: "
                  f"{news_message.headline[:50]}... "
                  f"(sentiment={news_message.sentiment:.2f}, "
                  f"impact={news_message.impact:.2f}) -> {message_id}")

        except Exception as e:
            print(f"[{self.agent_name}] ✗ Error processing news: {e}")

    async def run(self):
        """Główna pętla agenta"""
        await self.connect()

        try:
            print(f"[{self.agent_name}] Starting event loop (fetch every {self.fetch_interval}s)...")
            print(f"[{self.agent_name}] Press Ctrl+C to stop\n")

            iteration = 0
            while True:
                iteration += 1
                print(f"[{self.agent_name}] --- Iteration {iteration} ---")

                # Pobierz surowe newsy
                raw_news_list = await self.news_source.fetch_raw_news()
                print(f"[{self.agent_name}] Fetched {len(raw_news_list)} news items")

                # Normalizuj i publikuj każdy news
                for raw_news in raw_news_list:
                    await self.normalize_and_publish(raw_news)

                print(f"[{self.agent_name}] Waiting {self.fetch_interval}s...\n")
                await asyncio.sleep(self.fetch_interval)

        except KeyboardInterrupt:
            print(f"\n[{self.agent_name}] Shutting down gracefully...")
        except Exception as e:
            print(f"[{self.agent_name}] Fatal error: {e}")
        finally:
            await self.disconnect()


async def main():
    """Entry point"""
    agent = IngestNewsAgent()
    await agent.run()


if __name__ == "__main__":
    asyncio.run(main())
