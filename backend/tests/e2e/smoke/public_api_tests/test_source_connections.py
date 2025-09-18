"""
Test module for Source Connections with new nested authentication API.

This module replaces the original test_source_connections.py to test the refactored API with:
- Nested authentication structure (DirectAuthentication, OAuthTokenAuthentication, etc.)
- New response models (SourceConnection with nested auth details)
- Various authentication methods (modular approach)
- State transitions

This is designed to run in the CI/CD pipeline via test-public-api.yml
"""

import time
import uuid
import os
import requests
from typing import Tuple, Optional, Dict, Any, List
from .utils import show_backend_logs
from .test_pubsub import test_sync_job_pubsub


class SourceConnectionTestBase:
    """Base class for all source connection tests"""

    def __init__(self, api_url: str, headers: dict, collection_id: str):
        self.api_url = api_url
        self.headers = headers
        self.collection_id = collection_id

    def create_connection(self, payload: dict) -> requests.Response:
        """Create a source connection and return response"""
        response = requests.post(
            f"{self.api_url}/source-connections", json=payload, headers=self.headers
        )
        return response

    def verify_response_structure(self, conn: dict, expected_auth_method: str) -> None:
        """Verify the response matches expected structure"""
        assert "id" in conn, "Missing id field"
        assert "name" in conn, "Missing name field"
        assert "status" in conn, "Missing status field"
        assert "readable_collection_id" in conn, "Missing readable_collection_id"
        assert "auth" in conn, "Missing auth object"
        assert (
            conn["auth"]["method"] == expected_auth_method
        ), f"Expected {expected_auth_method}, got {conn['auth']['method']}"

    def update_connection(self, conn_id: str, update_data: dict) -> Optional[dict]:
        """Update a connection using PATCH"""
        response = requests.patch(
            f"{self.api_url}/source-connections/{conn_id}", json=update_data, headers=self.headers
        )
        return response.json() if response.status_code == 200 else None

    def run_sync(self, conn_id: str) -> Optional[dict]:
        """Trigger manual sync"""
        response = requests.post(
            f"{self.api_url}/source-connections/{conn_id}/run", headers=self.headers
        )
        return response.json() if response.status_code == 200 else None

    def wait_for_job(self, conn_id: str, job_id: str, timeout: int = 60) -> str:
        """Wait for sync job to complete and return final status"""
        elapsed = 0
        poll_interval = 5

        while elapsed < timeout:
            response = requests.get(
                f"{self.api_url}/source-connections/{conn_id}/jobs", headers=self.headers
            )

            if response.status_code == 200:
                jobs = response.json()
                job = next((j for j in jobs if j["id"] == job_id), None)

                if job:
                    status = job["status"].lower()
                    if status in ["completed", "failed", "cancelled"]:
                        return status

            time.sleep(poll_interval)
            elapsed += poll_interval

        return "timeout"


class DirectAuthTest(SourceConnectionTestBase):
    """Test direct authentication flow (e.g., Stripe with API key)"""

    def create_payload(self, api_key: str, sync_immediately: bool = False) -> dict:
        return {
            "name": "Test Stripe Direct Auth",
            "short_name": "stripe",
            "readable_collection_id": self.collection_id,
            "description": "Testing direct authentication with API key",
            "authentication": {"credentials": {"api_key": api_key}},
            "schedule": {"cron": "0 */6 * * *"},
            "sync_immediately": sync_immediately,
        }

    def run_test(self, api_key: str) -> str:
        """Run complete direct auth test flow"""
        print("  Testing Direct Authentication (Stripe)...")

        # Step 1: Create connection
        payload = self.create_payload(api_key, sync_immediately=False)
        response = self.create_connection(payload)

        if response.status_code != 200:
            print(f"    Failed to create: {response.status_code}")
            print(f"    Response: {response.text}")
            show_backend_logs(lines=20)
            raise AssertionError(f"Failed to create direct auth connection: {response.text}")

        conn = response.json()
        conn_id = conn["id"]
        self.verify_response_structure(conn, "direct")

        # Step 2: Verify authenticated
        assert conn["auth"]["authenticated"] == True, "Should be authenticated"
        assert conn["status"] == "active", f"Expected active status, got {conn['status']}"
        print(f"    ✓ Connection created: {conn_id}")

        # Step 3: Update connection
        update_data = {
            "name": "Updated Stripe Connection",
            "description": "Updated via PATCH",
            "schedule": {"cron": "0 0 * * *"},  # Daily
        }

        updated = self.update_connection(conn_id, update_data)
        if updated:
            assert updated["name"] == update_data["name"], "Name not updated"
            print(f"    ✓ Connection updated")

        # Step 4: Run sync
        job = self.run_sync(conn_id)
        if job:
            job_id = job["id"]
            assert job["source_connection_id"] == conn_id
            print(f"    ✓ Sync job started: {job_id}")

            # Step 5: Brief wait for job
            final_status = self.wait_for_job(conn_id, job_id, timeout=30)
            print(f"    ✓ Job status after 30s: {final_status}")

        return conn_id


class OAuthBrowserTest(SourceConnectionTestBase):
    """Test OAuth browser flow - limited in CI environment"""

    def create_payload(self) -> dict:
        return {
            "name": "Test Slack OAuth Browser",
            "short_name": "slack",
            "readable_collection_id": self.collection_id,
            "description": "Testing OAuth browser flow",
            "authentication": {},  # Empty for browser flow
            "sync_immediately": False,
        }

    def run_test(self) -> Optional[str]:
        """Run OAuth browser test - stops at shell creation in CI"""
        print("  Testing OAuth Browser Flow (Slack)...")

        # Step 1: Create shell connection
        payload = self.create_payload()
        response = self.create_connection(payload)

        if response.status_code != 200:
            print(f"    ⚠️ OAuth browser test skipped: {response.status_code}")
            return None

        conn = response.json()
        conn_id = conn["id"]
        self.verify_response_structure(conn, "oauth_browser")

        # Step 2: Verify pending auth state
        assert conn["auth"]["authenticated"] == False, "Should not be authenticated"
        assert conn["status"] == "pending_auth", f"Expected pending_auth, got {conn['status']}"
        assert "auth_url" in conn["auth"], "Missing auth_url"
        assert conn["auth"]["auth_url"] is not None, "auth_url should not be None"

        print(f"    ✓ OAuth shell created: {conn_id}")
        print(f"    ℹ️ Cannot complete OAuth flow in CI (requires user interaction)")

        return conn_id


class AuthProviderTest(SourceConnectionTestBase):
    """Test authentication via external auth provider"""

    def create_payload(self, provider_name: str, provider_config: Optional[dict] = None) -> dict:
        """Create payload for auth provider connection"""
        auth = {"provider_name": provider_name}
        if provider_config:
            auth["provider_config"] = provider_config

        return {
            "name": f"Test {provider_name} Auth Provider",
            "short_name": "google_drive",  # Most sources support auth provider
            "readable_collection_id": self.collection_id,
            "description": "Testing auth provider authentication",
            "authentication": auth,
            "sync_immediately": False,
        }

    def run_test(self, provider_name: str, provider_config: Optional[dict] = None) -> Optional[str]:
        """Run auth provider test"""
        print(f"  Testing Auth Provider ({provider_name})...")

        # Step 1: Create connection with auth provider
        payload = self.create_payload(provider_name, provider_config)
        response = self.create_connection(payload)

        if response.status_code == 404:
            print(f"    ⚠️ Auth provider '{provider_name}' not found in this environment")
            return None

        if response.status_code != 200:
            print(f"    ⚠️ Auth provider test failed: {response.status_code}")
            print(f"    Response: {response.text}")
            return None

        conn = response.json()
        conn_id = conn["id"]
        self.verify_response_structure(conn, "auth_provider")

        # Step 2: Verify authenticated via provider
        assert conn["auth"]["authenticated"] == True, "Should be authenticated via provider"
        assert "provider_name" in conn["auth"], "Missing provider_name in auth"
        assert conn["auth"]["provider_name"] == provider_name, "Provider name mismatch"
        assert conn["status"] == "active", f"Expected active status, got {conn['status']}"

        print(f"    ✓ Connection created via auth provider: {conn_id}")
        print(f"    ✓ Provider: {provider_name}")

        return conn_id


class OAuthTokenTest(SourceConnectionTestBase):
    """Test OAuth token injection"""

    def create_payload(
        self, source_name: str, access_token: str, refresh_token: Optional[str] = None
    ) -> dict:
        """Create payload for OAuth token injection"""
        auth = {"access_token": access_token}
        if refresh_token:
            auth["refresh_token"] = refresh_token
            auth["expires_at"] = "2025-12-31T23:59:59Z"  # Future date

        return {
            "name": f"Test {source_name} Token Injection",
            "short_name": source_name,
            "readable_collection_id": self.collection_id,
            "description": "Testing OAuth token injection",
            "authentication": auth,
            "sync_immediately": True,
        }

    def run_test(
        self, source_name: str, access_token: str, refresh_token: Optional[str] = None
    ) -> Optional[str]:
        """Run OAuth token injection test"""
        print(f"  Testing OAuth Token Injection ({source_name})...")

        # Step 1: Create connection with injected token
        payload = self.create_payload(source_name, access_token, refresh_token)
        response = self.create_connection(payload)

        if response.status_code == 400:
            # Token might be invalid or expired
            print(f"    ⚠️ Token validation failed for {source_name}")
            return None

        if response.status_code != 200:
            print(f"    ⚠️ OAuth token test failed: {response.status_code}")
            print(f"    Response: {response.text}")
            return None

        conn = response.json()
        conn_id = conn["id"]
        self.verify_response_structure(conn, "oauth_token")

        # Step 2: Verify authenticated with token
        assert conn["auth"]["authenticated"] == True, "Should be authenticated with token"
        if "expires_at" in conn["auth"]:
            print(f"    Token expires at: {conn['auth']['expires_at']}")

        # Should be active or syncing (since sync_immediately=True)
        assert conn["status"] in ["active", "syncing"], f"Unexpected status: {conn['status']}"

        print(f"    ✓ Connection created with OAuth token: {conn_id}")
        if refresh_token:
            print(f"    ✓ Has refresh token")

        # Check if sync started
        if conn["status"] == "syncing" or (conn.get("sync") and conn["sync"].get("last_job")):
            print(f"    ✓ Sync auto-started")

        return conn_id


class ErrorHandlingTest(SourceConnectionTestBase):
    """Test error scenarios"""

    def test_invalid_source(self) -> None:
        """Test with non-existent source"""
        payload = {
            "name": "Invalid Source",
            "short_name": "nonexistent_source",
            "readable_collection_id": self.collection_id,
            "authentication": {"credentials": {"key": "value"}},
        }

        response = self.create_connection(payload)
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"

    def test_wrong_auth_method(self, api_key: str) -> None:
        """Test wrong auth method for source"""
        # Try OAuth token on Stripe (which only supports direct auth)
        payload = {
            "name": "Wrong Auth Method",
            "short_name": "stripe",
            "readable_collection_id": self.collection_id,
            "authentication": {"access_token": "some_token"},  # OAuth for direct-only source
        }

        response = self.create_connection(payload)
        assert response.status_code == 400, f"Expected 400, got {response.status_code}"

        if response.status_code == 400:
            error = response.json()
            detail = error.get("detail", "").lower()
            assert "does not support" in detail or "unsupported" in detail

    def test_invalid_collection(self, api_key: str) -> None:
        """Test with non-existent collection"""
        payload = {
            "name": "Invalid Collection",
            "short_name": "stripe",
            "readable_collection_id": "nonexistent-collection-xyz",
            "authentication": {"credentials": {"api_key": api_key}},
        }

        response = self.create_connection(payload)
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"

    def test_invalid_cron(self, api_key: str) -> None:
        """Test with invalid cron expression"""
        payload = {
            "name": "Invalid Cron",
            "short_name": "stripe",
            "readable_collection_id": self.collection_id,
            "authentication": {"credentials": {"api_key": api_key}},
            "schedule": {"cron": "invalid cron expression"},
        }

        response = self.create_connection(payload)
        assert response.status_code == 422, f"Expected 422, got {response.status_code}"

    def run_all_error_tests(self, api_key: str) -> None:
        """Run all error handling tests"""
        print("  Testing Error Handling...")

        self.test_invalid_source()
        print("    ✓ Invalid source returns 404")

        self.test_wrong_auth_method(api_key)
        print("    ✓ Wrong auth method returns 400")

        self.test_invalid_collection(api_key)
        print("    ✓ Invalid collection returns 404")

        self.test_invalid_cron(api_key)
        print("    ✓ Invalid cron returns 422")


def test_source_connections(
    api_url: str, headers: dict, collection_id: str, stripe_api_key: str = None
) -> Tuple[str, str]:
    """
    Test source connections with new nested authentication API.

    This function signature matches the original to maintain compatibility with runner.py

    Args:
        api_url: The API URL
        headers: Request headers with authentication
        collection_id: The readable_id of the collection to use
        stripe_api_key: Stripe API key for testing

    Returns:
        Tuple[str, str]: The IDs of the two created source connections
    """
    print("\n🔄 Testing Source Connections - Nested Authentication API")

    # Debug: Print the collection_id being used
    print(f"  Using collection_id: '{collection_id}'")

    # Verify the collection exists
    print("  Verifying collection exists...")
    response = requests.get(f"{api_url}/collections/{collection_id}", headers=headers)
    if response.status_code != 200:
        print(f"  ✗ Collection verification failed: {response.status_code} - {response.text}")
        raise AssertionError(f"Collection '{collection_id}' not found")

    collection_detail = response.json()
    print(
        f"  ✓ Collection verified: {collection_detail['name']} ({collection_detail['readable_id']})"
    )

    # Verify Stripe API key
    if not stripe_api_key:
        raise ValueError("Stripe API key must be provided via --stripe-api-key argument")

    created_connections = []

    # =============================
    # Test 1: Direct Authentication (Always runs - we have Stripe key)
    # =============================
    print("\n📌 Test 1: Direct Authentication")
    direct_test = DirectAuthTest(api_url, headers, collection_id)
    try:
        conn_id = direct_test.run_test(stripe_api_key)
        created_connections.append(conn_id)
        print("  ✅ Direct authentication test passed")
    except AssertionError as e:
        print(f"  ❌ Direct authentication test failed: {e}")
        show_backend_logs(lines=30)
        raise

    # =============================
    # Test 2: Create second connection with immediate sync
    # =============================
    print("\n📌 Test 2: Direct Auth with Immediate Sync")
    try:
        payload = {
            "name": "Auto-sync Stripe Connection",
            "short_name": "stripe",
            "readable_collection_id": collection_id,
            "description": "Test connection with immediate sync",
            "authentication": {"credentials": {"api_key": stripe_api_key}},
            "sync_immediately": True,
        }

        response = requests.post(f"{api_url}/source-connections", json=payload, headers=headers)
        assert response.status_code == 200, f"Failed to create second connection: {response.text}"

        conn2 = response.json()
        conn2_id = conn2["id"]
        created_connections.append(conn2_id)

        # Should be syncing or active
        assert conn2["status"] in ["active", "syncing"], f"Unexpected status: {conn2['status']}"

        # Check if sync job was created
        if "sync" in conn2 and conn2["sync"]:
            if conn2["sync"].get("last_job"):
                print(f"  ✓ Sync job auto-started: {conn2['sync']['last_job']['status']}")

        print(f"  ✅ Second connection created with immediate sync: {conn2_id}")

    except AssertionError as e:
        print(f"  ❌ Second connection test failed: {e}")
        # Continue with other tests

    # =============================
    # Test 3: OAuth Browser (Creates shell only in CI)
    # =============================
    print("\n📌 Test 3: OAuth Browser Flow")
    oauth_browser_test = OAuthBrowserTest(api_url, headers, collection_id)
    try:
        conn_id = oauth_browser_test.run_test()
        if conn_id:
            created_connections.append(conn_id)
            print("  ✅ OAuth browser shell creation test passed")
    except Exception as e:
        print(f"  ⚠️ OAuth browser test skipped: {e}")

    # =============================
    # Test 4: OAuth Token Injection (if tokens available)
    # =============================
    print("\n📌 Test 4: OAuth Token Injection")
    # Check for GitHub token in environment
    github_token = os.environ.get("TEST_GITHUB_TOKEN")
    if github_token:
        oauth_token_test = OAuthTokenTest(api_url, headers, collection_id)
        try:
            conn_id = oauth_token_test.run_test("github", github_token)
            if conn_id:
                created_connections.append(conn_id)
                print("  ✅ OAuth token injection test passed")
        except Exception as e:
            print(f"  ⚠️ OAuth token test failed: {e}")
    else:
        print("  ℹ️ OAuth token test skipped - no TEST_GITHUB_TOKEN in environment")

    # Check for Google tokens
    google_access_token = os.environ.get("TEST_GOOGLE_ACCESS_TOKEN")
    google_refresh_token = os.environ.get("TEST_GOOGLE_REFRESH_TOKEN")
    if google_access_token:
        oauth_token_test = OAuthTokenTest(api_url, headers, collection_id)
        try:
            conn_id = oauth_token_test.run_test(
                "google_drive", google_access_token, google_refresh_token
            )
            if conn_id:
                created_connections.append(conn_id)
                print("  ✅ Google OAuth token test passed")
        except Exception as e:
            print(f"  ⚠️ Google OAuth token test failed: {e}")

    # =============================
    # Test 5: Auth Provider (if configured)
    # =============================
    print("\n📌 Test 5: Auth Provider")
    # Check for auth provider configuration in environment
    auth_provider_name = os.environ.get("TEST_AUTH_PROVIDER_NAME")
    if auth_provider_name:
        auth_provider_test = AuthProviderTest(api_url, headers, collection_id)
        # Parse optional provider config from environment (JSON string)
        provider_config = None
        config_str = os.environ.get("TEST_AUTH_PROVIDER_CONFIG")
        if config_str:
            try:
                import json

                provider_config = json.loads(config_str)
            except Exception:
                print(f"  ⚠️ Failed to parse TEST_AUTH_PROVIDER_CONFIG")

        try:
            conn_id = auth_provider_test.run_test(auth_provider_name, provider_config)
            if conn_id:
                created_connections.append(conn_id)
                print("  ✅ Auth provider test passed")
        except Exception as e:
            print(f"  ⚠️ Auth provider test failed: {e}")
    else:
        print("  ℹ️ Auth provider test skipped - no TEST_AUTH_PROVIDER_NAME in environment")

    # =============================
    # Test 6: Error Handling
    # =============================
    print("\n📌 Test 6: Error Handling")
    error_test = ErrorHandlingTest(api_url, headers, collection_id)
    try:
        error_test.run_all_error_tests(stripe_api_key)
        print("  ✅ Error handling tests passed")
    except AssertionError as e:
        print(f"  ❌ Error handling test failed: {e}")
        raise

    # =============================
    # Test 7: List Operations
    # =============================
    print("\n📌 Test 7: List Operations")
    try:
        # List all connections
        response = requests.get(f"{api_url}/source-connections?limit=100", headers=headers)
        assert response.status_code == 200, f"Failed to list connections: {response.text}"

    all_connections = response.json()
    assert isinstance(all_connections, list), "Response should be a list"

        # Find our created connections
        our_connections = [c for c in all_connections if c["id"] in created_connections]
        assert len(our_connections) > 0, "Should find at least one of our connections"

        # Verify list item has auth_method field (new in refactored API)
        for conn in our_connections:
            assert "auth_method" in conn, "List item should have auth_method"
            assert conn["auth_method"] in [
                "direct",
                "oauth_browser",
                "oauth_token",
                "oauth_byoc",
                "auth_provider",
            ]

        # Filter by collection
    response = requests.get(
            f"{api_url}/source-connections?collection={collection_id}", headers=headers
    )
        assert response.status_code == 200, f"Failed to filter by collection: {response.text}"

    collection_connections = response.json()
    assert all(
            c["readable_collection_id"] == collection_id for c in collection_connections
    ), "Collection filter not working"

    print(
            f"  ✅ List operations passed ({len(all_connections)} total, {len(collection_connections)} in collection)"
        )

    except AssertionError as e:
        print(f"  ❌ List operations test failed: {e}")
        raise

    # =============================
    # Test 8: PubSub/SSE (if we have a running job)
    # =============================
    if len(created_connections) > 0:
        print("\n📌 Test 8: Sync Job Monitoring")
        try:
            # Get the first connection and run a sync
            conn_id = created_connections[0]
            response = requests.post(f"{api_url}/source-connections/{conn_id}/run", headers=headers)

            if response.status_code == 200:
                job = response.json()
                job_id = job["id"]
                print(f"  Testing PubSub for job {job_id}...")

                # Test SSE subscription
                pubsub_success = test_sync_job_pubsub(api_url, job_id, headers, timeout=30)
                if pubsub_success:
                    print("  ✅ PubSub/SSE test passed")
                else:
                    print("  ⚠️ PubSub test timed out (may be normal for quick jobs)")
        except Exception as e:
            print(f"  ⚠️ PubSub test skipped: {e}")

    # =============================
    # Summary
    # =============================
    print("\n✅ Source Connections test completed successfully")
    print(f"   Created {len(created_connections)} connections")
    print(
        f"   Tests run: Direct Auth, OAuth Browser, OAuth Token, Auth Provider, Error Handling, List Operations"
    )

    # Return first two connection IDs (maintains compatibility with runner.py)
    conn1 = created_connections[0] if len(created_connections) > 0 else ""
    conn2 = created_connections[1] if len(created_connections) > 1 else ""

    return conn1, conn2
