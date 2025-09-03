import pytest
from fastapi.testclient import TestClient
from app import app

client = TestClient(app)

def test_root_endpoint():
    """Test that the root endpoint returns HTML."""
    response = client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]

def test_upload_endpoint_get():
    """Test that the upload endpoint serves React app for GET requests."""
    response = client.get("/upload")
    assert response.status_code == 200  # React app served by catch-all route

def test_app_startup():
    """Test that the FastAPI app can be created successfully."""
    assert app is not None
    assert hasattr(app, 'routes')

def test_static_files_mount():
    """Test that static files are properly mounted."""
    # This tests that the app has the uploads mount
    route_paths = [route.path for route in app.routes]
    uploads_mounted = any('/uploads' in path for path in route_paths)
    assert uploads_mounted
