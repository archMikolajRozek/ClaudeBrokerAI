# Quick Start Guide - News Agents

Szybki start dla agentów `ingest_news` i `score_news`.

## Wymagania

- Python 3.11+
- Redis (lokalny lub Docker)

## Instalacja

### 1. Sklonuj i zainstaluj zależności

```bash
# Instalacja dependencies
pip install -r requirements.txt
pip install -r packages/common/requirements.txt
pip install -r agents/ingest_news/requirements.txt
pip install -r agents/score_news/requirements.txt
```

### 2. Uruchom Redis

**Opcja A: Docker**
```bash
docker run -d -p 6379:6379 redis:7-alpine
```

**Opcja B: docker-compose**
```bash
docker-compose up redis
```

**Opcja C: Lokalny Redis**
```bash
redis-server
```

### 3. Konfiguracja

```bash
# Skopiuj przykładową konfigurację
cp .env.example .env

# Edytuj .env (opcjonalnie - działa też bez API keys w trybie placeholder)
# Dodaj NEWS_API_KEY z https://newsapi.org/ dla prawdziwych newsów
```

## Uruchomienie

### Opcja 1: Test script (oba agenty razem)

```bash
python test_agents.py
```

To uruchomi oba agenty równolegle i pokaże logi.

### Opcja 2: Ręcznie (osobne terminale)

**Terminal 1 - Ingest News:**
```bash
cd agents/ingest_news
python main.py
```

**Terminal 2 - Score News:**
```bash
cd agents/score_news
python main.py
```

## Co zobaczysz

### Ingest News Agent:
```
[ingest_news] Initialized with watchlist: ['AAPL', 'MSFT', 'GOOGL']
[ingest_news] ✓ Connected to Redis
[ingest_news] === Iteration 1 ===
[ingest_news] ⚠️  No NewsAPI key, using placeholder data
[ingest_news] Fetched 6 articles total
[ingest_news] ✓ Published: AAPL - Apple announces strong quarterly earnings... (sentiment=0.60, impact=0.45)
[ingest_news] Published 6/6 articles to stream
```

### Score News Agent:
```
[score_news] Initialized with tau=24.0h
[score_news] ✓ Connected to Redis
[score_news] Listening on stream: news_ingested
[score_news] ✓ Scored: AAPL - score=0.2700 (sentiment=0.60, impact=0.45, decay=1.0000)
[score_news] Processed 6 messages total
```

## Monitoring Redis

### W osobnym terminalu:

```bash
# Sprawdź streamy
docker exec -it <redis-container> redis-cli

# Lista streamów
KEYS *

# Info o stream
XINFO STREAM news_ingested
XINFO STREAM news_scored

# Czytaj wiadomości
XREAD COUNT 5 STREAMS news_ingested 0
XREAD COUNT 5 STREAMS news_scored 0

# Real-time monitor
MONITOR
```

## Przykładowe dane

### News Ingested (input):
```json
{
  "ticker": "AAPL",
  "datetime": "2025-01-10T12:00:00Z",
  "headline": "Apple announces strong quarterly earnings, beating analyst expectations",
  "body": "Apple announces strong quarterly earnings...",
  "sentiment": 0.60,
  "impact": 0.45,
  "relevance": 0.90,
  "source": "PlaceholderNews"
}
```

### News Scored (output):
```json
{
  "ticker": "AAPL",
  "score": 0.2700,
  "timestamp": "2025-01-10T12:00:05Z",
  "decay_factor": 1.0000,
  "relevance": 0.90,
  "original_sentiment": 0.60,
  "original_impact": 0.45,
  "headline": "Apple announces strong quarterly earnings..."
}
```

## Konfiguracja zaawansowana

### Zmiana interwału pobierania (domyślnie 5 min):

```bash
# .env
NEWS_FETCH_INTERVAL=60  # 1 minuta
```

### Zmiana decay tau (domyślnie 24h):

```bash
# .env
NEWS_DECAY_TAU_HOURS=12.0  # Szybszy decay
```

### Custom watchlist:

```bash
# .env
WATCHLIST=TSLA,NVDA,META,GOOGL
```

## Troubleshooting

### "Connection refused" (Redis)
```bash
# Sprawdź czy Redis działa
redis-cli ping
# Powinno zwrócić: PONG
```

### "No module named 'common'"
```bash
# Zainstaluj common package
pip install -r packages/common/requirements.txt
```

### Agent nie publikuje wiadomości
```bash
# Sprawdź streamy w Redis
redis-cli XINFO STREAM news_ingested
```

## Następne kroki

1. **Dodaj News API key** w `.env` dla prawdziwych newsów
2. **Uruchom więcej agentów**: market_data, strategy, risk
3. **Dashboard**: Uruchom `apps/api` dla REST API
4. **Production**: Użyj `docker-compose up` dla wszystkich serwisów

## Help

- Issues: [GitHub Issues](https://github.com/your-org/ClaudeBrokerAI/issues)
- Docs: Sprawdź README.md w każdym agencie
