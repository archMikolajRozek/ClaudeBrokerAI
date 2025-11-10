"""
Score News Agent - Main Event Loop
Konsumuje wiadomości z Redis Streams, oblicza score z decay factor i publikuje wyniki.
"""

import asyncio
import os
import json
import math
from datetime import datetime
from typing import Dict, Any, Optional
import redis.asyncio as redis

# Import schemas z packages/common
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
from packages.common.schemas import IngestedNewsMessage, ScoredNewsMessage, StreamNames
from packages.common.redis_utils import publish_message, create_consumer_group, deserialize_message


class ScoreNewsAgent:
    def __init__(self):
        self.redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
        self.redis_client = None
        self.input_stream = StreamNames.NEWS_INGESTED
        self.output_stream = StreamNames.NEWS_SCORED
        self.consumer_group = "score_news_group"
        self.consumer_name = os.getenv("CONSUMER_NAME", "score_news_consumer_1")
        self.agent_name = "score_news"

        # Parametr tau (czas półtrwania w godzinach)
        # Określa jak szybko maleje wpływ newsa w czasie
        # tau = 24h oznacza, że po 24h news ma ~37% początkowego wpływu
        self.tau_hours = float(os.getenv("NEWS_DECAY_TAU_HOURS", "24"))
        print(f"[{self.agent_name}] Decay tau: {self.tau_hours} hours")

    async def connect(self):
        """Połącz z Redis i utwórz consumer group"""
        self.redis_client = await redis.from_url(
            self.redis_url,
            decode_responses=True,
            encoding="utf-8"
        )
        print(f"[{self.agent_name}] ✓ Connected to Redis at {self.redis_url}")

        # Utwórz consumer group jeśli nie istnieje
        created = await create_consumer_group(
            self.redis_client,
            self.input_stream,
            self.consumer_group,
            start_id="$"  # Czytaj tylko nowe wiadomości
        )

        if created:
            print(f"[{self.agent_name}] ✓ Created consumer group: {self.consumer_group}")
        else:
            print(f"[{self.agent_name}] ✓ Using existing consumer group: {self.consumer_group}")

        print(f"[{self.agent_name}] Listening on: {self.input_stream}")
        print(f"[{self.agent_name}] Publishing to: {self.output_stream}")

    async def disconnect(self):
        """Rozłącz z Redis"""
        if self.redis_client:
            await self.redis_client.close()
            print(f"[{self.agent_name}] Disconnected from Redis")

    def calculate_decay_factor(self, news_datetime_str: str, current_datetime: datetime) -> float:
        """
        Oblicza współczynnik czasowego rozpadu (decay factor).

        Wzór: decay_factor = exp(-Δt / tau)

        Gdzie:
        - Δt = różnica czasu między teraz a datą publikacji newsa (w godzinach)
        - tau = parametr półtrwania (czas w którym wpływ spada do ~37%)

        Args:
            news_datetime_str: Data publikacji newsa (ISO format)
            current_datetime: Obecny czas

        Returns:
            decay_factor w przedziale [0, 1]
        """
        try:
            # Parse news datetime
            news_datetime = datetime.fromisoformat(news_datetime_str.replace('Z', '+00:00'))

            # Oblicz różnicę czasu w godzinach
            delta_time = (current_datetime - news_datetime).total_seconds() / 3600.0  # godziny

            # Oblicz decay factor: exp(-Δt / tau)
            decay_factor = math.exp(-delta_time / self.tau_hours)

            # Ogranicz do [0, 1]
            decay_factor = max(0.0, min(1.0, decay_factor))

            return decay_factor

        except Exception as e:
            print(f"[{self.agent_name}] ✗ Error calculating decay: {e}")
            return 1.0  # W razie błędu zwróć 1.0 (brak decay)

    def calculate_score(self, ingested_news: IngestedNewsMessage) -> ScoredNewsMessage:
        """
        Oblicza score dla newsa.

        Wzór: adjusted_impact = sentiment * impact * decay_factor

        Args:
            ingested_news: Znormalizowany news z agenta ingest_news

        Returns:
            ScoredNewsMessage z obliczonym score
        """
        current_time = datetime.now()

        # Oblicz decay factor
        decay_factor = self.calculate_decay_factor(
            ingested_news.datetime,
            current_time
        )

        # Oblicz adjusted impact (score)
        # sentiment ∈ [-1, 1], impact ∈ [0, 1], decay ∈ [0, 1]
        # score ∈ [-1, 1]
        score = ingested_news.sentiment * ingested_news.impact * decay_factor

        # Utwórz scored message
        scored_news = ScoredNewsMessage(
            ticker=ingested_news.ticker,
            score=round(score, 4),
            timestamp=current_time.isoformat(),
            decay_factor=round(decay_factor, 4),
            relevance=ingested_news.relevance,
            original_sentiment=ingested_news.sentiment,
            original_impact=ingested_news.impact,
            news_datetime=ingested_news.datetime,
            headline=ingested_news.headline,
            metadata={
                "tau_hours": self.tau_hours,
                "original_source": ingested_news.source,
                "original_url": ingested_news.url,
                "agent_version": "1.0"
            }
        )

        return scored_news

    async def process_message(self, message_id: str, message_data: Dict[str, str]):
        """
        Przetwórz pojedynczą wiadomość z Redis Stream.

        Args:
            message_id: ID wiadomości w Redis Stream
            message_data: Surowe dane wiadomości
        """
        try:
            # Deserializuj wiadomość
            stream_message = deserialize_message(message_data)

            # Parse do IngestedNewsMessage
            ingested_news = IngestedNewsMessage(**stream_message.data)

            # Oblicz score
            scored_news = self.calculate_score(ingested_news)

            # Publikuj do output stream
            message_id_out = await publish_message(
                redis_client=self.redis_client,
                stream_name=self.output_stream,
                agent_name=self.agent_name,
                data=scored_news.model_dump(),
                message_type="ScoredNewsMessage"
            )

            # Acknowledge message (potwierdzenie przetworzenia)
            await self.redis_client.xack(
                self.input_stream,
                self.consumer_group,
                message_id
            )

            # Log
            age_hours = (datetime.now() - datetime.fromisoformat(
                ingested_news.datetime.replace('Z', '+00:00')
            )).total_seconds() / 3600.0

            print(f"[{self.agent_name}] ✓ Scored {ingested_news.ticker}: "
                  f"score={scored_news.score:+.3f} "
                  f"(sentiment={scored_news.original_sentiment:+.2f} × "
                  f"impact={scored_news.original_impact:.2f} × "
                  f"decay={scored_news.decay_factor:.3f}) "
                  f"| age={age_hours:.1f}h -> {message_id_out}")

        except Exception as e:
            print(f"[{self.agent_name}] ✗ Error processing {message_id}: {e}")
            import traceback
            traceback.print_exc()

    async def run(self):
        """Główna pętla agenta - event listener"""
        await self.connect()

        try:
            print(f"[{self.agent_name}] Starting event loop...")
            print(f"[{self.agent_name}] Consumer: {self.consumer_name}")
            print(f"[{self.agent_name}] Press Ctrl+C to stop\n")

            messages_processed = 0

            while True:
                # Czytaj z strumienia (blocking z timeout)
                # XREADGROUP: czyta tylko nowe wiadomości dla tej grupy konsumentów
                messages = await self.redis_client.xreadgroup(
                    self.consumer_group,
                    self.consumer_name,
                    {self.input_stream: ">"},  # ">" = tylko nowe
                    count=10,  # Maksymalnie 10 wiadomości na raz
                    block=5000  # Timeout 5 sekund
                )

                if messages:
                    for stream_name, stream_messages in messages:
                        for message_id, message_data in stream_messages:
                            await self.process_message(message_id, message_data)
                            messages_processed += 1

                    # Pokaż status co kilka wiadomości
                    if messages_processed % 10 == 0:
                        print(f"[{self.agent_name}] --- Processed {messages_processed} messages ---\n")

                # Krótkie oczekiwanie
                await asyncio.sleep(0.1)

        except KeyboardInterrupt:
            print(f"\n[{self.agent_name}] Shutting down gracefully...")
        except Exception as e:
            print(f"[{self.agent_name}] Fatal error: {e}")
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
