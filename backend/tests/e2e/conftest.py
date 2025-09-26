"""
Shared pytest fixtures for E2E tests.

Provides async HTTP client and test configuration.
"""

import pytest
import pytest_asyncio
import uuid
import time
from typing import AsyncGenerator, Dict, Optional
import httpx
from config import settings


# pytest-asyncio is now configured in root conftest.py


@pytest.fixture(scope="session")
def anyio_backend():
    """Use asyncio as the async backend."""
    return "asyncio"


@pytest.fixture(scope="session")
def config():
    """Get test configuration."""
    return settings


@pytest_asyncio.fixture
async def api_client() -> AsyncGenerator[httpx.AsyncClient, None]:
    """Create async HTTP client for API requests."""
    async with httpx.AsyncClient(
        base_url=settings.api_url,
        headers=settings.api_headers,
        timeout=httpx.Timeout(settings.default_timeout),
        follow_redirects=True,
    ) as client:
        yield client


@pytest_asyncio.fixture
async def collection(api_client: httpx.AsyncClient) -> AsyncGenerator[Dict, None]:
    """Create a test collection that's cleaned up after use."""
    # Create collection
    collection_data = {"name": f"Test Collection {int(time.time())}"}
    response = await api_client.post("/collections/", json=collection_data)

    if response.status_code != 200:
        pytest.fail(f"Failed to create test collection: {response.text}")

    collection = response.json()

    # Yield for test to useclear

    yield collection

    # Cleanup
    try:
        await api_client.delete(f"/collections/{collection['readable_id']}")
    except:
        pass  # Best effort cleanup


@pytest_asyncio.fixture
async def composio_auth_provider(
    api_client: httpx.AsyncClient, config
) -> AsyncGenerator[Dict, None]:
    """Create Composio auth provider connection for testing."""
    if not config.TEST_COMPOSIO_API_KEY:
        pytest.skip("Composio API key not configured")

    provider_readable_id = f"composio-test-{int(time.time())}"
    auth_provider_payload = {
        "name": "Test Composio Provider",
        "short_name": "composio",
        "readable_id": provider_readable_id,
        "auth_fields": {"api_key": config.TEST_COMPOSIO_API_KEY},
    }

    response = await api_client.put("/auth-providers/connect", json=auth_provider_payload)

    if response.status_code != 200:
        pytest.fail(f"Failed to create Composio auth provider: {response.text}")

    provider = response.json()

    # Yield for test to use
    yield provider

    # Cleanup
    try:
        await api_client.delete(f"/auth-providers/{provider['readable_id']}")
    except:
        pass  # Best effort cleanup


@pytest_asyncio.fixture
async def source_connection_fast(
    api_client: httpx.AsyncClient,
    collection: Dict,
    composio_auth_provider: Dict,
    config,
) -> AsyncGenerator[Dict, None]:
    """Create a fast Asana source connection via Composio."""
    connection_data = {
        "name": f"Asana Fast Connection {int(time.time())}",
        "short_name": "asana",
        "readable_collection_id": collection["readable_id"],
        "authentication": {
            "provider_readable_id": composio_auth_provider["readable_id"],
            "provider_config": {
                "auth_config_id": config.TEST_COMPOSIO_ASANA_AUTH_CONFIG_ID,
                "account_id": config.TEST_COMPOSIO_ASANA_ACCOUNT_ID,
            },
        },
        "sync_immediately": False,
    }

    response = await api_client.post("/source-connections", json=connection_data)

    if response.status_code != 200:
        pytest.fail(f"Failed to create Asana connection: {response.text}")

    connection = response.json()

    # Yield for test to use
    yield connection

    # Cleanup
    try:
        await api_client.delete(f"/source-connections/{connection['id']}")
    except:
        pass  # Best effort cleanup


@pytest_asyncio.fixture
async def source_connection_medium(
    api_client: httpx.AsyncClient, collection: Dict, config
) -> AsyncGenerator[Dict, None]:
    """Create a medium-speed Stripe source connection for testing quick syncs.

    Uses real Stripe API key from environment variables.
    Full sync but faster than Gmail.
    """
    connection_data = {
        "name": f"Stripe Medium Connection {int(time.time())}",
        "short_name": "stripe",
        "readable_collection_id": collection["readable_id"],
        "authentication": {"credentials": {"api_key": config.stripe_api_key}},
        "sync_immediately": False,  # Control sync timing in tests
    }

    response = await api_client.post("/source-connections", json=connection_data)

    if response.status_code == 400 and "invalid" in response.text.lower():
        # Skip if using dummy/invalid credentials
        pytest.skip(f"Skipping due to invalid Stripe credentials: {response.text}")

    if response.status_code != 200:
        pytest.fail(f"Failed to create Stripe connection: {response.text}")

    connection = response.json()

    # Yield for test to use
    yield connection

    # Cleanup
    try:
        await api_client.delete(f"/source-connections/{connection['id']}")
    except:
        pass  # Best effort cleanup


@pytest_asyncio.fixture
async def source_connection_slow(
    api_client: httpx.AsyncClient, collection: Dict, composio_auth_provider: Dict, config
) -> AsyncGenerator[Dict, None]:
    """Create a slow Gmail source connection via Composio.

    Uses cursor fields and is the slowest sync option.
    """
    # Skip if Gmail config not available
    if not config.TEST_COMPOSIO_GMAIL_AUTH_CONFIG_ID or not config.TEST_COMPOSIO_GMAIL_ACCOUNT_ID:
        pytest.skip("Gmail Composio configuration not available")

    connection_data = {
        "name": f"Gmail Slow Connection {int(time.time())}",
        "short_name": "gmail",
        "readable_collection_id": collection["readable_id"],
        "authentication": {
            "provider_readable_id": composio_auth_provider["readable_id"],
            "provider_config": {
                "auth_config_id": config.TEST_COMPOSIO_GMAIL_AUTH_CONFIG_ID,
                "account_id": config.TEST_COMPOSIO_GMAIL_ACCOUNT_ID,
            },
        },
        "sync_immediately": False,
    }

    response = await api_client.post("/source-connections", json=connection_data)

    if response.status_code != 200:
        pytest.fail(f"Failed to create Gmail connection: {response.text}")

    connection = response.json()

    # Yield for test to use
    yield connection

    # Cleanup
    try:
        await api_client.delete(f"/source-connections/{connection['id']}")
    except:
        pass  # Best effort cleanup


@pytest.fixture
def unique_name() -> str:
    """Generate a unique name for test resources."""
    return f"test_{int(time.time())}_{uuid.uuid4().hex[:8]}"


@pytest_asyncio.fixture
async def pipedream_auth_provider(api_client: httpx.AsyncClient) -> Dict:
    """Create a Pipedream auth provider for testing."""
    import os

    # Check for Pipedream environment variables
    pipedream_client_id = os.environ.get("TEST_PIPEDREAM_CLIENT_ID")
    pipedream_client_secret = os.environ.get("TEST_PIPEDREAM_CLIENT_SECRET")

    if not all([pipedream_client_id, pipedream_client_secret]):
        pytest.skip("Pipedream credentials not configured")

    provider_id = f"pipedream-test-{int(time.time())}"
    auth_provider_payload = {
        "name": "Test Pipedream Provider",
        "short_name": "pipedream",
        "readable_id": provider_id,
        "auth_fields": {
            "client_id": pipedream_client_id,
            "client_secret": pipedream_client_secret,
        },
    }

    response = await api_client.put("/auth-providers/connect", json=auth_provider_payload)

    if response.status_code != 200:
        pytest.fail(f"Failed to create Pipedream auth provider: {response.text}")

    provider = response.json()

    # Yield for test to use
    yield provider

    # Cleanup
    try:
        await api_client.delete(f"/auth-providers/{provider['readable_id']}")
    except:
        pass  # Best effort cleanup


# Markers for test categorization
def pytest_configure(config):
    """Register custom markers."""
    config.addinivalue_line("markers", "slow: marks tests as slow")
    config.addinivalue_line("markers", "requires_sync: tests that require completed sync")
    config.addinivalue_line(
        "markers", "requires_temporal: tests that require Temporal (local only)"
    )
    config.addinivalue_line("markers", "critical: critical path tests that must pass")
    config.addinivalue_line("markers", "requires_openai: tests that require OpenAI API key")
    config.addinivalue_line(
        "markers", "requires_composio: tests that require Composio auth provider"
    )
