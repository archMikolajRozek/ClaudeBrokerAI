# Streamlit UI - AI Portfolio Manager

Interactive dashboard for approving trade proposals and monitoring portfolio.

## Features

- **Trade Proposals**: View and approve/reject pending trades
- **Risk Summary**: Real-time portfolio metrics
  - Active positions
  - Exposure tracking
  - Daily P&L
  - NAV monitoring
- **Executed Orders**: View order history with details
- **Learning Notes**: Impact memory insights
- **Statistics**: Trading activity overview
- **Auto-refresh**: Optional automatic dashboard updates

## Installation

```bash
cd apps/ui
pip install -r requirements.txt
```

## Configuration

Set environment variables in `.env`:

```bash
API_BASE_URL=http://localhost:8000
```

## Running

```bash
streamlit run main.py
```

The dashboard will open in your browser at `http://localhost:8501`

## Usage

### Dashboard Sections

1. **Statistics Cards**
   - Total proposals
   - Pending count
   - Approved today
   - Executed today

2. **Risk Summary**
   - Position count and capacity
   - Total exposure
   - NAV and daily P&L
   - Active trades list

3. **Trade Proposals** (Main Section)
   - View pending proposals
   - See trade details (ticker, side, quantity, price)
   - View scores (combined, news, momentum)
   - Risk/reward metrics
   - Approve/reject buttons

4. **Executed Orders**
   - Order history table
   - Execution details
   - Commission and slippage
   - Summary statistics

5. **Learning Notes**
   - Impact memory system overview
   - Shock event tracking (coming soon)
   - Pattern learning insights

### Sidebar Controls

- **Auto-refresh**: Toggle and configure refresh interval
- **API Status**: Check backend connection
- **Manual Refresh**: Force dashboard update
- **Documentation**: Quick reference guide

## Screenshots

### Approving Trades
Click the "✅ Approve" button on any pending proposal to send it to execution.

### Risk Monitoring
Real-time risk metrics help you stay within portfolio limits.

### Order History
Track all executed orders with detailed execution data.

## Architecture

- **Streamlit**: Interactive web framework
- **Requests**: REST API client
- **Pandas**: Data display and manipulation
- **REST Integration**: Fetches data from FastAPI backend

## Tips

- Use auto-refresh for monitoring mode
- Check risk summary before approving large positions
- Review executed orders to track slippage and commission
- Monitor learning notes to understand AI decisions

## Troubleshooting

### Cannot connect to API
1. Ensure FastAPI backend is running (`python apps/api/main.py`)
2. Check `API_BASE_URL` in `.env` matches backend URL
3. Verify Redis is running for backend connectivity

### Proposals not showing
1. Check that agents are running and generating proposals
2. Verify Redis streams contain data
3. Check backend logs for errors
