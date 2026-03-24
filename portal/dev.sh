#!/usr/bin/env bash
# Start API server and Vite dev server for local development.
# Usage: bash portal/dev.sh

set -e
cd "$(dirname "$0")/.."

echo "Starting PyEDI Portal (dev mode)..."
echo "  API:  http://localhost:8000"
echo "  UI:   http://localhost:5173"
echo ""

# Start API in background
PYTHONPATH=. uvicorn portal.api.app:app --reload --port 8000 &
API_PID=$!

# Start Vite dev server
cd portal/ui
npm run dev &
UI_PID=$!

trap "kill $API_PID $UI_PID 2>/dev/null" EXIT
wait
