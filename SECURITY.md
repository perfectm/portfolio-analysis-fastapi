# Security Configuration

## Environment Variables

This application requires sensitive configuration through environment variables. **Never commit passwords or API keys to version control.**

### Required Environment Variables

For production deployment, set these environment variables in your hosting platform:

```bash
DATABASE_URL=postgresql://username:password@host:port/database_name
RENDER=true
ENVIRONMENT=production
```

### Local Development

For local development, create a `.env.production` file (already gitignored):

```bash
# Copy from .env.example and fill in actual values
cp .env.example .env.production
```

Then edit `.env.production` with your actual database credentials.

### Hosting Platform Setup

#### Render.com
1. Go to your Render dashboard
2. Select your web service
3. Navigate to "Environment" tab
4. Add the required environment variables

#### Other Platforms
Set the environment variables according to your platform's documentation.

### Security Best Practices

1. **Never commit credentials**: All sensitive files are gitignored
2. **Use environment variables**: Configuration should come from the environment
3. **Rotate passwords**: Change database passwords periodically
4. **Limit access**: Only grant necessary database permissions
5. **Monitor logs**: Check for authentication failures

### Files Excluded from Git

The following files contain sensitive data and are excluded from version control:

- `.env.production`
- `.env.render`
- `.env.local`
- `test_postgresql.py` (when configured with credentials)
- `create_tables.py` (when configured with credentials)
- `init_production_db.py` (when configured with credentials)
- `check_env.py` (when configured with credentials)
- Documentation files that may contain example credentials

### Testing Database Connection

To test your database connection securely:

```bash
# Set the DATABASE_URL environment variable
export DATABASE_URL="postgresql://user:password@host:port/database"

# Run the test script
python test_postgresql.py
```

### Troubleshooting

If you encounter authentication errors:

1. Verify environment variables are set correctly
2. Check database host and port accessibility
3. Confirm username and password are correct
4. Ensure database exists and user has proper permissions

For more help, check the application logs for specific error messages.
