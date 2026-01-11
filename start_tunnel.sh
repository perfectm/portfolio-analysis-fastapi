#!/bin/bash
# Start SSH tunnel to production database in the background

echo "🚇 Starting SSH tunnel to production database..."

# Check if tunnel is already running
if lsof -ti:5433 > /dev/null 2>&1; then
    echo "⚠️  SSH tunnel already running on port 5433"
    echo "   PID: $(lsof -ti:5433)"
    echo ""
    echo "To stop it, run: ./stop_tunnel.sh"
    exit 1
fi

# Start tunnel in background with nohup
nohup ssh -N -L 5433:localhost:5432 \
    -o ServerAliveInterval=60 \
    -o ServerAliveCountMax=3 \
    -o TCPKeepAlive=yes \
    cotton@srv1173534 > tunnel.log 2>&1 &

TUNNEL_PID=$!
sleep 2

# Check if tunnel started successfully
if lsof -ti:5433 > /dev/null 2>&1; then
    echo "✅ SSH tunnel started successfully!"
    echo "   PID: $TUNNEL_PID"
    echo "   Port: 5433 → srv1173534:5432"
    echo ""
    echo "📝 Tunnel logs: tail -f tunnel.log"
    echo "🛑 To stop: ./stop_tunnel.sh"
    echo ""
    echo "Now you can run:"
    echo "   python sync_prod_to_dev.py \"postgresql://cmtool:PASSWORD@localhost:5433/portfolio_analysis\""
else
    echo "❌ Failed to start SSH tunnel"
    echo "   Check tunnel.log for errors"
    cat tunnel.log
    exit 1
fi
