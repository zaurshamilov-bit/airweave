"""
Async test module for Auth Provider source connections.

Tests authentication via external auth providers like Composio and Pipedream.
"""

import pytest
import httpx
import time
import asyncio
from typing import Dict


SLEEP_TIME = 30


class TestAuthProviderAuthentication:
    """Test suite for auth provider source connections."""

    @pytest.mark.asyncio
    async def test_composio_auth_provider(
        self,
        api_client: httpx.AsyncClient,
        collection: Dict,
        composio_auth_provider: Dict,
        config,
    ):
        """Test Composio auth provider for Asana."""

        # Create source connection using the auth provider fixture
        connection_payload = {
            "name": "Test Asana via Composio",
            "short_name": "asana",
            "readable_collection_id": collection["readable_id"],
            "description": "Testing auth provider authentication with Asana",
            "authentication": {
                "provider_readable_id": composio_auth_provider["readable_id"],
                "provider_config": {
                    "auth_config_id": config.TEST_COMPOSIO_ASANA_AUTH_CONFIG_ID,
                    "account_id": config.TEST_COMPOSIO_ASANA_ACCOUNT_ID,
                },
            },
            "sync_immediately": False,
        }

        response = await api_client.post("/source-connections", json=connection_payload)

        response.raise_for_status()
        connection = response.json()
        assert connection["id"]
        assert connection["auth"]["method"] == "auth_provider"
        assert connection["auth"]["authenticated"] == True
        assert connection["auth"]["provider_id"] == composio_auth_provider["readable_id"]
        assert connection["status"] == "active"
        assert connection["sync"] == None

        # Cleanup
        await api_client.delete(f"/source-connections/{connection['id']}")

    @pytest.mark.asyncio
    async def test_composio_auth_provider_sync_immediately(
        self,
        api_client: httpx.AsyncClient,
        collection: Dict,
        composio_auth_provider: Dict,
        config,
    ):
        """Test Composio auth provider for Todoist."""

        # Create source connection using the auth provider fixture
        connection_payload = {
            "name": "Test Todoist via Composio",
            "short_name": "todoist",
            "readable_collection_id": collection["readable_id"],
            "description": "Testing auth provider authentication with Todoist",
            "authentication": {
                "provider_readable_id": composio_auth_provider["readable_id"],
                "provider_config": {
                    "auth_config_id": config.TEST_COMPOSIO_TODOIST_AUTH_CONFIG_ID,
                    "account_id": config.TEST_COMPOSIO_TODOIST_ACCOUNT_ID,
                },
            },
            "sync_immediately": True,
        }

        response = await api_client.post("/source-connections", json=connection_payload)

        response.raise_for_status()
        connection = response.json()
        assert connection["id"]
        assert connection["auth"]["method"] == "auth_provider"
        assert connection["auth"]["authenticated"] == True
        assert connection["auth"]["provider_id"] == composio_auth_provider["readable_id"]
        assert connection["status"] == "active"
        assert connection["sync"]["last_job"]["status"] == "pending"
        assert connection["sync"]["last_job"]["entities_processed"] == 0

        await asyncio.sleep(SLEEP_TIME)

        response = await api_client.get(f"/source-connections/{connection['id']}")
        response.raise_for_status()
        updated_connection = response.json()
        assert updated_connection["status"] == "active"
        assert updated_connection["auth"]["method"] == "auth_provider"
        assert updated_connection["auth"]["authenticated"] == True
        assert updated_connection["auth"]["provider_id"] == composio_auth_provider["readable_id"]
        assert updated_connection["sync"]["last_job"]["status"] == "completed"
        assert updated_connection["sync"]["last_job"]["entities_processed"] > 0

        # Cleanup
        await api_client.delete(f"/source-connections/{connection['id']}")

    @pytest.mark.asyncio
    async def test_pipedream_proxy_auth_provider(
        self, api_client: httpx.AsyncClient, collection: Dict, pipedream_auth_provider: Dict, config
    ):
        """Test Pipedream proxy auth provider for Google Drive."""
        import os

        pipedream_project_id = config.TEST_PIPEDREAM_PROJECT_ID
        pipedream_account_id = config.TEST_PIPEDREAM_ACCOUNT_ID
        pipedream_external_user_id = config.TEST_PIPEDREAM_EXTERNAL_USER_ID

        if not all(
            [
                pipedream_project_id,
                pipedream_account_id,
                pipedream_external_user_id,
            ]
        ):
            raise ValueError("Pipedream project config not set")

        # Create Google Drive connection via Pipedream
        connection_payload = {
            "name": "Test Google Drive via Pipedream",
            "short_name": "google_drive",
            "readable_collection_id": collection["readable_id"],
            "description": "Testing Google Drive with Pipedream proxy authentication",
            "authentication": {
                "provider_readable_id": pipedream_auth_provider["readable_id"],
                "provider_config": {
                    "project_id": pipedream_project_id,
                    "account_id": pipedream_account_id,
                    "external_user_id": pipedream_external_user_id,
                    "environment": "development",
                },
            },
            "sync_immediately": False,
        }

        response = await api_client.post("/source-connections", json=connection_payload)

        assert (
            response.status_code == 200
        ), f"Failed to create Google Drive connection: {response.text}"
        connection = response.json()

        # Verify connection
        assert connection["auth"]["method"] == "auth_provider"
        assert connection["auth"]["authenticated"] == True
        assert connection["auth"]["provider_id"] == pipedream_auth_provider["readable_id"]
        assert connection["status"] == "active"

        # Test sync
        response = await api_client.post(f"/source-connections/{connection['id']}/run")

        job = response.json()

        # Wait a bit for sync to process
        await asyncio.sleep(SLEEP_TIME)

        # Get updated source connection details with entity information
        response = await api_client.get(f"/source-connections/{connection['id']}")
        response.raise_for_status()
        updated_connection = response.json()

        assert updated_connection["status"] == "syncing"
        assert updated_connection["auth"]["method"] == "auth_provider"
        assert updated_connection["auth"]["authenticated"] == True
        assert updated_connection["auth"]["provider_id"] == pipedream_auth_provider["readable_id"]
        # Google Drive runs for some time, so we expect it to be running
        assert updated_connection["sync"]["last_job"]["status"] == "running"
        assert updated_connection["entities"]["total_entities"] > 0

        # Cleanup
        await api_client.delete(f"/source-connections/{connection['id']}")

    @pytest.mark.asyncio
    async def test_invalid_auth_provider(self, api_client: httpx.AsyncClient, collection: Dict):
        """Test using non-existent auth provider."""
        connection_payload = {
            "name": "Test Invalid Provider",
            "short_name": "asana",
            "readable_collection_id": collection["readable_id"],
            "authentication": {"provider_readable_id": "non-existent-provider-xyz"},
        }

        response = await api_client.post("/source-connections", json=connection_payload)

        assert response.status_code == 404
        error = response.json()
        assert "not found" in error.get("detail", "").lower()
