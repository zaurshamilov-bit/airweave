"""E2E tests for White Label CRUD operations."""

import uuid

import pytest
import requests


@pytest.fixture
def white_label_data():
    """Fixture to provide test white label data."""
    return {
        "name": f"Test White Label {uuid.uuid4()}",
        "source_short_name": "slack",  # Using a known source type
        "redirect_url": "https://example.com/callback",
        "client_id": f"client-{uuid.uuid4()}",
        "client_secret": f"secret-{uuid.uuid4()}",
    }


def test_white_label_crud_operations(e2e_environment, e2e_api_url, white_label_data):
    """Test the complete CRUD lifecycle for a White Label.

    This test:
    1. Creates a new white label
    2. Retrieves the white label by ID
    3. Updates the white label
    4. Deletes the white label
    5. Verifies the white label is gone
    """
    # Step 1: Create a new white label
    create_response = requests.post(f"{e2e_api_url}/white_labels/", json=white_label_data)
    assert create_response.status_code == 200, (
        f"Failed to create white label: {create_response.text}"
    )

    # Extract the white label ID from the response
    white_label = create_response.json()
    white_label_id = white_label["id"]
    assert white_label["name"] == white_label_data["name"]
    assert white_label["source_short_name"] == white_label_data["source_short_name"]
    assert white_label["redirect_url"] == white_label_data["redirect_url"]
    assert white_label["client_id"] == white_label_data["client_id"]
    # client_secret should not be returned in the response for security reasons

    # Step 2: Retrieve the white label by ID
    get_response = requests.get(f"{e2e_api_url}/white_labels/{white_label_id}")
    assert get_response.status_code == 200, f"Failed to get white label: {get_response.text}"
    retrieved_white_label = get_response.json()
    assert retrieved_white_label["id"] == white_label_id
    assert retrieved_white_label["name"] == white_label_data["name"]

    # Step 3: Update the white label
    update_data = {
        "name": f"Updated White Label {uuid.uuid4()}",
        "redirect_url": "https://updated-example.com/callback",
    }
    update_response = requests.put(f"{e2e_api_url}/white_labels/{white_label_id}", json=update_data)
    assert update_response.status_code == 200, (
        f"Failed to update white label: {update_response.text}"
    )
    updated_white_label = update_response.json()
    assert updated_white_label["name"] == update_data["name"]
    assert updated_white_label["redirect_url"] == update_data["redirect_url"]
    # Other fields should remain unchanged
    assert updated_white_label["source_short_name"] == white_label_data["source_short_name"]
    assert updated_white_label["client_id"] == white_label_data["client_id"]

    # Step 4: Delete the white label
    delete_response = requests.delete(f"{e2e_api_url}/white_labels/{white_label_id}")
    assert delete_response.status_code == 200, (
        f"Failed to delete white label: {delete_response.text}"
    )

    # Step 5: Verify the white label is gone
    get_after_delete_response = requests.get(f"{e2e_api_url}/white_labels/{white_label_id}")
    assert get_after_delete_response.status_code == 404, "White label should be deleted"
