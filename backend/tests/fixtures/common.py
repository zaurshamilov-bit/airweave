"""Common test fixtures."""

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import AsyncSession

from airweave import schemas
from airweave.core.shared_models import SyncJobStatus, SyncStatus


@pytest.fixture
def mock_user():
    """Create a mock user for tests."""
    organization_id = uuid.uuid4()
    user = schemas.User(
        id=uuid.uuid4(),
        email="test@example.com",
        is_active=True,
        is_superuser=False,
        full_name="Test User",
        organization_id=organization_id,
    )
    return user


@pytest.fixture
def mock_sync():
    """Create a mock sync for tests."""
    organization_id = uuid.uuid4()
    return schemas.Sync(
        id=uuid.uuid4(),
        name="Test Sync",
        description="Test description",
        source_connection_id=uuid.uuid4(),
        destination_connection_ids=[uuid.uuid4()],
        user_id=uuid.uuid4(),
        tenant_id=uuid.uuid4(),
        created_at="2023-01-01T00:00:00",
        updated_at="2023-01-01T00:00:00",
        organization_id=organization_id,
        status=SyncStatus.ACTIVE,
        modified_at="2023-01-01T00:00:00",
        created_by_email="test@example.com",
        modified_by_email="test@example.com",
    )


@pytest.fixture
def mock_sync_job():
    """Create a mock sync job for tests."""
    organization_id = uuid.uuid4()
    return schemas.SyncJob(
        id=uuid.uuid4(),
        sync_id=uuid.uuid4(),
        status=SyncJobStatus.PENDING,
        progress=0,
        error=None,
        started_at=None,
        completed_at=None,
        created_at="2023-01-01T00:00:00",
        updated_at="2023-01-01T00:00:00",
        organization_id=organization_id,
        created_by_email="test@example.com",
        modified_by_email="test@example.com",
        modified_at="2023-01-01T00:00:00",
        entities_detected=0,
        entities_inserted=0,
        entities_deleted=0,
        entities_skipped=0,
    )


@pytest.fixture
def mock_sync_dag():
    """Create a mock sync DAG for tests."""
    organization_id = uuid.uuid4()
    return schemas.SyncDag(
        id=uuid.uuid4(),
        sync_id=uuid.uuid4(),
        dag={},
        created_at="2023-01-01T00:00:00",
        updated_at="2023-01-01T00:00:00",
        organization_id=organization_id,
        created_by_email="test@example.com",
        modified_by_email="test@example.com",
        modified_at="2023-01-01T00:00:00",
        name="Test DAG",
        nodes=[],
        edges=[],
    )


@pytest.fixture
def mock_db():
    """Create a mock database session."""
    return AsyncMock(spec=AsyncSession)


@pytest.fixture
def mock_background_tasks():
    """Create a mock background tasks."""
    return MagicMock()


@pytest.fixture
def app():
    """Create a test FastAPI application."""
    return FastAPI()
