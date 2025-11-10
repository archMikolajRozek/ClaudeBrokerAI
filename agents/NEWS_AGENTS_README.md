# News Agents - Documentation

Kompletna implementacja agentów do przetwarzania newsów finansowych z wykorzystaniem Redis Streams.

## Architektura

```
┌─────────────────┐
│  News Sources   │ (API, RSS, Twitter)
└────────┬────────┘
         │
         v
┌─────────────────────────────────────────┐
│      ingest_news Agent                  │
│  - Pobiera surowe newsy                 │
│  - Normalizuje do formatu               │
│  - Analizuje sentiment/impact/relevance │
│  - Publikuje do: news_ingested         │
└────────┬────────────────────────────────┘
         │
         │ Redis Stream: news_ingested
         │ {ticker, datetime, headline, body,
         │  sentiment, impact, relevance}
         │
         v
┌─────────────────────────────────────────┐
│      score_news Agent                   │
│  - Konsumuje: news_ingested            │
│  - Oblicza decay_factor                │
│  - Oblicza score = sentiment × impact   │
│    × decay_factor                       │
│  - Publikuje do: news_scored           │
└────────┬────────────────────────────────┘
         │
         │ Redis Stream: news_scored
         │ {ticker, score, timestamp,
         │  decay_factor, relevance}
         │
         v
┌─────────────────────────────────────────┐
│      strategy Agent                     │
│  (konsumuje scored news dla decyzji)    │
└─────────────────────────────────────────┘
```

## Agent: `ingest_news`

### Opis
Pobiera wiadomości finansowe z zewnętrznych źródeł (API, RSS), normalizuje je do ujednoliconego formatu i publikuje do Redis Stream.

### Format wyjściowy (`IngestedNewsMessage`)
```python
{
    "ticker": "AAPL",              # Symbol akcji
    "datetime": "2025-11-10T...",  # ISO timestamp publikacji
    "headline": "Apple announces...",
    "body": "Full article text...",
    "sentiment": 0.75,              # [-1, 1] negatywny do pozytywnego
    "impact": 0.6,                  # [0, 1] przewidywany wpływ na cenę
    "relevance": 0.9,               # [0, 1] relevancja dla tickera
    "source": "NewsAPI",
    "url": "https://...",
    "metadata": {...}
}
```

### Konfiguracja
- `REDIS_URL`: URL do Redis (domyślnie: `redis://localhost:6379`)
- `INGEST_INTERVAL`: Częstotliwość pobierania newsów w sekundach (domyślnie: 60)

### Źródła newsów (placeholder)
Obecna implementacja używa placeholderów. W produkcji podłączyć:
- **NewsAPI** (newsapi.org)
- **Alpha Vantage News & Sentiments**
- **Financial RSS feeds** (Reuters, Bloomberg, CNBC)
- **Twitter/X API** dla trendów

### Analiza sentymentu (placeholder)
Obecna implementacja używa prostej heurystyki. W produkcji użyć:
- **OpenAI GPT-4** / **Claude** dla zaawansowanej analizy
- **FinBERT** - model NLP specjalizujący się w finansach
- Własny model wytrenowany na danych finansowych

### Uruchomienie
```bash
# Z katalogu głównego projektu
python agents/ingest_news/main.py

# Lub z docker-compose
docker-compose up ingest_news
```

### Monitoring
Agent loguje każdą opublikowaną wiadomość:
```
[ingest_news] ✓ Published news for AAPL: Apple announces quarterly earnings beat...
              (sentiment=0.75, impact=0.60) -> 1699999999-0
```

---

## Agent: `score_news`

### Opis
Konsumuje znormalizowane newsy z `news_ingested`, oblicza score z uwzględnieniem czasowego rozpadu (decay factor) i publikuje do `news_scored`.

### Algorytm scoring

#### 1. Obliczanie decay factor
```python
decay_factor = exp(-Δt / tau)
```

Gdzie:
- **Δt**: różnica czasu między obecnym momentem a datą publikacji newsa (w godzinach)
- **tau**: parametr półtrwania (czas w którym wpływ spada do ~37% oryginalnego)

Przykłady dla `tau = 24h`:
- News sprzed 0h: `decay = 1.00` (100%)
- News sprzed 12h: `decay = 0.61` (61%)
- News sprzed 24h: `decay = 0.37` (37%)
- News sprzed 48h: `decay = 0.14` (14%)

#### 2. Obliczanie adjusted impact score
```python
score = sentiment × impact × decay_factor
```

Gdzie:
- **sentiment** ∈ [-1, 1]: Czy news jest pozytywny czy negatywny
- **impact** ∈ [0, 1]: Jak silny jest przewidywany wpływ
- **decay_factor** ∈ [0, 1]: Redukcja wpływu w czasie

Wynik: **score** ∈ [-1, 1]

#### Przykłady:
- Pozytywny news (0.8) × wysoki impact (0.7) × świeży (1.0) = **+0.56**
- Pozytywny news (0.8) × wysoki impact (0.7) × stary 48h (0.14) = **+0.08**
- Negatywny news (-0.6) × średni impact (0.5) × świeży (1.0) = **-0.30**

### Format wyjściowy (`ScoredNewsMessage`)
```python
{
    "ticker": "AAPL",
    "score": 0.42,                  # Adjusted impact score
    "timestamp": "2025-11-10T...",  # Czas obliczenia
    "decay_factor": 0.75,           # Współczynnik rozpadu
    "relevance": 0.9,
    "original_sentiment": 0.8,      # Oryginalny sentiment
    "original_impact": 0.7,         # Oryginalny impact
    "news_datetime": "2025-11-10T...",
    "headline": "Apple announces...",
    "metadata": {...}
}
```

### Konfiguracja
- `REDIS_URL`: URL do Redis
- `NEWS_DECAY_TAU_HOURS`: Parametr tau w godzinach (domyślnie: 24)
- `CONSUMER_NAME`: Nazwa konsumenta Redis (domyślnie: `score_news_consumer_1`)

### Consumer Groups
Agent używa **Redis Consumer Groups** dla:
- **Równoległego przetwarzania**: Możliwość uruchomienia wielu instancji agenta
- **Gwarantowanej dostawy**: Każdy news jest przetwarzany dokładnie raz
- **Fault tolerance**: Wiadomości są acknowledge'owane po przetworzeniu

### Uruchomienie
```bash
# Z katalogu głównego projektu
python agents/score_news/main.py

# Lub z docker-compose
docker-compose up score_news
```

### Monitoring
Agent loguje każdy przetworzony news z detalami:
```
[score_news] ✓ Scored AAPL: score=+0.420
             (sentiment=+0.80 × impact=0.70 × decay=0.750)
             | age=12.3h -> 1699999999-1
```

---

## Uruchomienie pełnego pipeline

### 1. Uruchom Redis
```bash
docker-compose up -d redis
```

### 2. Uruchom agenty
W osobnych terminalach:

```bash
# Terminal 1: Ingest news
python agents/ingest_news/main.py

# Terminal 2: Score news
python agents/score_news/main.py
```

### 3. Monitoruj Redis Streams
```bash
# Podłącz się do Redis CLI
docker exec -it redis redis-cli

# Zobacz wiadomości w news_ingested
XREAD COUNT 10 STREAMS news_ingested 0

# Zobacz wiadomości w news_scored
XREAD COUNT 10 STREAMS news_scored 0

# Sprawdź consumer groups
XINFO GROUPS news_ingested
```

---

## Testowanie

### Test jednostkowy decay factor
```python
from agents.score_news.main import ScoreNewsAgent

agent = ScoreNewsAgent()
agent.tau_hours = 24

# News sprzed 24h powinien mieć decay ~0.37
decay = agent.calculate_decay_factor("2025-11-09T12:00:00", datetime(2025, 11, 10, 12, 0, 0))
assert 0.36 < decay < 0.38
```

### Test end-to-end
```bash
# 1. Uruchom agenty
python agents/ingest_news/main.py &
python agents/score_news/main.py &

# 2. Czekaj na pierwsze newsy (60s)

# 3. Sprawdź Redis
redis-cli XLEN news_ingested
redis-cli XLEN news_scored
```

---

## Rozszerzenia

### Integracja z prawdziwym API
W `agents/ingest_news/main.py`, zamień `NewsSource.fetch_raw_news()` na:

```python
import requests

async def fetch_raw_news(self):
    # NewsAPI.org
    url = "https://newsapi.org/v2/everything"
    params = {
        "q": "stocks OR earnings",
        "apiKey": os.getenv("NEWS_API_KEY"),
        "pageSize": 10
    }
    response = requests.get(url, params=params)
    articles = response.json()["articles"]

    # Mapuj do naszego formatu
    # ...
```

### Integracja z prawdziwym NLP
W `agents/ingest_news/main.py`, zamień `NewsSource.analyze_sentiment()` na:

```python
from openai import OpenAI

async def analyze_sentiment(self, headline, body):
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    prompt = f"""
    Analyze this financial news:
    Headline: {headline}
    Body: {body}

    Return JSON:
    {{
        "sentiment": <float -1 to 1>,
        "impact": <float 0 to 1>,
        "relevance": <float 0 to 1>
    }}
    """

    response = client.chat.completions.create(
        model="gpt-4",
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"}
    )

    return json.loads(response.choices[0].message.content)
```

### Dostrajanie tau
Eksperymentuj z różnymi wartościami `NEWS_DECAY_TAU_HOURS`:

- **tau = 6h**: Szybki rozpad, newsy "stare" po kilku godzinach (day trading)
- **tau = 24h**: Standardowy rozpad, newsy relevantne ~2 dni (domyślne)
- **tau = 72h**: Wolny rozpad, newsy relevantne przez tydzień (swing trading)

---

## Schematy danych

Pełne schematy Pydantic dostępne w: `packages/common/schemas.py`

- `IngestedNewsMessage`: Wiadomość z ingest_news
- `ScoredNewsMessage`: Wiadomość z score_news
- `StreamNames`: Nazwy Redis Streams

---

## FAQ

**Q: Dlaczego używamy Redis Streams a nie kolejek (RabbitMQ, Kafka)?**
A: Redis Streams oferują:
- Niską latencję (< 1ms)
- Prostą konfigurację
- Built-in consumer groups
- Wystarczającą wydajność dla naszego use case

**Q: Jak skalować przetwarzanie newsów?**
A: Uruchom wiele instancji `score_news` z różnymi `CONSUMER_NAME`:
```bash
CONSUMER_NAME=score_news_consumer_1 python agents/score_news/main.py &
CONSUMER_NAME=score_news_consumer_2 python agents/score_news/main.py &
```

**Q: Jak długo przechowywać newsy w Redis?**
A: Redis Streams można trimować automatycznie:
```python
await redis_client.xtrim("news_ingested", maxlen=10000, approximate=True)
```

**Q: Co jeśli agent score_news crashuje?**
A: Dzięki consumer groups, niepotwierdzone wiadomości można odzyskać:
```bash
XPENDING news_ingested score_news_group
XCLAIM news_ingested score_news_group consumer_2 3600000 <message-id>
```

---

## Autorzy

ClaudeBrokerAI Team - 2025
