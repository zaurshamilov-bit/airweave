"""Unit tests for the API keys endpoints."""

from unittest.mock import AsyncMock, patch
from uuid import UUID

import pytest

from airweave.api.v1.endpoints.api_keys import create_api_key, read_api_key
from airweave.schemas import APIKey, APIKeyCreate, User


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
        expiration_date=None,  # Let the backend handle the default
    )


@pytest.fixture
def mock_api_key():
    """Create a mock API key response."""
    return APIKey(
        id=UUID("11111111-2222-3333-4444-555555555555"),
        organization_id=UUID("87654321-8765-4321-8765-432187654321"),
        created_at="2023-01-01T00:00:00",
        modified_at="2023-01-01T00:00:00",
        created_by_email="test@example.com",
        modified_by_email="test@example.com",
        expiration_date="2023-01-01T00:00:00",
        last_used_date=None,
        organization=UUID("87654321-8765-4321-8765-432187654321"),
        decrypted_key="test-api-key-plain-text",  # Using decrypted_key instead of plain_key
    )


@pytest.mark.asyncio
async def test_create_api_key(mock_user, mock_api_key_create, mock_api_key):
    """Test creating a new API key."""
    # Mock the database session
    mock_db = AsyncMock()

    # Create a mock API key DB object with encrypted_key
    mock_db_api_key = AsyncMock()
    mock_db_api_key.id = mock_api_key.id
    mock_db_api_key.encrypted_key = "encrypted-version-of-key"  # This would be the encrypted key
    mock_db_api_key.organization_id = mock_api_key.organization
    mock_db_api_key.created_at = mock_api_key.created_at
    mock_db_api_key.modified_at = mock_api_key.modified_at
    mock_db_api_key.expiration_date = mock_api_key.expiration_date
    mock_db_api_key.created_by_email = mock_api_key.created_by_email
    mock_db_api_key.modified_by_email = mock_api_key.modified_by_email

    # Mock the CRUD and decryption functions
    with patch("airweave.crud.api_key.create_with_user", return_value=mock_db_api_key) as mock_create, \
         patch("airweave.core.credentials.decrypt", return_value={"key": mock_api_key.decrypted_key}):

        # Call the function
        result = await create_api_key(
            db=mock_db,
            api_key_in=mock_api_key_create,
            user=mock_user,
        )

        # Check the result
        assert result.id == mock_api_key.id
        assert result.decrypted_key == mock_api_key.decrypted_key


@pytest.mark.asyncio
async def test_read_api_key(mock_user, mock_api_key):
    """Test reading an API key."""
    # Mock the database session
    mock_db = AsyncMock()

    # Create a mock API key DB object with encrypted_key
    mock_db_api_key = AsyncMock()
    mock_db_api_key.id = mock_api_key.id
    mock_db_api_key.encrypted_key = "encrypted-version-of-key"
    mock_db_api_key.organization_id = mock_api_key.organization
    mock_db_api_key.created_at = mock_api_key.created_at
    mock_db_api_key.modified_at = mock_api_key.modified_at
    mock_db_api_key.expiration_date = mock_api_key.expiration_date
    mock_db_api_key.created_by_email = mock_api_key.created_by_email
    mock_db_api_key.modified_by_email = mock_api_key.modified_by_email

    # Mock the CRUD and decryption functions
    with patch("airweave.crud.api_key.get", return_value=mock_db_api_key) as mock_get, \
         patch("airweave.core.credentials.decrypt", return_value={"key": mock_api_key.decrypted_key}):

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
        assert result.id == mock_api_key.id
        assert result.decrypted_key == mock_api_key.decrypted_key
