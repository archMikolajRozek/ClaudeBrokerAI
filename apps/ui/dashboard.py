"""
AI Portfolio Manager - Professional Trading Dashboard
Real-time portfolio monitoring, pozycje, P&L tracking, performance metrics

FEATURES:
- Live portfolio overview (NAV, P&L, positions)
- Detailed position table z unrealized P&L per position
- Performance metrics (win rate, Sharpe ratio, max drawdown)
- Real-time charts (equity curve, P&L, allocation)
- Live news feed z Redis
- System health monitoring
- Auto-refresh co 5 sekund
"""

import streamlit as st
import redis
import json
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Any
import os
from dotenv import load_dotenv
import time

load_dotenv()

# ============================================================================
# Configuration
# ============================================================================

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
STARTING_NAV = float(os.getenv("RISK_NAV", "50000.0"))

st.set_page_config(
    page_title="AI Portfolio Manager Pro",
    page_icon="💰",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for better styling
st.markdown("""
<style>
    .big-metric { font-size: 2.5rem; font-weight: bold; }
    .positive { color: #00FF00; }
    .negative { color: #FF0000; }
    .neutral { color: #FFFF00; }
    .position-row { padding: 10px; border-bottom: 1px solid #333; }
    .profit { background-color: rgba(0, 255, 0, 0.1); }
    .loss { background-color: rgba(255, 0, 0, 0.1); }
</style>
""", unsafe_allow_html=True)

# ============================================================================
# Redis Helper Functions
# ============================================================================

@st.cache_resource
def get_redis_client():
    """Get Redis client (cached)"""
    try:
        client = redis.from_url(REDIS_URL, decode_responses=True)
        client.ping()
        return client
    except Exception as e:
        st.error(f"❌ Redis connection failed: {e}")
        return None


def get_latest_from_stream(client, stream_name: str, count: int = 10) -> List[Dict]:
    """Pobierz ostatnie wiadomości ze streamu"""
    try:
        messages = client.xrevrange(stream_name, count=count)

        result = []
        for msg_id, msg_data in messages:
            # Deserialize data field (JSON string)
            if 'data' in msg_data:
                data = json.loads(msg_data['data'])
                data['_stream_id'] = msg_id
                result.append(data)

        return result
    except Exception as e:
        return []


def get_stream_length(client, stream_name: str) -> int:
    """Sprawdź długość streamu"""
    try:
        return client.xlen(stream_name)
    except:
        return 0


def get_latest_prices(client, tickers: List[str]) -> Dict[str, float]:
    """
    Pobierz aktualne ceny dla tickerów z market_candles stream

    Returns:
        Dict {ticker: price}
    """
    prices = {}

    try:
        # Pobierz ostatnie 100 candles (żeby mieć pewność że mamy wszystkie tickery)
        candles = get_latest_from_stream(client, "market_candles", count=100)

        # Dla każdego tickera, znajdź najnowszą świecę
        for candle in candles:
            ticker = candle.get('ticker')
            close_price = candle.get('close')

            if ticker and close_price and ticker not in prices:
                prices[ticker] = float(close_price)

    except Exception as e:
        st.sidebar.error(f"Error fetching prices: {e}")

    return prices


# ============================================================================
# Data Processing Functions
# ============================================================================

def calculate_position_pnl(position: Dict, current_price: float) -> Dict:
    """
    Oblicz P&L dla pozycji

    Args:
        position: Dict z kluczami: ticker, quantity, entry_price, side
        current_price: Aktualna cena rynkowa

    Returns:
        Dict z unrealized_pnl, unrealized_pnl_pct, current_value, cost_basis
    """
    quantity = position['quantity']
    entry_price = position['entry_price']
    side = position.get('side', 'BUY')

    # Cost basis (ile zapłaciliśmy)
    cost_basis = entry_price * quantity

    # Current value (ile jest warte teraz)
    current_value = current_price * quantity

    # P&L
    if side == 'BUY':
        unrealized_pnl = current_value - cost_basis
    else:  # SHORT
        unrealized_pnl = cost_basis - current_value

    unrealized_pnl_pct = (unrealized_pnl / cost_basis * 100) if cost_basis > 0 else 0

    return {
        'current_price': current_price,
        'current_value': current_value,
        'cost_basis': cost_basis,
        'unrealized_pnl': unrealized_pnl,
        'unrealized_pnl_pct': unrealized_pnl_pct
    }


def get_open_positions(client) -> List[Dict]:
    """
    Pobierz otwarte pozycje z executed_orders stream

    Filtruje tylko FILLED orders i grupuje po tickerach
    """
    executed_orders = get_latest_from_stream(client, "executed_orders", count=100)

    # Group by ticker - najnowszy order per ticker
    positions = {}

    for order in executed_orders:
        ticker = order.get('ticker')
        status = order.get('status', '')

        # Skip if not filled
        if status != 'FILLED' and status != 'PENDING':
            continue

        # Jeśli już mamy pozycję na tym tickerze, skip (chcemy najnowszą)
        if ticker in positions:
            continue

        quantity = order.get('quantity', 0)
        filled_price = order.get('filled_price', order.get('entry_price', 0))

        positions[ticker] = {
            'ticker': ticker,
            'quantity': quantity,
            'entry_price': filled_price,
            'side': order.get('side', 'BUY'),
            'entry_time': order.get('executed_at', order.get('timestamp', '')),
            'stop_loss': order.get('stop'),
            'take_profit': order.get('take_profit'),
            'order_id': order.get('order_id', '')
        }

    return list(positions.values())


def calculate_portfolio_stats(positions_with_pnl: List[Dict]) -> Dict:
    """Oblicz statystyki portfela"""
    if not positions_with_pnl:
        return {
            'total_positions': 0,
            'total_cost_basis': 0.0,
            'total_current_value': 0.0,
            'total_unrealized_pnl': 0.0,
            'total_unrealized_pnl_pct': 0.0
        }

    total_cost = sum(p['cost_basis'] for p in positions_with_pnl)
    total_value = sum(p['current_value'] for p in positions_with_pnl)
    total_pnl = sum(p['unrealized_pnl'] for p in positions_with_pnl)

    total_pnl_pct = (total_pnl / total_cost * 100) if total_cost > 0 else 0

    return {
        'total_positions': len(positions_with_pnl),
        'total_cost_basis': total_cost,
        'total_current_value': total_value,
        'total_unrealized_pnl': total_pnl,
        'total_unrealized_pnl_pct': total_pnl_pct
    }


def calculate_performance_metrics(client) -> Dict:
    """Oblicz performance metrics z historical data"""
    # TODO: Pobierz historical trades z PostgreSQL lub Redis
    # Na razie mock data

    executed_orders = get_latest_from_stream(client, "executed_orders", count=100)

    filled_orders = [o for o in executed_orders if o.get('status') == 'FILLED']

    total_trades = len(filled_orders)

    # Na razie proste metrics
    return {
        'total_trades': total_trades,
        'win_rate': 0.0,  # TODO: calculate from closed positions
        'profit_factor': 0.0,
        'sharpe_ratio': 0.0,
        'max_drawdown': 0.0,
        'max_drawdown_pct': 0.0,
        'best_trade': 0.0,
        'worst_trade': 0.0
    }


# ============================================================================
# UI Components
# ============================================================================

def render_header():
    """Render header z logo i timestamp"""
    col1, col2 = st.columns([3, 1])

    with col1:
        st.title("💰 AI Portfolio Manager Pro")
        st.caption("Real-time Portfolio Monitoring & Trading Dashboard")

    with col2:
        st.metric(
            label="🕒 Last Update",
            value=datetime.now().strftime("%H:%M:%S")
        )


def render_portfolio_overview(client):
    """Render głównych metrics portfolio"""
    st.subheader("📊 Portfolio Overview")

    # Get positions with current prices
    positions = get_open_positions(client)

    if not positions:
        st.info("No open positions")
        col1, col2, col3, col4 = st.columns(4)

        with col1:
            st.metric("💵 Current NAV", f"${STARTING_NAV:,.2f}")
        with col2:
            st.metric("📈 Total P&L", "$0.00", "0.00%")
        with col3:
            st.metric("💰 Available Cash", f"${STARTING_NAV:,.2f}")
        with col4:
            st.metric("📂 Open Positions", "0")

        return

    # Get current prices
    tickers = [p['ticker'] for p in positions]
    current_prices = get_latest_prices(client, tickers)

    # Calculate P&L for each position
    positions_with_pnl = []
    for pos in positions:
        ticker = pos['ticker']
        current_price = current_prices.get(ticker, pos['entry_price'])

        pnl_data = calculate_position_pnl(pos, current_price)
        positions_with_pnl.append({**pos, **pnl_data})

    # Calculate portfolio stats
    stats = calculate_portfolio_stats(positions_with_pnl)

    # Current NAV = starting NAV + unrealized P&L
    current_nav = STARTING_NAV + stats['total_unrealized_pnl']
    total_pnl_pct = (stats['total_unrealized_pnl'] / STARTING_NAV * 100)
    available_cash = current_nav - stats['total_current_value']

    # Display metrics
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        delta_nav = current_nav - STARTING_NAV
        st.metric(
            "💵 Current NAV",
            f"${current_nav:,.2f}",
            f"${delta_nav:,.2f}"
        )

    with col2:
        pnl_color = "normal" if stats['total_unrealized_pnl'] >= 0 else "inverse"
        st.metric(
            "📈 Total Unrealized P&L",
            f"${stats['total_unrealized_pnl']:,.2f}",
            f"{total_pnl_pct:.2f}%",
            delta_color=pnl_color
        )

    with col3:
        st.metric(
            "💰 Available Cash",
            f"${available_cash:,.2f}",
            f"{(available_cash/current_nav*100):.1f}%"
        )

    with col4:
        st.metric(
            "📂 Open Positions",
            f"{stats['total_positions']}",
            f"${stats['total_current_value']:,.0f} invested"
        )

    # Store in session state for charts
    st.session_state['current_nav'] = current_nav
    st.session_state['positions_with_pnl'] = positions_with_pnl
    st.session_state['portfolio_stats'] = stats


def render_positions_table(client):
    """
    Render szczegółowej tabeli pozycji - GŁÓWNA FUNKCJA!
    To jest to co user najbardziej chce zobaczyć
    """
    st.subheader("📋 Open Positions - Detailed View")

    positions_with_pnl = st.session_state.get('positions_with_pnl', [])

    if not positions_with_pnl:
        st.info("No open positions to display")
        return

    # Sort by unrealized P&L (best performing first)
    positions_with_pnl.sort(key=lambda x: x['unrealized_pnl'], reverse=True)

    # Create DataFrame for display
    df_data = []
    for pos in positions_with_pnl:
        # Calculate time in position
        try:
            entry_time = datetime.fromisoformat(pos['entry_time'].replace('Z', '+00:00'))
            duration = datetime.now(timezone.utc) - entry_time
            duration_str = f"{duration.days}d {duration.seconds//3600}h" if duration.days > 0 else f"{duration.seconds//3600}h {(duration.seconds%3600)//60}m"
        except:
            duration_str = "N/A"

        # Risk (ile możemy stracić do SL)
        risk_amount = abs(pos['entry_price'] - pos.get('stop_loss', pos['entry_price'])) * pos['quantity']

        # Reward (ile możemy zyskać do TP)
        reward_amount = abs(pos.get('take_profit', pos['entry_price']) - pos['entry_price']) * pos['quantity']

        df_data.append({
            'Ticker': pos['ticker'],
            'Side': pos['side'],
            'Qty': pos['quantity'],
            'Entry $': f"${pos['entry_price']:.2f}",
            'Current $': f"${pos['current_price']:.2f}",
            'P&L $': f"${pos['unrealized_pnl']:.2f}",
            'P&L %': f"{pos['unrealized_pnl_pct']:+.2f}%",
            'Value $': f"${pos['current_value']:,.2f}",
            'Risk $': f"${risk_amount:.2f}",
            'Reward $': f"${reward_amount:.2f}",
            'Duration': duration_str,
            'SL $': f"${pos.get('stop_loss', 0):.2f}" if pos.get('stop_loss') else "N/A",
            'TP $': f"${pos.get('take_profit', 0):.2f}" if pos.get('take_profit') else "N/A"
        })

    df = pd.DataFrame(df_data)

    # Display table with conditional formatting
    st.dataframe(
        df,
        use_container_width=True,
        hide_index=True,
        height=400
    )

    # Summary row
    st.markdown("---")
    col1, col2, col3, col4 = st.columns(4)

    stats = st.session_state.get('portfolio_stats', {})

    with col1:
        st.metric("Total Cost Basis", f"${stats.get('total_cost_basis', 0):,.2f}")
    with col2:
        st.metric("Current Value", f"${stats.get('total_current_value', 0):,.2f}")
    with col3:
        pnl = stats.get('total_unrealized_pnl', 0)
        pnl_pct = stats.get('total_unrealized_pnl_pct', 0)
        color = "🟢" if pnl >= 0 else "🔴"
        st.metric(f"{color} Total P&L", f"${pnl:,.2f}", f"{pnl_pct:+.2f}%")
    with col4:
        total_risk = sum(abs(p['entry_price'] - p.get('stop_loss', p['entry_price'])) * p['quantity'] for p in positions_with_pnl)
        st.metric("Total Risk (to SL)", f"${total_risk:,.2f}")


def render_performance_metrics(client):
    """Render performance metrics"""
    st.subheader("📊 Performance Metrics")

    metrics = calculate_performance_metrics(client)

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("Total Trades", metrics['total_trades'])
        st.metric("Win Rate", f"{metrics['win_rate']:.1f}%")

    with col2:
        st.metric("Profit Factor", f"{metrics['profit_factor']:.2f}")
        st.metric("Sharpe Ratio", f"{metrics['sharpe_ratio']:.2f}")

    with col3:
        st.metric("Max Drawdown", f"${metrics['max_drawdown']:,.2f}")
        st.metric("Max DD %", f"{metrics['max_drawdown_pct']:.2f}%")

    with col4:
        st.metric("Best Trade", f"${metrics['best_trade']:,.2f}")
        st.metric("Worst Trade", f"${metrics['worst_trade']:,.2f}")


def render_allocation_chart():
    """Render position allocation pie chart"""
    positions_with_pnl = st.session_state.get('positions_with_pnl', [])

    if not positions_with_pnl:
        st.info("No data for allocation chart")
        return

    # Prepare data
    tickers = [p['ticker'] for p in positions_with_pnl]
    values = [p['current_value'] for p in positions_with_pnl]

    fig = px.pie(
        values=values,
        names=tickers,
        title="Position Allocation by Value",
        hole=0.3
    )

    fig.update_traces(textposition='inside', textinfo='percent+label')

    st.plotly_chart(fig, use_container_width=True)


def render_equity_curve(client):
    """Render equity curve (NAV over time)"""
    st.subheader("📈 Equity Curve (NAV Over Time)")

    # TODO: Get historical NAV from PostgreSQL
    # For now, mock data

    current_nav = st.session_state.get('current_nav', STARTING_NAV)

    # Generate mock historical data (last 30 days)
    dates = pd.date_range(end=datetime.now(), periods=30, freq='D')
    navs = [STARTING_NAV] * 30
    navs[-1] = current_nav  # Current NAV at end

    df = pd.DataFrame({
        'Date': dates,
        'NAV': navs
    })

    fig = go.Figure()

    fig.add_trace(go.Scatter(
        x=df['Date'],
        y=df['NAV'],
        mode='lines+markers',
        name='NAV',
        line=dict(color='#00FF00', width=2),
        fill='tozeroy'
    ))

    # Add starting NAV line
    fig.add_hline(
        y=STARTING_NAV,
        line_dash="dash",
        line_color="yellow",
        annotation_text="Starting NAV"
    )

    fig.update_layout(
        title="Portfolio Net Asset Value",
        xaxis_title="Date",
        yaxis_title="NAV ($)",
        hovermode='x unified',
        template="plotly_dark"
    )

    st.plotly_chart(fig, use_container_width=True)


def render_live_news_feed(client):
    """Render live news feed from news_scored stream"""
    st.subheader("📰 Live News Feed")

    news_items = get_latest_from_stream(client, "news_scored", count=10)

    if not news_items:
        st.info("No recent news")
        return

    for news in news_items:
        ticker = news.get('ticker', 'N/A')
        headline = news.get('headline', 'No headline')
        score = news.get('score', 0)
        timestamp = news.get('timestamp', '')

        # Sentiment color
        if score > 0.5:
            sentiment = "🟢 Bullish"
        elif score < -0.5:
            sentiment = "🔴 Bearish"
        else:
            sentiment = "🟡 Neutral"

        with st.expander(f"{ticker} - {sentiment} (score: {score:.2f})", expanded=False):
            st.write(headline)
            st.caption(f"Time: {timestamp}")


def render_trade_signals(client):
    """Render recent trade signals from trade_proposals"""
    st.subheader("🎯 Recent Trade Signals")

    proposals = get_latest_from_stream(client, "trade_proposals", count=10)

    if not proposals:
        st.info("No recent signals")
        return

    for prop in proposals:
        ticker = prop.get('ticker', 'N/A')
        side = prop.get('side', 'N/A')
        entry = prop.get('entry', 0)
        score = prop.get('combined_score', 0)

        side_emoji = "🟢" if side == "BUY" else "🔴"

        st.text(f"{side_emoji} {side} {ticker} @ ${entry:.2f} (score: {score:.2f})")


def render_system_health(client):
    """Render system health indicators"""
    st.subheader("🏥 System Health")

    # Redis connection
    try:
        client.ping()
        st.success("✅ Redis: Connected")
    except:
        st.error("❌ Redis: Disconnected")

    # Stream lengths
    streams = {
        "market_candles": get_stream_length(client, "market_candles"),
        "news_scored": get_stream_length(client, "news_scored"),
        "trade_proposals": get_stream_length(client, "trade_proposals"),
        "executed_orders": get_stream_length(client, "executed_orders")
    }

    col1, col2 = st.columns(2)

    with col1:
        for stream, length in list(streams.items())[:2]:
            st.metric(stream, length)

    with col2:
        for stream, length in list(streams.items())[2:]:
            st.metric(stream, length)


def render_sidebar():
    """Render sidebar with controls"""
    with st.sidebar:
        st.header("⚙️ Dashboard Controls")

        # Auto-refresh
        auto_refresh = st.checkbox("🔄 Auto-Refresh", value=True)

        if auto_refresh:
            refresh_interval = st.slider("Refresh Interval (sec)", 5, 60, 5)
            st.info(f"Auto-refreshing every {refresh_interval}s")
            time.sleep(refresh_interval)
            st.rerun()

        st.divider()

        # Manual refresh
        if st.button("🔄 Refresh Now", use_container_width=True):
            st.rerun()

        st.divider()

        # Settings
        st.header("📋 Settings")
        st.text(f"Starting NAV: ${STARTING_NAV:,.2f}")
        st.text(f"Redis: {REDIS_URL}")

        st.divider()

        # Quick stats
        st.header("⚡ Quick Stats")
        client = get_redis_client()
        if client:
            st.metric("market_candles", get_stream_length(client, "market_candles"))
            st.metric("trade_proposals", get_stream_length(client, "trade_proposals"))
            st.metric("executed_orders", get_stream_length(client, "executed_orders"))


# ============================================================================
# Main App
# ============================================================================

def main():
    """Main dashboard app"""

    # Get Redis client
    client = get_redis_client()

    if not client:
        st.error("❌ Cannot connect to Redis. Check if Redis is running.")
        return

    # Render header
    render_header()
    st.divider()

    # Render sidebar
    render_sidebar()

    # Main content - 2 columns
    col_main, col_side = st.columns([3, 1])

    with col_main:
        # Portfolio Overview (top metrics)
        render_portfolio_overview(client)
        st.divider()

        # MAIN TABLE - Open Positions (szczegółowa tabela)
        render_positions_table(client)
        st.divider()

        # Charts
        col_chart1, col_chart2 = st.columns(2)

        with col_chart1:
            render_allocation_chart()

        with col_chart2:
            render_equity_curve(client)

        st.divider()

        # Performance Metrics
        render_performance_metrics(client)

    with col_side:
        # Live feeds
        render_live_news_feed(client)
        st.divider()

        render_trade_signals(client)
        st.divider()

        render_system_health(client)


if __name__ == "__main__":
    main()
