# Ingest News Agent

Pobiera wiadomości finansowe z zewnętrznych API (NewsAPI.org) i publikuje znormalizowane wiadomości do Redis Stream.

## Funkcjonalność

- **Pobieranie newsów**: Integracja z NewsAPI.org dla finansowych wiadomości
- **Normalizacja**: Konwersja do jednolitego formatu `NewsIngestedMessage`
- **Analiza wstępna**:
  - **Sentiment**: Analiza sentymentu na podstawie słów kluczowych (-1 do 1)
  - **Impact**: Przewidywany wpływ na cenę akcji (0 do 1)
  - **Relevance**: Relevancja newsa dla konkretnego tickera (0 do 1)
- **Publikacja**: Wysyła do Redis Stream `news_ingested`

## Konfiguracja

W pliku `.env`:

```bash
# API Key (https://newsapi.org/)
NEWS_API_KEY=your-newsapi-key

# Watchlist tickerów
WATCHLIST=AAPL,MSFT,GOOGL,AMZN,TSLA,META,NVDA

# Interwał pobierania (sekundy)
NEWS_FETCH_INTERVAL=300

# Ile dni wstecz
NEWS_DAYS_BACK=1
```

## Uruchomienie

```bash
# Z poziomu głównego katalogu
cd agents/ingest_news
python main.py
```

## Format wiadomości

Output: `NewsIngestedMessage`
```json
{
  "ticker": "AAPL",
  "datetime": "2025-01-10T12:00:00Z",
  "headline": "Apple announces...",
  "body": "Full article text...",
  "sentiment": 0.75,
  "impact": 0.6,
  "relevance": 0.9,
  "source": "TechCrunch",
  "url": "https://..."
}
```

## Placeholder Mode

Jeśli nie podano `NEWS_API_KEY`, agent działa w trybie placeholder - generuje przykładowe newsy dla testów.

## TODO

- [ ] Dodać więcej źródeł newsów (RSS feeds, Twitter/X, Reddit)
- [ ] Zamienić keyword-based sentiment na LLM API (OpenAI/Anthropic)
- [ ] Cache dla już pobranych artykułów
- [ ] Parallel fetching dla tickerów
