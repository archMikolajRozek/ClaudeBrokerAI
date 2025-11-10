# Market Data Agent - Real-Time Streaming

Agent pobierający dane rynkowe w czasie rzeczywistym przez websocket.

## 🎯 Co robi ten agent?

**Zadanie:** Streaming 1-minutowych świec (OHLCV) z Polygon.io lub Alpaca do Redis

**Architektura:**
```
Polygon.io Websocket → Market Data Agent → Redis Stream (market_candles)
                ↓
        Oblicza log returns
        Normalizuje dane
        Publikuje do Redis
```

## ⚙️ Konfiguracja

### 1. Wybierz Provider w `.env`:

```bash
# Opcja 1: Polygon.io (ZALECANE)
POLYGON_API_KEY=twój_klucz
MARKET_DATA_PROVIDER=polygon

# Opcja 2: Alpaca (backup)
ALPACA_API_KEY=twój_key
ALPACA_API_SECRET=twój_secret
MARKET_DATA_PROVIDER=alpaca
```

### 2. Ustaw Watchlist:

```bash
# Ticker'y do monitorowania (comma-separated)
WATCHLIST=AAPL,MSFT,GOOGL,AMZN,TSLA,META,NVDA
```

### 3. Redis:

```bash
# Domyślnie localhost
REDIS_URL=redis://localhost:6379
```

## 🚀 Uruchomienie

### Lokalnie:

```bash
# 1. Zainstaluj dependencies
pip install -r requirements.txt

# 2. Uruchom Redis
docker run -d -p 6379:6379 redis:7-alpine

# 3. Skonfiguruj .env (skopiuj z .env.example)
cp ../../.env.example ../../.env
# Edytuj .env i dodaj POLYGON_API_KEY lub ALPACA_API_KEY

# 4. Uruchom agenta
python main.py
```

**Powinno wypisać:**
```
[market_data] Initialized
  Provider: polygon
  Watchlist: ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'TSLA', 'META', 'NVDA']
[market_data] ✓ Connected to Redis
[PolygonWS] Connected to wss://socket.polygon.io/stocks
[PolygonWS] ✓ Authentication successful
[PolygonWS] Subscribed to 7 tickers: ['AAPL', 'MSFT', ...]
[market_data] 🚀 Starting real-time market data stream...
[market_data] Streaming 7 tickers
```

### Docker:

```bash
# Agent już skonfigurowany w docker-compose.yml
docker-compose up agent-market-data
```

## 📊 Output Format

Agent publikuje do Redis stream: `market_candles`

**Message Schema: MarketCandleMessage**
```json
{
  "ticker": "AAPL",
  "open": 150.25,
  "high": 151.50,
  "low": 150.00,
  "close": 151.00,
  "volume": 125000,
  "timestamp": "2025-11-10T14:30:00Z",
  "returns": 0.0049  // log(close/prev_close)
}
```

## 🧪 Testowanie

### Sprawdź czy działa:

```bash
# W innym terminalu:
redis-cli

# Sprawdź ile wiadomości w stream
> XLEN market_candles

# Przeczytaj ostatnie 5 świec
> XREVRANGE market_candles + - COUNT 5

# Monitor w czasie rzeczywistym
> XREAD BLOCK 0 STREAMS market_candles $
```

### Oczekiwany output:

Podczas sesji (9:30-16:00 EST) powinny napływać nowe świece co ~60 sekund dla każdego ticker'a.

## 🔧 Klasy i Funkcje - Opis

### PolygonWebsocketClient

**Cel:** Klient websocket dla Polygon.io API

**Metody:**
- `connect()` - Łączy się z wss://socket.polygon.io/stocks i autoryzuje
- `subscribe(tickers)` - Subskrybuje ticker'y (format: "AM.AAPL")
- `listen()` - Infinite loop odbierający wiadomości
- `process_bar(bar_data)` - Przetwarza odebraną świecę i wywołuje callback
- `close()` - Zamyka połączenie

**Callback:** `on_bar_callback(ticker, bar_data)` wywoływany dla każdej nowej świecy

### AlpacaWebsocketClient

**Cel:** Backup klient dla Alpaca API (podobna struktura co Polygon)

**URL:** wss://stream.data.alpaca.markets/v2/iex (IEX data - free)

**Metody:** Takie same jak PolygonWebsocketClient

### MarketDataAgent

**Cel:** Główny agent zarządzający websocket i Redis

**Atrybuty:**
- `redis_client` - Połączenie z Redis
- `ws_client` - Aktywny websocket client (Polygon lub Alpaca)
- `last_close_prices` - Cache zamknięć do obliczenia returns
- `provider` - Wybrany provider ("polygon" lub "alpaca")
- `watchlist` - Lista ticker'ów do streamowania

**Metody:**
- `connect_redis()` - Połącz z Redis
- `connect_market_data()` - Utwórz i połącz websocket client
- `on_new_bar(ticker, bar_data)` - **CALLBACK** wywoływany dla każdej świecy:
  1. Oblicza log returns = ln(close/prev_close)
  2. Tworzy MarketCandleMessage (Pydantic schema)
  3. Publikuje do Redis stream: market_candles
  4. Loguje (jeśli duży ruch lub co 10 świec)
- `run()` - Główna pętla: connect → listen → infinite loop

**Flow:**
```
run()
 ├─> connect_redis()
 ├─> connect_market_data()
 │    ├─> PolygonWebsocketClient(on_bar_callback=on_new_bar)
 │    └─> ws_client.connect() → subscribe() → listen()
 └─> ws_client.listen() // Infinite loop
      └─> For each bar → process_bar() → on_new_bar()
           └─> Publish to Redis
```

## 📈 Log Returns - Dlaczego?

**Formuła:** `returns = ln(close_t / close_{t-1})`

**Zalety log returns:**
1. **Addytywne** - można sumować przez czas
2. **Symetryczne** - +10% i -10% nie daje 0% (w regular returns daje)
3. **Lepsze dla volatility** - łatwiej modelować dystrybucję
4. **Standard w finance** - używane w większości modeli

**Przykład:**
```
Cena: $100 → $110 → $100
Log returns: +0.0953 → -0.1054 = -0.0101 (strata ~1%)
Regular returns: +10% → -9.09% = +0.91% (zysk? błąd!)
```

## 🐛 Troubleshooting

### "Authentication failed"
- Sprawdź czy POLYGON_API_KEY jest w .env
- Upewnij się że klucz jest aktywny (polygon.io dashboard)

### "No data received"
- **Polygon FREE** ma 15-min delay - dane napływają z opóźnieniem
- Sprawdź czy to godziny sesji: 9:30-16:00 EST (14:30-21:00 CET)
- Weekendy/święta - brak danych

### "Connection closed"
- Sprawdź internet
- Firewall może blokować websocket (wss://)
- Polygon FREE ma limit 5 conn/min - nie restartuj za często

### "Redis connection error"
- Upewnij się że Redis działa: `redis-cli ping` → PONG
- Sprawdź REDIS_URL w .env

## 📚 Więcej Info

- **Polygon API Docs:** https://polygon.io/docs/stocks/ws_stocks_am
- **Alpaca API Docs:** https://alpaca.markets/docs/api-references/market-data-api/stock-pricing-data/realtime/
- **Redis Streams Tutorial:** https://redis.io/docs/data-types/streams/

## 💡 Następne Kroki

Po uruchomieniu market_data agent, uruchom kolejne agenty:

1. ✅ **market_data** - ← Jesteś tutaj
2. **momentum** - Oblicza RSI, MACD z candles
3. **strategy** - Generuje trade proposals
4. **risk** - Waliduje ryzyk
5. **execution** - Wykonuje zlecenia

**Sprawdź:** RUNNING_GUIDE.md dla pełnego workflow

---

**Gotowy do streamingu! 📊** Uruchom `python main.py` i obserwuj świece w Redis! 🚀
