# Production to Development Database Sync

This guide explains how to sync data from the production PostgreSQL database (Hostinger VPS) to your local SQLite development database for testing.

## Overview

The `sync_prod_to_dev.py` script safely copies all data from production to your local development environment:
- **Read-only** on production (no changes to production data)
- **Replaces** local SQLite data with production data
- **Preserves** database schema and relationships
- **Batch processing** for large datasets

## Prerequisites

1. **SSH access** to Hostinger VPS: `ssh cotton@srv1173534`
2. **Production database password** for user `cmtool`
3. **Python dependencies**: SQLAlchemy, psycopg2

## Method 1: Using SSH Tunnel (Recommended)

### Step 1: Create SSH Tunnel
Open a terminal and create an SSH tunnel to the production database:

```bash
# Option 1: Basic tunnel (recommended)
ssh -N -L 5433:localhost:5432 cotton@srv1173534

# Option 2: With compression (if connection is slow)
ssh -N -C -L 5433:localhost:5432 cotton@srv1173534

# Option 3: With verbose logging (for troubleshooting)
ssh -v -N -L 5433:localhost:5432 cotton@srv1173534
```

**Flags explained:**
- `-N`: Don't execute remote commands (just forward)
- `-L`: Local port forwarding
- `-C`: Enable compression
- `-v`: Verbose output for debugging

**Note:** Keep this terminal open while syncing. The `-N` flag means it won't give you a shell prompt - this is normal.

### Step 2: Run Sync Script
In another terminal:

```bash
# Navigate to project directory
cd /Users/closet/projects/portfolio-analysis-fastapi

# Run sync with tunneled connection
python sync_prod_to_dev.py "postgresql://cmtool:YOUR_PASSWORD@localhost:5433/portfolio_analysis"
```

Replace `YOUR_PASSWORD` with the actual `cmtool` database password.

## Method 2: Using Environment Variable

### Option A: Set environment variable temporarily

```bash
export PROD_DATABASE_URL="postgresql://cmtool:YOUR_PASSWORD@localhost:5433/portfolio_analysis"
python sync_prod_to_dev.py
```

### Option B: Create a local .env file

```bash
# Create .env.sync (not tracked by git)
echo 'PROD_DATABASE_URL=postgresql://cmtool:YOUR_PASSWORD@localhost:5433/portfolio_analysis' > .env.sync

# Source it before running
source .env.sync
python sync_prod_to_dev.py
```

## What Gets Synced

The script syncs all tables in the correct order (respecting foreign keys):

1. ✅ **users** - User accounts and authentication
2. ✅ **portfolios** - Portfolio metadata
3. ✅ **portfolio_data** - Raw CSV data (can be large!)
4. ✅ **analysis_results** - Computed metrics
5. ✅ **analysis_plots** - Chart references
6. ✅ **blended_portfolios** - Multi-portfolio configurations
7. ✅ **blended_portfolio_mappings** - Portfolio relationships
8. ✅ **favorite_settings** - User preferences
9. ✅ **regime_data** - Market regime analysis
10. ✅ **regime_performance** - Regime performance metrics
11. ✅ **margin_requirements** - Margin configurations
12. ✅ **portfolio_margin_data** - Margin calculations
13. ✅ **optimization_cache** - Cached optimization results

## Safety Features

- ✅ **Read-only** connection to production
- ✅ **User confirmation** required before replacing local data
- ✅ **Backup recommendation** shown before sync
- ✅ **Progress feedback** during sync
- ✅ **Error handling** with detailed messages
- ✅ **Foreign key integrity** maintained

## Example Output

```
🚀 Production to Development Database Sync
   Production: postgresql://***@localhost:5433/portfolio_analysis
   Local:      sqlite:///./portfolio_analysis.db

⚠️  This will REPLACE all local data. Continue? [y/N]: y

🔌 Connecting to production database...
✅ Connected to production: portfolio_analysis as cmtool
   PostgreSQL version: PostgreSQL 16.3

🔌 Connecting to local database: sqlite:///./portfolio_analysis.db
✅ Connected to local SQLite: version 3.43.2

🗑️  Clearing local database...
   Cleared users
   Cleared portfolios
   ...
✅ Local database cleared

======================================================================
🔄 Starting database sync...
======================================================================
📋 Syncing users (5 rows)...
   ✅ Synced 5 rows
📋 Syncing portfolios (38 rows)...
   ✅ Synced 38 rows
📋 Syncing portfolio_data (125,432 rows)...
   ... 5,000 / 125,432 rows
   ... 10,000 / 125,432 rows
   ...
   ✅ Synced 125,432 rows
...
======================================================================
✅ Sync completed!
   Total rows synced: 126,543
   Duration: 0:01:23.456789
======================================================================

📊 Local Database Summary:
----------------------------------------------------------------------
   users                               5 rows
   portfolios                         38 rows
   portfolio_data                125,432 rows
   analysis_results                  156 rows
   ...
----------------------------------------------------------------------

✅ Sync completed successfully!
   Your local database now has production data for testing.
```

## Tips

### 1. Backup Before Syncing
Although the script only affects your local database, it's good practice to backup first:

```bash
cp portfolio_analysis.db portfolio_analysis.db.backup
```

### 2. Large Datasets
The `portfolio_data` table can be very large (100K+ rows). The script uses batch processing, but syncing may take a few minutes.

### 3. Incremental Sync
If you only need recent data, you can modify the script to add a date filter. Example:

```python
# In sync_table function, add WHERE clause
query = table.select().where(table.c.date >= '2024-01-01')
```

### 4. SSH Tunnel Troubleshooting
If the tunnel disconnects during sync:
- Check SSH connection: `ssh cotton@srv1173534`
- Try with `-N` flag: `ssh -N -L 5433:localhost:5432 cotton@srv1173534`
- Add verbose logging: `ssh -v -L 5433:localhost:5432 cotton@srv1173534`

### 5. Verify Sync Success

```bash
# Check row counts in local database
python -c "
from database import SessionLocal, engine
from sqlalchemy import text
session = SessionLocal()
result = session.execute(text('SELECT COUNT(*) FROM portfolios'))
print(f'Portfolios: {result.scalar()}')
result = session.execute(text('SELECT COUNT(*) FROM portfolio_data'))
print(f'Portfolio Data: {result.scalar()}')
session.close()
"
```

## Security Notes

- ⚠️ **Never commit** database passwords to git
- ⚠️ **Use SSH tunnel** instead of exposing PostgreSQL port publicly
- ⚠️ **Don't share** the `cmtool` password
- ⚠️ **Rotate passwords** periodically
- ⚠️ **Use read-only** database user if possible

## Troubleshooting

### Error: "connection refused"
- Make sure SSH tunnel is active
- Check that port 5433 is not already in use: `lsof -i :5433`

### Error: "channel XX: open failed: connect failed"
This error appears when the SSH tunnel can't forward connections to PostgreSQL.

**Test the tunnel:**
```bash
./test_ssh_tunnel.sh
```

**Common causes and fixes:**

1. **PostgreSQL not listening on localhost**
   ```bash
   # Check on server
   ssh cotton@srv1173534 'sudo netstat -tlnp | grep 5432'

   # Should show: 127.0.0.1:5432 or 0.0.0.0:5432
   ```

2. **pg_hba.conf doesn't allow local connections**
   ```bash
   # Check configuration
   ssh cotton@srv1173534 'sudo cat /etc/postgresql/*/main/pg_hba.conf | grep local'

   # Should have: local all all trust OR local all all md5
   ```

3. **PostgreSQL service is down**
   ```bash
   # Check status
   ssh cotton@srv1173534 'sudo systemctl status postgresql'

   # Restart if needed
   ssh cotton@srv1173534 'sudo systemctl restart postgresql'
   ```

4. **Too many connections or tunnel instability**
   ```bash
   # Kill existing tunnel
   pkill -f "ssh.*5433.*5432"

   # Restart with keep-alive options
   ssh -N -L 5433:localhost:5432 \
       -o ServerAliveInterval=60 \
       -o ServerAliveCountMax=3 \
       cotton@srv1173534
   ```

5. **Use direct database connection (if VPS allows)**
   ```bash
   # If PostgreSQL allows external connections (check with admin)
   python sync_prod_to_dev.py "postgresql://cmtool:PASSWORD@srv1173534:5432/portfolio_analysis"
   ```

### Error: "password authentication failed"
- Verify the `cmtool` password
- Check if user has permissions: `psql -U cmtool -d portfolio_analysis`

### Error: "could not translate host name"
- Make sure you're using `localhost:5433` (tunneled port)
- Not `srv1173534:5432` (direct connection - won't work)

### Sync is very slow
- Normal for large datasets (100K+ rows in portfolio_data)
- Monitor progress in terminal
- Consider syncing during off-peak hours

### Foreign key constraint errors
- Should not happen (script respects FK order)
- If it does, report the issue - the TABLE_ORDER may need adjustment

## Future Improvements

Potential enhancements for this script:
- [ ] Add `--dry-run` mode to preview changes
- [ ] Add `--tables` flag to sync specific tables only
- [ ] Add `--date-filter` to sync recent data only
- [ ] Add progress bar for large tables
- [ ] Add compression for data transfer
- [ ] Add automatic backup before sync
- [ ] Support for incremental sync (only changed data)

## Questions?

If you encounter issues:
1. Check the error message carefully
2. Review this documentation
3. Check server logs: `ssh cotton@srv1173534 'tail -100 /opt/cmtool/logs/portfolio_analysis.log'`
4. Verify database status on server: `ssh cotton@srv1173534 'sudo systemctl status cmtool'`
