# Multi-stage build for React frontend + FastAPI backend
FROM node:20-alpine AS frontend-builder

# Build React frontend
WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# Python backend stage
FROM python:3.11-slim

WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy Python application
COPY . .

# Copy built React frontend from previous stage
COPY --from=frontend-builder /app/frontend/dist ./frontend/dist

# Ensure required directories exist
RUN mkdir -p uploads/plots && \
    mkdir -p frontend/dist/assets && \
    touch frontend/dist/index.html

EXPOSE 8000

# Use PORT environment variable from Render
CMD ["sh", "-c", "uvicorn app:app --host 0.0.0.0 --port ${PORT:-8000}"]
