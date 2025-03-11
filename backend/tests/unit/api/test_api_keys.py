"""Unit tests for the API keys endpoints."""

from unittest.mock import AsyncMock, patch
from uuid import UUID

import pytest

from airweave.api.v1.endpoints.api_keys import create_api_key, read_api_key
from airweave.schemas import APIKey, APIKeyCreate, APIKeyWithPlainKey, User


@pytest.fixture
def mock_user():
    """Create a mock user for testing."""
    return User(
        id=UUID("12345678-1234-5678-1234-567812345678"),
        email="test@example.com",
        full_name="Test User",
        is_active=True,
        organization_id=UUID("87654321-8765-4321-8765-432187654321"),
    )


@pytest.fixture
def mock_api_key_create():
    """Create a mock API key creation object."""
    return APIKeyCreate(
        name="Test API Key",
        description="API key for testing",
    )


@pytest.fixture
def mock_api_key_with_plain_key():
    """Create a mock API key with plain key response."""
    return APIKeyWithPlainKey(
        id=UUID("11111111-2222-3333-4444-555555555555"),
        name="Test API Key",
        description="API key for testing",
        organization_id=UUID("87654321-8765-4321-8765-432187654321"),
        key_prefix="test",
        plain_key="test-api-key-plain-text",
        created_at="2023-01-01T00:00:00",
        modified_at="2023-01-01T00:00:00",
        last_used_date=None,
        expiration_date="2023-01-01T00:00:00",
        created_by_email="test@example.com",
        modified_by_email="test@example.com",
        organization=UUID("87654321-8765-4321-8765-432187654321"),
    )


@pytest.fixture
def mock_api_key():
    """Create a mock API key response (without plain key)."""
    return APIKey(
        id=UUID("11111111-2222-3333-4444-555555555555"),
        name="Test API Key",
        description="API key for testing",
        organization_id=UUID("87654321-8765-4321-8765-432187654321"),
        created_at="2023-01-01T00:00:00",
        updated_at="2023-01-01T00:00:00",
        created_by_email="test@example.com",
        modified_by_email="test@example.com",
        key_prefix="test",
        plain_key="test-api-key-plain-text",
        expiration_date="2023-01-01T00:00:00",
        last_used_date=None,
        organization=UUID("87654321-8765-4321-8765-432187654321"),
        modified_at="2023-01-01T00:00:00",
    )


@pytest.mark.asyncio
async def test_create_api_key(mock_user, mock_api_key_create, mock_api_key_with_plain_key):
    """Test creating a new API key."""
    # Mock the database session
    mock_db = AsyncMock()

    # Mock the crud.api_key.create_with_user function
    with patch(
        "airweave.crud.api_key.create_with_user", return_value=mock_api_key_with_plain_key
    ) as mock_create:
        # Call the function
        result = await create_api_key(
            db=mock_db,
            api_key_in=mock_api_key_create,
            user=mock_user,
        )

        # Check that the crud function was called with the right arguments
        mock_create.assert_called_once_with(
            db=mock_db,
            obj_in=mock_api_key_create,
            current_user=mock_user,
        )

        # Check the result
        assert result == mock_api_key_with_plain_key
        assert result.key_prefix == "test"


@pytest.mark.asyncio
async def test_read_api_key(mock_user, mock_api_key):
    """Test reading an API key."""
    # Mock the database session
    mock_db = AsyncMock()

    # Mock the crud.api_key.get function
    with patch("airweave.crud.api_key.get", return_value=mock_api_key) as mock_get:
        # Call the function
        result = await read_api_key(
            db=mock_db,
            id=UUID("11111111-2222-3333-4444-555555555555"),
            user=mock_user,
        )

        # Check that the crud function was called with the right arguments
        mock_get.assert_called_once_with(
            db=mock_db,
            id=UUID("11111111-2222-3333-4444-555555555555"),
            current_user=mock_user,
        )

        # Check the result
        assert result == mock_api_key
