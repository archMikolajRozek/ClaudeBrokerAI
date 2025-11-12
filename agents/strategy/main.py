"""
Strategy Agent - Complete Implementation
Konsumuje news_scored i market_momentum, generuje trade proposals.
"""

import asyncio
import os
import sys
from datetime import datetime, timezone
from typing import Dict, Any, Optional, Tuple
from collections import defaultdict
import json

import redis.asyncio as redis
from dotenv import load_dotenv

# Add packages to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../packages'))
from common.schemas import (
    NewsScoredMessage,
    MarketMomentumMessage,
    MarketCandleMessage,  # DODANE - fix NameError
    TradeProposal,
    StreamNames
)
from common.redis_utils import publish_message, create_consumer_group, deserialize_message


load_dotenv()


class SignalGenerator:
    """Generator sygnałów handlowych z kombinacją news i momentum"""

    def __init__(
        self,
        alpha: float = 0.6,
        threshold: float = 0.3,
        risk_reward_ratio: float = 2.0
    ):
        """
        Args:
            alpha: Waga news score (0-1), (1-alpha) to waga momentum
            threshold: Minimalny combined_score do generowania sygnału
            risk_reward_ratio: Stosunek TP/SL
        """
        self.alpha = alpha
        self.threshold = threshold
        self.risk_reward_ratio = risk_reward_ratio

    def calculate_combined_score(
        self,
        news_score: Optional[float],
        momentum_score: Optional[float]
    ) -> Tuple[float, str]:
        """
        Oblicz combined score: S = α * score_news + (1-α) * score_mom

        Returns:
            (combined_score, rationale)
        """
        if news_score is None and momentum_score is None:
            return 0.0, "No data available"

        # Jeśli brakuje jednego ze score, użyj tylko dostępnego
        if news_score is None:
            return momentum_score, f"Momentum only: {momentum_score:.3f}"

        if momentum_score is None:
            return news_score, f"News only: {news_score:.3f}"

        # Kombinacja obu
        combined = self.alpha * news_score + (1 - self.alpha) * momentum_score

        rationale = (
            f"Combined α={self.alpha:.2f}: "
            f"news={news_score:.3f} × {self.alpha:.2f} + "
            f"momentum={momentum_score:.3f} × {1-self.alpha:.2f} "
            f"= {combined:.3f}"
        )

        return combined, rationale

    def generate_trade_proposal(
        self,
        ticker: str,
        combined_score: float,
        rationale: str,
        current_price: float,
        news_score: Optional[float] = None,
        momentum_score: Optional[float] = None
    ) -> Optional[TradeProposal]:
        """
        Generuj trade proposal jeśli score > threshold

        Returns:
            TradeProposal lub None
        """
        # Sprawdź threshold
        abs_score = abs(combined_score)
        if abs_score < self.threshold:
            return None

        # Określ side na podstawie znaku score
        side = "BUY" if combined_score > 0 else "SELL"

        # Oblicz stop loss i take profit
        # Używamy prostej metody: % od ceny
        stop_distance_pct = 0.02  # 2% stop loss
        tp_distance_pct = stop_distance_pct * self.risk_reward_ratio  # 4% TP dla R:R = 2:1

        if side == "BUY":
            stop = current_price * (1 - stop_distance_pct)
            take_profit = current_price * (1 + tp_distance_pct)
        else:  # SELL
            stop = current_price * (1 + stop_distance_pct)
            take_profit = current_price * (1 - tp_distance_pct)

        return TradeProposal(
            ticker=ticker,
            side=side,
            entry=current_price,
            stop=stop,
            take_profit=take_profit,
            rationale=rationale,
            alpha=self.alpha,
            combined_score=combined_score,
            news_score=news_score,
            momentum_score=momentum_score,
            timestamp=datetime.now(timezone.utc).isoformat()
        )


class StrategyAgent:
    """Agent strategii - generuje trade proposals"""

    def __init__(self):
        self.redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
        self.redis_client = None
        self.input_streams = [
            StreamNames.NEWS_SCORED,
            StreamNames.MARKET_MOMENTUM,
            StreamNames.MARKET_CANDLES  # Dodano: pobieranie cen bezpośrednio
        ]
        self.output_stream = StreamNames.TRADE_PROPOSALS
        self.consumer_group = "strategy_group"
        self.consumer_name = "strategy_consumer_1"
        self.agent_name = "strategy"

        # Signal generator z konfiguracją
        alpha = float(os.getenv("STRATEGY_ALPHA", "0.6"))
        threshold = float(os.getenv("STRATEGY_THRESHOLD", "0.3"))
        risk_reward = float(os.getenv("STRATEGY_RISK_REWARD", "2.0"))

        self.signal_generator = SignalGenerator(
            alpha=alpha,
            threshold=threshold,
            risk_reward_ratio=risk_reward
        )

        # Cache dla latest scores per ticker
        self.latest_news_scores: Dict[str, NewsScoredMessage] = {}
        self.latest_momentum_scores: Dict[str, MarketMomentumMessage] = {}
        self.latest_prices: Dict[str, float] = {}

        print(f"[{self.agent_name}] Initialized with:")
        print(f"  α={alpha}, threshold={threshold}, R:R={risk_reward}")

    async def connect(self):
        """Połącz z Redis"""
        self.redis_client = await redis.from_url(
            self.redis_url,
            decode_responses=True
        )

        # Utwórz consumer groups
        for stream in self.input_streams:
            await create_consumer_group(
                self.redis_client,
                stream,
                self.consumer_group,
                start_id="0"
            )

        print(f"[{self.agent_name}] ✓ Connected to Redis")
        print(f"[{self.agent_name}] Listening on: {', '.join(self.input_streams)}")

    async def disconnect(self):
        """Rozłącz z Redis"""
        if self.redis_client:
            await self.redis_client.close()
            print(f"[{self.agent_name}] Disconnected from Redis")

    async def process_news_scored(self, message_id: str, message_data: Dict[str, str]):
        """Przetwórz news scored message"""
        try:
            stream_msg = deserialize_message(message_data)
            news = NewsScoredMessage(**stream_msg.data)

            # Update cache
            self.latest_news_scores[news.ticker] = news

            # Spróbuj wygenerować sygnał
            await self.try_generate_signal(news.ticker)

            # ACK
            await self.redis_client.xack(
                StreamNames.NEWS_SCORED,
                self.consumer_group,
                message_id
            )

        except Exception as e:
            print(f"[{self.agent_name}] ❌ Error processing news_scored {message_id}: {e}")
            import traceback
            traceback.print_exc()

    async def process_momentum_scored(self, message_id: str, message_data: Dict[str, str]):
        """Przetwórz momentum scored message"""
        try:
            stream_msg = deserialize_message(message_data)
            momentum = MarketMomentumMessage(**stream_msg.data)

            # Update cache
            self.latest_momentum_scores[momentum.ticker] = momentum
            if momentum.price:
                self.latest_prices[momentum.ticker] = momentum.price

            # Spróbuj wygenerować sygnał
            await self.try_generate_signal(momentum.ticker)

            # ACK
            await self.redis_client.xack(
                StreamNames.MARKET_MOMENTUM,
                self.consumer_group,
                message_id
            )

        except Exception as e:
            print(f"[{self.agent_name}] ❌ Error processing momentum {message_id}: {e}")
            import traceback
            traceback.print_exc()

    async def process_market_candle(self, message_id: str, message_data: Dict[str, str]):
        """Przetwórz market candle message - aktualizuj latest_prices"""
        try:
            stream_msg = deserialize_message(message_data)
            candle = MarketCandleMessage(**stream_msg.data)

            # Update cache cen - używamy close price
            self.latest_prices[candle.ticker] = candle.close

            # ACK (nie generujemy sygnału, tylko aktualizujemy cenę)
            await self.redis_client.xack(
                StreamNames.MARKET_CANDLES,
                self.consumer_group,
                message_id
            )

        except Exception as e:
            print(f"[{self.agent_name}] ❌ Error processing candle {message_id}: {e}")
            import traceback
            traceback.print_exc()

    async def try_generate_signal(self, ticker: str):
        """Spróbuj wygenerować sygnał dla tickera"""

        # Pobierz latest scores
        news_msg = self.latest_news_scores.get(ticker)
        momentum_msg = self.latest_momentum_scores.get(ticker)

        news_score = news_msg.score if news_msg else None
        momentum_score = momentum_msg.momentum_score if momentum_msg else None

        # Potrzebujemy przynajmniej jednego score
        if news_score is None and momentum_score is None:
            return

        # Oblicz combined score
        combined_score, rationale = self.signal_generator.calculate_combined_score(
            news_score,
            momentum_score
        )

        # Potrzebujemy ceny (z momentum lub z cache)
        current_price = None
        if momentum_msg and momentum_msg.price:
            current_price = momentum_msg.price
        elif ticker in self.latest_prices:
            current_price = self.latest_prices[ticker]
        else:
            # Brak ceny - używamy placeholder
            current_price = 100.0  # Placeholder
            print(f"[{self.agent_name}] ⚠️  No price for {ticker}, using placeholder")

        # Generuj proposal
        proposal = self.signal_generator.generate_trade_proposal(
            ticker=ticker,
            combined_score=combined_score,
            rationale=rationale,
            current_price=current_price,
            news_score=news_score,
            momentum_score=momentum_score
        )

        if proposal:
            # Publikuj do Redis
            await publish_message(
                self.redis_client,
                self.output_stream,
                self.agent_name,
                proposal.model_dump(),  # Pydantic 2.x
                message_type="TradeProposal"
            )

            print(f"[{self.agent_name}] ✓ Generated: {proposal.side} {proposal.ticker} "
                  f"@ ${proposal.entry:.2f} | score={proposal.combined_score:.3f} "
                  f"| SL=${proposal.stop:.2f} TP=${proposal.take_profit:.2f}")

    async def run(self):
        """Główna pętla agenta - event listener"""
        await self.connect()

        try:
            print(f"[{self.agent_name}] 🚀 Starting event loop...")

            processed_count = 0

            while True:
                # Czytaj z obu streamów
                streams = {stream: ">" for stream in self.input_streams}
                messages = await self.redis_client.xreadgroup(
                    self.consumer_group,
                    self.consumer_name,
                    streams,
                    count=10,
                    block=5000
                )

                if messages:
                    for stream_name, stream_messages in messages:
                        for message_id, message_data in stream_messages:
                            if stream_name == StreamNames.NEWS_SCORED:
                                await self.process_news_scored(message_id, message_data)
                            elif stream_name == StreamNames.MARKET_MOMENTUM:
                                await self.process_momentum_scored(message_id, message_data)
                            elif stream_name == StreamNames.MARKET_CANDLES:
                                await self.process_market_candle(message_id, message_data)

                            processed_count += 1

                    if processed_count % 10 == 0:
                        print(f"[{self.agent_name}] Processed {processed_count} messages")

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
    agent = StrategyAgent()
    await agent.run()


if __name__ == "__main__":
    asyncio.run(main())
