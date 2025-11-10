"""
Streamlit UI for AI Portfolio Manager
Dashboard for approving trade proposals and monitoring executions.
"""

import streamlit as st
import requests
import pandas as pd
from datetime import datetime
from typing import List, Dict, Any
import os
from dotenv import load_dotenv

load_dotenv()


# ============================================================================
# Configuration
# ============================================================================

API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")

st.set_page_config(
    page_title="AI Portfolio Manager",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)


# ============================================================================
# API Client Functions
# ============================================================================

def fetch_proposals() -> List[Dict[str, Any]]:
    """Fetch trade proposals from API"""
    try:
        response = requests.get(f"{API_BASE_URL}/proposals", timeout=5)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        st.error(f"Error fetching proposals: {e}")
        return []


def approve_trade(proposal_id: str, approved: bool, reason: str = None) -> Dict[str, Any]:
    """Approve or reject a trade"""
    try:
        response = requests.post(
            f"{API_BASE_URL}/approve/{proposal_id}",
            json={"approved": approved, "reason": reason},
            timeout=5
        )
        response.raise_for_status()
        return response.json()
    except Exception as e:
        st.error(f"Error approving trade: {e}")
        return {}


def fetch_executed_orders() -> List[Dict[str, Any]]:
    """Fetch executed orders from API"""
    try:
        response = requests.get(f"{API_BASE_URL}/executed", timeout=5)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        st.error(f"Error fetching executed orders: {e}")
        return []


def fetch_risk_summary() -> Dict[str, Any]:
    """Fetch risk summary from API"""
    try:
        response = requests.get(f"{API_BASE_URL}/risk-summary", timeout=5)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        st.error(f"Error fetching risk summary: {e}")
        return {
            "total_positions": 0,
            "active_trades": [],
            "total_exposure": 0.0,
            "available_capacity": 5,
            "daily_pnl": 0.0,
            "nav": 10000.0
        }


def fetch_stats() -> Dict[str, Any]:
    """Fetch statistics from API"""
    try:
        response = requests.get(f"{API_BASE_URL}/stats", timeout=5)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        st.error(f"Error fetching stats: {e}")
        return {
            "total_proposals": 0,
            "pending_proposals": 0,
            "approved_today": 0,
            "rejected_today": 0,
            "executed_today": 0,
            "total_executed": 0
        }


# ============================================================================
# UI Components
# ============================================================================

def render_header():
    """Render dashboard header"""
    st.title("📈 AI Portfolio Manager")
    st.markdown("**Real-time trade approval and portfolio monitoring**")
    st.divider()


def render_stats_cards():
    """Render statistics cards"""
    stats = fetch_stats()

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric(
            label="📋 Total Proposals",
            value=stats["total_proposals"]
        )

    with col2:
        st.metric(
            label="⏳ Pending",
            value=stats["pending_proposals"]
        )

    with col3:
        st.metric(
            label="✅ Approved Today",
            value=stats["approved_today"]
        )

    with col4:
        st.metric(
            label="🎯 Executed Today",
            value=stats["executed_today"]
        )


def render_risk_summary():
    """Render risk summary section"""
    st.subheader("🛡️ Risk Summary")

    risk = fetch_risk_summary()

    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric(
            label="Active Positions",
            value=f"{risk['total_positions']} / 5"
        )
        st.metric(
            label="Available Capacity",
            value=risk["available_capacity"]
        )

    with col2:
        st.metric(
            label="Total Exposure",
            value=f"${risk['total_exposure']:,.2f}"
        )
        exposure_pct = (risk['total_exposure'] / risk['nav']) * 100 if risk['nav'] > 0 else 0
        st.metric(
            label="Exposure %",
            value=f"{exposure_pct:.1f}%"
        )

    with col3:
        st.metric(
            label="NAV",
            value=f"${risk['nav']:,.2f}"
        )
        pnl_color = "normal" if risk['daily_pnl'] >= 0 else "inverse"
        st.metric(
            label="Daily P&L",
            value=f"${risk['daily_pnl']:,.2f}",
            delta=f"{(risk['daily_pnl'] / risk['nav'] * 100):.2f}%",
            delta_color=pnl_color
        )

    # Active trades list
    if risk['active_trades']:
        with st.expander("📊 Active Trades", expanded=False):
            for trade in risk['active_trades']:
                st.text(f"• {trade}")


def render_proposals_section():
    """Render trade proposals section"""
    st.subheader("🎯 Trade Proposals")

    proposals = fetch_proposals()

    if not proposals:
        st.info("No pending proposals at the moment.")
        return

    # Filter to show only PENDING proposals
    pending_proposals = [p for p in proposals if p["status"] == "PENDING"]

    if not pending_proposals:
        st.info("No pending proposals. All proposals have been processed.")
        return

    st.write(f"**{len(pending_proposals)} proposal(s) waiting for approval**")

    # Display each proposal as a card
    for i, proposal in enumerate(pending_proposals):
        with st.container():
            col1, col2, col3, col4 = st.columns([3, 2, 2, 2])

            with col1:
                # Trade details
                side_emoji = "🟢" if proposal["side"] == "BUY" else "🔴"
                st.markdown(f"### {side_emoji} {proposal['ticker']} {proposal['side']}")
                st.text(f"Quantity: {proposal['quantity']} @ ${proposal['entry']:.2f}")
                st.text(f"Stop: ${proposal['stop']:.2f} | TP: ${proposal['take_profit']:.2f}")

            with col2:
                # Scores
                st.text("📊 Scores:")
                st.text(f"Combined: {proposal['combined_score']:.3f}")
                st.text(f"News: {proposal['news_score']:.3f}")
                st.text(f"Momentum: {proposal['momentum_score']:.3f}")

            with col3:
                # Risk metrics
                risk_amount = abs(proposal['entry'] - proposal['stop']) * proposal['quantity']
                reward_amount = abs(proposal['take_profit'] - proposal['entry']) * proposal['quantity']
                st.text("💰 Risk/Reward:")
                st.text(f"Risk: ${risk_amount:.2f}")
                st.text(f"Reward: ${reward_amount:.2f}")

            with col4:
                # Action buttons
                st.text("🎮 Actions:")

                approve_key = f"approve_{proposal['proposal_id']}_{i}"
                reject_key = f"reject_{proposal['proposal_id']}_{i}"

                if st.button("✅ Approve", key=approve_key, type="primary"):
                    result = approve_trade(proposal['proposal_id'], approved=True)
                    if result.get("status") == "approved":
                        st.success(f"✅ Trade approved! Sent to execution.")
                        st.rerun()

                if st.button("❌ Reject", key=reject_key):
                    result = approve_trade(proposal['proposal_id'], approved=False, reason="Rejected by user")
                    if result.get("status") == "rejected":
                        st.info(f"Trade rejected.")
                        st.rerun()

            # Timestamp
            st.caption(f"Proposed at: {proposal['proposed_at']}")
            st.divider()


def render_executed_orders():
    """Render executed orders section"""
    st.subheader("📋 Executed Orders")

    executed = fetch_executed_orders()

    if not executed:
        st.info("No executed orders yet.")
        return

    # Convert to DataFrame
    df = pd.DataFrame(executed)

    # Format columns
    if not df.empty:
        # Select and rename columns
        display_df = df[[
            'order_id', 'ticker', 'side', 'quantity',
            'entry_price', 'executed_price', 'status',
            'commission', 'slippage', 'executed_at'
        ]].copy()

        display_df['entry_price'] = display_df['entry_price'].apply(lambda x: f"${x:.2f}")
        display_df['executed_price'] = display_df['executed_price'].apply(lambda x: f"${x:.2f}")
        display_df['commission'] = display_df['commission'].apply(lambda x: f"${x:.2f}")
        display_df['slippage'] = display_df['slippage'].apply(lambda x: f"${x:.4f}")

        # Display with styling
        st.dataframe(
            display_df,
            use_container_width=True,
            hide_index=True
        )

        # Summary stats
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total Orders", len(executed))
        with col2:
            total_commission = sum(o['commission'] for o in executed)
            st.metric("Total Commission", f"${total_commission:.2f}")
        with col3:
            filled_count = sum(1 for o in executed if o['status'] == 'FILLED')
            st.metric("Filled Orders", filled_count)


def render_learning_notes():
    """Render learning notes section (impact memory)"""
    st.subheader("📚 Learning Notes")

    with st.expander("ℹ️ About Learning Notes", expanded=False):
        st.markdown("""
        **Impact Memory System**

        The AI Portfolio Manager learns from historical shock events and their causes:

        - **Shock Detection**: Monitors price/volume anomalies using statistical analysis
        - **Cause Attribution**: Correlates shocks with news events and market conditions
        - **Pattern Learning**: Builds a database of shock events and their attributions
        - **Future Prediction**: Uses historical patterns to predict market reactions

        This system continuously improves by learning from every market shock and its impact.
        """)

    # Placeholder for impact memory stats
    st.info("Impact memory statistics will be displayed here once shock events are detected and attributed.")

    # Add sample visualization placeholder
    col1, col2 = st.columns(2)

    with col1:
        st.markdown("**Recent Shock Events**")
        st.caption("Price/volume anomalies detected by statistical analysis")
        st.text("No shock events recorded yet.")

    with col2:
        st.markdown("**Attribution Confidence**")
        st.caption("Confidence in news-shock correlations")
        st.text("Awaiting data...")


def render_sidebar():
    """Render sidebar with controls"""
    with st.sidebar:
        st.header("⚙️ Settings")

        # Auto-refresh toggle
        auto_refresh = st.checkbox("Auto-refresh", value=False)
        if auto_refresh:
            refresh_interval = st.slider("Refresh interval (seconds)", 5, 60, 10)
            st.info(f"Dashboard will refresh every {refresh_interval} seconds")

        st.divider()

        # API status
        st.header("🔌 API Status")
        try:
            response = requests.get(f"{API_BASE_URL}/", timeout=2)
            if response.status_code == 200:
                st.success("✅ Connected")
            else:
                st.error("❌ Disconnected")
        except:
            st.error("❌ Cannot connect to API")

        st.caption(f"API: {API_BASE_URL}")

        st.divider()

        # Manual refresh button
        if st.button("🔄 Refresh Now", use_container_width=True):
            st.rerun()

        # Documentation
        st.divider()
        st.header("📖 Documentation")
        st.markdown("""
        **Quick Guide:**
        1. Review trade proposals
        2. Check risk metrics
        3. Approve/reject trades
        4. Monitor executions

        **Endpoints:**
        - GET `/proposals`
        - POST `/approve/{id}`
        - GET `/executed`
        - GET `/risk-summary`
        """)


# ============================================================================
# Main App
# ============================================================================

def main():
    """Main application"""
    render_header()
    render_sidebar()

    # Stats cards
    render_stats_cards()
    st.divider()

    # Risk summary
    render_risk_summary()
    st.divider()

    # Trade proposals (main section)
    render_proposals_section()
    st.divider()

    # Executed orders
    render_executed_orders()
    st.divider()

    # Learning notes
    render_learning_notes()


if __name__ == "__main__":
    main()
