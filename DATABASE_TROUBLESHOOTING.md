# Database Connection Troubleshooting Guide

## Common Issues and Solutions

### 1. 🚨 CRITICAL: No Password Supplied

**Error**: `fe_sendauth: no password supplied` or `password authentication failed`

**Root Cause**: The `DB_PASSWORD` environment variable is not set or is empty.

**Solution**:

1. **In Render Dashboard**:

   - Go to your web service
   - Click on "Environment" tab
   - Add or update: `DB_PASSWORD=iAthbnJVh3kqOBfeTWiG8sG6mr7DQ44G`
   - Click "Save Changes"
   - Redeploy your service

2. **Verify Environment Variables**:

   ```bash
   python check_env.py
   ```

3. **Required Environment Variables**:
   ```
   DB_HOST=dpg-d1u03gbipnbc73cqnl2g-a
   DB_PORT=5432
   DB_NAME=portanal
   DB_USER=portanal_user
   DB_PASSWORD=iAthbnJVh3kqOBfeTWiG8sG6mr7DQ44G
   ```

### 2. Hostname Resolution Error

**Error**: `could not translate host name "dpg-d1u03gbipnbc73cqnl2g-a.render.com" to address: Name or service not known`

**Solution**:

- Use the internal hostname without `.render.com`: `dpg-d1u03gbipnbc73cqnl2g-a`
- The application automatically tries both internal and external hostnames
- Set environment variable: `DB_HOST=dpg-d1u03gbipnbc73cqnl2g-a`

### 2. Connection Timeout

**Error**: Connection timeouts or hanging connections

**Solution**:

- The application now includes a 10-second connection timeout
- Render services may take time to start - wait a few minutes and retry
- Check Render dashboard for database status

### 3. Authentication Error

**Error**: `FATAL: password authentication failed`

**Solution**:

- Verify all environment variables are set correctly in Render dashboard:
  ```
  DB_HOST=dpg-d1u03gbipnbc73cqnl2g-a
  DB_PORT=5432
  DB_NAME=portanal
  DB_USER=portanal_user
  DB_PASSWORD=iAthbnJVh3kqOBfeTWiG8sG6mr7DQ44G
  ```

### 4. Database Not Found

**Error**: `FATAL: database "portanal" does not exist`

**Solution**:

- Verify the database name in Render dashboard
- Ensure the PostgreSQL service is running
- Check that the database was created successfully

### 5. Local Development

**Issue**: Want to test locally without PostgreSQL

**Solution**:

- The application automatically falls back to SQLite for local development
- No additional configuration needed
- SQLite database file: `portfolio_analysis.db`

## Environment Variable Priority

The application checks environment variables in this order:

1. **DATABASE_URL** (full connection string) - highest priority
2. **DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD** (individual components)
3. **Localhost PostgreSQL** (development fallback)
4. **SQLite** (final fallback)

## Testing Database Connection

Test the database connection locally:

```bash
python -c "from database import engine, DATABASE_URL; print(f'Database URL: {DATABASE_URL}'); print(f'Engine: {engine}')"
```

## Render Deployment Checklist

- [ ] Set all required environment variables in Render dashboard
- [ ] Use internal hostname (without .render.com)
- [ ] Verify database service is running
- [ ] Check application logs for connection status
- [ ] Test `/portfolios` endpoint to verify database functionality

## Logs to Check

Look for these log messages:

- `✅ Database engine created successfully with PostgreSQL`
- `⚠️ Falling back to SQLite database for local development`
- `❌ Failed to create PostgreSQL engine: [error details]`

## Production Environment Variables

Set these in Render dashboard (Environment tab):

```
DB_HOST=dpg-d1u03gbipnbc73cqnl2g-a
DB_PORT=5432
DB_NAME=portanal
DB_USER=portanal_user
DB_PASSWORD=iAthbnJVh3kqOBfeTWiG8sG6mr7DQ44G
RENDER=true
ENVIRONMENT=production
```
