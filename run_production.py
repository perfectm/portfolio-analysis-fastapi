#!/usr/bin/env python3
"""
Run the FastAPI application with production database configuration.
This loads environment variables from .env.production file.
"""

import os
from dotenv import load_dotenv

# Load production environment variables
load_dotenv('.env.production')

print("🚀 Starting FastAPI with Production Database...")
print(f"📊 Database: {os.getenv('DATABASE_URL', 'NOT SET')[:50]}...")

# Import and run the application
if __name__ == "__main__":
    import uvicorn
    from app import app
    
    # Run the development server
    uvicorn.run(
        app, 
        host="127.0.0.1", 
        port=8004, 
        reload=True,
        log_level="info"
    )
