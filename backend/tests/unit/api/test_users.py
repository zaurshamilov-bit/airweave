"""Unit tests for the users endpoints."""

from uuid import UUID

import pytest

from airweave.api.v1.endpoints.users import read_user
from airweave.schemas import User


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


@pytest.mark.asyncio
async def test_read_user(mock_user):
    """Test reading the current user information."""
    # Call the function directly with the mock user
    result = await read_user(current_user=mock_user)

    # Check the result
    assert result.email == mock_user.email
    assert result.full_name == mock_user.full_name
    assert result.id == mock_user.id
