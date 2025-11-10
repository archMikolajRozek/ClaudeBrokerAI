# Score News Agent

Konsumuje newsy z Redis Stream i oblicza adjusted impact z decay factor (time-weighted scoring).

## Funkcjonalność

- **Event-driven**: Nasłuchuje strumienia `news_ingested` z consumer group
- **Decay factor**: Oblicza `exp(-Δt / tau)` - im starszy news, tym mniejszy wpływ
- **Adjusted impact**: `score = sentiment * impact * decay_factor`
- **Publikacja**: Wysyła scored news do strumienia `news_scored`

## Formuła

```
Δt = current_time - news_datetime  (w sekundach)
decay_factor = exp(-Δt / tau)
score = sentiment * impact * decay_factor
```

Gdzie:
- `tau` - parametr half-life (domyślnie 24h)
- Po `tau` godzinach, `decay_factor ≈ 0.368`
- Po `2*tau`, `decay_factor ≈ 0.135`

## Konfiguracja

W pliku `.env`:

```bash
# Decay tau parameter (hours)
NEWS_DECAY_TAU_HOURS=24.0
```

### Przykłady tau:
- `12.0` - newsy starzą się szybciej (half-life 12h)
- `24.0` - domyślny (half-life 24h)
- `48.0` - newsy mają dłuższy wpływ (half-life 48h)

## Uruchomienie

```bash
# Z poziomu głównego katalogu
cd agents/score_news
python main.py
```

## Format wiadomości

Input: `NewsIngestedMessage`
```json
{
  "ticker": "AAPL",
  "sentiment": 0.75,
  "impact": 0.6,
  "datetime": "2025-01-10T12:00:00Z"
}
```

Output: `NewsScoredMessage`
```json
{
  "ticker": "AAPL",
  "score": 0.413,
  "decay_factor": 0.918,
  "relevance": 0.9,
  "timestamp": "2025-01-10T14:00:00Z",
  "original_sentiment": 0.75,
  "original_impact": 0.6,
  "news_datetime": "2025-01-10T12:00:00Z",
  "headline": "Apple announces..."
}
```

## Consumer Group

Agent używa Redis Consumer Groups dla reliability:
- **Stream**: `news_ingested`
- **Group**: `score_news_group`
- **Consumer**: `score_news_consumer_1`

Wiadomości są ACK'owane po przetworzeniu.

## TODO

- [ ] Aggregacja score dla wielu newsów tego samego tickera
- [ ] Adaptive tau based on market volatility
- [ ] Score persistence (database)
- [ ] Historical score tracking
