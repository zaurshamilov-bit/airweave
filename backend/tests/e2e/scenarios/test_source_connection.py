"""E2E tests for Source Connection operations."""

import uuid

import pytest
import requests


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


def test_source_connection_operations(
    e2e_environment, e2e_api_url, source_connection_data, integration_credential_data
):
    """Test the complete lifecycle for a Source Connection.

    This test:
    1. Creates a new integration credential
    2. Creates a new source connection using the credential
    3. Retrieves the source connection
    4. Updates the source connection
    5. Deletes the source connection
    6. Verifies the source connection is gone
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
    assert connection["name"] == source_connection_data["name"]
    assert connection["short_name"] == source_connection_data["short_name"]
    assert connection["integration_type"] == source_connection_data["integration_type"]
    assert connection["status"] == source_connection_data["status"]

    # Step 3: Retrieve the source connection
    get_response = requests.get(f"{e2e_api_url}/connections/{connection_id}")
    assert get_response.status_code == 200, f"Failed to get connection: {get_response.text}"
    retrieved_connection = get_response.json()
    assert retrieved_connection["id"] == connection_id
    assert retrieved_connection["name"] == source_connection_data["name"]

    # Step 4: Update the source connection
    update_data = {"name": f"Updated Source Connection {uuid.uuid4()}", "status": "INACTIVE"}
    update_response = requests.put(f"{e2e_api_url}/connections/{connection_id}", json=update_data)
    assert update_response.status_code == 200, (
        f"Failed to update connection: {update_response.text}"
    )
    updated_connection = update_response.json()
    assert updated_connection["name"] == update_data["name"]
    assert updated_connection["status"] == update_data["status"]
    # Other fields should remain unchanged
    assert updated_connection["short_name"] == source_connection_data["short_name"]
    assert updated_connection["integration_type"] == source_connection_data["integration_type"]

    # Step 5: Delete the source connection
    delete_response = requests.delete(f"{e2e_api_url}/connections/{connection_id}")
    assert delete_response.status_code == 200, (
        f"Failed to delete connection: {delete_response.text}"
    )

    # Step 6: Verify the source connection is gone
    get_after_delete_response = requests.get(f"{e2e_api_url}/connections/{connection_id}")
    assert get_after_delete_response.status_code == 404, "Source connection should be deleted"

    # Clean up: Delete the integration credential
    delete_credential_response = requests.delete(
        f"{e2e_api_url}/connections/credentials/{credential_id}"
    )
    assert delete_credential_response.status_code == 200, (
        f"Failed to delete credential: {delete_credential_response.text}"
    )
