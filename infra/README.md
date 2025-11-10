# Infrastructure

This directory contains infrastructure configuration files.

## Files

- `Dockerfile.agent` - Dockerfile for agent services
- `Dockerfile.api` - Dockerfile for FastAPI backend
- `Dockerfile.ui` - Dockerfile for React/Next.js frontend (TODO)

## Usage

All services are orchestrated via `docker-compose.yml` in the root directory.

```bash
# Build and start all services
docker-compose up --build

# Start specific services
docker-compose up redis postgres api

# Start specific agent
docker-compose up agent-ingest-news

# View logs
docker-compose logs -f agent-strategy

# Stop all services
docker-compose down
```

## Development

For local development without Docker, install dependencies manually:

```bash
# Install common package dependencies
pip install -r packages/common/requirements.txt

# Install agent dependencies
pip install redis pydantic openai anthropic python-dotenv

# Install API dependencies
pip install -r apps/api/requirements.txt
```
