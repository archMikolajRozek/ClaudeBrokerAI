#!/bin/bash
# Entrypoint script dla agentów - instaluje agent-specific requirements

set -e

echo "[Entrypoint] Starting agent container..."

# Jeśli agent ma swój requirements.txt, zainstaluj go
if [ -f "/app/agent/requirements.txt" ]; then
    echo "[Entrypoint] Installing agent-specific requirements..."
    pip install --no-cache-dir -r /app/agent/requirements.txt
    echo "[Entrypoint] ✓ Requirements installed"
else
    echo "[Entrypoint] No agent requirements.txt found, skipping..."
fi

# Uruchom właściwą komendę (przekazaną przez CMD)
echo "[Entrypoint] Executing: $@"
exec "$@"
