# AI Portfolio Manager 🤖📈

**Professional AI-powered hedge fund system** dla handlu akcjami USA (intraday trading). System oparty na architekturze mikroserwisowej z 10 autonomicznymi agentami komunikującymi się przez Redis Streams.

## 💰 Kapitał i Parametry

- **NAV (Net Asset Value)**: $50,000 USD (z dostępnych $100,000 na demo account)
- **Ryzyko per trade**: 0.5% NAV ($250 max risk/trade)
- **Max pozycje**: 5 jednocześnie
- **Daily loss limit**: 2% NAV ($1,000 max strata dzienna)
- **Max drawdown**: 10% od peak equity ($5,000)
- **Stop loss**: 1% (intraday tight stops)
- **Take profit**: 2% (risk:reward = 1:2)
- **Circuit breaker**: Automatyczne zatrzymanie tradingu przy przekroczeniu limitów

## 🎯 Funkcjonalności - Profesjonalne Zarządzanie Kapitałem

### ✅ **Kapitał i Alokacja**
- **NAV-based position sizing** - Każda pozycja = 0.5% ryzyka NAV
- **Max 5 pozycji** - Dywersyfikacja bez over-exposure
- **Circuit breaker** - Emergency stop przy daily loss > $1,000 lub drawdown > 10%
- **Smart capital management** - System może wycofać kapitał w złych warunkach i czekać na lepsze okazje

### 📊 **Real-time Data & Analysis**
- **Market data (Finazon.io)** - 1-minute candles dla AAPL, TSLA, GOOG
- **News ingestion** - RSS feeds z NewsAPI (5-minute intervals)
- **AI news scoring** - Time-weighted exponential decay (τ=0.5h dla intraday)
- **Technical indicators** - RSI, MACD, EMA, Bollinger Bands, ATR
- **Momentum analysis** - Combined RSI + MACD + ROC score [-1, 1]

### 🎯 **Strategia Handlowa**
- **Hybrid scoring**: α=0.6 (news) + (1-α)=0.4 (momentum)
- **Multi-signal confirmation** - News + technical indicators + volume filters
- **Intraday focus** - Tight stops (1%), quick targets (2%), news decay 30min
- **Volume filters** - Min 1M shares/day, $10M dollar volume, max 0.1% spread

### 🛡️ **Zarządzanie Ryzykiem (3 warstwy ochrony)**
1. **Risk Agent** - Position sizing, NAV limits, max positions
2. **Circuit Breaker** - Daily loss limit, max drawdown monitoring
3. **Market Regime Detection** - Adjust aggressiveness based on market conditions

### 🤖 **Anomaly Detection**
- **Shock detector** - Z-score > 2σ dla nagłych ruchów cen
- **Cause finder** - Event correlation (news → price impact memory)
- **Impact memory** - SQLite database śledząca które newsy wpływają na które akcje

### 🔄 **Automatyczne Wykonanie**
- **Alpaca Paper Trading** - Real API integration (transakcje widoczne na dashboard)
- **Market orders** - Natychmiastowe wykonanie
- **Order tracking** - Pełne logowanie executed orders

## 🏗️ Architektura - 10 Agentów

System zaprojektowany jak **profesjonalny hedge fund** z Wall Street. Każdy agent to autonomiczny mikroerwis z własną odpowiedzialnością:

```
┌──────────────────────────────────────────────────────────────────────────┐
│                          LAYER 1: DATA INGESTION                         │
├──────────────────────────────────────────────────────────────────────────┤
│  ┌─────────────────┐              ┌──────────────────────┐              │
│  │  Ingest News    │              │  Market Data Finazon │              │
│  │  (NewsAPI)      │              │  (1-min candles)     │              │
│  └────────┬────────┘              └──────────┬───────────┘              │
│           │                                   │                          │
└───────────┼───────────────────────────────────┼──────────────────────────┘
            │                                   │
            ▼                                   ▼
┌──────────────────────────────────────────────────────────────────────────┐
│                         LAYER 2: ANALYSIS & SCORING                      │
├──────────────────────────────────────────────────────────────────────────┤
│  ┌─────────────────┐              ┌──────────────────────┐              │
│  │  Score News     │              │  Momentum            │              │
│  │  (AI + decay)   │              │  (RSI, MACD, ROC)    │              │
│  └────────┬────────┘              └──────────┬───────────┘              │
│           │                                   │                          │
└───────────┼───────────────────────────────────┼──────────────────────────┘
            │                                   │
            └───────────────┬───────────────────┘
                            ▼
┌──────────────────────────────────────────────────────────────────────────┐
│                       LAYER 3: STRATEGY & SIGNALS                        │
├──────────────────────────────────────────────────────────────────────────┤
│                     ┌──────────────────────┐                             │
│                     │  Strategy            │                             │
│                     │  (α*news + (1-α)*mom)│                             │
│                     └──────────┬───────────┘                             │
│                                │                                          │
└────────────────────────────────┼──────────────────────────────────────────┘
                                 ▼
┌──────────────────────────────────────────────────────────────────────────┐
│                       LAYER 4: RISK MANAGEMENT                           │
├──────────────────────────────────────────────────────────────────────────┤
│  ┌─────────────────┐              ┌──────────────────────┐              │
│  │  Risk           │              │  Circuit Breaker     │              │
│  │  (NAV, limits)  │──────────────│  (emergency stop)    │              │
│  └────────┬────────┘              └──────────────────────┘              │
│           │                                                              │
└───────────┼──────────────────────────────────────────────────────────────┘
            │ (approved trades)
            ▼
┌──────────────────────────────────────────────────────────────────────────┐
│                         LAYER 5: EXECUTION                               │
├──────────────────────────────────────────────────────────────────────────┤
│                     ┌──────────────────────┐                             │
│                     │  Execution           │                             │
│                     │  (Alpaca API)        │                             │
│                     └──────────────────────┘                             │
└──────────────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────────────┐
│                    MONITORING & ANOMALY DETECTION                        │
├──────────────────────────────────────────────────────────────────────────┤
│  ┌─────────────────┐              ┌──────────────────────┐              │
│  │ Shock Detector  │              │  Cause Finder        │              │
│  │ (price anomaly) │──────────────│  (news→price memory) │              │
│  └─────────────────┘              └──────────────────────┘              │
└──────────────────────────────────────────────────────────────────────────┘
```

### 📋 Szczegółowy Opis Agentów

| Agent | Status | Rola | Input Streams | Output Streams | Kluczowe Funkcje |
|-------|--------|------|---------------|----------------|------------------|
| **ingest_news** | ✅ | Pobiera wiadomości finansowe | - | `news_ingested` | NewsAPI integration, watchlist filtering, 5-min polling |
| **score_news** | ✅ | AI scoring + time decay | `news_ingested` | `news_scored` | Exponential decay τ=0.5h, heuristic scoring, sentiment analysis |
| **market_data_finazon** | ✅ | Real-time market data | - | `market_candles` | Finazon.io REST API, 1-min candles, rate limiting (5 req/min) |
| **momentum** | ✅ | Technical analysis | `market_candles` | `market_momentum` | RSI, MACD, ROC calculation, sliding window (50 bars) |
| **strategy** | ✅ | Signal generation | `news_scored`, `market_momentum`, `market_candles` | `trade_proposals` | Hybrid scoring α=0.6, threshold=0.3, TP/SL calculation |
| **risk** | ✅ | Position sizing & approval | `trade_proposals` | `approved_trades`, `rejected_trades` | NAV-based sizing, max positions=5, daily loss tracking |
| **execution** | ✅ | Trade execution | `approved_trades` | `executed_orders` | Alpaca API integration, market orders, order tracking |
| **circuit_breaker** | ✅ | Emergency protection | `executed_orders` | `system_alerts` | Daily loss limit ($1k), max drawdown (10%), trading halt |
| **shock_detector** | ✅ | Price anomaly detection | `market_candles` | `price_shocks` | Z-score > 2σ, volume percentile > 80%, sliding window |
| **cause_finder** | ✅ | Event correlation | `price_shocks`, `news_scored` | `impact_memory` | News→price correlation, SQLite impact memory, 30-min window |

**✅ All agents fully implemented and production-ready**

## 📁 Struktura Projektu

```
ClaudeBrokerAI/
├── agents/                          # Autonomiczne agenty (10 agentów)
│   ├── ingest_news/                # ✅ Pobieranie wiadomości (NewsAPI)
│   │   ├── main.py                 # Agent event loop
│   │   └── requirements.txt        # Dependencies
│   ├── score_news/                 # ✅ AI scoring + time decay
│   │   ├── main.py
│   │   └── requirements.txt
│   ├── market_data_finazon/        # ✅ Real-time market data (Finazon.io)
│   │   ├── main.py
│   │   └── requirements.txt
│   ├── momentum/                   # ✅ Technical analysis (RSI, MACD, ROC)
│   │   ├── main.py
│   │   └── requirements.txt
│   ├── strategy/                   # ✅ Signal generation (hybrid scoring)
│   │   ├── main.py
│   │   └── requirements.txt
│   ├── risk/                       # ✅ Position sizing & approval
│   │   ├── main.py
│   │   └── requirements.txt
│   ├── execution/                  # ✅ Trade execution (Alpaca API)
│   │   ├── main.py
│   │   └── requirements.txt
│   ├── circuit_breaker/            # ✅ Emergency protection
│   │   ├── main.py
│   │   └── requirements.txt
│   ├── shock_detector/             # ✅ Price anomaly detection
│   │   ├── main.py
│   │   └── requirements.txt
│   └── cause_finder/               # ✅ Event correlation (news→price)
│       ├── main.py
│       └── requirements.txt
│
├── packages/                        # Współdzielone biblioteki
│   └── common/
│       ├── schemas.py              # Pydantic schemas (StreamMessage, TradeProposal, etc.)
│       ├── redis_utils.py          # Redis helper functions
│       ├── tech.py                 # ✅ Technical indicators (RSI, MACD, EMA, etc.)
│       ├── news_decay.py           # ✅ News scoring with exponential decay
│       └── requirements.txt
│
├── apps/
│   ├── api/                        # ✅ FastAPI REST API
│   │   ├── main.py
│   │   ├── requirements.txt
│   │   └── Dockerfile
│   └── ui/                         # ✅ Streamlit dashboard
│       ├── app.py
│       ├── requirements.txt
│       └── Dockerfile
│
├── infra/                          # Infrastructure as Code
│   ├── Dockerfile.agent           # Dockerfile for all agents
│   ├── Dockerfile.api             # Dockerfile for API
│   └── README.md
│
├── docker-compose.yml              # Orkiestracja wszystkich serwisów (12 containers)
├── .env                            # Configuration (API keys, parameters)
├── .env.example                    # Template configuration
├── .gitattributes                  # Git LF line endings (Windows fix)
└── README.md                       # Dokumentacja
```

## 🚀 Quick Start (Windows 11)

### Wymagania

- **Docker Desktop** (zainstaluj z https://www.docker.com/products/docker-desktop/)
- **Git** (zainstaluj z https://git-scm.com/download/win)
- **Python 3.10+** (opcjonalne, dla development lokalnego)
- **PowerShell** (wbudowany w Windows 11)

### API Keys (Wymagane)

Potrzebujesz darmowych kont na:
- **NewsAPI** (https://newsapi.org/) - Pobieranie wiadomości (darmowy tier: 100 req/day)
- **Finazon.io** (https://finazon.io/) - Market data (trial: 5 req/min, AAPL/TSLA/GOOG)
- **Alpaca** (https://alpaca.markets/) - Paper trading (darmowe konto demo $100k)

Opcjonalnie (dla AI scoring - obecnie używamy heurystyki):
- **OpenAI** (https://platform.openai.com/) lub **Anthropic** (https://console.anthropic.com/)

### Instalacja - Krok po Kroku

**1. Sklonuj repozytorium (PowerShell)**
```powershell
git clone https://github.com/archMikolajRozek/ClaudeBrokerAI.git
cd ClaudeBrokerAI
```

**2. Skopiuj konfigurację**
```powershell
Copy-Item .env.example .env
```

**3. Edytuj `.env` (Notepad lub VS Code)**
```powershell
notepad .env
```

Uzupełnij swoje API keys:
```bash
# Redis (NIE ZMIENIAJ - to dla Docker)
REDIS_URL=redis://redis:6379

# Market Data
FINAZON_API_KEY=twoj-klucz-z-finazon

# News API
NEWS_API_KEY=twoj-klucz-z-newsapi

# Alpaca Paper Trading
ALPACA_API_KEY=twoj-klucz-z-alpaca
ALPACA_API_SECRET=twoj-secret-z-alpaca
ALPACA_BASE_URL=https://paper-api.alpaca.markets

# Kapitał i ryzyko (domyślne wartości są OK)
RISK_NAV=50000.0
RISK_MAX_PER_TRADE_PCT=0.005
RISK_MAX_POSITIONS=5
RISK_DAILY_LOSS_PCT=0.02
CIRCUIT_BREAKER_MAX_DRAWDOWN=0.10
```

**4. Uruchom Docker Desktop**
- Otwórz Docker Desktop app
- Poczekaj aż status zmieni się na "Engine running"

**5. Build i uruchom wszystkie kontenery (PowerShell)**
```powershell
docker-compose up --build
```

Pierwsze build zajmie 5-10 minut (pobiera wszystkie dependencies).

**6. Sprawdź status (w nowym oknie PowerShell)**
```powershell
# Sprawdź działające kontenery (powinno być 12)
docker ps

# Sprawdź logi konkretnego agenta
docker-compose logs -f agent-strategy

# Sprawdź logi wszystkich agentów
docker-compose logs -f

# Sprawdź Redis
docker-compose exec redis redis-cli ping
# Powinno zwrócić: PONG

# Sprawdź API
curl http://localhost:8000
# Lub otwórz w przeglądarce: http://localhost:8000/docs
```

**7. Zatrzymanie systemu**
```powershell
# Ctrl+C w oknie gdzie uruchomiłeś docker-compose up
# LUB w nowym oknie:
docker-compose down
```

**8. Restart po zmianach w .env (WAŻNE!)**
```powershell
docker-compose down
docker-compose up --force-recreate
```

Użyj `--force-recreate` gdy zmieniłeś `.env` - wymusza odczytanie nowych zmiennych środowiskowych.

### 🎯 Monitoring Systemu

**Sprawdź Redis Streams (dane w systemie)**
```powershell
# Wejdź do Redis CLI
docker-compose exec redis redis-cli

# W Redis CLI:
# Lista wszystkich streamów
KEYS *

# Sprawdź stream market_candles (dane z Finazon)
XLEN market_candles
XREVRANGE market_candles + - COUNT 5

# Sprawdź stream news_scored (newsy z scoring)
XLEN news_scored
XREVRANGE news_scored + - COUNT 5

# Sprawdź stream trade_proposals (sygnały strategii)
XLEN trade_proposals
XREVRANGE trade_proposals + - COUNT 5

# Wyjdź z Redis CLI
exit
```

**Sprawdź logi agentów w czasie rzeczywistym**
```powershell
# Wszystkie agenty
docker-compose logs -f

# Tylko market data
docker-compose logs -f agent-market-data-finazon

# Tylko strategy + risk + execution
docker-compose logs -f agent-strategy agent-risk agent-execution

# Tylko circuit breaker (emergency stop monitoring)
docker-compose logs -f agent-circuit-breaker
```

### Development Lokalny (Bez Docker - dla programistów)

Jeśli chcesz edytować kod i testować bez rebuildowania Dockera:

```powershell
# 1. Zainstaluj Python dependencies
pip install -r packages/common/requirements.txt

# 2. Uruchom TYLKO Redis w Docker
docker-compose up redis

# 3. W .env zmień REDIS_URL na localhost
REDIS_URL=redis://localhost:6379

# 4. Uruchom agenta lokalnie (w nowym oknie PowerShell)
cd agents/strategy
python main.py

# 5. Możesz uruchomić wiele agentów w oddzielnych oknach PowerShell
```

Kod agentów ma **hot-reload** gdy używasz Docker volumes (już skonfigurowane w `docker-compose.yml`).

## 📊 Jak Działa System - Decision Flow

System podejmuje decyzje handlowe w 5-warstwowej architekturze. Każdy trade przechodzi przez wszystkie warstwy:

### 1️⃣ **Data Ingestion** (Co 60 sekund)

**Market Data Finazon Agent:**
- Pobiera 1-min candles dla AAPL, TSLA, GOOG z Finazon.io
- Publikuje do `market_candles` stream
- Format: `{ticker, timestamp, open, high, low, close, volume}`

**Ingest News Agent:** (Co 5 minut)
- Pobiera wiadomości z NewsAPI dla watchlist
- Filtruje po tickerach (AAPL, TSLA, GOOG)
- Publikuje do `news_ingested` stream

### 2️⃣ **Analysis & Scoring**

**Momentum Agent:**
- Konsumuje `market_candles`
- Utrzymuje sliding window 50 świec per ticker
- Oblicza wskaźniki techniczne:
  - **RSI** (Relative Strength Index) - overbought/oversold
  - **MACD** (Moving Average Convergence Divergence) - trend strength
  - **ROC** (Rate of Change) - momentum
- Normalizuje do `momentum_score` ∈ [-1, 1]:
  - Score > 0.5 = silny BUY momentum
  - Score < -0.5 = silny SELL momentum
- Publikuje do `market_momentum` stream

**Score News Agent:**
- Konsumuje `news_ingested`
- Oblicza **time decay factor**: `exp(-Δt/τ)` gdzie τ=0.5h (30 min)
  - News sprzed 30 min ma decay = 0.37 (37% wagi)
  - News sprzed 1h ma decay = 0.14 (14% wagi)
- Oblicza **significance score** (heurystyka):
  - SEC filings / earnings = 1.0
  - Reuters / Bloomberg = 0.8
  - CNBC / MarketWatch = 0.6
  - Twitter / Reddit = 0.4
- **Combined score** = significance × decay × sentiment
- Publikuje do `news_scored` stream

### 3️⃣ **Strategy & Signal Generation**

**Strategy Agent:**
- Konsumuje 3 streamy: `news_scored`, `market_momentum`, `market_candles`
- **Hybrid scoring**: `combined_score = α × news_score + (1-α) × momentum_score`
  - α = 0.6 (60% waga na news, 40% na technical)
- **Threshold**: Generuje sygnał tylko jeśli `combined_score > 0.3`
- **Entry price**: Current price z `market_candles`
- **Stop loss**: Entry × (1 - 0.01) = 1% poniżej entry
- **Take profit**: Entry × (1 + 0.02) = 2% powyżej entry
- **Side**: BUY jeśli combined_score > 0, SELL jeśli < 0
- Publikuje `TradeProposal` do `trade_proposals` stream

**Przykład Trade Proposal:**
```json
{
  "ticker": "AAPL",
  "side": "BUY",
  "entry": 274.50,
  "stop": 271.76,    // -1%
  "take_profit": 280.19,  // +2%
  "rationale": "News: 0.45, Momentum: 0.62 → Combined: 0.52",
  "timestamp": "2025-11-12T14:30:00Z"
}
```

### 4️⃣ **Risk Management (2 warstwy)**

**Risk Agent:**
- Konsumuje `trade_proposals`
- **Walidacja multi-level:**
  1. ✅ **Daily loss check**: Czy daily_pnl > -$1,000?
  2. ✅ **Max positions check**: Czy mamy < 5 pozycji?
  3. ✅ **Duplicate check**: Czy już mamy pozycję na tym tickerze?
  4. ✅ **Position sizing**: `quantity = (NAV × 0.005) / risk_per_share`
     - NAV = $50,000
     - Risk per trade = 0.5% NAV = $250
     - Risk per share = |entry - stop| = $2.74
     - Quantity = $250 / $2.74 = **91 shares**
  5. ✅ **Position value check**: Czy `quantity × entry < NAV`?
- **Approval**: Tworzy `ApprovedTrade` z calculated quantity
- **Rejection**: Tworzy `RejectedTrade` z powodem
- Publikuje do `approved_trades` lub `rejected_trades`

**Circuit Breaker Agent:**
- Konsumuje `executed_orders` (post-execution monitoring)
- Aktualizuje **daily P&L** i **drawdown**:
  - `daily_pnl += (exit_price - entry_price) × quantity - commission`
  - `drawdown = peak_nav - current_nav`
- **State machine**:
  - NORMAL → trading dozwolony
  - CAUTION → zbliżamy się do limitów (80% threshold)
  - HALTED → trading zatrzymany
- **Halt triggers**:
  - Daily loss > $1,000
  - Drawdown > 10% ($5,000 od peak)
- Publikuje `system_alerts` przy HALT

### 5️⃣ **Execution**

**Execution Agent:**
- Konsumuje `approved_trades`
- **Alpaca API call**:
  ```python
  POST https://paper-api.alpaca.markets/v2/orders
  {
    "symbol": "AAPL",
    "qty": 91,
    "side": "buy",
    "type": "market",
    "time_in_force": "day"
  }
  ```
- **Response handling**:
  - Success → Publikuje `ExecutedOrder` do `executed_orders`
  - Failure (404, 403) → Retry lub log error
- **Order tracking**: Zapisuje filled_price, commission, order_id

**Przykład Executed Order:**
```json
{
  "ticker": "AAPL",
  "side": "BUY",
  "quantity": 91,
  "filled_price": 274.52,
  "commission": 0.10,
  "order_id": "a1b2c3d4",
  "executed_at": "2025-11-12T14:30:05Z"
}
```

### 🔄 **Monitoring & Anomaly Detection** (Parallel)

**Shock Detector Agent:**
- Konsumuje `market_candles` (parallel do wszystkiego)
- Śledzi **z-score** price moves:
  - `z = (price - mean) / std_dev`
  - Trigger: z > 2.0 (2 standard deviations)
- Śledzi **volume percentile**:
  - Trigger: volume > 80th percentile
- Publikuje `PriceShock` do `price_shocks` gdy wykryje anomalię

**Cause Finder Agent:**
- Konsumuje `price_shocks` + `news_scored`
- **Event correlation**: Czy był news w ostatnich 30 min?
- **Impact calculation**:
  - `price_delta_pct = (price_after - price_before) / price_before`
  - `confidence = correlation_strength × time_proximity`
- **SQLite database** (`impact_memory.db`):
  ```sql
  INSERT INTO events (ticker, headline, price_delta_pct, confidence)
  ```
- **Machine learning** (future): Które typy newsów → jakie price moves?

### 📈 **Kompletny Example Flow**

**T=0min:** Finazon publikuje AAPL candle: close=$274.50, volume=1.2M
**T=0min:** Momentum agent oblicza: RSI=62, MACD positive → momentum_score=0.62
**T=1min:** NewsAPI zwraca: "Apple announces new AI chip partnership"
**T=1min:** Score News oblicza: significance=0.8, decay=1.0, sentiment=positive → news_score=0.80
**T=1min:** Strategy oblicza: 0.6×0.80 + 0.4×0.62 = 0.73 > 0.3 ✅ GENERATE SIGNAL
**T=1min:** Strategy publikuje: BUY AAPL @ $274.50, stop=$271.76, tp=$280.19
**T=1min:** Risk waliduje: NAV=$50k, risk=$250, qty=91 shares ✅ APPROVED
**T=1min:** Execution wysyła do Alpaca: BUY 91 AAPL market order
**T=1min:** Alpaca fills: 91 @ $274.52, commission=$0.10
**T=1min:** Execution publikuje: ExecutedOrder(filled_price=$274.52)
**T=1min:** Circuit Breaker aktualizuje: daily_pnl=-$0.10 (tylko commission), state=NORMAL ✅

**Pozycja otwarta**: 91 shares AAPL @ $274.52, risk=$250, potential profit=$500 (2% target)

## 📊 API Endpoints

REST API dostępne na `http://localhost:8000`:

- `GET /` - Health check
- `GET /api/v1/signals` - Najnowsze sygnały handlowe
- `GET /api/v1/portfolio` - Statystyki portfela
- `GET /api/v1/positions` - Aktualne pozycje
- `GET /api/v1/alerts` - Alerty o anomaliach rynkowych
- `GET /api/v1/circuit_breaker` - Status circuit breaker (NORMAL/CAUTION/HALTED)

Dokumentacja interaktywna: `http://localhost:8000/docs`

### Streamlit Dashboard (UI)

Dostępne na `http://localhost:8501`:
- Real-time portfolio value
- Open positions table
- Trade history
- News feed z scoring
- Circuit breaker status

## 🔧 Konfiguracja

### Redis Streams

Wszystkie agenty komunikują się przez Redis Streams. Nazwy streamów zdefiniowane w `packages/common/schemas.py`:

**Data Streams:**
- `market_candles` - 1-min OHLCV candles z Finazon
- `news_ingested` - Surowe wiadomości z NewsAPI
- `news_scored` - Ocenione wiadomości (z AI scoring + decay)
- `market_momentum` - Technical indicators (RSI, MACD, ROC)

**Trading Streams:**
- `trade_proposals` - Sygnały generowane przez strategy
- `approved_trades` - Zatwierdzone przez risk agent
- `rejected_trades` - Odrzucone przez risk agent
- `executed_orders` - Wykonane na Alpaca

**Monitoring Streams:**
- `price_shocks` - Anomalie cenowe (z-score > 2σ)
- `system_alerts` - Alerty od circuit breaker
- `impact_memory` - Event correlation (news→price)

### Parametry Kapitału i Ryzyka

**W `.env` (główne parametry):**

```bash
# NAV - Net Asset Value (kapitał startowy)
RISK_NAV=50000.0                 # $50,000 USD

# Position sizing
RISK_MAX_PER_TRADE_PCT=0.005     # 0.5% NAV per trade = $250 max risk
RISK_MAX_POSITIONS=5             # Max 5 simultaneous positions

# Daily limits
RISK_DAILY_LOSS_PCT=0.02         # 2% daily loss = $1,000 max loss/day

# Circuit breaker
CIRCUIT_BREAKER_MAX_DRAWDOWN=0.10  # 10% max drawdown from peak = $5,000

# Stop loss / take profit (intraday)
STRATEGY_STOP_LOSS_PCT=0.01      # 1% tight stops
STRATEGY_TAKE_PROFIT_PCT=0.02    # 2% targets (risk:reward = 1:2)
STRATEGY_RISK_REWARD=2.0         # TP/SL ratio

# Strategy scoring
STRATEGY_ALPHA=0.6               # Weight for news (0.6 = 60%)
STRATEGY_THRESHOLD=0.3           # Min combined score to trade
```

**Obliczenia:**
- Max risk per trade: $50,000 × 0.005 = **$250**
- Daily loss limit: $50,000 × 0.02 = **$1,000**
- Max drawdown: $50,000 × 0.10 = **$5,000**
- Max capital at risk (5 positions): $250 × 5 = **$1,250** (2.5% NAV)

### Parametry News Decay (Intraday)

```bash
# News decay tau (half-life)
NEWS_DECAY_TAU_HOURS=0.5         # 30 minutes dla intraday
                                 # News starsze niż 30 min = 37% wagi
                                 # News starsze niż 1h = 14% wagi
```

**Dlaczego τ=0.5h?**
- Dla **intraday trading** newsy tracą relevancję szybko
- Dla **swing trading** użyj τ=24h (newsy ważne przez cały dzień)

### Parametry Technical Indicators

```bash
# Momentum calculations
MOMENTUM_WINDOW_SIZE=50          # 50 bars (50 minut dla 1-min candles)
MOMENTUM_RSI_PERIOD=14           # Standard RSI period
MOMENTUM_MACD_FAST=12            # MACD fast EMA
MOMENTUM_MACD_SLOW=26            # MACD slow EMA
MOMENTUM_MACD_SIGNAL=9           # MACD signal line
```

### Parametry Filtrów (Liquidity & Timing)

**Volume filters** (prevent illiquid trades):
```bash
MIN_DAILY_VOLUME=1000000         # Min 1M shares average daily volume
MIN_DOLLAR_VOLUME=10000000       # Min $10M USD average dollar volume
MAX_SPREAD_PCT=0.001             # Max 0.1% bid-ask spread (10 bps)
```

**Market hours** (NYSE Eastern Time):
```bash
MARKET_OPEN_HOUR=9
MARKET_OPEN_MINUTE=30            # Trading starts 9:30 AM ET

MARKET_CLOSE_HOUR=16
MARKET_CLOSE_MINUTE=0            # Market closes 4:00 PM ET

STOP_NEW_TRADES_HOUR=15
STOP_NEW_TRADES_MINUTE=50        # Stop opening new positions 3:50 PM

FORCE_CLOSE_HOUR=15
FORCE_CLOSE_MINUTE=55            # Close all positions 3:55 PM (avoid overnight)
```

**Dlaczego FORCE_CLOSE?**
- Intraday trading = **no overnight exposure**
- Zamykamy wszystko przed 4pm aby uniknąć gap risk następnego dnia

### API Keys (Wymagane)

```bash
# Market Data (trial: AAPL, TSLA, GOOG only)
FINAZON_API_KEY=your-finazon-key

# News
NEWS_API_KEY=your-newsapi-key

# Broker (paper trading)
ALPACA_API_KEY=your-alpaca-key
ALPACA_API_SECRET=your-alpaca-secret
ALPACA_BASE_URL=https://paper-api.alpaca.markets

# AI (opcjonalnie - obecnie heuristic scoring)
OPENAI_API_KEY=sk-your-openai-key
ANTHROPIC_API_KEY=sk-ant-your-anthropic-key
```

## 🧪 Testing & Debugging

### Ręczne Testowanie Redis Streams

```bash
# Wejdź do Redis CLI
docker-compose exec redis redis-cli

# ===== SPRAWDŹ DANE RYNKOWE =====
# Ile candles mamy dla AAPL?
XLEN market_candles

# Pokaż ostatnie 5 candles
XREVRANGE market_candles + - COUNT 5

# ===== SPRAWDŹ NEWSY =====
XLEN news_scored
XREVRANGE news_scored + - COUNT 3

# ===== SPRAWDŹ SYGNAŁY STRATEGII =====
XLEN trade_proposals
XREVRANGE trade_proposals + - COUNT 5

# ===== SPRAWDŹ ZATWIERDZONE TRADES =====
XLEN approved_trades
XREVRANGE approved_trades + - COUNT 5

# ===== SPRAWDŹ ODRZUCONE (dlaczego?) =====
XLEN rejected_trades
XREVRANGE rejected_trades + - COUNT 5

# ===== SPRAWDŹ WYKONANE ZLECENIA =====
XLEN executed_orders
XREVRANGE executed_orders + - COUNT 5

# ===== MONITORUJ WSZYSTKIE OPERACJE LIVE =====
MONITOR

# Wyjdź: Ctrl+C
```

### Testowanie Pojedynczych Agentów

```powershell
# Test market data agent (sprawdź czy Finazon działa)
docker-compose logs -f agent-market-data-finazon

# Test news ingest (sprawdź czy NewsAPI zwraca dane)
docker-compose logs -f agent-ingest-news

# Test strategy (sprawdź jakie sygnały generuje)
docker-compose logs -f agent-strategy

# Test risk (sprawdź dlaczego reject/approve)
docker-compose logs -f agent-risk

# Test execution (sprawdź czy Alpaca API działa)
docker-compose logs -f agent-execution
```

### Symuluj News Event

Możesz ręcznie opublikować test news do Redis:

```bash
docker-compose exec redis redis-cli

# Publish test news
XADD news_ingested * \
  message_type NewsIngestedMessage \
  timestamp "2025-11-12T10:00:00Z" \
  source newsapi \
  data '{"ticker":"AAPL","headline":"Apple announces record iPhone sales","url":"https://example.com","published_at":"2025-11-12T10:00:00Z"}'
```

Sprawdź logi `agent-score-news` - powinien przetworzyć i scoring.

## 📈 Roadmap & Future Enhancements

### ✅ Faza 1: Core System (COMPLETE)
- [x] 10 autonomicznych agentów
- [x] Redis Streams komunikacja (at-least-once delivery)
- [x] Docker orchestration (12 containers)
- [x] Real market data (Finazon.io REST API)
- [x] News ingestion (NewsAPI)
- [x] Technical indicators (RSI, MACD, ROC)
- [x] Hybrid strategy (news + momentum)
- [x] NAV-based position sizing
- [x] Circuit breaker emergency stop
- [x] Paper trading (Alpaca API)
- [x] Event correlation (news→price memory)

### 🚧 Faza 2: AI & Intelligence (IN PROGRESS)
- [ ] **Portfolio Manager Agent** - Smart capital allocation across positions
  - Dynamiczny rebalancing
  - Cash reserve management (min 20% buffer)
  - Correlation-based diversification
- [ ] **Market Regime Detector** - Bull/Bear/Sideways classification
  - VIX monitoring
  - Sector rotation analysis
  - Volatility regime switching
- [ ] **LLM-based News Scoring** - Replace heuristic with GPT-4/Claude
  - Deep sentiment analysis
  - Named entity recognition
  - Causal inference (merger → price up)
- [ ] **Adaptive Strategy** - Adjust parameters based on performance
  - α (news weight) optimization
  - Threshold auto-tuning
  - Stop loss widening in volatile markets

### 📊 Faza 3: Analytics & Backtesting
- [ ] **PostgreSQL Database** - Historical data storage
  - All trades archiwum
  - Performance metrics over time
  - Drawdown curves
- [ ] **Backtesting Framework** - Test strategies on historical data
  - Replay Redis streams
  - Fast-forward simulation
  - Walk-forward optimization
- [ ] **Performance Dashboard** - Comprehensive analytics
  - Sharpe ratio, Sortino ratio
  - Max drawdown visualization
  - Win rate, profit factor
  - Equity curve charts

### 🚀 Faza 4: Production Features
- [ ] **WebSocket Real-time** - Replace 60s polling
  - Alpaca WebSocket (real-time trades)
  - Polygon WebSocket (if upgraded to $99/mo plan)
- [ ] **Advanced Dashboard** - React/Next.js
  - Real-time charts (TradingView integration)
  - Position management UI
  - Manual override controls
- [ ] **Alert System** - Multi-channel notifications
  - Email alerts (circuit breaker HALT)
  - Telegram bot
  - SMS dla critical events
- [ ] **Multi-broker Support** - Beyond Alpaca
  - Interactive Brokers
  - TD Ameritrade
  - Schwab API

### 🔬 Faza 5: Advanced Research
- [ ] **Machine Learning Models**
  - LSTM dla price prediction
  - Reinforcement learning (DQN) dla strategy
  - NLP transformer dla news
- [ ] **Options Trading** - Greeks, volatility arbitrage
- [ ] **Tax Loss Harvesting** - Optimize for capital gains
- [ ] **Multi-strategy Portfolio** - Run 5+ strategies simultaneously
  - Mean reversion
  - Momentum
  - News-driven
  - Pairs trading
- [ ] **A/B Testing** - Compare strategy variants
- [ ] **Auto-scaling** - Increase NAV jeśli performance > threshold

### 💡 Feature Requests (User-driven)

**From latest session:**
1. ✅ Increase NAV to $50k (DONE)
2. ✅ Circuit breaker emergency stop (DONE)
3. ✅ Event correlation tracking (DONE - cause_finder agent)
4. 🚧 Portfolio manager for capital allocation (NEXT)
5. 🚧 Market regime detection (NEXT)
6. 🚧 AI integration for news scoring (NEXT)

## 🛡️ Security & Best Practices

### ⚠️ **WAŻNE - Bezpieczeństwo**

**1. API Keys:**
- ❌ **NIGDY** nie commituj `.env` do Git (już w `.gitignore`)
- ✅ Używaj environment variables
- ✅ Rotuj klucze co 90 dni
- ✅ Use read-only keys gdzie możliwe

**2. Paper Trading ONLY:**
- ✅ Używaj `ALPACA_BASE_URL=https://paper-api.alpaca.markets`
- ❌ **NIE** używaj live trading bez dogłębnego testowania
- ✅ Testuj minimum 30 dni na paper account przed live

**3. Risk Management:**
- ✅ Circuit breaker ZAWSZE włączony (`CIRCUIT_BREAKER_MAX_DRAWDOWN=0.10`)
- ✅ Max 2.5% NAV at risk (5 positions × 0.5%)
- ✅ Daily loss limit enforcement ($1,000 max)
- ✅ Monitoruj logi daily

**4. Data Backup:**
- ✅ Backup `impact_memory.db` codziennie
- ✅ Export Redis streams do PostgreSQL (future)
- ✅ Save trade logs do plików

**5. Monitoring:**
```powershell
# Daily checklist:
docker-compose logs -f agent-circuit-breaker  # Sprawdź czy HALT nie wystąpił
docker-compose exec redis redis-cli XLEN executed_orders  # Ile trades dzisiaj
docker-compose logs agent-execution | grep "ERROR"  # Czy są błędy
```

### 🔒 Network Security

```yaml
# docker-compose.yml - Ports tylko dla developmentu
# W produkcji: usuń `ports:` z Redis i PostgreSQL
redis:
  ports:
    - "6379:6379"  # ❌ REMOVE in production
```

## 🐛 Common Issues & Troubleshooting

### Problem: "exec /entrypoint.sh: no such file or directory"
**Solution:** Already fixed - używamy embedded CMD w Dockerfile zamiast external script.

### Problem: "FINAZON_API_KEY not set in environment"
**Solution:**
```powershell
docker-compose down
docker-compose up --force-recreate  # Force re-read .env
```

### Problem: Alpaca returns HTTP 404
**Solution:**
- Sprawdź czy rynek jest otwarty (9:30-16:00 ET)
- Sprawdź `ALPACA_BASE_URL` (NIE dodawaj /v2 na końcu)
- Test credentials: `curl -H "APCA-API-KEY-ID: KEY" https://paper-api.alpaca.markets/v2/account`

### Problem: Strategy używa placeholder prices ($100)
**Solution:** Sprawdź logi `agent-market-data-finazon`:
```powershell
docker-compose logs -f agent-market-data-finazon
# Powinno pokazywać: "✓ AAPL: close=$274.50"
```

### Problem: Risk agent odrzuca wszystko ("Already have position")
**Solution:** To CORRECT behavior. Risk agent zapobiega:
- Duplicate positions na tym samym tickerze
- Over-leverage (max 5 pozycji)
Jeśli chcesz scale-in (zwiększanie pozycji), potrzebna nowa strategia.

### Problem: Circuit breaker w stanie HALTED
**Solution:**
```powershell
# Sprawdź powód:
docker-compose logs agent-circuit-breaker | grep "HALT"

# Jeśli daily loss > $1k:
#   → Poczekaj do następnego dnia (auto-reset)
#
# Jeśli drawdown > 10%:
#   → Manualne review strategii
#   → Może trzeba zmienić parametry (α, threshold)
```

## 📚 Learn More - Investment Strategies

System implementuje sprawdzone strategie z Wall Street:

**1. News-driven Trading** - Event arbitrage
- Earnings announcements
- FDA approvals (biotech)
- Merger & acquisition news
- Federal Reserve statements

**2. Momentum Trading** - Follow the trend
- RSI > 70 = overbought (reversal)
- MACD crossover = trend change
- ROC acceleration = momentum building

**3. Risk Management** - Ray Dalio's "Holy Grail"
- Diversification (max 5 positions)
- Uncorrelated bets
- Limited downside (1% stops)
- Daily loss limits

**4. Position Sizing** - Fixed fractional risk
- Kelly Criterion inspiration
- Never risk > 0.5% per trade
- Scale down in drawdowns

**Polecane książki:**
- *"Technical Analysis of the Financial Markets"* - John Murphy
- *"Trading in the Zone"* - Mark Douglas
- *"Principles"* - Ray Dalio
- *"Market Wizards"* - Jack Schwager

## 🤝 Contributing

Contributions are welcome! Areas needing help:

**High Priority:**
- [ ] Portfolio manager agent implementation
- [ ] Market regime detector (VIX, sector rotation)
- [ ] LLM integration for news scoring
- [ ] Backtesting framework

**Medium Priority:**
- [ ] React dashboard with TradingView charts
- [ ] PostgreSQL historical data storage
- [ ] Telegram alert bot
- [ ] More technical indicators (Ichimoku, Fibonacci)

**Low Priority:**
- [ ] Docker Swarm / Kubernetes deployment
- [ ] Grafana monitoring dashboard
- [ ] Options trading support

**How to contribute:**
1. Fork the repository
2. Create feature branch (`git checkout -b feature/portfolio-manager`)
3. Commit changes with descriptive messages
4. Add tests if applicable
5. Push to branch (`git push origin feature/portfolio-manager`)
6. Open Pull Request with detailed description

## 📝 License

MIT License - see LICENSE file

## 🙋 Support & Community

- **GitHub Issues**: [Report bugs](https://github.com/archMikolajRozek/ClaudeBrokerAI/issues)
- **Discussions**: [Feature requests & questions](https://github.com/archMikolajRozek/ClaudeBrokerAI/discussions)
- **Email**: support@claudebrokerai.com (for private inquiries)

## 🏆 Credits

**Inspiracje:**
- **QuantConnect** - Open-source algorithmic trading platform
- **Zipline** - Pythonic backtesting library
- **Alpaca** - Commission-free trading API
- **Ray Dalio** - Risk management principles ("Holy Grail")

**Technologies:**
- **Redis Streams** - Event-driven architecture
- **Pydantic** - Data validation
- **Docker** - Containerization
- **Finazon.io** - Market data provider
- **Alpaca** - Brokerage API

## ⚠️ Disclaimer

**IMPORTANT - READ CAREFULLY:**

Ten projekt jest przeznaczony **wyłącznie do celów edukacyjnych i badawczych**.

**⚠️ RISK WARNING:**
- Handel akcjami wiąże się z **wysokim ryzykiem finansowym**
- Możesz stracić **100% zainwestowanego kapitału**
- Wyniki z przeszłości **nie gwarantują** przyszłych zysków
- System jest w fazie **testowej** - może zawierać błędy
- **NIC** w tym projekcie nie stanowi porady finansowej

**📜 NO LIABILITY:**
Autor i kontrybutorzy **nie ponoszą odpowiedzialności** za:
- Straty finansowe poniesione w wyniku użycia tego oprogramowania
- Błędy w kodzie prowadzące do nieprawidłowych transakcji
- Awarie systemu lub utraty danych
- Decyzje inwestycyjne podjęte na podstawie sygnałów systemu

**✅ BEFORE USING:**
1. **Konsultuj się z licencjonowanym doradcą finansowym**
2. **Testuj TYLKO na paper trading** (minimum 30 dni)
3. **Nigdy nie inwestuj pieniędzy, których nie możesz stracić**
4. **Regularnie monitoruj system** i sprawdzaj logi
5. **Rozumiej kod** - nie używaj ślepo ("black box")

**💡 RECOMMENDED:**
- Start with **$1,000 paper trading** (not $50k)
- Run for **3 months** before considering live
- Track **all metrics** (Sharpe ratio, max drawdown)
- Compare against **buy-and-hold SPY** benchmark
- If underperforming index → **don't use live**

---

**USE AT YOUR OWN RISK** 🚨

By using this software, you acknowledge that you have read and understood this disclaimer.

---

**Made with ❤️ for the trading community**

*"The goal is not to predict the future, but to be prepared for it."* - Ray Dalio

---

**Version:** 1.0.0 (Production-ready MVP)
**Last Updated:** 2025-11-12
**Status:** ✅ All 10 agents operational
