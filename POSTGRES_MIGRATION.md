# PostgreSQL Migration Guide

This guide will help you migrate from SQLite to PostgreSQL for improved performance.

## Current Database Size
- **270 MB** total
- **757,123** margin data records
- **65,723** portfolio data records
- **Expected performance improvement**: 30-50% faster queries

## Prerequisites (Completed ✅)
- [x] PostgreSQL installed on Hostinger
- [x] Database `portfolio_analysis` created
- [x] User `cmtool` created with permissions

## Migration Steps

### Step 1: Set PostgreSQL Password

On your **Hostinger server**, set a secure password for the cmtool user:

```bash
# SSH to Hostinger
ssh cotton@srv1173534

# Set password for cmtool database user
sudo -u postgres psql -c "ALTER USER cmtool WITH PASSWORD 'YOUR_SECURE_PASSWORD_HERE';"
```

Save this password - you'll need it in Step 3.

### Step 2: Test PostgreSQL Connection

```bash
# On Hostinger, navigate to your app directory
cd /opt/cmtool

# Activate the Python virtual environment
source venv/bin/activate
# (You should see (venv) in your prompt)

# Set the DATABASE_URL with your password
export DATABASE_URL='postgresql://cmtool:YOUR_PASSWORD_HERE@localhost:5432/portfolio_analysis'

# Run the connection test
python test_postgres.py
```

You should see:
```
✅ Connection successful!
PostgreSQL version: PostgreSQL 14.x
✅ All tests passed! Ready for migration.
```

If the test fails, check the troubleshooting steps in the output.

### Step 3: Run Migration

**IMPORTANT**: This will copy all data from SQLite to PostgreSQL. Your SQLite database will remain unchanged as a backup.

```bash
# Still on Hostinger in /opt/cmtool
# Make sure venv is activated and DATABASE_URL is still set
# (If you closed the terminal, run these again:)
source venv/bin/activate
export DATABASE_URL='postgresql://cmtool:YOUR_PASSWORD_HERE@localhost:5432/portfolio_analysis'

# Run the migration
python migrate_to_postgres.py
```

The migration will:
1. Verify both database connections
2. Create all tables in PostgreSQL
3. Copy data in batches (showing progress)
4. Reset PostgreSQL sequences
5. Provide a summary report

**Expected duration**: 2-5 minutes for 270 MB

### Step 4: Configure Production Environment

Update your systemd service to use PostgreSQL:

```bash
# Create environment file for cmtool service
sudo nano /opt/cmtool/.env

# Add this line (replace with your actual password):
DATABASE_URL=postgresql://cmtool:YOUR_PASSWORD_HERE@localhost:5432/portfolio_analysis
```

Or update the systemd service file directly:

```bash
sudo nano /etc/systemd/system/cmtool.service

# Add this line in the [Service] section:
Environment="DATABASE_URL=postgresql://cmtool:YOUR_PASSWORD_HERE@localhost:5432/portfolio_analysis"

# Reload systemd
sudo systemctl daemon-reload
```

### Step 5: Restart Application

```bash
# Restart the cmtool service
sudo systemctl restart cmtool

# Check status
sudo systemctl status cmtool

# Check logs for PostgreSQL connection
tail -f /opt/cmtool/logs/portfolio_analysis.log
```

Look for this line in the logs:
```
✅ Database engine created successfully with PostgreSQL
```

### Step 6: Verify Application

1. Open your application: `https://portfolio.cottonmike.com`
2. Test portfolio analysis
3. Check that all data appears correctly
4. Run a weighted analysis to test performance

### Step 7: Monitor Performance

After migration, you can check PostgreSQL performance:

```bash
# On Hostinger
sudo -u postgres psql -d portfolio_analysis

# Check database size
\dt+

# Check active connections
SELECT count(*) FROM pg_stat_activity;

# Check slow queries (later)
SELECT query, mean_exec_time
FROM pg_stat_statements
ORDER BY mean_exec_time DESC
LIMIT 10;

\q
```

## Rollback Plan (If Needed)

If something goes wrong, you can quickly rollback to SQLite:

```bash
# Remove or comment out DATABASE_URL
sudo nano /opt/cmtool/.env
# (Comment out the DATABASE_URL line)

# Or remove from systemd service
sudo nano /etc/systemd/system/cmtool.service
# (Comment out Environment="DATABASE_URL=...")

# Restart
sudo systemctl daemon-reload
sudo systemctl restart cmtool
```

The application will automatically fall back to SQLite.

## Post-Migration Optimization

Once PostgreSQL is working, you can optimize further:

### 1. Remove Duplicate Indexes (saves ~40 MB)

```sql
-- Connect to database
sudo -u postgres psql -d portfolio_analysis

-- Drop redundant indexes
DROP INDEX IF EXISTS ix_portfolio_margin_data_date;
DROP INDEX IF EXISTS ix_portfolio_margin_data_id;

-- PostgreSQL will still use the other indexes efficiently
```

### 2. Enable Query Performance Tracking

```sql
-- Enable pg_stat_statements extension
CREATE EXTENSION IF NOT EXISTS pg_stat_statements;
```

### 3. Configure PostgreSQL for VPS

Edit PostgreSQL config for better VPS performance:

```bash
sudo nano /etc/postgresql/14/main/postgresql.conf

# Adjust these based on your VPS RAM (example for 4GB VPS):
shared_buffers = 512MB          # 25% of RAM
effective_cache_size = 3GB      # 75% of RAM
maintenance_work_mem = 128MB
work_mem = 32MB
```

Then restart PostgreSQL:
```bash
sudo systemctl restart postgresql
```

## Troubleshooting

### "password authentication failed"
- Check your password is correct
- Verify DATABASE_URL has correct password

### "database 'portfolio_analysis' does not exist"
- Create it: `sudo -u postgres createdb -O cmtool portfolio_analysis`

### "relation does not exist"
- Tables weren't created. Run: `python -c "from database import create_tables; create_tables()"`

### Migration incomplete
- Check `/opt/cmtool/logs/portfolio_analysis.log` for errors
- Re-run migration (it will skip existing data)

## Performance Comparison

### Before (SQLite):
- Portfolio analysis: ~3-5 seconds
- Margin calculations: ~2-3 seconds
- Database size: 270 MB (lots of wasted space)

### After (PostgreSQL) - Expected:
- Portfolio analysis: ~2-3 seconds (30% faster)
- Margin calculations: ~1-2 seconds (40% faster)
- Database size: ~180 MB (better compression)
- Concurrent users: No more locking issues

## Backup Strategy

### PostgreSQL Backups

```bash
# Daily backup (add to cron)
pg_dump -U cmtool portfolio_analysis | gzip > /opt/cmtool/backups/portfolio_analysis_$(date +%Y%m%d).sql.gz

# Restore from backup
gunzip -c /opt/cmtool/backups/portfolio_analysis_20231227.sql.gz | psql -U cmtool portfolio_analysis
```

### Keep SQLite as Emergency Backup
Don't delete `portfolio_analysis.db` for at least 2 weeks after migration.

## Questions?

Check the application logs:
```bash
tail -f /opt/cmtool/logs/portfolio_analysis.log
```

Or review the migration script output for specific error messages.
