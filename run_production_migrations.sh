#!/bin/bash
# Script to run database migrations on production PostgreSQL
# Run this script ON THE PRODUCTION SERVER after pulling the latest code

set -e  # Exit on error

echo "🔧 Running Production Database Migrations"
echo "=========================================="
echo ""

# Ensure we're in the right directory
cd /opt/cmtool

# Pull latest code
echo "📥 Pulling latest code from git..."
sudo -u deployuser git pull
echo "✅ Code updated"
echo ""

# Activate virtual environment
echo "🐍 Activating virtual environment..."
source venv/bin/activate
echo "✅ Virtual environment activated"
echo ""

# Run migrations in order
echo "🗄️  Running database migrations..."
echo ""

echo "1️⃣  Creating favorite_settings table..."
python migrations/add_favorite_settings_table.py
echo ""

echo "2️⃣  Adding optimization tracking fields..."
python migrations/add_favorite_optimization_fields.py
echo ""

echo "✅ All migrations completed successfully!"
echo ""

# Restart the service to apply changes
echo "🔄 Restarting application service..."
sudo systemctl restart cmtool
echo "✅ Service restarted"
echo ""

# Check service status
echo "📊 Service status:"
sudo systemctl status cmtool --no-pager
echo ""

echo "🎉 Production migrations completed!"
echo ""
echo "Next steps:"
echo "1. Check the application logs: tail -f /opt/cmtool/logs/portfolio_analysis.log"
echo "2. Visit https://portfolio.cottonmike.com to verify it's working"
