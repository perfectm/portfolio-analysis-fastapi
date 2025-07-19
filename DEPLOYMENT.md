# Deployment Guide for Render

## Prerequisites

- Render account
- PostgreSQL database already created on Render with hostname: `dpg-d1u03gbipnbc73cqnl2g-a`

## Deployment Steps

### 1. Create Web Service on Render

1. Connect your GitHub repository to Render
2. Create a new Web Service
3. Configure the following settings:
   - **Runtime**: Python 3
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `uvicorn app:app --host 0.0.0.0 --port $PORT`

### 2. Environment Variables

Set the following environment variables in Render dashboard:

#### Required Database Variables

```
DB_HOST=dpg-d1u03gbipnbc73cqnl2g-a.render.com
DB_PORT=5432
DB_NAME=portanal
DB_USER=portanal_user
DB_PASSWORD=iAthbnJVh3kqOBfeTWiG8sG6mr7DQ44G
```

**Important**: The database password should be set directly in Render's environment variables dashboard and never committed to Git.

#### Optional Variables

```
RENDER=true
ENVIRONMENT=production
LOG_LEVEL=INFO
SESSION_SECRET_KEY=<generate-secure-key>
```

### 3. Database Initialization

After first deployment, initialize the database:

1. Access Render shell or use database management tool
2. Run: `python init_db.py` (if this file exists)
3. Or the tables will be created automatically on first request

### 4. Verification

1. Check deployment logs for any errors
2. Visit your app URL
3. Test file upload functionality
4. Verify data persistence by checking PostgreSQL database

## Troubleshooting

### Database Connection Issues

- Verify database hostname and credentials
- Check if database allows external connections
- Review connection logs in Render dashboard

### Application Errors

- Check Render deployment logs
- Verify all required packages in requirements.txt
- Ensure environment variables are set correctly

### File Upload Issues

- Render has ephemeral storage - uploaded files won't persist between deployments
- Consider using cloud storage (AWS S3, etc.) for file persistence if needed

## Security Notes

- Never commit actual passwords to Git
- Use Render's environment variables for sensitive data
- Consider enabling SSL/HTTPS for production
