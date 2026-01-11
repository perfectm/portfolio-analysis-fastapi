#!/bin/bash
# Stop SSH tunnel to production database

echo "🛑 Stopping SSH tunnel..."

# Find tunnel process
TUNNEL_PID=$(lsof -ti:5433)

if [ -z "$TUNNEL_PID" ]; then
    echo "⚠️  No SSH tunnel found on port 5433"
    exit 0
fi

echo "   Found tunnel PID: $TUNNEL_PID"

# Kill the tunnel
kill $TUNNEL_PID 2>/dev/null

sleep 1

# Verify it's stopped
if lsof -ti:5433 > /dev/null 2>&1; then
    echo "⚠️  Tunnel still running, forcing shutdown..."
    kill -9 $TUNNEL_PID 2>/dev/null
    sleep 1
fi

if ! lsof -ti:5433 > /dev/null 2>&1; then
    echo "✅ SSH tunnel stopped successfully"
else
    echo "❌ Failed to stop tunnel"
    exit 1
fi
