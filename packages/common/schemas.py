"""
JSON Schemas for inter-agent communication
Definicje struktur wiadomości przesyłanych przez Redis Streams.
"""

from typing import List, Optional, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field


# ============================================================================
# NEWS SCHEMAS
# ============================================================================

class NewsIngestedMessage(BaseModel):
    """Wiadomość z agenta ingest_news - znormalizowany news"""
    ticker: str = Field(..., description="Symbol akcji (np. AAPL)")
    datetime: str = Field(..., description="Data i czas newsa (ISO format)")
    headline: str = Field(..., description="Nagłówek wiadomości")
    body: str = Field(..., description="Treść wiadomości")
    sentiment: float = Field(..., ge=-1.0, le=1.0, description="Sentyment: -1 (negatywny) do 1 (pozytywny)")
    impact: float = Field(..., ge=0.0, le=1.0, description="Przewidywany wpływ na cenę (0-1)")
    relevance: float = Field(..., ge=0.0, le=1.0, description="Relevancja dla tickera (0-1)")
    source: Optional[str] = Field(None, description="Źródło newsa")
    url: Optional[str] = Field(None, description="URL do pełnego artykułu")


class NewsScoredMessage(BaseModel):
    """Wiadomość z agenta score_news - news z decay factor"""
    ticker: str = Field(..., description="Symbol akcji")
    score: float = Field(..., description="Adjusted impact = sentiment * impact * decay_factor")
    timestamp: str = Field(..., description="Timestamp obliczenia score (ISO format)")
    decay_factor: float = Field(..., ge=0.0, le=1.0, description="exp(-Δt / tau)")
    relevance: float = Field(..., ge=0.0, le=1.0, description="Relevancja dla tickera")
    original_sentiment: Optional[float] = Field(None, description="Oryginalny sentiment przed decay")
    original_impact: Optional[float] = Field(None, description="Oryginalny impact przed decay")
    news_datetime: Optional[str] = Field(None, description="Oryginalny datetime newsa")
    headline: Optional[str] = Field(None, description="Nagłówek dla referencji")


# ============================================================================
# MARKET DATA SCHEMAS
# ============================================================================

class MarketMomentumMessage(BaseModel):
    """Wiadomość z momentum score (placeholder dla przyszłego agenta)"""
    ticker: str = Field(..., description="Symbol akcji")
    momentum_score: float = Field(..., description="Momentum score (może być ujemny)")
    timestamp: str = Field(..., description="Timestamp obliczenia")
    price: Optional[float] = Field(None, description="Aktualna cena")
    metadata: Optional[Dict[str, Any]] = None

class TechnicalIndicators(BaseModel):
    """Wskaźniki techniczne"""
    rsi: Optional[float] = Field(None, description="Relative Strength Index")
    macd: Optional[float] = Field(None, description="MACD")
    macd_signal: Optional[float] = None
    sma_20: Optional[float] = Field(None, description="Simple Moving Average 20")
    sma_50: Optional[float] = Field(None, description="Simple Moving Average 50")
    sma_200: Optional[float] = Field(None, description="Simple Moving Average 200")
    ema_12: Optional[float] = None
    ema_26: Optional[float] = None
    bollinger_upper: Optional[float] = None
    bollinger_lower: Optional[float] = None
    atr: Optional[float] = Field(None, description="Average True Range")


class MarketDataMessage(BaseModel):
    """Wiadomość z agenta market_data"""
    ticker: str
    price: float
    volume: int
    change_pct: float = Field(..., description="Zmiana procentowa")
    high: float
    low: float
    open: float
    timestamp: str
    indicators: Optional[TechnicalIndicators] = None
    metadata: Optional[Dict[str, Any]] = None


class MarketCandleMessage(BaseModel):
    """1-minutowa świeca dla shock detection"""
    ticker: str = Field(..., description="Symbol akcji")
    open: float
    high: float
    low: float
    close: float
    volume: int
    timestamp: str = Field(..., description="Timestamp zamknięcia świecy")
    returns: Optional[float] = Field(None, description="Log returns (close/prev_close)")


class MarketShockEvent(BaseModel):
    """Wykryte wydarzenie szokowe na rynku"""
    ticker: str = Field(..., description="Symbol akcji")
    shock_type: str = Field(..., description="PRICE_SPIKE, PRICE_DROP, VOLUME_SPIKE")
    detected_at: str = Field(..., description="Timestamp wykrycia")
    price: float = Field(..., description="Cena w momencie wykrycia")
    z_score: float = Field(..., description="Z-score zwrotu (ile std od średniej)")
    volume_percentile: Optional[float] = Field(None, description="Percentyl wolumenu")
    returns: float = Field(..., description="Zwrot w % który wywołał shock")
    severity: float = Field(..., ge=0.0, le=1.0, description="Severity 0-1")
    metadata: Optional[Dict[str, Any]] = None


# ============================================================================
# STRATEGY AGENT SCHEMAS
# ============================================================================

class TradeProposal(BaseModel):
    """Propozycja trade z agenta strategy"""
    ticker: str = Field(..., description="Symbol akcji")
    side: str = Field(..., description="BUY lub SELL")
    entry: float = Field(..., description="Cena wejścia")
    stop: float = Field(..., description="Stop loss")
    take_profit: float = Field(..., description="Take profit")
    rationale: str = Field(..., description="Uzasadnienie sygnału")
    alpha: float = Field(..., ge=0.0, le=1.0, description="Waga news score w formule")
    combined_score: float = Field(..., description="S = α * score_news + (1-α) * score_mom")
    news_score: Optional[float] = Field(None, description="Score z news")
    momentum_score: Optional[float] = Field(None, description="Score z momentum")
    timestamp: str = Field(..., description="Timestamp propozycji")
    metadata: Optional[Dict[str, Any]] = None


# ============================================================================
# RISK AGENT SCHEMAS
# ============================================================================

class ApprovedTrade(BaseModel):
    """Zatwierdzony trade z agenta risk"""
    ticker: str
    side: str
    entry: float
    stop: float
    take_profit: float
    quantity: int = Field(..., description="Ilość akcji do zakupu/sprzedaży")
    risk_amount: float = Field(..., description="Kwota ryzyka w USD")
    risk_pct: float = Field(..., description="% NAV ryzykowane")
    rationale: str
    timestamp: str
    approved_at: str
    metadata: Optional[Dict[str, Any]] = None


class RejectedTrade(BaseModel):
    """Odrzucony trade z agenta risk"""
    ticker: str
    side: str
    entry: float
    rejection_reason: str = Field(..., description="Powód odrzucenia")
    timestamp: str
    rejected_at: str
    metadata: Optional[Dict[str, Any]] = None


# ============================================================================
# EXECUTION SCHEMAS
# ============================================================================

class ExecutedOrder(BaseModel):
    """Wykonane zlecenie z agenta execution"""
    order_id: str = Field(..., description="Unikalny ID zlecenia")
    ticker: str
    side: str = Field(..., description="BUY lub SELL")
    quantity: int
    entry_price: float = Field(..., description="Cena oczekiwana")
    executed_price: float = Field(..., description="Cena wykonania")
    stop: float
    take_profit: float
    status: str = Field(..., description="FILLED, PARTIAL, REJECTED, PENDING")
    executed_at: str
    commission: float = Field(default=0.0)
    slippage: float = Field(default=0.0, description="Różnica entry vs executed")
    error_message: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


# ============================================================================
# SHOCK DETECTION & CAUSE ATTRIBUTION SCHEMAS
# ============================================================================

class ShockAlert(BaseModel):
    """Alert o anomalii rynkowej z agenta shock_detector (legacy)"""
    ticker: str
    shock_type: str = Field(..., description="PRICE_SHOCK, VOLUME_SHOCK, VOLATILITY_SPIKE, CORRELATION_BREAK")
    severity: float = Field(..., ge=0.0, le=1.0)
    price: float
    change_pct: float
    volume: int
    detected_at: str
    message: str
    recommended_action: Optional[str] = Field(None, description="HALT_TRADING, REDUCE_EXPOSURE, MONITOR")
    metadata: Optional[Dict[str, Any]] = None


class CauseAttribution(BaseModel):
    """Przypisana przyczyna dla shock event (z cause_finder)"""
    event_id: str = Field(..., description="ID wydarzenia szokowego")
    ticker: str
    shock_type: str
    shock_detected_at: str
    cause_type: str = Field(..., description="NEWS, EARNINGS, MACRO, TECHNICAL, UNKNOWN")
    cause_text: str = Field(..., description="Opis przyczyny")
    cause_source: Optional[str] = Field(None, description="Źródło (np. news headline)")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Pewność przypisania")
    impact_strength: float = Field(..., ge=0.0, le=1.0, description="Siła wpływu")
    time_delta_minutes: float = Field(..., description="Ile minut między newsem a shockiem")
    attributed_at: str = Field(..., description="Timestamp przypisania")
    metadata: Optional[Dict[str, Any]] = None


# ============================================================================
# REDIS STREAM ENVELOPE
# ============================================================================

class StreamMessage(BaseModel):
    """Uniwersalna koperta dla wiadomości Redis Stream"""
    agent: str = Field(..., description="Nazwa agenta wysyłającego")
    timestamp: str
    data: Dict[str, Any] = Field(..., description="Właściwe dane wiadomości")
    message_type: Optional[str] = Field(None, description="Typ wiadomości dla deserializacji")


# ============================================================================
# REDIS STREAM NAMES
# ============================================================================

class StreamNames:
    """Nazwy Redis Streams używane w systemie"""
    NEWS_INGESTED = "news_ingested"
    NEWS_SCORED = "news_scored"
    MARKET_MOMENTUM = "market_momentum"
    MARKET_CANDLES = "market_candles"
    MARKET_SHOCKS = "market_shocks"
    TRADE_PROPOSALS = "trade_proposals"
    APPROVED_TRADES = "approved_trades"
    REJECTED_TRADES = "rejected_trades"
    EXECUTED_ORDERS = "executed_orders"
    MARKET_DATA = "market:data"
    ALERTS_SHOCKS = "alerts:shocks"


# ============================================================================
# CONSUMER GROUPS
# ============================================================================

class ConsumerGroups:
    """Nazwy Consumer Groups dla Redis Streams"""
    SCORE_NEWS = "score_news_group"
    STRATEGY = "strategy_group"
    RISK = "risk_group"
    EXECUTION = "execution_group"
    SHOCK_DETECTOR = "shock_detector_group"
