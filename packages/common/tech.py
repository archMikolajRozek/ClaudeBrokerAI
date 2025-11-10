"""
Technical Indicators Library
Biblioteka wskaźników technicznych dla analizy momentum.

ZAWARTOŚĆ:
- EMA (Exponential Moving Average)
- SMA (Simple Moving Average)
- RSI (Relative Strength Index)
- MACD (Moving Average Convergence Divergence)
- Bollinger Bands
- ATR (Average True Range)
- Rate of Change (Momentum)

UŻYCIE:
Wszystkie funkcje przyjmują listę cen (List[float]) i zwracają wartość wskaźnika.
Dla smooth indicators (EMA, RSI) używamy Wilder smoothing.
"""

from typing import List, Tuple, Optional
import math


# ============================================================================
# MOVING AVERAGES
# ============================================================================

def sma(prices: List[float], period: int) -> Optional[float]:
    """
    Simple Moving Average (SMA)

    Średnia arytmetyczna z ostatnich N cen.

    Args:
        prices: Lista cen zamknięcia (najnowsza na końcu)
        period: Okres (np. 20 dla SMA20)

    Returns:
        Wartość SMA lub None jeśli za mało danych

    Przykład:
        prices = [100, 101, 102, 103, 104]
        sma(prices, 3) → (102 + 103 + 104) / 3 = 103.0
    """
    if len(prices) < period:
        return None

    # Weź ostatnie N cen i policz średnią
    recent_prices = prices[-period:]
    return sum(recent_prices) / period


def ema(prices: List[float], period: int, previous_ema: Optional[float] = None) -> Optional[float]:
    """
    Exponential Moving Average (EMA)

    Średnia ważona wykładniczo - nowsze ceny mają większą wagę.

    Formuła: EMA_t = price_t * k + EMA_{t-1} * (1-k)
    gdzie k = 2 / (period + 1)

    Args:
        prices: Lista cen (najnowsza na końcu)
        period: Okres (np. 12 dla EMA12)
        previous_ema: Poprzednia wartość EMA (opcjonalne, dla update)

    Returns:
        Wartość EMA lub None jeśli za mało danych

    Przykład:
        # Pierwsza kalkulacja (używa SMA jako seed)
        ema(prices, 12)

        # Update z nową ceną (szybsze, używa previous_ema)
        new_ema = ema([new_price], 12, previous_ema=last_ema)
    """
    if len(prices) < period and previous_ema is None:
        return None

    # Smoothing factor
    k = 2.0 / (period + 1)

    if previous_ema is None:
        # Pierwsza kalkulacja - użyj SMA jako seed
        previous_ema = sma(prices, period)
        if previous_ema is None:
            return None

        # Teraz oblicz EMA dla pozostałych cen
        for price in prices[period:]:
            previous_ema = price * k + previous_ema * (1 - k)

        return previous_ema
    else:
        # Update: mamy previous_ema, oblicz tylko dla ostatniej ceny
        current_price = prices[-1]
        return current_price * k + previous_ema * (1 - k)


# ============================================================================
# RSI (RELATIVE STRENGTH INDEX)
# ============================================================================

def rsi(prices: List[float], period: int = 14) -> Optional[float]:
    """
    Relative Strength Index (RSI)

    Oscylator momentum mierzący prędkość zmian cen (0-100).
    - RSI > 70: Overbought (przewartościowanie)
    - RSI < 30: Oversold (niedowartościowanie)

    Używa Wilder smoothing (EMA-like ale k = 1/period zamiast 2/(period+1)).

    Formuła:
        RS = avg_gain / avg_loss
        RSI = 100 - (100 / (1 + RS))

    Args:
        prices: Lista cen zamknięcia (min. period+1)
        period: Okres (standardowo 14)

    Returns:
        RSI w zakresie 0-100 lub None jeśli za mało danych

    Przykład:
        prices = [44, 44.34, 44.09, 43.61, 44.33, ...]
        rsi(prices, 14) → 65.23  (przykładowa wartość)
    """
    if len(prices) < period + 1:
        return None

    # Oblicz zmiany cen (deltas)
    deltas = [prices[i] - prices[i-1] for i in range(1, len(prices))]

    # Rozdziel na gains (dodatnie) i losses (ujemne)
    gains = [delta if delta > 0 else 0 for delta in deltas]
    losses = [-delta if delta < 0 else 0 for delta in deltas]

    # Pierwsza średnia (SMA jako seed)
    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period

    # Wilder smoothing dla pozostałych (k = 1/period)
    for i in range(period, len(gains)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period

    # Oblicz RSI
    if avg_loss == 0:
        return 100.0  # Brak strat = max overbought

    rs = avg_gain / avg_loss
    rsi_value = 100 - (100 / (1 + rs))

    return rsi_value


# ============================================================================
# MACD (MOVING AVERAGE CONVERGENCE DIVERGENCE)
# ============================================================================

def macd(
    prices: List[float],
    fast_period: int = 12,
    slow_period: int = 26,
    signal_period: int = 9
) -> Optional[Tuple[float, float, float]]:
    """
    MACD - Moving Average Convergence Divergence

    Oscylator momentum używający różnicy EMA.
    - MACD Line = EMA(fast) - EMA(slow)
    - Signal Line = EMA(MACD, signal_period)
    - Histogram = MACD - Signal

    Sygnały:
    - MACD > Signal: Bullish (kupuj)
    - MACD < Signal: Bearish (sprzedaj)
    - Histogram > 0: Momentum wzrostowe

    Args:
        prices: Lista cen zamknięcia
        fast_period: Okres szybkiej EMA (domyślnie 12)
        slow_period: Okres wolnej EMA (domyślnie 26)
        signal_period: Okres signal line (domyślnie 9)

    Returns:
        Tuple (macd_line, signal_line, histogram) lub None

    Przykład:
        macd_line, signal, hist = macd(prices, 12, 26, 9)
        if hist > 0:
            print("Bullish momentum")
    """
    if len(prices) < slow_period + signal_period:
        return None

    # Oblicz EMA fast i slow
    ema_fast = ema(prices, fast_period)
    ema_slow = ema(prices, slow_period)

    if ema_fast is None or ema_slow is None:
        return None

    # MACD Line = różnica EMA
    macd_line = ema_fast - ema_slow

    # Oblicz historyczne MACD values dla signal line
    # (potrzebujemy min. slow_period + signal_period punktów)
    macd_values = []

    # Zbuduj historię MACD
    for i in range(slow_period, len(prices)):
        ema_f = ema(prices[:i+1], fast_period)
        ema_s = ema(prices[:i+1], slow_period)
        if ema_f is not None and ema_s is not None:
            macd_values.append(ema_f - ema_s)

    if len(macd_values) < signal_period:
        return None

    # Signal Line = EMA z MACD values
    signal_line = ema(macd_values, signal_period)

    if signal_line is None:
        return None

    # Histogram = różnica
    histogram = macd_line - signal_line

    return (macd_line, signal_line, histogram)


# ============================================================================
# BOLLINGER BANDS
# ============================================================================

def bollinger_bands(
    prices: List[float],
    period: int = 20,
    num_std: float = 2.0
) -> Optional[Tuple[float, float, float]]:
    """
    Bollinger Bands

    Wstęgi wokół SMA mierzące volatility.
    - Middle Band = SMA(period)
    - Upper Band = Middle + (num_std * std_dev)
    - Lower Band = Middle - (num_std * std_dev)

    Sygnały:
    - Cena > Upper Band: Overbought
    - Cena < Lower Band: Oversold
    - Squeeze (wąskie wstęgi): Niska volatility, możliwy breakout

    Args:
        prices: Lista cen
        period: Okres SMA (domyślnie 20)
        num_std: Liczba odchyleń std (domyślnie 2)

    Returns:
        Tuple (lower_band, middle_band, upper_band) lub None

    Przykład:
        lower, middle, upper = bollinger_bands(prices, 20, 2)
        if prices[-1] > upper:
            print("Overbought - rozważ short")
    """
    if len(prices) < period:
        return None

    # Middle band = SMA
    middle_band = sma(prices, period)
    if middle_band is None:
        return None

    # Oblicz standard deviation
    recent_prices = prices[-period:]
    variance = sum((p - middle_band) ** 2 for p in recent_prices) / period
    std_dev = math.sqrt(variance)

    # Bands
    upper_band = middle_band + (num_std * std_dev)
    lower_band = middle_band - (num_std * std_dev)

    return (lower_band, middle_band, upper_band)


# ============================================================================
# ATR (AVERAGE TRUE RANGE)
# ============================================================================

def atr(
    highs: List[float],
    lows: List[float],
    closes: List[float],
    period: int = 14
) -> Optional[float]:
    """
    Average True Range (ATR)

    Mierzy volatility (zmienność) - średni zakres ruchu ceny.
    Używany do position sizing i stop loss placement.

    True Range = max(high - low, |high - prev_close|, |low - prev_close|)
    ATR = Wilder smoothed average of TR

    Args:
        highs: Lista high prices
        lows: Lista low prices
        closes: Lista close prices
        period: Okres (domyślnie 14)

    Returns:
        Wartość ATR lub None jeśli za mało danych

    Przykład:
        atr_val = atr(highs, lows, closes, 14)
        stop_loss = entry - (2 * atr_val)  # 2×ATR stop
    """
    if len(highs) < period + 1 or len(lows) < period + 1 or len(closes) < period + 1:
        return None

    # Oblicz True Range dla każdego okresu
    true_ranges = []

    for i in range(1, len(closes)):
        high = highs[i]
        low = lows[i]
        prev_close = closes[i-1]

        # True Range = max z 3 wartości
        tr = max(
            high - low,
            abs(high - prev_close),
            abs(low - prev_close)
        )
        true_ranges.append(tr)

    if len(true_ranges) < period:
        return None

    # Pierwsza ATR = średnia z pierwszych N TR
    current_atr = sum(true_ranges[:period]) / period

    # Wilder smoothing dla pozostałych
    for i in range(period, len(true_ranges)):
        current_atr = (current_atr * (period - 1) + true_ranges[i]) / period

    return current_atr


# ============================================================================
# MOMENTUM / RATE OF CHANGE
# ============================================================================

def momentum(prices: List[float], period: int = 20) -> Optional[float]:
    """
    Momentum / Rate of Change (ROC)

    Mierzy prędkość zmian ceny jako % zmiana względem N okresów temu.

    Formuła: ROC = ((price_t - price_{t-n}) / price_{t-n}) * 100

    Args:
        prices: Lista cen
        period: Okres lookback (domyślnie 20)

    Returns:
        ROC w procentach lub None

    Przykład:
        mom = momentum(prices, 20)
        if mom > 5:  # +5% w 20 okresów
            print("Strong upward momentum")
    """
    if len(prices) < period + 1:
        return None

    current_price = prices[-1]
    old_price = prices[-(period + 1)]

    if old_price == 0:
        return None

    # % zmiana
    roc = ((current_price - old_price) / old_price) * 100

    return roc


# ============================================================================
# MOMENTUM SCORE (NORMALIZED)
# ============================================================================

def momentum_score(
    prices: List[float],
    rsi_period: int = 14,
    macd_fast: int = 12,
    macd_slow: int = 26,
    macd_signal: int = 9,
    roc_period: int = 20
) -> Optional[float]:
    """
    Unified Momentum Score - kombinacja wskaźników znormalizowana do [-1, 1]

    Łączy sygnały z:
    - RSI (overbought/oversold)
    - MACD (direction)
    - Rate of Change (velocity)

    Formuła:
        rsi_norm = (RSI - 50) / 50  # -1 (oversold) do +1 (overbought)
        macd_norm = sign(histogram) * min(1, |histogram|/threshold)
        roc_norm = tanh(ROC / 10)  # smooth clamp

        score = (rsi_norm * 0.3) + (macd_norm * 0.4) + (roc_norm * 0.3)

    Args:
        prices: Lista cen zamknięcia (potrzebne min. ~50 punktów)
        rsi_period: Okres RSI (domyślnie 14)
        macd_fast/slow/signal: Parametry MACD
        roc_period: Okres momentum

    Returns:
        Score od -1 (strong bearish) do +1 (strong bullish) lub None

    Przykład:
        score = momentum_score(prices)
        if score > 0.6:
            print("Strong bullish momentum")
        elif score < -0.6:
            print("Strong bearish momentum")
    """
    if len(prices) < max(rsi_period, macd_slow, roc_period) + 10:
        return None

    # 1. RSI score (-1 do +1)
    rsi_val = rsi(prices, rsi_period)
    if rsi_val is None:
        return None

    # RSI: 0-100 → normalize do -1, +1
    # 50 = neutral, 0 = oversold (-1), 100 = overbought (+1)
    rsi_norm = (rsi_val - 50) / 50
    rsi_norm = max(-1, min(1, rsi_norm))  # Clamp

    # 2. MACD score
    macd_result = macd(prices, macd_fast, macd_slow, macd_signal)
    if macd_result is None:
        return None

    macd_line, signal_line, histogram = macd_result

    # Histogram > 0 = bullish, < 0 = bearish
    # Normalize przez threshold (np. typowy histogram ~0.5-2.0)
    macd_threshold = 1.0
    macd_norm = histogram / macd_threshold
    macd_norm = max(-1, min(1, macd_norm))  # Clamp

    # 3. Rate of Change score
    roc = momentum(prices, roc_period)
    if roc is None:
        return None

    # ROC: % zmiana, typ. -10% do +10% dla znaczących ruchów
    # Używamy tanh dla smooth normalization
    roc_norm = math.tanh(roc / 10.0)  # tanh(-inf, inf) → (-1, 1)

    # 4. Combined score (weighted average)
    # Wagi: RSI 30%, MACD 40%, ROC 30%
    combined_score = (
        rsi_norm * 0.3 +
        macd_norm * 0.4 +
        roc_norm * 0.3
    )

    return combined_score


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def normalize_to_range(value: float, min_val: float, max_val: float) -> float:
    """
    Normalize wartości do zakresu [-1, 1]

    Args:
        value: Wartość do znormalizowania
        min_val: Minimum zakresu
        max_val: Maximum zakresu

    Returns:
        Znormalizowana wartość w [-1, 1]
    """
    if max_val == min_val:
        return 0.0

    # Normalize do [0, 1]
    norm = (value - min_val) / (max_val - min_val)

    # Scale do [-1, 1]
    return (norm * 2) - 1


# ============================================================================
# EXAMPLE USAGE
# ============================================================================

if __name__ == "__main__":
    # Example prices (AAPL-like movement)
    test_prices = [
        150.0, 150.5, 151.0, 150.8, 151.2,
        151.5, 152.0, 151.8, 152.5, 153.0,
        152.8, 153.5, 153.2, 154.0, 154.5,
        154.2, 155.0, 154.8, 155.5, 156.0,
        155.8, 156.5, 156.2, 157.0, 157.5,
        157.2, 158.0, 157.8, 158.5, 159.0
    ]

    print("=== Technical Indicators Test ===\n")

    # SMA
    sma_20 = sma(test_prices, 20)
    print(f"SMA(20): {sma_20:.2f}")

    # EMA
    ema_12 = ema(test_prices, 12)
    print(f"EMA(12): {ema_12:.2f}")

    # RSI
    rsi_14 = rsi(test_prices, 14)
    print(f"RSI(14): {rsi_14:.2f}")

    # MACD
    macd_result = macd(test_prices, 12, 26, 9)
    if macd_result:
        macd_line, signal, hist = macd_result
        print(f"MACD: {macd_line:.3f}, Signal: {signal:.3f}, Hist: {hist:.3f}")

    # Momentum
    mom = momentum(test_prices, 20)
    print(f"Momentum(20): {mom:.2f}%")

    # Combined Momentum Score
    score = momentum_score(test_prices)
    if score is not None:
        print(f"\nMomentum Score: {score:.3f}")
        if score > 0.6:
            print("→ STRONG BULLISH")
        elif score > 0.3:
            print("→ Bullish")
        elif score < -0.6:
            print("→ STRONG BEARISH")
        elif score < -0.3:
            print("→ Bearish")
        else:
            print("→ Neutral")
