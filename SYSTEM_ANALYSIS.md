# AI Portfolio Manager - Analiza Systemu i Rekomendacje

**Data:** 2025-11-10
**Cel:** Weryfikacja zgodności z wymaganiami + optymalizacja dla intraday trading

---

## 📊 ANALIZA: Co mamy vs Co powinno być

### ✅ Zaimplementowane Komponenty (GOTOWE)

| Komponent | Status | Funkcjonalność | Zgodność z wymaganiami |
|-----------|--------|----------------|------------------------|
| **ingest_news** | ✅ **READY** | Pobieranie newsów z NewsAPI, normalizacja, sentiment analysis | ✅ Zgodne z wymaganiami |
| **score_news** | ✅ **READY** | Decay factor (exp(-Δt/tau)), time-weighted scoring | ✅ Zgodne z wymaganiami |
| **strategy** | ✅ **READY** | Kombinacja news + momentum → TradeProposal | ✅ Zgodne z wymaganiami |
| **risk** | ✅ **READY** | NAV-based position sizing, walidacja limitów | ✅ Zgodne z wymaganiami |
| **execution** | ⚠️ **PLACEHOLDER** | Symulacja brokera (nie IB API) | ⚠️ Wymaga integracji z IB |
| **shock_detector** | ✅ **READY** | Z-score anomaly detection, volume spike detection | ✅ Zgodne z wymaganiami |
| **cause_finder** | ✅ **READY** | Korelacja szoków z newsami, SQLite persistence | ✅ Zgodne z wymaganiami |
| **FastAPI Backend** | ✅ **READY** | REST API: /proposals, /approve, /executed, /risk-summary | ✅ Zgodne z HITL panel |
| **Streamlit UI** | ✅ **READY** | Dashboard z approve/reject, risk monitoring | ✅ Zgodne z HITL panel |
| **Redis Streams** | ✅ **READY** | Async komunikacja między agentami | ✅ Zgodne z wymaganiami |
| **Docker Compose** | ✅ **READY** | Orkiestracja wszystkich serwisów | ✅ Zgodne z wymaganiami |
| **PostgreSQL** | ✅ **READY** | Baza danych (skonfigurowana, nie wykorzystana) | ⚠️ Wymaga integracji |

---

### ❌ Brakujące/Niekompletne Komponenty

| Komponent | Status | Co brakuje | Priorytet |
|-----------|--------|------------|-----------|
| **market_data agent** | ⚠️ **SKELETON** | Tylko placeholder, brak real-time data feed | 🔴 **KRYTYCZNY** |
| **momentum agent** | ❌ **BRAK** | Nie ma dedykowanego agenta momentum | 🔴 **KRYTYCZNY** |
| **IB API Integration** | ❌ **BRAK** | Brak Interactive Brokers Client Portal API | 🔴 **KRYTYCZNY** |
| **Real-time candles** | ❌ **BRAK** | Brak 1-min/5-min candle streaming | 🔴 **KRYTYCZNY** |
| **Technical indicators** | ⚠️ **PLACEHOLDER** | RSI, MACD, SMA są placeholderami | 🟡 **WAŻNY** |
| **Flat overnight enforcement** | ❌ **BRAK** | Brak automatycznego zamykania pozycji przed EOD | 🟡 **WAŻNY** |
| **PostgreSQL integration** | ❌ **BRAK** | Baza nie jest używana (tylko Redis) | 🟢 **ŚREDNI** |
| **Learning Loop** | ❌ **BRAK** | Brak systemu uczenia z wykonanych transakcji | 🟢 **ŚREDNI** |
| **Position tracking** | ⚠️ **PARTIAL** | Tracking tylko w risk agent, brak persistence | 🟡 **WAŻNY** |
| **Real P&L calculation** | ❌ **BRAK** | Brak śledzenia realized/unrealized P&L | 🟡 **WAŻNY** |
| **Multi-broker support** | ❌ **BRAK** | Tylko IB (+ placeholder ALT) | 🟢 **NISKI** |

---

## 🚨 Luki Krytyczne dla Intraday Trading

### 1. **Brak Real-Time Market Data Feed** 🔴
**Problem:**
- Agent `market_data` ma tylko placeholder z fake data
- Brak streaming z Interactive Brokers
- Brak 1-min candles dla intraday

**Wpływ:**
- System nie może działać w czasie rzeczywistym
- Sygnały są generowane na fake danych
- Niemożliwe jest intraday trading

**Rozwiązanie:** → Patrz sekcja "Rekomendowane zmiany" poniżej

---

### 2. **Brak Dedykowanego Agenta Momentum** 🔴
**Problem:**
- Agent `strategy` łączy news + momentum, ale momentum_score jest placeholderem
- Brak obliczania rzeczywistych wskaźników technicznych
- Brak momentum agenta jak w specyfikacji

**Wpływ:**
- Sygnały oparte tylko na news (nie hybrid NEWS-GATE + MOMENTUM)
- Brak analizy technicznej

**Rozwiązanie:** → Patrz sekcja "Rekomendowane zmiany" poniżej

---

### 3. **Brak Interactive Brokers API Integration** 🔴
**Problem:**
- Agent `execution` używa symulowanego brokera
- Brak Client Portal API / TWS API
- Niemożliwe wykonanie rzeczywistych zleceń

**Wpływ:**
- System działa tylko w trybie symulacji
- Brak możliwości paper trading
- Brak możliwości live trading

**Rozwiązanie:** → Patrz sekcja "Rekomendowane zmiany" poniżej

---

### 4. **Brak Flat Overnight Enforcement** 🟡
**Problem:**
- Brak mechanizmu automatycznego zamykania pozycji przed końcem sesji
- Brak time-based triggers (np. 15:55 EST → close all)
- Risk agent nie egzekwuje polityki overnight

**Wpływ:**
- Ryzyko overnight gaps
- Naruszenie założenia "flat overnight"
- Potencjalne straty z powodu newsów after-hours

**Rozwiązanie:**
```python
# W risk agent lub nowym scheduler agent:
- Monitor czasu (15:50 EST)
- Generuj sygnały CLOSE dla wszystkich otwartych pozycji
- Blokuj nowe propozycje BUY/SELL po 15:55
- Force close wszystko o 15:58
```

---

### 5. **Brak Persistence Pozycji i P&L** 🟡
**Problem:**
- PostgreSQL skonfigurowany ale nie używany
- Pozycje tracone przy restarcie agentów
- Brak historii transakcji w bazie
- Brak śledzenia realized/unrealized P&L

**Wpływ:**
- Brak audytu transakcji
- Niemożliwe backtesting
- Brak learning loop
- Restart = utrata stanu portfela

**Rozwiązanie:** → Patrz sekcja "Rekomendowane zmiany" poniżej

---

## 🎯 Rekomendowane Zmiany - PRIORYTETYZACJA

### 🔴 PRIORYTET 1: Krytyczne dla działania (1-2 tygodnie)

#### 1.1 **Implementacja Real-Time Market Data**
```
Agent: market_data
Źródło danych: Interactive Brokers TWS API lub Polygon.io (backup)
Funkcjonalność:
  - Streaming 1-min candles dla watchlist
  - Real-time L1 quotes (bid/ask/last)
  - Volume tracking
  - Publikacja do market_candles stream

Technologie:
  - ib_insync dla IB TWS API
  - websocket dla Polygon.io
  - Async streaming z Redis

Schemat danych:
  - MarketCandleMessage (już zdefiniowany w schemas.py)
  - Frequency: 1-min bars
  - Latency target: < 500ms
```

**Implementacja:**
```python
# agents/market_data/main.py
from ib_insync import IB, util
import asyncio

class IBMarketDataAgent:
    def __init__(self):
        self.ib = IB()
        self.watchlist = ["AAPL", "MSFT", ...]

    async def connect_ib(self):
        await self.ib.connectAsync('127.0.0.1', 7497, clientId=1)

    async def stream_bars(self, ticker):
        contract = Stock(ticker, 'SMART', 'USD')
        bars = await self.ib.reqHistoricalDataAsync(
            contract,
            endDateTime='',
            durationStr='1 D',
            barSizeSetting='1 min',
            whatToShow='TRADES',
            useRTH=True,
            keepUpToDate=True  # Real-time updates
        )

        for bar in bars:
            await self.publish_candle(ticker, bar)
```

**Estymacja:** 3-5 dni

---

#### 1.2 **Dedykowany Agent Momentum z Technical Indicators**
```
Agent: momentum (NOWY)
Input: market_candles stream
Output: market_momentum stream
Funkcjonalność:
  - Obliczanie wskaźników: RSI, MACD, Bollinger Bands, ATR
  - Momentum score: -1 (bearish) do +1 (bullish)
  - Sliding window (20-50 bars)
  - Real-time update

Algorytm momentum score:
  S_momentum = normalize(
    w1 * RSI_signal +
    w2 * MACD_signal +
    w3 * BB_signal +
    w4 * Price_momentum
  )

Biblioteki:
  - pandas_ta lub ta-lib
  - numpy dla sliding windows
```

**Implementacja:**
```python
# agents/momentum/main.py
import pandas_ta as ta

class MomentumAgent:
    def __init__(self):
        self.candle_windows = defaultdict(list)  # ticker -> list of candles
        self.window_size = 50

    async def process_candle(self, candle: MarketCandleMessage):
        # Add to window
        self.candle_windows[candle.ticker].append(candle)

        # Keep only last N
        if len(self.candle_windows[candle.ticker]) > self.window_size:
            self.candle_windows[candle.ticker].pop(0)

        # Calculate indicators
        df = self.build_dataframe(candle.ticker)
        rsi = ta.rsi(df['close'], length=14).iloc[-1]
        macd = ta.macd(df['close']).iloc[-1]

        # Generate momentum score
        momentum_score = self.calculate_momentum_score(rsi, macd, ...)

        # Publish
        await self.publish_momentum(candle.ticker, momentum_score)
```

**Estymacja:** 3-4 dni

---

#### 1.3 **Interactive Brokers API Integration**
```
Agent: execution
API: IB Client Portal Gateway API (REST) lub TWS API (ib_insync)
Funkcjonalność:
  - Składanie market orders
  - Składanie limit orders
  - Tracking order status
  - Cancellation support
  - Position reconciliation

Wybór API:
  - TWS API (ib_insync): Lepsze dla low-latency, wymaga TWS running
  - Client Portal API: REST, nie wymaga TWS, ale wyższe latency

Dla intraday: TWS API (ib_insync)
```

**Implementacja:**
```python
# agents/execution/ib_broker.py
from ib_insync import IB, MarketOrder, LimitOrder

class IBBroker:
    def __init__(self):
        self.ib = IB()

    async def connect(self):
        await self.ib.connectAsync('127.0.0.1', 7497, clientId=2)

    async def place_order(self, trade: ApprovedTrade):
        contract = Stock(trade.ticker, 'SMART', 'USD')

        if trade.order_type == "MARKET":
            order = MarketOrder(
                action='BUY' if trade.side == 'BUY' else 'SELL',
                totalQuantity=trade.quantity
            )
        else:
            order = LimitOrder(
                action='BUY' if trade.side == 'BUY' else 'SELL',
                totalQuantity=trade.quantity,
                lmtPrice=trade.entry
            )

        trade_obj = self.ib.placeOrder(contract, order)

        # Wait for fill
        while not trade_obj.isDone():
            await asyncio.sleep(0.1)

        # Publish execution
        await self.publish_execution(trade_obj)
```

**Estymacja:** 5-7 dni (+ testy)

---

### 🟡 PRIORYTET 2: Ważne dla optymalizacji (1 tydzień)

#### 2.1 **Flat Overnight Enforcement**
```
Komponent: Nowy scheduler agent lub rozszerzenie risk agent
Funkcjonalność:
  - Monitor czasu sesji (9:30-16:00 EST)
  - Auto-close wszystkich pozycji o 15:55 EST
  - Blokada nowych pozycji po 15:50 EST
  - Alert jeśli pozycja nie została zamknięta do 15:58

Implementacja:
  - Pytz dla timezone handling (EST)
  - Cron-like scheduler (APScheduler)
  - Integration z risk agent
```

**Kod:**
```python
# agents/risk/flat_overnight.py
from apscheduler.schedulers.asyncio import AsyncIOScheduler
import pytz

class FlatOvernightEnforcer:
    def __init__(self, risk_agent):
        self.risk_agent = risk_agent
        self.scheduler = AsyncIOScheduler()
        self.est = pytz.timezone('US/Eastern')

    def start(self):
        # Codziennie o 15:50 EST
        self.scheduler.add_job(
            self.warn_close_positions,
            'cron',
            hour=15,
            minute=50,
            timezone=self.est
        )

        # Codziennie o 15:55 EST - force close
        self.scheduler.add_job(
            self.force_close_all,
            'cron',
            hour=15,
            minute=55,
            timezone=self.est
        )

        self.scheduler.start()

    async def force_close_all(self):
        positions = self.risk_agent.get_open_positions()
        for pos in positions:
            await self.risk_agent.close_position(pos, reason="FLAT_OVERNIGHT")
```

**Estymacja:** 2 dni

---

#### 2.2 **PostgreSQL Integration dla Persistence**
```
Schema design:
  - positions: aktualne pozycje (ticker, quantity, entry_price, pnl)
  - orders: historia zleceń (order_id, status, fill_price, timestamp)
  - trades: historia transakcji (trade_id, pnl, signals, rationale)
  - daily_pnl: dzienny P&L snapshot

ORM: SQLAlchemy (async)
Migration: Alembic

Persistence points:
  - Execution agent → orders table
  - Risk agent → positions table
  - EOD → daily_pnl snapshot
```

**Schema:**
```sql
CREATE TABLE positions (
    id SERIAL PRIMARY KEY,
    ticker VARCHAR(10) NOT NULL,
    quantity INT NOT NULL,
    side VARCHAR(4) CHECK (side IN ('LONG', 'SHORT')),
    entry_price DECIMAL(10, 2),
    current_price DECIMAL(10, 2),
    unrealized_pnl DECIMAL(10, 2),
    opened_at TIMESTAMP,
    updated_at TIMESTAMP
);

CREATE TABLE orders (
    id SERIAL PRIMARY KEY,
    order_id VARCHAR(50) UNIQUE,
    ticker VARCHAR(10),
    side VARCHAR(4),
    quantity INT,
    order_type VARCHAR(10),
    status VARCHAR(20),
    filled_price DECIMAL(10, 2),
    commission DECIMAL(10, 4),
    created_at TIMESTAMP,
    filled_at TIMESTAMP
);

CREATE TABLE daily_pnl (
    id SERIAL PRIMARY KEY,
    date DATE UNIQUE,
    realized_pnl DECIMAL(10, 2),
    unrealized_pnl DECIMAL(10, 2),
    total_pnl DECIMAL(10, 2),
    trades_count INT,
    win_rate DECIMAL(5, 2)
);
```

**Estymacja:** 3-4 dni

---

#### 2.3 **Real P&L Tracking**
```
Komponent: Rozszerzenie risk agent
Funkcjonalność:
  - Realized P&L (z wykonanych transakcji)
  - Unrealized P&L (z otwartych pozycji)
  - Position-level P&L
  - Daily P&L aggregation
  - Commission tracking
  - Slippage analysis

Integracja:
  - Subscribe do executed_orders
  - Subscribe do market_candles (dla current price)
  - Update positions w PostgreSQL
  - Publish do risk_metrics stream
```

**Implementacja:**
```python
class PnLTracker:
    def __init__(self, db_session):
        self.db = db_session
        self.positions = {}  # ticker -> Position

    async def process_fill(self, order: ExecutedOrder):
        if order.side == "BUY":
            # Open long or close short
            if order.ticker in self.positions and self.positions[order.ticker].side == "SHORT":
                # Close short
                pnl = self.calculate_close_pnl(self.positions[order.ticker], order)
                await self.record_realized_pnl(pnl)
                del self.positions[order.ticker]
            else:
                # Open long
                self.positions[order.ticker] = Position(
                    ticker=order.ticker,
                    side="LONG",
                    quantity=order.quantity,
                    entry_price=order.executed_price
                )
        # Similar for SELL...

    async def update_unrealized_pnl(self, candle: MarketCandleMessage):
        if candle.ticker in self.positions:
            pos = self.positions[candle.ticker]
            pos.current_price = candle.close
            pos.unrealized_pnl = (candle.close - pos.entry_price) * pos.quantity
            await self.db.update(pos)
```

**Estymacja:** 2-3 dni

---

### 🟢 PRIORYTET 3: Nice-to-have (1-2 tygodnie)

#### 3.1 **Learning Loop System**
```
Komponent: Nowy agent learning_loop
Funkcjonalność:
  - Zbieranie danych z wykonanych transakcji
  - Analiza accuracy sygnałów (news vs momentum)
  - Optymalizacja parametrów (alpha, thresholds)
  - A/B testing strategii

Algorytm:
  - Każdy trade → zapis (sygnały, parametry, wynik)
  - Co tydzień: analiza win rate per strategy
  - Gradient descent dla alpha parameter
  - Bayesian optimization dla thresholds
```

**Estymacja:** 1-2 tygodnie

---

#### 3.2 **Advanced Risk Metrics**
```
Metryki:
  - Sharpe Ratio (rolling)
  - Max Drawdown
  - Win Rate %
  - Average Win / Average Loss
  - Risk-adjusted returns
  - Correlation z S&P500

Dashboard:
  - Real-time charts w Streamlit
  - Historical performance
  - Equity curve
```

**Estymacja:** 3-5 dni

---

#### 3.3 **Multi-Timeframe Analysis**
```
Dla intraday trading:
  - 1-min bars: momentum signals
  - 5-min bars: trend confirmation
  - 15-min bars: broader context
  - Daily: trend filter (tylko long jeśli daily trend up)

Implementacja:
  - Market data agent publikuje multiple timeframes
  - Momentum agent agreguje
  - Strategy agent używa multi-TF confirmation
```

**Estymacja:** 4-6 dni

---

## 🚀 Specyficzne Wymagania dla Intraday Trading

### 1. **Latency Requirements**
```
Target latencies:
  - Market data → Redis: < 500ms
  - Signal generation: < 1s
  - Order execution: < 2s (from approval)
  - Total: News → Execution < 5s

Optymalizacje:
  - Redis pipelining
  - Async everywhere
  - Minimize cross-agent hops
  - Cache frequently accessed data
```

### 2. **Signal Frequency**
```
Dla intraday (9:30-16:00):
  - Market data: 1-min bars = 390 bars/day/ticker
  - News: realtime stream (może być 0-50/day)
  - Signals: expect 5-20 signals/day
  - Trades: 2-8 executed trades/day (after filtering)

Throughput requirements:
  - Market data: 10 tickers × 390 bars = 3,900 msgs/day
  - Redis: ~10k messages/day total
  - PostgreSQL: ~100 writes/day
```

### 3. **Stop Loss & Take Profit Management**
```
KRYTYCZNE dla intraday:
  - Tight stops (0.5-2% from entry)
  - Quick take profits (1-4% target)
  - Trailing stops po osiągnięciu 50% TP
  - Time-based exits (jeśli po 30 min brak ruchu → close)

Implementacja:
  - Nowy agent: stop_loss_manager
  - Subscribe do market_candles
  - Monitor każdej pozycji
  - Auto-trigger close orders
```

**Kod:**
```python
class StopLossManager:
    async def monitor_position(self, position):
        while position.is_open:
            current_price = await self.get_current_price(position.ticker)

            # Check stop loss
            if position.side == "LONG":
                if current_price <= position.stop:
                    await self.close_position(position, "STOP_LOSS")

                # Check take profit
                if current_price >= position.take_profit:
                    await self.close_position(position, "TAKE_PROFIT")

                # Trailing stop (jeśli w zysku)
                if current_price > position.entry * 1.02:  # 2% profit
                    new_stop = max(position.stop, current_price * 0.99)
                    position.stop = new_stop
```

### 4. **Volume Filters**
```
Dla intraday KONIECZNE:
  - Minimum ADV (Average Daily Volume) > 1M shares
  - Minimum $ volume > $10M/day
  - Spread < 0.1% (tight bid-ask)

Powód:
  - Likwidność dla quick entry/exit
  - Minimize slippage
  - Avoid pump & dump

Implementacja w strategy agent:
  - Filter proposals z low volume tickers
  - Check spread przed approval
```

### 5. **News Staleness Filter**
```
Dla intraday:
  - Tylko newsy < 30 min: max weight
  - Newsy 30-60 min: decay 50%
  - Newsy > 60 min: ignore dla intraday

Obecny decay (tau=24h) jest ZA WOLNY dla intraday.

ZMIANA w score_news:
  tau_hours = 0.5  # 30 minut half-life dla intraday
  # vs obecne 24.0 hours
```

---

## 📋 PLAN IMPLEMENTACJI - Roadmap

### Tydzień 1-2: Krytyczne podstawy
- [ ] Real-time market data (IB TWS API)
- [ ] Momentum agent z technical indicators
- [ ] IB execution API integration

### Tydzień 3: Risk & persistence
- [ ] Flat overnight enforcement
- [ ] PostgreSQL integration
- [ ] P&L tracking

### Tydzień 4: Optymalizacje intraday
- [ ] Stop loss manager
- [ ] News staleness (tau adjustment)
- [ ] Volume filters
- [ ] Latency optimization

### Tydzień 5-6: Advanced features
- [ ] Learning loop
- [ ] Multi-timeframe analysis
- [ ] Advanced risk metrics
- [ ] Backtesting framework

---

## 🎯 QUICK WINS (1-2 dni każdy)

1. **Adjust news decay tau dla intraday**
   ```python
   # agents/score_news/main.py
   # Zmień:
   tau_hours = float(os.getenv("NEWS_DECAY_TAU_HOURS", "0.5"))  # było 24.0
   ```

2. **Dodaj volume filter do strategy**
   ```python
   # agents/strategy/main.py
   MIN_VOLUME = 1_000_000
   if proposal.volume < MIN_VOLUME:
       return None  # Skip low volume
   ```

3. **Dodaj time-of-day filter**
   ```python
   # Nie generuj sygnałów po 15:50 EST
   from datetime import datetime
   import pytz

   now_est = datetime.now(pytz.timezone('US/Eastern'))
   if now_est.hour >= 15 and now_est.minute >= 50:
       return None  # Too late for new positions
   ```

4. **Tighter stop losses dla intraday**
   ```python
   # agents/strategy/main.py
   # Zmień:
   stop_pct = 0.01  # 1% stop (było 2%)
   tp_pct = 0.02    # 2% TP (było 4%)
   ```

---

## ✅ CHECKLIST - Co działa, co wymaga naprawy

### Architektura ✅
- [x] Multi-agent design
- [x] Redis Streams komunikacja
- [x] Docker orchestration
- [x] Async/await everywhere
- [x] Pydantic schemas

### Data Pipeline ⚠️
- [x] News ingestion
- [x] News scoring
- [ ] **Real-time market data** ← BRAK
- [ ] **Technical indicators** ← PLACEHOLDER
- [x] Shock detection

### Trading Logic ⚠️
- [x] Hybrid signals (news + momentum)
- [ ] **Real momentum calculation** ← BRAK
- [x] Position sizing
- [x] Risk limits
- [ ] **Flat overnight** ← BRAK
- [ ] **Stop loss management** ← BRAK

### Execution ❌
- [ ] **IB API integration** ← PLACEHOLDER
- [ ] **Order tracking** ← PARTIAL
- [ ] **Position reconciliation** ← BRAK

### Monitoring ✅
- [x] HITL panel (Streamlit)
- [x] REST API
- [x] Proposal approval
- [x] Risk summary
- [ ] **P&L tracking** ← BRAK
- [ ] **Performance metrics** ← BRAK

### Persistence ⚠️
- [x] Redis (ephemeral)
- [ ] **PostgreSQL** ← NIE UŻYWANE
- [x] SQLite (tylko dla impact memory)

---

## 🔥 KRYTYCZNE UWAGI - Must-fix przed production

1. **Market data MUSI być real-time** - obecny placeholder uniemożliwia działanie
2. **IB API MUSI być zintegrowany** - bez tego brak execution
3. **Flat overnight MUSI być enforced** - inaczej overnight risk
4. **P&L tracking MUSI być persistent** - bez tego brak audytu
5. **Stop losses MUSZĄ być monitored** - inaczej unlimited risk

---

## 📊 ESTYMACJA CZASU - Total

| Faza | Czas | Wynik |
|------|------|-------|
| **Faza 1: Minimum Viable** | 2 tygodnie | Paper trading ready |
| **Faza 2: Production Ready** | +2 tygodnie | Live trading capable |
| **Faza 3: Optimized** | +2 tygodnie | Full features |
| **TOTAL** | **6 tygodni** | Production-grade system |

---

## 🎓 PODSUMOWANIE

### Co mamy: ✅
- Solidną architekturę multi-agentową
- Działający news pipeline
- Shock detection
- HITL panel
- Docker orchestration

### Co brakuje: ❌
- Real-time market data
- Momentum agent
- IB API integration
- Flat overnight
- P&L tracking

### Co zrobić najpierw: 🔴
1. **Market data + IB API** (Tydzień 1-2)
2. **Momentum agent** (Tydzień 2)
3. **Flat overnight + P&L** (Tydzień 3)

### Czy system jest gotowy do użycia?
**NIE** - wymaga implementacji krytycznych komponentów (market data + IB API).

**Ale:** Architektura jest prawidłowa i można szybko dodać brakujące elementy.

---

**Następny krok:** Chcesz, żebym zaimplementował któryś z priorytetowych komponentów? Mogę zacząć od:
- Real-time market data agent (IB TWS)
- Momentum agent z indicators
- Flat overnight enforcer
- PostgreSQL integration

Powiedz, od czego zaczynamy! 🚀
