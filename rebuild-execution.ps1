#!/usr/bin/env pwsh
# Rebuild execution_ibkr container with latest code changes

Write-Host "🔨 Rebuilding execution_ibkr container..." -ForegroundColor Cyan

# Stop the container
Write-Host "Stopping agent-execution-ibkr..." -ForegroundColor Yellow
docker-compose stop agent-execution-ibkr

# Remove the container to force rebuild
Write-Host "Removing old container..." -ForegroundColor Yellow
docker-compose rm -f agent-execution-ibkr

# Rebuild the image (no cache)
Write-Host "Rebuilding image from latest code..." -ForegroundColor Yellow
docker-compose build --no-cache agent-execution-ibkr

# Start the container
Write-Host "Starting agent-execution-ibkr..." -ForegroundColor Yellow
docker-compose up -d agent-execution-ibkr

# Wait a moment for container to initialize
Start-Sleep -Seconds 5

# Show logs
Write-Host "`n✅ Container rebuilt! Showing logs...`n" -ForegroundColor Green
docker-compose logs -f --tail 50 agent-execution-ibkr
