"""
Ingest News Agent - Complete Implementation
Pobiera wiadomości finansowe z zewnętrznych API i publikuje do Redis Streams.
"""

import asyncio
import os
import sys
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
import json
import re

import redis.asyncio as redis
from dotenv import load_dotenv
import aiohttp

# Add packages to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../packages'))
from common.schemas import NewsIngestedMessage, StreamNames
from common.redis_utils import publish_message, create_consumer_group


load_dotenv()


class NewsAPIClient:
    """Client dla NewsAPI.org"""

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://newsapi.org/v2"

    async def fetch_financial_news(
        self,
        tickers: List[str],
        days_back: int = 1
    ) -> List[Dict[str, Any]]:
        """Pobierz newsy finansowe dla danych tickerów"""

        if not self.api_key or self.api_key == "your-newsapi-key":
            # Placeholder mode - zwróć przykładowe dane
            print("[ingest_news] ⚠️  No NewsAPI key, using placeholder data")
            return self._generate_placeholder_news(tickers)

        from_date = (datetime.now() - timedelta(days=days_back)).strftime('%Y-%m-%d')

        all_articles = []

        async with aiohttp.ClientSession() as session:
            for ticker in tickers:
                try:
                    # Szukaj po nazwie firmy lub tickerze
                    query = f"{ticker} stock OR {self._ticker_to_company(ticker)}"

                    params = {
                        'q': query,
                        'from': from_date,
                        'sortBy': 'publishedAt',
                        'language': 'en',
                        'apiKey': self.api_key,
                        'pageSize': 10
                    }

                    url = f"{self.base_url}/everything"

                    async with session.get(url, params=params) as response:
                        if response.status == 200:
                            data = await response.json()
                            articles = data.get('articles', [])

                            for article in articles:
                                article['detected_ticker'] = ticker
                                all_articles.append(article)

                            print(f"[ingest_news] Fetched {len(articles)} articles for {ticker}")
                        else:
                            error_text = await response.text()
                            print(f"[ingest_news] Error fetching {ticker}: {response.status} - {error_text}")

                    # Rate limiting
                    await asyncio.sleep(0.5)

                except Exception as e:
                    print(f"[ingest_news] Exception fetching news for {ticker}: {e}")

        return all_articles

    def _ticker_to_company(self, ticker: str) -> str:
        """Mapowanie tickera na nazwę firmy (prosty przykład)"""
        mapping = {
            'AAPL': 'Apple',
            'MSFT': 'Microsoft',
            'GOOGL': 'Google',
            'AMZN': 'Amazon',
            'TSLA': 'Tesla',
            'META': 'Meta Facebook',
            'NVDA': 'Nvidia',
            'JPM': 'JPMorgan',
            'V': 'Visa',
            'WMT': 'Walmart'
        }
        return mapping.get(ticker, ticker)

    def _generate_placeholder_news(self, tickers: List[str]) -> List[Dict[str, Any]]:
        """Generuj placeholder newsy dla testów"""
        templates = [
            "{company} announces strong quarterly earnings, beating analyst expectations",
            "{company} stock rises on positive market sentiment and strong demand",
            "Analysts upgrade {company} rating citing robust growth prospects",
            "{company} faces regulatory scrutiny over market practices",
            "{company} unveils new product line, investors react positively",
            "Market volatility impacts {company} stock performance",
            "{company} CEO discusses future strategy in investor call",
            "Industry experts predict growth for {company} in coming quarters"
        ]

        articles = []
        for ticker in tickers[:3]:  # Limit to 3 tickers for placeholder
            company = self._ticker_to_company(ticker)

            for i, template in enumerate(templates[:2]):  # 2 articles per ticker
                headline = template.format(company=company)

                articles.append({
                    'title': headline,
                    'description': f"Detailed analysis of {company} ({ticker}) market performance and outlook.",
                    'content': f"{headline}. This is placeholder content for testing purposes. "
                               f"The article discusses recent developments at {company} and their "
                               f"potential impact on stock price and market position.",
                    'url': f"https://example.com/news/{ticker.lower()}-{i}",
                    'publishedAt': (datetime.now() - timedelta(hours=i * 2)).isoformat(),
                    'source': {'name': 'PlaceholderNews'},
                    'detected_ticker': ticker
                })

        return articles


class NewsNormalizer:
    """Normalizacja i wstępna analiza newsów"""

    @staticmethod
    def normalize_article(article: Dict[str, Any], ticker: str) -> Optional[NewsIngestedMessage]:
        """Normalizuj artykuł do formatu NewsIngestedMessage"""

        try:
            headline = article.get('title', '')
            body = article.get('content') or article.get('description', '')

            if not headline or not body:
                return None

            # Parsuj datetime
            published_at = article.get('publishedAt', datetime.now().isoformat())
            if not published_at.endswith('Z') and '+' not in published_at:
                published_at = published_at + 'Z'

            # Wstępna analiza sentymentu (prosty algorytm słów kluczowych)
            sentiment = NewsNormalizer._analyze_sentiment(headline + " " + body)

            # Analiza wpływu (impact) na podstawie słów kluczowych
            impact = NewsNormalizer._analyze_impact(headline + " " + body)

            # Relevancja - jak bardzo news jest powiązany z tickerem
            relevance = NewsNormalizer._analyze_relevance(
                headline + " " + body,
                ticker
            )

            return NewsIngestedMessage(
                ticker=ticker,
                datetime=published_at,
                headline=headline[:500],  # Limit długości
                body=body[:2000],  # Limit długości
                sentiment=sentiment,
                impact=impact,
                relevance=relevance,
                source=article.get('source', {}).get('name', 'Unknown'),
                url=article.get('url')
            )

        except Exception as e:
            print(f"[ingest_news] Error normalizing article: {e}")
            return None

    @staticmethod
    def _analyze_sentiment(text: str) -> float:
        """
        Prosta analiza sentymentu na podstawie słów kluczowych.
        Zwraca wartość od -1 (negatywny) do 1 (pozytywny).

        TODO: Zamienić na ML model lub LLM API
        """
        text_lower = text.lower()

        positive_words = [
            'growth', 'profit', 'gain', 'rise', 'increase', 'positive',
            'strong', 'beat', 'exceed', 'success', 'upgrade', 'bullish',
            'optimistic', 'opportunity', 'improvement', 'record', 'high'
        ]

        negative_words = [
            'loss', 'decline', 'fall', 'drop', 'negative', 'weak',
            'miss', 'concern', 'risk', 'downgrade', 'bearish',
            'pessimistic', 'threat', 'warning', 'low', 'volatile'
        ]

        positive_count = sum(1 for word in positive_words if word in text_lower)
        negative_count = sum(1 for word in negative_words if word in text_lower)

        total = positive_count + negative_count
        if total == 0:
            return 0.0

        sentiment = (positive_count - negative_count) / total
        return max(-1.0, min(1.0, sentiment))

    @staticmethod
    def _analyze_impact(text: str) -> float:
        """
        Analiza potencjalnego wpływu newsa na cenę.
        Zwraca wartość od 0 (niski wpływ) do 1 (wysoki wpływ).
        """
        text_lower = text.lower()

        high_impact_keywords = [
            'earnings', 'revenue', 'acquisition', 'merger', 'bankruptcy',
            'lawsuit', 'ceo', 'scandal', 'investigation', 'fda', 'regulatory',
            'dividend', 'split', 'buyback', 'guidance', 'forecast'
        ]

        medium_impact_keywords = [
            'product', 'launch', 'partnership', 'contract', 'deal',
            'upgrade', 'downgrade', 'analyst', 'target', 'price'
        ]

        high_count = sum(1 for word in high_impact_keywords if word in text_lower)
        medium_count = sum(1 for word in medium_impact_keywords if word in text_lower)

        # Scoring
        impact_score = (high_count * 0.3) + (medium_count * 0.15)

        return max(0.0, min(1.0, impact_score))

    @staticmethod
    def _analyze_relevance(text: str, ticker: str) -> float:
        """
        Analiza relevancji newsa dla danego tickera.
        Zwraca wartość od 0 (niska relevancja) do 1 (wysoka relevancja).
        """
        text_lower = text.lower()
        ticker_lower = ticker.lower()

        # Ile razy ticker występuje w tekście
        ticker_count = text_lower.count(ticker_lower)

        # Bonus za ticker w nagłówku
        if ticker_lower in text_lower[:100]:
            relevance = 0.8 + (ticker_count * 0.05)
        else:
            relevance = 0.5 + (ticker_count * 0.1)

        return max(0.0, min(1.0, relevance))


class IngestNewsAgent:
    """Agent pobierający newsy i publikujący do Redis"""

    def __init__(self):
        self.redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
        self.redis_client = None
        self.agent_name = "ingest_news"

        # NewsAPI client
        self.news_api_key = os.getenv("NEWS_API_KEY", "your-newsapi-key")
        self.news_client = NewsAPIClient(self.news_api_key)

        # Watchlist tickerów
        watchlist_str = os.getenv("WATCHLIST", "AAPL,MSFT,GOOGL,AMZN,TSLA,META,NVDA")
        self.watchlist = [t.strip() for t in watchlist_str.split(',')]

        # Konfiguracja
        self.fetch_interval = int(os.getenv("NEWS_FETCH_INTERVAL", "300"))  # 5 minut
        self.days_back = int(os.getenv("NEWS_DAYS_BACK", "1"))

        print(f"[{self.agent_name}] Initialized with watchlist: {self.watchlist}")
        print(f"[{self.agent_name}] Fetch interval: {self.fetch_interval}s")

    async def connect(self):
        """Połącz z Redis"""
        self.redis_client = await redis.from_url(
            self.redis_url,
            decode_responses=True
        )
        print(f"[{self.agent_name}] ✓ Connected to Redis")

    async def disconnect(self):
        """Rozłącz z Redis"""
        if self.redis_client:
            await self.redis_client.close()
            print(f"[{self.agent_name}] Disconnected from Redis")

    async def fetch_and_publish_news(self):
        """Pobierz newsy i opublikuj do Redis Stream"""

        try:
            # Pobierz newsy z API
            articles = await self.news_client.fetch_financial_news(
                self.watchlist,
                self.days_back
            )

            print(f"[{self.agent_name}] Fetched {len(articles)} articles total")

            published_count = 0

            # Normalizuj i publikuj każdy artykuł
            for article in articles:
                ticker = article.get('detected_ticker')

                normalized = NewsNormalizer.normalize_article(article, ticker)

                if normalized:
                    # Publikuj do Redis Stream
                    message_id = await publish_message(
                        self.redis_client,
                        StreamNames.NEWS_INGESTED,
                        self.agent_name,
                        normalized.model_dump(),
                        message_type="NewsIngestedMessage"
                    )

                    published_count += 1

                    print(f"[{self.agent_name}] ✓ Published: {ticker} - {normalized.headline[:60]}... "
                          f"(sentiment={normalized.sentiment:.2f}, impact={normalized.impact:.2f})")

            print(f"[{self.agent_name}] Published {published_count}/{len(articles)} articles to stream")

            return published_count

        except Exception as e:
            print(f"[{self.agent_name}] ❌ Error in fetch_and_publish: {e}")
            import traceback
            traceback.print_exc()
            return 0

    async def run(self):
        """Główna pętla agenta"""
        await self.connect()

        try:
            print(f"[{self.agent_name}] 🚀 Starting event loop...")

            iteration = 0

            while True:
                iteration += 1
                print(f"\n[{self.agent_name}] === Iteration {iteration} ===")

                # Pobierz i publikuj newsy
                count = await self.fetch_and_publish_news()

                # Czekaj przed następnym cyklem
                print(f"[{self.agent_name}] Sleeping for {self.fetch_interval}s...")
                await asyncio.sleep(self.fetch_interval)

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
    agent = IngestNewsAgent()
    await agent.run()


if __name__ == "__main__":
    asyncio.run(main())
