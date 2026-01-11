#!/bin/bash
# Test SSH tunnel and PostgreSQL connection

echo "🔍 SSH Tunnel Troubleshooting"
echo "=============================="
echo ""

# Check if SSH tunnel is running
echo "1. Checking SSH tunnel status..."
TUNNEL_PID=$(lsof -ti:5433)
if [ -z "$TUNNEL_PID" ]; then
    echo "   ❌ No SSH tunnel found on port 5433"
    echo "   → Start tunnel: ssh -N -L 5433:localhost:5432 cotton@srv1173534"
    exit 1
else
    echo "   ✅ SSH tunnel running (PID: $TUNNEL_PID)"
fi

echo ""
echo "2. Testing local port 5433..."
nc -z localhost 5433
if [ $? -eq 0 ]; then
    echo "   ✅ Port 5433 is open"
else
    echo "   ❌ Port 5433 is not accessible"
    exit 1
fi

echo ""
echo "3. Testing PostgreSQL connection via tunnel..."
# This requires psql to be installed
if command -v psql &> /dev/null; then
    echo "   Enter cmtool password when prompted:"
    psql "postgresql://cmtool@localhost:5433/portfolio_analysis" -c "SELECT version();" 2>&1 | head -5

    if [ ${PIPESTATUS[0]} -eq 0 ]; then
        echo "   ✅ PostgreSQL connection successful"
    else
        echo "   ❌ PostgreSQL connection failed"
        echo ""
        echo "Possible issues:"
        echo "  • Check if PostgreSQL is running on the server"
        echo "  • Verify cmtool password"
        echo "  • Check PostgreSQL pg_hba.conf allows localhost connections"
    fi
else
    echo "   ⚠️  psql not installed, skipping PostgreSQL test"
    echo "   Install with: brew install postgresql"
fi

echo ""
echo "4. Checking SSH tunnel health..."
CONN_COUNT=$(lsof -ti:5433 | wc -l | tr -d ' ')
echo "   Active tunnel processes: $CONN_COUNT"

echo ""
echo "=============================="
echo "If you see 'channel open failed' errors:"
echo ""
echo "Option 1: Restart SSH tunnel with verbose logging"
echo "  ssh -v -N -L 5433:localhost:5432 cotton@srv1173534"
echo ""
echo "Option 2: Use SSH config compression"
echo "  ssh -N -C -L 5433:localhost:5432 cotton@srv1173534"
echo ""
echo "Option 3: Check server PostgreSQL status"
echo "  ssh cotton@srv1173534 'sudo systemctl status postgresql'"
echo ""
echo "Option 4: Check if PostgreSQL listens on localhost"
echo "  ssh cotton@srv1173534 'sudo netstat -tlnp | grep 5432'"
echo ""
