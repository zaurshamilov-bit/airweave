"""
Async test module for OAuth source connections.

Tests OAuth authentication flows including:
- OAuth browser flow
- OAuth token injection
- OAuth BYOC (Bring Your Own Credentials)
"""

import pytest
import httpx
import asyncio
from typing import Dict


@pytest.mark.asyncio
class TestOAuthAuthentication:
    """Test suite for OAuth authentication source connections."""

    async def test_oauth_browser_flow(self, api_client: httpx.AsyncClient, collection: Dict):
        """Test OAuth browser flow (creates shell connection)."""
        payload = {
            "name": "Test Linear OAuth Browser",
            "short_name": "linear",
            "readable_collection_id": collection["readable_id"],
            "description": "Testing OAuth browser flow",
            "authentication": {},  # Empty for browser flow
            "sync_immediately": False,
        }

        response = await api_client.post("/source-connections", json=payload)

        response.raise_for_status()
        connection = response.json()

        # Verify OAuth browser flow response
        assert connection["id"]
        assert connection["auth"]["method"] == "oauth_browser"
        assert connection["auth"]["authenticated"] == False
        assert connection["status"] == "pending_auth"
        assert "auth_url" in connection["auth"]
        assert connection["auth"]["auth_url"] is not None

        # Cleanup
        await api_client.delete(f"/source-connections/{connection['id']}")

    async def test_oauth_token_injection_notion(
        self, api_client: httpx.AsyncClient, collection: Dict, config
    ):
        """Test OAuth token injection with Notion."""
        payload = {
            "name": "Test Notion Token Injection",
            "short_name": "notion",
            "readable_collection_id": collection["readable_id"],
            "description": "Testing OAuth token injection",
            "authentication": {"access_token": config.TEST_NOTION_TOKEN},
            "sync_immediately": False,
        }

        response = await api_client.post("/source-connections", json=payload)

        response.raise_for_status()
        connection = response.json()

        # Verify OAuth token injection response
        assert connection["id"]
        assert connection["auth"]["method"] == "oauth_token"
        assert connection["auth"]["authenticated"] == True
        assert connection["status"] in ["active", "syncing"]

        # Cleanup
        await api_client.delete(f"/source-connections/{connection['id']}")

    async def test_oauth_byoc_google_drive(
        self, api_client: httpx.AsyncClient, collection: Dict, config
    ):
        """Test OAuth BYOC with Google Drive."""
        client_id = config.TEST_GOOGLE_CLIENT_ID
        client_secret = config.TEST_GOOGLE_CLIENT_SECRET

        payload = {
            "name": "Test Google Drive BYOC",
            "short_name": "google_drive",
            "readable_collection_id": collection["readable_id"],
            "description": "Testing OAuth BYOC flow",
            "authentication": {"client_id": client_id, "client_secret": client_secret},
            "sync_immediately": False,
        }

        response = await api_client.post("/source-connections", json=payload)

        response.raise_for_status()
        connection = response.json()

        # BYOC returns oauth_browser after creation
        assert connection["id"]
        assert connection["auth"]["method"] == "oauth_browser"
        assert connection["auth"]["authenticated"] == False
        assert connection["status"] == "pending_auth"
        assert "auth_url" in connection["auth"]
        assert connection["auth"]["auth_url"] is not None

        # Cleanup
        await api_client.delete(f"/source-connections/{connection['id']}")

    async def test_minimal_oauth_payload(self, api_client: httpx.AsyncClient, collection: Dict):
        """Test minimal OAuth payload defaults."""
        # Minimal payload - should default to OAuth browser
        payload = {"short_name": "notion", "readable_collection_id": collection["readable_id"]}

        response = await api_client.post("/source-connections", json=payload)

        response.raise_for_status()
        connection = response.json()

        # Verify defaults
        assert connection["name"] == "Notion Connection"  # Default name
        assert connection["status"] == "pending_auth"
        assert connection["auth"]["method"] == "oauth_browser"
        assert "auth_url" in connection["auth"]
        auth_url = connection["auth"]["auth_url"]
        assert isinstance(auth_url, str)
        assert auth_url.startswith("http://") or auth_url.startswith("https://")

        # Cleanup
        await api_client.delete(f"/source-connections/{connection['id']}")

    async def test_oauth_wrong_auth_method(self, api_client: httpx.AsyncClient, collection: Dict):
        """Test using OAuth on source that doesn't support it."""
        # Try OAuth token on Stripe (which only supports API key)
        payload = {
            "name": "Wrong Auth Method",
            "short_name": "stripe",
            "readable_collection_id": collection["readable_id"],
            "authentication": {"access_token": "some_token"},
        }

        response = await api_client.post("/source-connections", json=payload)

        assert response.status_code == 400
        error = response.json()
        detail = error.get("detail", "").lower()
        assert "does not support" in detail or "unsupported" in detail
