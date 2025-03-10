"""E2E tests for Source CRUD operations."""

import uuid

import pytest
import requests


@pytest.fixture
def source_data():
    """Fixture to provide test source data."""
    return {
        "name": f"Test Source {uuid.uuid4()}",
        "description": "Test source created by E2E test",
        "type": "file",
        "config": {"path": "/tmp/test", "file_types": ["txt", "md", "pdf"]},
    }


def test_source_crud_operations(e2e_environment, e2e_api_url, source_data):
    """Test the complete CRUD lifecycle for a Source.

    This test:
    1. Creates a new source
    2. Retrieves the source by ID
    3. Updates the source
    4. Deletes the source
    5. Verifies the source is gone
    """
    # Step 1: Create a new source
    create_response = requests.post(f"{e2e_api_url}/sources/", json=source_data)
    assert create_response.status_code == 200, f"Failed to create source: {create_response.text}"

    # Extract the source ID from the response
    source = create_response.json()
    source_id = source["id"]
    assert source["name"] == source_data["name"]
    assert source["description"] == source_data["description"]

    # Step 2: Retrieve the source by ID
    get_response = requests.get(f"{e2e_api_url}/sources/{source_id}")
    assert get_response.status_code == 200, f"Failed to get source: {get_response.text}"
    retrieved_source = get_response.json()
    assert retrieved_source["id"] == source_id
    assert retrieved_source["name"] == source_data["name"]

    # Step 3: Update the source
    update_data = {
        "name": f"Updated Source {uuid.uuid4()}",
        "description": "Updated description from E2E test",
    }
    update_response = requests.put(f"{e2e_api_url}/sources/{source_id}", json=update_data)
    assert update_response.status_code == 200, f"Failed to update source: {update_response.text}"
    updated_source = update_response.json()
    assert updated_source["id"] == source_id
    assert updated_source["name"] == update_data["name"]
    assert updated_source["description"] == update_data["description"]

    # Step 4: Delete the source
    delete_response = requests.delete(f"{e2e_api_url}/sources/{source_id}")
    assert delete_response.status_code == 200, f"Failed to delete source: {delete_response.text}"

    # Step 5: Verify the source is gone
    get_deleted_response = requests.get(f"{e2e_api_url}/sources/{source_id}")
    assert get_deleted_response.status_code == 404, "Source should be deleted"
