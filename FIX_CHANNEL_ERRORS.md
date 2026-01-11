# Fixing "channel open failed" SSH Tunnel Errors

## Current Status
✅ SSH tunnel is running (port 5433 is open)
❓ Need to verify PostgreSQL on the server

## Step-by-Step Fix

### Step 1: Check PostgreSQL Status on Server
```bash
ssh cotton@srv1173534 'sudo systemctl status postgresql'
```

**Expected output:** Active (running)
**If not running:** `ssh cotton@srv1173534 'sudo systemctl start postgresql'`

### Step 2: Verify PostgreSQL Listens on Localhost
```bash
ssh cotton@srv1173534 'sudo ss -tlnp | grep 5432'
```

**Expected output:** Should show PostgreSQL listening on `127.0.0.1:5432`

**If not listening on localhost:**
```bash
# Check postgresql.conf
ssh cotton@srv1173534 'sudo grep "^listen_addresses" /etc/postgresql/*/main/postgresql.conf'

# Should be: listen_addresses = 'localhost' OR listen_addresses = '*'
```

### Step 3: Check pg_hba.conf Allows Local Connections
```bash
ssh cotton@srv1173534 'sudo cat /etc/postgresql/*/main/pg_hba.conf | grep -v "^#" | grep local'
```

**Expected output:**
```
local   all             all                                     md5
# OR
local   all             all                                     trust
```

### Step 4: Test Direct Connection on Server
```bash
ssh cotton@srv1173534 'psql -U cmtool -d portfolio_analysis -c "SELECT version();"'
```

This tests if you can connect to PostgreSQL directly on the server (not through tunnel).

### Step 5: Restart SSH Tunnel with Better Options
```bash
# Kill existing tunnel
pkill -f "ssh.*5433.*5432"

# Start new tunnel with keepalive options
ssh -N -L 5433:localhost:5432 \
    -o ServerAliveInterval=60 \
    -o ServerAliveCountMax=3 \
    -o TCPKeepAlive=yes \
    cotton@srv1173534
```

### Step 6: Test Sync with Smaller Batch Size
If the tunnel keeps dropping connections, modify the sync script to use smaller batches:

Edit `sync_prod_to_dev.py` line 169:
```python
# Change from:
batch_size = 1000

# To:
batch_size = 100  # Smaller batches = less data per connection
```

## Alternative: Direct Connection (Without Tunnel)

If the SSH tunnel continues to have issues, you can configure PostgreSQL to accept direct connections:

### On Server (as root):
```bash
# 1. Edit postgresql.conf to listen on all interfaces
sudo nano /etc/postgresql/*/main/postgresql.conf
# Find: listen_addresses = 'localhost'
# Change to: listen_addresses = '*'

# 2. Edit pg_hba.conf to allow your IP
sudo nano /etc/postgresql/*/main/pg_hba.conf
# Add this line (replace YOUR_IP with your actual IP):
host    portfolio_analysis    cmtool    YOUR_IP/32    md5

# 3. Restart PostgreSQL
sudo systemctl restart postgresql

# 4. Check firewall allows port 5432
sudo ufw status
sudo ufw allow from YOUR_IP to any port 5432
```

### Then connect directly:
```bash
python sync_prod_to_dev.py "postgresql://cmtool:PASSWORD@srv1173534:5432/portfolio_analysis"
```

## Quick Diagnostic Commands

Run these to gather info:

```bash
# 1. Check if tunnel is active
lsof -i :5433

# 2. Test tunnel connectivity
nc -zv localhost 5433

# 3. Check PostgreSQL on server
ssh cotton@srv1173534 'sudo systemctl is-active postgresql'

# 4. Check database connections
ssh cotton@srv1173534 'sudo -u postgres psql -c "SELECT count(*) FROM pg_stat_activity WHERE datname = '\''portfolio_analysis'\'';"'

# 5. Check for connection errors in PostgreSQL logs
ssh cotton@srv1173534 'sudo tail -50 /var/log/postgresql/postgresql-*-main.log | grep -i error'
```

## Most Likely Issue

Based on the errors you're seeing, the most common cause is:

**PostgreSQL is not listening on localhost (127.0.0.1)**

To fix:
1. SSH to server: `ssh cotton@srv1173534`
2. Check PostgreSQL config: `sudo grep listen_addresses /etc/postgresql/*/main/postgresql.conf`
3. If it shows only specific IPs (not localhost), edit it: `sudo nano /etc/postgresql/*/main/postgresql.conf`
4. Add or uncomment: `listen_addresses = 'localhost,<other_ips>'`
5. Restart: `sudo systemctl restart postgresql`

## Need More Help?

If these steps don't resolve it, run all diagnostic commands and provide the output:

```bash
# Save diagnostics to file
{
    echo "=== PostgreSQL Status ==="
    ssh cotton@srv1173534 'sudo systemctl status postgresql'
    echo ""
    echo "=== PostgreSQL Listen Addresses ==="
    ssh cotton@srv1173534 'sudo grep listen_addresses /etc/postgresql/*/main/postgresql.conf'
    echo ""
    echo "=== PostgreSQL Port Binding ==="
    ssh cotton@srv1173534 'sudo ss -tlnp | grep 5432'
    echo ""
    echo "=== Recent PostgreSQL Errors ==="
    ssh cotton@srv1173534 'sudo tail -30 /var/log/postgresql/postgresql-*-main.log'
} > diagnostic_output.txt

cat diagnostic_output.txt
```
