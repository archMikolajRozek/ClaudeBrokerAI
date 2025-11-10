# AI Portfolio Manager - Running Guide

Complete guide to running the AI Portfolio Manager system.

## Prerequisites

- Python 3.9+
- Redis server
- pip package manager

## System Architecture

```
┌─────────────────┐
│  Streamlit UI   │ (Port 8501)
│   apps/ui       │
└────────┬────────┘
         │ REST API
         ▼
┌─────────────────┐
│  FastAPI Backend│ (Port 8000)
│   apps/api      │
└────────┬────────┘
         │ Redis Streams
         ▼
┌─────────────────────────────────────────────────────┐
│                   Redis Streams                      │
├──────────────┬──────────────┬──────────────────────┤
│ news_ingested│market_shocks │ trade_proposals      │
│ news_scored  │market_candles│ approved_trades      │
│              │              │ executed_orders      │
└──────────────┴──────────────┴──────────────────────┘
         ▲                    ▲                    ▲
         │                    │                    │
    ┌────┴────┐      ┌────────┴──────┐    ┌───────┴────────┐
    │ Agents  │      │   Agents      │    │    Agents      │
    │ News    │      │   Detection   │    │    Trading     │
    │ Pipeline│      │   Pipeline    │    │    Pipeline    │
    └─────────┘      └───────────────┘    └────────────────┘
```

## Quick Start

### 1. Install Redis

```bash
# Ubuntu/Debian
sudo apt-get install redis-server
sudo systemctl start redis

# macOS
brew install redis
brew services start redis

# Or use Docker
docker run -d -p 6379:6379 redis:7-alpine
```

### 2. Configure Environment

```bash
# Copy example config
cp .env.example .env

# Edit .env with your settings
nano .env
```

Minimum required settings:
```bash
REDIS_URL=redis://localhost:6379
API_HOST=0.0.0.0
API_PORT=8000
API_BASE_URL=http://localhost:8000
RISK_NAV=10000.0
```

### 3. Install Dependencies

Each component has its own requirements:

```bash
# Backend API
cd apps/api
pip install -r requirements.txt
cd ../..

# Frontend UI
cd apps/ui
pip install -r requirements.txt
cd ../..

# Agents (install as needed)
cd agents/ingest_news
pip install -r requirements.txt
cd ../..
```

## Running the System

### Option 1: Full System (Recommended for Production)

Run each component in a separate terminal:

#### Terminal 1: Backend API
```bash
cd apps/api
python main.py
```
Backend will start on `http://localhost:8000`
- API docs: `http://localhost:8000/docs`

#### Terminal 2: Frontend UI
```bash
cd apps/ui
streamlit run main.py
```
Dashboard will open at `http://localhost:8501`

#### Terminal 3-N: Agents (as needed)

```bash
# News pipeline
cd agents/ingest_news && python main.py &
cd agents/score_news && python main.py &

# Detection pipeline
cd agents/shock_detector && python main.py &
cd agents/cause_finder && python main.py &

# Trading pipeline
cd agents/strategy && python main.py &
cd agents/risk && python main.py &
cd agents/execution && python main.py &
```

### Option 2: Development Mode (API + UI only)

For testing the UI without agents:

```bash
# Terminal 1: Backend
cd apps/api && python main.py

# Terminal 2: Frontend
cd apps/ui && streamlit run main.py
```

**Note**: Without agents running, you won't see any proposals. You can test with mock data.

## Using the Dashboard

### 1. View Statistics
Top cards show:
- Total proposals generated
- Pending proposals waiting for approval
- Approved trades today
- Executed orders today

### 2. Monitor Risk
Risk summary displays:
- Active positions vs. capacity (default: max 5 positions)
- Total exposure in dollars
- Net Asset Value (NAV)
- Daily P&L with percentage

### 3. Approve Trades
For each pending proposal:
1. Review trade details (ticker, side, quantity, price)
2. Check combined score (news + momentum)
3. Evaluate risk/reward metrics
4. Click **✅ Approve** to execute or **❌ Reject** to decline

### 4. Track Executions
View execution history with:
- Order ID and status
- Executed price vs. entry price
- Commission and slippage
- Timestamp

### 5. Learning Notes
Monitor the AI's learning system:
- Shock events detected
- Cause attributions
- Pattern recognition insights

## API Endpoints

### Trade Management
```bash
# Get proposals
curl http://localhost:8000/proposals

# Approve a trade
curl -X POST http://localhost:8000/approve/{proposal_id} \
  -H "Content-Type: application/json" \
  -d '{"approved": true}'

# Get executed orders
curl http://localhost:8000/executed
```

### Monitoring
```bash
# Risk summary
curl http://localhost:8000/risk-summary

# Statistics
curl http://localhost:8000/stats
```

## Data Flow

1. **News Ingestion** → `ingest_news` agent fetches news → publishes to `news_ingested`
2. **News Scoring** → `score_news` agent calculates decay-adjusted scores → publishes to `news_scored`
3. **Strategy** → `strategy` agent combines news+momentum → publishes to `trade_proposals`
4. **User Approval** → Dashboard/API approves trade → publishes to `approved_trades`
5. **Risk Check** → `risk` agent validates position sizing → publishes to `approved_trades` (or rejects)
6. **Execution** → `execution` agent places orders → publishes to `executed_orders`

Parallel pipelines:
- **Shock Detection** → `shock_detector` monitors candles → publishes to `market_shocks`
- **Cause Attribution** → `cause_finder` correlates shocks with news → stores in SQLite

## Monitoring

### Check Redis Streams
```bash
redis-cli

# List all streams
SCAN 0 MATCH *:stream

# View stream contents
XREAD COUNT 10 STREAMS news_ingested 0-0
XREAD COUNT 10 STREAMS trade_proposals 0-0
XREAD COUNT 10 STREAMS executed_orders 0-0
```

### Check Agent Health
Each agent prints status to console:
- `✓ Connected to Redis`
- `🚀 Starting event loop...`
- Processing counts

### Check API Health
```bash
curl http://localhost:8000/
# Should return: {"status": "ok", ...}
```

## Troubleshooting

### No Proposals Appearing
1. Check that `strategy` agent is running
2. Verify Redis streams have data: `redis-cli XLEN trade_proposals`
3. Check agent logs for errors

### API Connection Failed
1. Ensure backend is running: `curl http://localhost:8000/`
2. Check `API_BASE_URL` in `.env` matches backend
3. Verify no firewall blocking ports

### Agents Not Processing
1. Check Redis connection: `redis-cli PING`
2. Verify consumer groups exist
3. Check agent logs for errors

### Execution Not Working
1. Ensure `execution` agent is running
2. Check `approved_trades` stream has messages
3. Verify `TRADING_MODE=paper` in `.env`

## Production Deployment

### Using Docker (Recommended)

```bash
# Build images
docker-compose build

# Run all services
docker-compose up -d

# View logs
docker-compose logs -f
```

### Using Process Manager (PM2)

```bash
npm install -g pm2

# Start all services
pm2 start ecosystem.config.js

# Monitor
pm2 monit

# View logs
pm2 logs
```

## Next Steps

1. **Add Market Data**: Integrate real-time market data feed
2. **Enable News API**: Add API key to fetch real news
3. **Configure Broker**: Set up Alpaca or IB credentials for live trading
4. **Backtest**: Run historical simulations to tune parameters
5. **Monitor Performance**: Track P&L, Sharpe ratio, max drawdown

## Support

For issues or questions:
- Check logs in each agent/app
- Review Redis stream contents
- Verify environment variables
- See individual README files in agent directories

---

**Happy Trading! 📈**
