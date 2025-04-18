"""Unit tests for the health check endpoint."""

import pytest
from fastapi.testclient import TestClient

from airweave.main import app


def test_health_check():
    """Test the health check endpoint returns status as healthy."""
    # Create a test client for the FastAPI app
    client = TestClient(app)

    # Make a GET request to the health endpoint
    response = client.get("/health")

    # Check the response status code is 200 OK
    assert response.status_code == 200
    # Check the response payload
    assert response.json() == {"status": "healthy"}
