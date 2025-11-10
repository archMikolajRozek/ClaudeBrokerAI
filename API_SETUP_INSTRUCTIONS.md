# API Keys - Instrukcje Rejestracji i Konfiguracji

Przewodnik krok po kroku jak zdobyć **DARMOWE** klucze API dla wszystkich serwisów używanych przez AI Portfolio Manager.

---

## 📊 Market Data API (Real-Time Quotes)

### Opcja 1: Polygon.io (ZALECANE dla developmentu)

**Co daje:**
- Real-time stock quotes (z 15-min delay na free tier)
- 1-min candle bars
- Websocket streaming
- 5 requests/min na free tier

**Koszty:**
- **FREE Tier**: Delayed data (15 min), 5 req/min - **WYSTARCZAJĄCE DO TESTÓW**
- Starter: $99/mo - Real-time, unlimited

**Kroki rejestracji:**

1. **Wejdź na:** https://polygon.io/

2. **Kliknij** "Get Free API Key" lub "Sign Up"

3. **Zarejestruj się** (email + hasło)

4. **Potwierdź email** (sprawdź skrzynkę)

5. **Dashboard → API Keys**
   - Skopiuj swój API key (format: `xxxxxxxxxxxxxxxxxxxxxxxxxxx`)

6. **Wklej do `.env`:**
   ```bash
   POLYGON_API_KEY=twój_klucz_tutaj
   ```

7. **Ustaw provider:**
   ```bash
   MARKET_DATA_PROVIDER=polygon
   ```

**Test połączenia:**
```bash
# Testuj w terminalu
curl "https://api.polygon.io/v2/aggs/ticker/AAPL/range/1/minute/2023-01-09/2023-01-09?apiKey=TWOJ_KLUCZ"
```

---

### Opcja 2: Alpaca (BACKUP lub jeśli wolisz Alpaca)

**Co daje:**
- Real-time IEX data (free - ~2% market volume)
- SIP data (paid - all exchanges)
- Paper trading account (fake money)
- Websocket streaming

**Koszty:**
- **FREE**: IEX data + paper trading - **WYSTARCZAJĄCE DO TESTÓW**
- Unlimited: $99/mo - SIP consolidated data

**Kroki rejestracji:**

1. **Wejdź na:** https://alpaca.markets/

2. **Kliknij** "Sign Up" → wybierz **"Paper Trading Only"** (nie potrzebujesz prawdziwego konta)

3. **Wypełnij formularz:**
   - Imię, nazwisko, email
   - **NIE** musisz podawać SSN ani danych bankowych dla paper trading

4. **Potwierdź email**

5. **Dashboard → API Keys (Paper Trading)**
   - Wygeneruj nowy key (jeśli nie ma)
   - Skopiuj:
     - API Key
     - Secret Key

6. **Wklej do `.env`:**
   ```bash
   ALPACA_API_KEY=twój_api_key
   ALPACA_API_SECRET=twój_secret_key
   ALPACA_BASE_URL=https://paper-api.alpaca.markets
   ```

7. **Ustaw provider:**
   ```bash
   MARKET_DATA_PROVIDER=alpaca
   ```

**Test połączenia:**
```bash
# Testuj w terminalu
curl -X GET "https://paper-api.alpaca.markets/v2/account" \
  -H "APCA-API-KEY-ID: TWOJ_KEY" \
  -H "APCA-API-SECRET-KEY: TWOJ_SECRET"
```

---

## 📰 News API (Wiadomości Finansowe)

### NewsAPI.org

**Co daje:**
- Wiadomości finansowe ze 150+ źródeł
- Real-time news stream
- 100 requests/day na free tier

**Koszty:**
- **FREE**: 100 req/day - **WYSTARCZAJĄCE DO TESTÓW**
- Developer: $449/mo - Unlimited

**Kroki rejestracji:**

1. **Wejdź na:** https://newsapi.org/

2. **Kliknij** "Get API Key"

3. **Zarejestruj się** (email + użyj FREE planu)

4. **Skopiuj API Key** z dashboardu

5. **Wklej do `.env`:**
   ```bash
   NEWS_API_KEY=twój_klucz_tutaj
   ```

**Test:**
```bash
curl "https://newsapi.org/v2/everything?q=AAPL&apiKey=TWOJ_KLUCZ"
```

---

## 🤖 AI API (Sentiment Analysis - OPCJONALNE)

System działa z keyword-based sentiment analysis (bez AI API), ale możesz dodać AI dla lepszych wyników.

### Opcja A: OpenAI (GPT-3.5/GPT-4)

**Koszty:**
- Pay-as-you-go (no monthly fee)
- GPT-3.5-turbo: ~$0.001 per request
- **~$1-5/month** dla testów

**Kroki:**

1. **Wejdź na:** https://platform.openai.com/

2. **Sign Up** → potwierdź email

3. **Dodaj kartę kredytową** (wymagane, ale opłaty pay-as-you-go)

4. **API Keys** → Create new key

5. **Wklej do `.env`:**
   ```bash
   OPENAI_API_KEY=sk-proj-xxxxxxxxxxxxxxxxxxxx
   ```

**Uwaga:** Agent `score_news` używa tylko keyword analysis domyślnie. AI API jest opcjonalne.

---

### Opcja B: Anthropic Claude (Alternatywa dla OpenAI)

**Koszty:**
- Pay-as-you-go
- Claude 3 Haiku: ~$0.001 per request

**Kroki:**

1. **Wejdź na:** https://console.anthropic.com/

2. **Sign Up** → Email + phone

3. **Dodaj kartę** (wymagane)

4. **API Keys** → Create key

5. **Wklej do `.env`:**
   ```bash
   ANTHROPIC_API_KEY=sk-ant-xxxxxxxxxxxxxxxxxxxxx
   ```

---

## 🏦 Broker API (Paper Trading - OPCJONALNE dla testów)

Używany tylko przez `execution` agent. Możesz go pominąć na początku (agent ma symulację).

### Alpaca Paper Trading (już masz jeśli zarejestrowałeś się wyżej)

Keys są te same co dla market data.

---

## ✅ Szybka Konfiguracja - Minimum dla Startu

**Absolutne minimum żeby system działał:**

```bash
# Redis (lokalnie, bez klucza)
docker run -d -p 6379:6379 redis:7-alpine

# Market Data (wybierz JEDNO)
POLYGON_API_KEY=twój_klucz    # LUB
ALPACA_API_KEY=...            # LUB pomiń (system użyje symulacji)

# News (opcjonalne, system ma keyword fallback)
NEWS_API_KEY=twój_klucz       # Opcjonalne
```

**Zalecana konfiguracja dla testów (100% FREE):**

1. ✅ **Polygon.io FREE tier** → market data (15-min delayed)
2. ✅ **NewsAPI.org FREE tier** → newsy (100/day)
3. ❌ Skip OpenAI/Anthropic → użyj keyword sentiment
4. ❌ Skip Alpaca broker → użyj symulację execution

**Łączny koszt:** $0/miesiąc 🎉

---

## 📝 Pełny `.env` File - Template

Skopiuj to do `.env` i wypełnij swoje klucze:

```bash
# ============================================================================
# WYMAGANE
# ============================================================================

# Redis (lokalny Docker - bez klucza)
REDIS_URL=redis://localhost:6379

# Market Data - WYBIERZ JEDNO:

# Opcja 1: Polygon.io (ZALECANE)
POLYGON_API_KEY=twój_polygon_klucz_tutaj
MARKET_DATA_PROVIDER=polygon

# Opcja 2: Alpaca
#ALPACA_API_KEY=twój_alpaca_key
#ALPACA_API_SECRET=twój_alpaca_secret
#MARKET_DATA_PROVIDER=alpaca

# ============================================================================
# OPCJONALNE (system działa bez tego)
# ============================================================================

# News API (opcjonalne - system ma keyword fallback)
NEWS_API_KEY=twój_newsapi_klucz

# AI Sentiment (opcjonalne - domyślnie keyword-based)
#OPENAI_API_KEY=sk-proj-xxxxx
#ANTHROPIC_API_KEY=sk-ant-xxxxx

# Broker dla execution (opcjonalne - domyślnie symulacja)
#ALPACA_API_KEY=twój_key
#ALPACA_API_SECRET=twój_secret

# ============================================================================
# PARAMETRY TRADING (możesz zostawić defaults)
# ============================================================================

WATCHLIST=AAPL,MSFT,GOOGL,AMZN,TSLA,META,NVDA
NEWS_DECAY_TAU_HOURS=0.5
RISK_NAV=10000.0
STRATEGY_STOP_LOSS_PCT=0.01
STRATEGY_TAKE_PROFIT_PCT=0.02
```

---

## 🧪 Testowanie Po Konfiguracji

### 1. Test Redis:
```bash
docker ps  # Sprawdź czy Redis działa
redis-cli ping  # Powinno zwrócić PONG
```

### 2. Test Market Data Agent:
```bash
cd agents/market_data
python main.py

# Powinno wypisać:
# [market_data] Initialized
# [market_data] Provider: polygon
# [PolygonWS] Connected to wss://socket.polygon.io/stocks
# [PolygonWS] ✓ Authentication successful
```

### 3. Test Newsów:
```bash
cd agents/ingest_news
python main.py

# Sprawdź czy pobiera newsy
```

### 4. Sprawdź Redis Streams:
```bash
redis-cli
> XLEN market_candles
> XREAD COUNT 1 STREAMS market_candles 0-0
```

---

## ❓ Troubleshooting

### "Authentication failed" - Polygon
- Sprawdź czy klucz jest poprawnie skopiowany (bez spacji)
- Upewnij się że klucz jest aktywny (sprawdź dashboard)
- Free tier ma limit 5 req/min - nie przekraczaj

### "Connection error" - Websocket
- Sprawdź firewall (musi przepuszczać wss://)
- Spróbuj z innej sieci (czasem corporate firewall blokuje)

### "No data received"
- Polygon FREE tier ma 15-min delay - poczekaj
- Sprawdź czy ticker jest na NYSE/NASDAQ (nie crypto)
- Sprawdź czy to godziny sesji (9:30-16:00 EST)

### "Rate limit exceeded"
- Polygon FREE: max 5 req/min
- NewsAPI FREE: max 100 req/day
- Zmniejsz częstotliwość (NEWS_FETCH_INTERVAL=600 zamiast 300)

---

## 💡 Wskazówki

1. **Zacznij od Polygon FREE** - najprostszy setup, wystarczy na testy

2. **Pomiń AI API na początku** - keyword sentiment działa OK

3. **Użyj paper trading Alpaca** - bezpieczne testy bez ryzyka

4. **Monitoruj limity** - FREE tier ma ograniczenia, ale wystarczają

5. **Upgrade później** - gdy system działa, możesz upgrade'ować do paid

---

## 📞 Support

**Polygon.io:** support@polygon.io lub Discord: https://polygon.io/discord
**Alpaca:** support@alpaca.markets lub Slack: https://alpaca.markets/slack
**NewsAPI:** support@newsapi.org

---

**Gotowe! Masz wszystkie klucze? Przejdź do RUNNING_GUIDE.md żeby uruchomić system.** 🚀
