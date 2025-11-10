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

class RawNewsMessage(BaseModel):
    """Wiadomość z agenta ingest_news"""
    title: str
    content: str
    source: str
    url: str
    published_at: str
    tickers: List[str] = Field(default_factory=list)
    metadata: Optional[Dict[str, Any]] = None


class ScoredNewsMessage(BaseModel):
    """Wiadomość z agenta score_news"""
    title: str
    content: str
    source: str
    url: str
    published_at: str
    tickers: List[str]
    sentiment_score: float = Field(..., ge=-1.0, le=1.0, description="Sentyment: -1 (negatywny) do 1 (pozytywny)")
    impact_score: float = Field(..., ge=0.0, le=1.0, description="Przewidywany wpływ na cenę")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Pewność predykcji")
    scored_at: str
    metadata: Optional[Dict[str, Any]] = None


# ============================================================================
# MARKET DATA SCHEMAS
# ============================================================================

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


# ============================================================================
# TRADING SIGNAL SCHEMAS
# ============================================================================

class TradingSignal(BaseModel):
    """Sygnał handlowy z agenta strategy"""
    ticker: str
    signal: str = Field(..., description="BUY, SELL, HOLD")
    confidence: float = Field(..., ge=0.0, le=1.0)
    price: float = Field(..., description="Cena sygnału")
    quantity: int = Field(..., description="Sugerowana ilość")
    reason: str = Field(..., description="Powód sygnału")
    timestamp: str
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    metadata: Optional[Dict[str, Any]] = None


class ApprovedSignal(BaseModel):
    """Zatwierdzony sygnał z agenta risk"""
    ticker: str
    signal: str
    confidence: float
    price: float
    quantity: int
    adjusted_quantity: int = Field(..., description="Ilość dostosowana przez risk management")
    reason: str
    risk_approved: bool
    risk_reason: str
    risk_score: float = Field(..., ge=0.0, le=1.0)
    assessed_at: str
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    metadata: Optional[Dict[str, Any]] = None


# ============================================================================
# EXECUTION SCHEMAS
# ============================================================================

class ExecutionResult(BaseModel):
    """Wynik wykonania transakcji z agenta execution"""
    order_id: str
    ticker: str
    signal: str = Field(..., description="BUY, SELL")
    quantity: int
    executed_price: float
    status: str = Field(..., description="FILLED, PARTIAL, REJECTED, PENDING, CANCELLED")
    executed_at: str
    commission: float = Field(default=0.0)
    slippage: float = Field(default=0.0, description="Różnica między ceną oczekiwaną a wykonaną")
    error_message: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


# ============================================================================
# SHOCK DETECTION SCHEMAS
# ============================================================================

class ShockAlert(BaseModel):
    """Alert o anomalii rynkowej z agenta shock_detector"""
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
    NEWS_RAW = "news:raw"
    NEWS_SCORED = "news:scored"
    MARKET_DATA = "market:data"
    SIGNALS_TRADING = "signals:trading"
    SIGNALS_APPROVED = "signals:approved"
    EXECUTIONS_COMPLETED = "executions:completed"
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
