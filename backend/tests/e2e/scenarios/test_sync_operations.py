"""E2E tests for Sync operations."""

import uuid

import pytest
import requests


@pytest.fixture
def integration_credential_data():
    """Fixture to provide test integration credential data."""
    return {
        "name": f"Test Integration Credential {uuid.uuid4()}",
        "description": "Test credential created by E2E test",
        "integration_short_name": "slack",
        "integration_type": "SOURCE",
        "auth_type": "api_key",
        "credentials": {"api_key": f"test-api-key-{uuid.uuid4()}"},
        "auth_config_class": None,
    }


@pytest.fixture
def source_connection_data():
    """Fixture to provide test source connection data."""
    return {
        "name": f"Test Source Connection {uuid.uuid4()}",
        "integration_type": "SOURCE",
        "status": "ACTIVE",
        "short_name": "slack",  # Using a known source type
        "integration_credential_id": None,  # Will be created during test
    }


@pytest.fixture
def sync_data():
    """Fixture to provide test sync data."""
    return {
        "name": f"Test Sync {uuid.uuid4()}",
        "description": "Test sync created by E2E test",
        "source_connection_id": None,  # Will be created during test
        "destination_connection_id": None,  # Will use default destination
        "embedding_model_connection_id": None,  # Will use default embedding model
        "run_immediately": False,
        "schedule": None,
    }


def test_sync_operations(
    e2e_environment, e2e_api_url, integration_credential_data, source_connection_data, sync_data
):
    """Test the complete lifecycle for a Sync.

    This test:
    1. Creates a new integration credential
    2. Creates a new source connection using the credential
    3. Creates a new sync using the source connection
    4. Retrieves the sync
    5. Updates the sync
    6. Deletes the sync
    7. Verifies the sync is gone
    8. Cleans up the source connection and credential
    """
    # Step 1: Create a new integration credential
    create_credential_response = requests.post(
        f"{e2e_api_url}/connections/credentials/", json=integration_credential_data
    )
    assert create_credential_response.status_code == 200, (
        f"Failed to create credential: {create_credential_response.text}"
    )

    # Extract the credential ID from the response
    credential = create_credential_response.json()
    credential_id = credential["id"]

    # Update the source connection data with the credential ID
    source_connection_data["integration_credential_id"] = credential_id

    # Step 2: Create a new source connection
    create_connection_response = requests.post(
        f"{e2e_api_url}/connections/", json=source_connection_data
    )
    assert create_connection_response.status_code == 200, (
        f"Failed to create connection: {create_connection_response.text}"
    )

    # Extract the connection ID from the response
    connection = create_connection_response.json()
    connection_id = connection["id"]

    # Update the sync data with the source connection ID
    sync_data["source_connection_id"] = connection_id

    # Step 3: Create a new sync
    create_sync_response = requests.post(f"{e2e_api_url}/sync/", json=sync_data)
    assert create_sync_response.status_code == 200, (
        f"Failed to create sync: {create_sync_response.text}"
    )

    # Extract the sync ID from the response
    sync = create_sync_response.json()
    sync_id = sync["id"]
    assert sync["name"] == sync_data["name"]
    assert sync["description"] == sync_data["description"]
    assert sync["source_connection_id"] == sync_data["source_connection_id"]

    # Step 4: Retrieve the sync
    get_response = requests.get(f"{e2e_api_url}/sync/{sync_id}")
    assert get_response.status_code == 200, f"Failed to get sync: {get_response.text}"
    retrieved_sync = get_response.json()
    assert retrieved_sync["id"] == sync_id
    assert retrieved_sync["name"] == sync_data["name"]

    # Step 5: Update the sync
    update_data = {
        "name": f"Updated Sync {uuid.uuid4()}",
        "description": "Updated sync description",
    }
    update_response = requests.put(f"{e2e_api_url}/sync/{sync_id}", json=update_data)
    assert update_response.status_code == 200, f"Failed to update sync: {update_response.text}"
    updated_sync = update_response.json()
    assert updated_sync["name"] == update_data["name"]
    assert updated_sync["description"] == update_data["description"]
    # Other fields should remain unchanged
    assert updated_sync["source_connection_id"] == sync_data["source_connection_id"]

    # Step 6: Delete the sync
    delete_response = requests.delete(f"{e2e_api_url}/sync/{sync_id}")
    assert delete_response.status_code == 200, f"Failed to delete sync: {delete_response.text}"

    # Step 7: Verify the sync is gone
    get_after_delete_response = requests.get(f"{e2e_api_url}/sync/{sync_id}")
    assert get_after_delete_response.status_code == 404, "Sync should be deleted"

    # Step 8: Clean up - Delete the source connection and credential
    delete_connection_response = requests.delete(f"{e2e_api_url}/connections/{connection_id}")
    assert delete_connection_response.status_code == 200, (
        f"Failed to delete connection: {delete_connection_response.text}"
    )

    delete_credential_response = requests.delete(
        f"{e2e_api_url}/connections/credentials/{credential_id}"
    )
    assert delete_credential_response.status_code == 200, (
        f"Failed to delete credential: {delete_credential_response.text}"
    )
