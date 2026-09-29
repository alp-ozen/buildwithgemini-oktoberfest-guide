#!/usr/bin/env bash
set -e

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$DIR"

echo "=== Stopping any previously running local instances ==="
fuser -k 8080/tcp 2>/dev/null || true
fuser -k 8000/tcp 2>/dev/null || true
fuser -k 80/tcp 2>/dev/null || true
pkill -f "python.*main.py" 2>/dev/null || true
pkill -f "socat TCP-LISTEN:80" 2>/dev/null || true
pkill -f "socat TCP-LISTEN:8000" 2>/dev/null || true
sleep 1

export AGENT_ENGINE_RESOURCE_NAME="projects/682858117164/locations/us-east1/reasoningEngines/370084618793123840"
export AGENT_DIRECTORY="app"
export PORT="8080"

echo "=== Starting FastAPI Chat Proxy on port 8080 ==="
.venv/bin/python main.py &
SERVER_PID=$!

echo "Waiting for server to become responsive..."
for i in {1..30}; do
  if curl -s http://127.0.0.1:8080/ >/dev/null 2>&1; then
    echo "Server is UP on http://localhost:8080"
    break
  fi
  sleep 0.5
done

echo "=== Forwarding port 80 (http://localhost) and port 8000 to port 8080 ==="
socat TCP-LISTEN:80,fork,reuseaddr TCP:127.0.0.1:8080 &
socat TCP-LISTEN:8000,fork,reuseaddr TCP:127.0.0.1:8080 &

echo "=== Launching Browser to http://localhost:8080 ==="
google-chrome http://localhost:8080 >/dev/null 2>&1 &

echo "=== Local Chat Interface is now live! ==="
wait $SERVER_PID
