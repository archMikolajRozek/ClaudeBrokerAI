.PHONY: help install dev up down logs clean test lint format

help: ## Show this help message
	@echo 'Usage: make [target]'
	@echo ''
	@echo 'Available targets:'
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2}'

install: ## Install Python dependencies
	pip install -r requirements.txt
	pip install -r packages/common/requirements.txt
	pip install -r apps/api/requirements.txt

dev: ## Start development environment
	docker-compose up redis postgres

up: ## Start all services
	docker-compose up --build

up-detached: ## Start all services in background
	docker-compose up -d --build

down: ## Stop all services
	docker-compose down

down-volumes: ## Stop all services and remove volumes
	docker-compose down -v

logs: ## Show logs from all services
	docker-compose logs -f

logs-agent: ## Show logs from specific agent (usage: make logs-agent AGENT=strategy)
	docker-compose logs -f agent-$(AGENT)

clean: ## Clean up Docker containers, images, and volumes
	docker-compose down -v
	docker system prune -f

test: ## Run tests
	pytest tests/ -v

lint: ## Run linting
	flake8 agents/ apps/ packages/
	pylint agents/ apps/ packages/

format: ## Format code with black
	black agents/ apps/ packages/

redis-cli: ## Open Redis CLI
	docker-compose exec redis redis-cli

db-shell: ## Open PostgreSQL shell
	docker-compose exec postgres psql -U postgres -d portfolio_db

# Agent-specific targets
run-ingest-news: ## Run ingest_news agent locally
	cd agents/ingest_news && python main.py

run-score-news: ## Run score_news agent locally
	cd agents/score_news && python main.py

run-market-data: ## Run market_data agent locally
	cd agents/market_data && python main.py

run-strategy: ## Run strategy agent locally
	cd agents/strategy && python main.py

run-risk: ## Run risk agent locally
	cd agents/risk && python main.py

run-execution: ## Run execution agent locally
	cd agents/execution && python main.py

run-shock-detector: ## Run shock_detector agent locally
	cd agents/shock_detector && python main.py

run-api: ## Run API locally
	cd apps/api && uvicorn main:app --reload

# Monitoring
monitor-streams: ## Monitor Redis streams
	@echo "Monitoring Redis Streams..."
	docker-compose exec redis redis-cli MONITOR

stream-info: ## Show info about all streams
	@echo "=== news:raw ==="
	docker-compose exec redis redis-cli XINFO STREAM news:raw
	@echo "\n=== market:data ==="
	docker-compose exec redis redis-cli XINFO STREAM market:data
	@echo "\n=== signals:trading ==="
	docker-compose exec redis redis-cli XINFO STREAM signals:trading
