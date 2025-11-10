# FastAPI Backend - AI Portfolio Manager

REST API for managing trade proposals and monitoring executions.

## Features

- **Trade Proposals**: List trade proposals from Redis stream
- **Approval System**: Approve/reject trades via POST endpoint
- **Execution Monitoring**: View executed orders and their status
- **Risk Summary**: Real-time portfolio risk metrics
- **Statistics**: Trading activity statistics

## Endpoints

### Health Check
```
GET /
```

### Trading
```
GET /proposals?limit=100
POST /approve/{proposal_id}
GET /executed?limit=100
```

### Risk & Stats
```
GET /risk-summary
GET /stats
```

## Installation

```bash
cd apps/api
pip install -r requirements.txt
```

## Configuration

Set environment variables in `.env`:

```bash
REDIS_URL=redis://localhost:6379
API_HOST=0.0.0.0
API_PORT=8000
RISK_NAV=10000.0
RISK_MAX_POSITIONS=5
```

## Running

### Development Mode (with auto-reload)
```bash
python main.py
```

### Production Mode
```bash
uvicorn main:app --host 0.0.0.0 --port 8000
```

## API Documentation

Once running, visit:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

## Architecture

- **FastAPI**: Async REST framework
- **Redis Streams**: Event-driven data source
- **Pydantic**: Schema validation
- **CORS**: Enabled for frontend integration

## Usage Example

### Fetch Proposals
```bash
curl http://localhost:8000/proposals
```

### Approve Trade
```bash
curl -X POST http://localhost:8000/approve/1234-5678 \
  -H "Content-Type: application/json" \
  -d '{"approved": true}'
```

### Get Risk Summary
```bash
curl http://localhost:8000/risk-summary
```
