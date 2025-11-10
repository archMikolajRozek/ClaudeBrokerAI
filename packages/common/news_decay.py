"""
News Decay Module
Moduł obliczający time-weighted scoring dla newsów.

TEORIA:
Newsy tracą na znaczeniu z czasem - świeży news (5 min temu) ma większy wpływ
niż news sprzed 2 godzin. Używamy exponential decay:

    decay_factor = exp(-Δt / τ)

gdzie:
- Δt = czas od publikacji newsa (sekundy)
- τ (tau) = time constant / półokres (sekundy)

PÓŁOKRES (half-life):
Po czasie τ, decay_factor = exp(-1) ≈ 0.368 (news ma 36.8% oryginalnej wartości)

PRZYKŁADY TAU:
- Intraday trading: τ = 1800s (30 min) - newsy liczą się tylko przez godzinę
- Swing trading: τ = 86400s (24h) - newsy liczą się przez kilka dni
- Position trading: τ = 604800s (7 dni) - newsy liczą się przez tygodnie

ADJUSTED SCORE:
    score = sentiment * significance * decay_factor

gdzie:
- sentiment ∈ [-1, 1]: Pozytywny (+1) lub negatywny (-1)
- significance ∈ [0, 1]: Jak ważny jest news (earnings > social media)
- decay_factor ∈ [0, 1]: Time decay

FINALNA WARTOŚĆ:
    score ∈ [-1, 1]: Wyższa wartość = silniejszy sygnał
"""

import math
from datetime import datetime, timezone
from typing import Optional
from dateutil import parser as date_parser


# ============================================================================
# DECAY FUNCTION
# ============================================================================

def calculate_decay_factor(
    news_datetime: str,
    current_datetime: datetime,
    tau_seconds: float = 3600.0
) -> float:
    """
    Oblicz exponential decay factor dla newsa

    Formuła: decay = exp(-Δt / τ)

    Args:
        news_datetime: ISO timestamp newsa (np. "2025-11-10T14:30:00Z")
        current_datetime: Obecny czas (datetime object z timezone)
        tau_seconds: Time constant / półokres (domyślnie 3600s = 1h)

    Returns:
        Decay factor w zakresie [0, 1]:
        - 1.0 = news bardzo świeży (Δt = 0)
        - 0.368 = news ma wiek τ (po półokresu)
        - 0.0 = news bardzo stary (praktycznie nieważny)

    Przykład:
        # News sprzed 30 minut, tau=1h
        decay = calculate_decay_factor(
            "2025-11-10T14:00:00Z",
            datetime.now(timezone.utc),  # 14:30
            tau_seconds=3600
        )
        # decay ≈ exp(-1800/3600) = exp(-0.5) ≈ 0.606
    """
    # Parse news datetime (może być z lub bez timezone)
    news_dt = date_parser.isoparse(news_datetime)

    # Dodaj UTC jeśli brak timezone
    if news_dt.tzinfo is None:
        news_dt = news_dt.replace(tzinfo=timezone.utc)

    # Upewnij się że current_datetime ma timezone
    if current_datetime.tzinfo is None:
        current_datetime = current_datetime.replace(tzinfo=timezone.utc)

    # Oblicz Δt (różnica w sekundach)
    delta_t = (current_datetime - news_dt).total_seconds()

    # Zabezpieczenie: jeśli news jest z przyszłości (clock skew), użyj 0
    if delta_t < 0:
        delta_t = 0

    # Oblicz decay: exp(-Δt / τ)
    decay_factor = math.exp(-delta_t / tau_seconds)

    # Clamp do [0, 1] (teoretycznie nie powinno przekraczać, ale dla pewności)
    return max(0.0, min(1.0, decay_factor))


# ============================================================================
# NEWS SCORE CALCULATION
# ============================================================================

def calculate_news_score(
    sentiment: float,
    significance: float,
    decay_factor: float,
    clamp: bool = True
) -> float:
    """
    Oblicz final news score z decay

    Formuła: score = sentiment * significance * decay_factor

    Args:
        sentiment: Sentyment newsa, zakres [-1, 1]
                  -1 = bardzo negatywny, 0 = neutralny, +1 = bardzo pozytywny
        significance: Znaczenie newsa, zakres [0, 1]
                     0 = nieważny, 1 = bardzo ważny (np. earnings)
        decay_factor: Time decay, zakres [0, 1]
        clamp: Czy clampować wynik do [-1, 1] (domyślnie True)

    Returns:
        News score w zakresie [-1, 1] (jeśli clamp=True)

    Przykład:
        # Pozytywny news (sent=0.8), ważny (sig=0.9), świeży (decay=0.9)
        score = calculate_news_score(0.8, 0.9, 0.9)
        # score = 0.8 * 0.9 * 0.9 = 0.648

        # Negatywny news (sent=-0.7), średni (sig=0.5), stary (decay=0.2)
        score = calculate_news_score(-0.7, 0.5, 0.2)
        # score = -0.7 * 0.5 * 0.2 = -0.07 (słaby sygnał przez decay)
    """
    score = sentiment * significance * decay_factor

    if clamp:
        # Clamp do [-1, 1]
        score = max(-1.0, min(1.0, score))

    return score


# ============================================================================
# TAU HELPERS
# ============================================================================

def tau_from_half_life_hours(hours: float) -> float:
    """
    Konwersja half-life (godziny) → tau (sekundy)

    Half-life = czas po którym wartość spada do 50%

    Args:
        hours: Półokres w godzinach

    Returns:
        Tau w sekundach

    Przykład:
        tau = tau_from_half_life_hours(0.5)  # 30 min half-life
        # tau = 1800 seconds
    """
    return hours * 3600.0


def tau_from_half_life_minutes(minutes: float) -> float:
    """
    Konwersja half-life (minuty) → tau (sekundy)

    Args:
        minutes: Półokres w minutach

    Returns:
        Tau w sekundach

    Przykład:
        tau = tau_from_half_life_minutes(30)  # 30 min half-life
        # tau = 1800 seconds
    """
    return minutes * 60.0


# ============================================================================
# SIGNIFICANCE SCORING (HEURISTIC)
# ============================================================================

def estimate_significance(
    source: Optional[str] = None,
    keywords: Optional[list] = None
) -> float:
    """
    Heurystyczna ocena znaczenia newsa na podstawie źródła i keywords

    ŹRÓDŁA (priorytet):
    1. SEC filings, earnings = 1.0 (najważniejsze)
    2. Reuters, Bloomberg, WSJ = 0.8 (wiarygodne)
    3. CNBC, MarketWatch = 0.6 (mainstream)
    4. Blogs, social media = 0.3 (niski priorytet)
    5. Unknown = 0.5 (default)

    KEYWORDS (boost):
    - "earnings", "SEC", "merger", "acquisition" → +0.2
    - "analyst upgrade/downgrade" → +0.15
    - "guidance", "forecast" → +0.1

    Args:
        source: Nazwa źródła (np. "Reuters", "SEC")
        keywords: Lista słów kluczowych z nagłówka

    Returns:
        Significance score [0, 1]

    Przykład:
        sig = estimate_significance(source="Reuters", keywords=["earnings", "beat"])
        # sig = 0.8 (Reuters) + 0.2 (earnings) = 1.0 (clamped)
    """
    # Base significance z source
    base_sig = 0.5  # Default dla unknown

    if source:
        source_lower = source.lower()

        # Tier 1: Regulatory/Official
        if any(x in source_lower for x in ["sec", "earnings", "filing", "8-k", "10-q"]):
            base_sig = 1.0

        # Tier 2: Premium news wires
        elif any(x in source_lower for x in ["reuters", "bloomberg", "wsj", "financial times"]):
            base_sig = 0.8

        # Tier 3: Mainstream financial media
        elif any(x in source_lower for x in ["cnbc", "marketwatch", "barron", "seeking alpha"]):
            base_sig = 0.6

        # Tier 4: Social/Blogs
        elif any(x in source_lower for x in ["twitter", "reddit", "blog", "social"]):
            base_sig = 0.3

    # Boost z keywords
    boost = 0.0
    if keywords:
        keywords_lower = [k.lower() for k in keywords]

        # High priority keywords
        if any(x in keywords_lower for x in ["earnings", "sec", "merger", "acquisition", "buyout"]):
            boost += 0.2

        # Medium priority
        elif any(x in keywords_lower for x in ["upgrade", "downgrade", "rating", "analyst"]):
            boost += 0.15

        # Low priority
        elif any(x in keywords_lower for x in ["guidance", "forecast", "outlook", "target"]):
            boost += 0.1

    # Combine
    significance = base_sig + boost

    # Clamp do [0, 1]
    return max(0.0, min(1.0, significance))


# ============================================================================
# BATCH PROCESSING
# ============================================================================

def score_news_batch(
    news_items: list,
    current_datetime: datetime,
    tau_seconds: float = 3600.0,
    sentiment_key: str = "sentiment",
    datetime_key: str = "datetime",
    source_key: str = "source"
) -> list:
    """
    Batch scoring wielu newsów na raz

    Args:
        news_items: Lista dict'ów z newsami
        current_datetime: Obecny czas
        tau_seconds: Time constant
        sentiment_key: Klucz dla sentiment w dict
        datetime_key: Klucz dla datetime w dict
        source_key: Klucz dla source w dict

    Returns:
        Lista dict'ów z dodanym 'score' i 'decay_factor'

    Przykład:
        news = [
            {"sentiment": 0.8, "datetime": "2025-11-10T14:00:00Z", "source": "Reuters"},
            {"sentiment": -0.5, "datetime": "2025-11-10T12:00:00Z", "source": "CNBC"}
        ]

        scored = score_news_batch(news, datetime.now(timezone.utc), tau_seconds=1800)
        # Każdy item ma teraz: score, decay_factor, significance
    """
    scored_items = []

    for item in news_items:
        # Extract fields
        sentiment = item.get(sentiment_key, 0.0)
        news_datetime = item.get(datetime_key)
        source = item.get(source_key)

        if news_datetime is None:
            # Skip jeśli brak datetime
            continue

        # Calculate decay
        decay_factor = calculate_decay_factor(news_datetime, current_datetime, tau_seconds)

        # Estimate significance
        significance = estimate_significance(source=source)

        # Calculate score
        score = calculate_news_score(sentiment, significance, decay_factor)

        # Add to result
        scored_item = item.copy()
        scored_item["decay_factor"] = decay_factor
        scored_item["significance"] = significance
        scored_item["score"] = score

        scored_items.append(scored_item)

    return scored_items


# ============================================================================
# EXAMPLE USAGE
# ============================================================================

if __name__ == "__main__":
    from datetime import timedelta

    print("=== News Decay Scoring Test ===\n")

    # Obecny czas
    now = datetime.now(timezone.utc)

    # Test różnych czasów newsa
    test_cases = [
        ("Just now", now, 3600),
        ("5 min ago", now - timedelta(minutes=5), 3600),
        ("30 min ago (half-life)", now - timedelta(minutes=30), 1800),
        ("1 hour ago", now - timedelta(hours=1), 3600),
        ("2 hours ago", now - timedelta(hours=2), 3600),
        ("1 day ago", now - timedelta(days=1), 3600),
    ]

    print("Decay factors (tau=1h unless noted):")
    for label, news_time, tau in test_cases:
        decay = calculate_decay_factor(
            news_time.isoformat(),
            now,
            tau_seconds=tau
        )
        print(f"{label:30} decay = {decay:.3f}")

    print("\n" + "="*50 + "\n")

    # Test scoring
    print("News scoring examples:")

    examples = [
        {
            "headline": "AAPL beats earnings",
            "sentiment": 0.9,
            "source": "Reuters",
            "datetime": (now - timedelta(minutes=10)).isoformat()
        },
        {
            "headline": "AAPL production issues",
            "sentiment": -0.6,
            "source": "CNBC",
            "datetime": (now - timedelta(hours=2)).isoformat()
        },
        {
            "headline": "Random blog post",
            "sentiment": 0.5,
            "source": "blog",
            "datetime": (now - timedelta(hours=1)).isoformat()
        }
    ]

    scored = score_news_batch(examples, now, tau_seconds=1800)  # 30 min tau

    for item in scored:
        print(f"\nHeadline: {item['headline']}")
        print(f"  Sentiment: {item['sentiment']:.2f}")
        print(f"  Significance: {item['significance']:.2f} (from {item['source']})")
        print(f"  Decay: {item['decay_factor']:.3f}")
        print(f"  → Final Score: {item['score']:.3f}")
