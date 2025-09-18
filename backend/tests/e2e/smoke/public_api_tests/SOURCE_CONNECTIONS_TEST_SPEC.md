# Source Connections Test Specification - CI/CD Compatible

## Overview
This specification defines the modular test structure for the refactored Source Connections API with nested authentication. The tests are designed to replace `test_source_connections.py` and run in the GitHub Actions CI/CD pipeline.

## CI/CD Context
- **Environment**: GitHub Actions Ubuntu runner
- **Workflow**: `.github/workflows/test-public-api.yml`
- **Available Secrets**: `STRIPE_API_KEY`, `OPENAI_API_KEY`
- **Execution**: Via `runner.py` which expects specific function signatures

## Test Architecture

### Core Test Function (Maintains Compatibility)
```python
def test_source_connections(
    api_url: str,
    headers: dict,
    collection_id: str,
    stripe_api_key: str = None
) -> Tuple[str, str]:
    """Main test function - signature must match for runner.py compatibility"""
```

### Modular Test Structure

#### 1. Base Test Class
```python
class SourceConnectionTestBase:
    """Base class for all source connection tests"""

    def __init__(self, api_url: str, headers: dict, collection_id: str):
        self.api_url = api_url
        self.headers = headers
        self.collection_id = collection_id

    def create_connection(self, payload: dict) -> dict:
        """Create a source connection and return response"""
        response = requests.post(
            f"{self.api_url}/source-connections",
            json=payload,
            headers=self.headers
        )
        return response

    def verify_response_structure(self, conn: dict, expected_auth_method: str):
        """Verify the response matches expected structure"""
        assert "id" in conn
        assert "name" in conn
        assert "status" in conn
        assert "auth" in conn
        assert conn["auth"]["method"] == expected_auth_method

    def run_sync(self, conn_id: str) -> dict:
        """Trigger manual sync"""
        response = requests.post(
            f"{self.api_url}/source-connections/{conn_id}/run",
            headers=self.headers
        )
        return response.json() if response.status_code == 200 else None

    def wait_for_job(self, conn_id: str, job_id: str, timeout: int = 60):
        """Wait for sync job to complete"""
        # Implementation here
```

#### 2. Authentication-Specific Test Classes

##### Direct Authentication Test
```python
class DirectAuthTest(SourceConnectionTestBase):
    """Test direct authentication flow"""

    def create_payload(self, api_key: str) -> dict:
        return {
            "name": "Test Stripe Direct Auth",
            "short_name": "stripe",
            "readable_collection_id": self.collection_id,
            "authentication": {
                "credentials": {
                    "api_key": api_key
                }
            },
            "schedule": {
                "cron": "0 */6 * * *"
            },
            "sync_immediately": False
        }

    def run_test(self, api_key: str) -> str:
        """Run complete direct auth test flow"""
        # Step 1: Create connection
        payload = self.create_payload(api_key)
        response = self.create_connection(payload)
        assert response.status_code == 200

        conn = response.json()
        self.verify_response_structure(conn, "direct")

        # Step 2: Verify authenticated
        assert conn["auth"]["authenticated"] == True
        assert conn["status"] == "active"

        # Step 3: Update connection
        update_response = self.update_connection(conn["id"])

        # Step 4: Run sync
        job = self.run_sync(conn["id"])

        # Step 5: Monitor job
        if job:
            self.wait_for_job(conn["id"], job["id"])

        return conn["id"]
```

##### OAuth Browser Test (Limited for CI)
```python
class OAuthBrowserTest(SourceConnectionTestBase):
    """Test OAuth browser flow - limited in CI environment"""

    def create_payload(self) -> dict:
        return {
            "name": "Test Slack OAuth Browser",
            "short_name": "slack",
            "readable_collection_id": self.collection_id,
            "authentication": {},  # Empty for browser flow
            "sync_immediately": False
        }

    def run_test(self) -> str:
        """Run OAuth browser test - stops at shell creation"""
        # Step 1: Create shell connection
        payload = self.create_payload()
        response = self.create_connection(payload)
        assert response.status_code == 200

        conn = response.json()
        self.verify_response_structure(conn, "oauth_browser")

        # Step 2: Verify pending auth state
        assert conn["auth"]["authenticated"] == False
        assert conn["status"] == "pending_auth"
        assert "auth_url" in conn["auth"]

        # Cannot complete OAuth flow in CI - would need user interaction
        print("  ℹ️ OAuth browser flow created shell - cannot complete in CI")

        return conn["id"]
```

##### OAuth Token Test (If Tokens Available)
```python
class OAuthTokenTest(SourceConnectionTestBase):
    """Test OAuth token injection"""

    def create_payload(self, access_token: str, refresh_token: str = None) -> dict:
        auth = {"access_token": access_token}
        if refresh_token:
            auth["refresh_token"] = refresh_token

        return {
            "name": "Test OAuth Token Injection",
            "short_name": "github",
            "readable_collection_id": self.collection_id,
            "authentication": auth,
            "sync_immediately": True
        }

    def run_test(self, access_token: str, refresh_token: str = None) -> str:
        """Run OAuth token test if tokens available"""
        payload = self.create_payload(access_token, refresh_token)
        response = self.create_connection(payload)

        if response.status_code != 200:
            print(f"  ⚠️ OAuth token test skipped - invalid token")
            return None

        conn = response.json()
        self.verify_response_structure(conn, "oauth_token")

        assert conn["auth"]["authenticated"] == True
        assert conn["status"] in ["active", "syncing"]

        return conn["id"]
```

### Main Test Orchestrator

```python
def test_source_connections(
    api_url: str,
    headers: dict,
    collection_id: str,
    stripe_api_key: str = None
) -> Tuple[str, str]:
    """
    Main test function that orchestrates all authentication method tests.
    Maintains compatibility with runner.py expectations.
    """
    print("\n🔄 Testing Source Connections - Nested Authentication API")

    # Verify prerequisites
    if not stripe_api_key:
        raise ValueError("Stripe API key required for testing")

    created_connections = []

    # Test 1: Direct Authentication (Always runs - we have Stripe key)
    direct_test = DirectAuthTest(api_url, headers, collection_id)
    try:
        conn_id = direct_test.run_test(stripe_api_key)
        created_connections.append(conn_id)
        print("  ✅ Direct authentication test passed")
    except AssertionError as e:
        print(f"  ❌ Direct authentication test failed: {e}")
        raise

    # Test 2: OAuth Browser (Creates shell only in CI)
    oauth_browser_test = OAuthBrowserTest(api_url, headers, collection_id)
    try:
        conn_id = oauth_browser_test.run_test()
        created_connections.append(conn_id)
        print("  ✅ OAuth browser shell creation test passed")
    except AssertionError as e:
        print(f"  ❌ OAuth browser test failed: {e}")

    # Test 3: OAuth Token (Only if tokens in environment)
    github_token = os.environ.get("TEST_GITHUB_TOKEN")
    if github_token:
        oauth_token_test = OAuthTokenTest(api_url, headers, collection_id)
        conn_id = oauth_token_test.run_test(github_token)
        if conn_id:
            created_connections.append(conn_id)
            print("  ✅ OAuth token injection test passed")
    else:
        print("  ℹ️ OAuth token test skipped - no GitHub token available")

    # Test 4: Error Handling
    error_test = ErrorHandlingTest(api_url, headers, collection_id)
    error_test.run_all_error_tests(stripe_api_key)
    print("  ✅ Error handling tests passed")

    # Test 5: List and Filter Operations
    list_test = ListOperationsTest(api_url, headers, collection_id)
    list_test.test_listing(created_connections)
    print("  ✅ List operations test passed")

    # Return first two connection IDs (maintains compatibility)
    conn1 = created_connections[0] if len(created_connections) > 0 else ""
    conn2 = created_connections[1] if len(created_connections) > 1 else ""

    return conn1, conn2
```

## Test Scenarios

### Scenario 1: Direct Authentication (Stripe)
**Available in CI: ✅ Yes**
```
1. Create connection with API key
2. Verify authenticated status
3. Update connection properties
4. Run manual sync
5. Monitor job progress
6. Verify state transitions
```

### Scenario 2: OAuth Browser Flow (Slack)
**Available in CI: ⚠️ Partial**
```
1. Create shell connection
2. Verify pending_auth status
3. Verify auth_url provided
4. [STOP - Cannot complete OAuth in CI]
```

### Scenario 3: OAuth Token Injection (GitHub)
**Available in CI: ⚠️ If token provided**
```
1. Create connection with token
2. Verify authenticated status
3. Run sync if valid token
4. Monitor progress
```

### Scenario 4: Error Handling
**Available in CI: ✅ Yes**
```
1. Invalid source name → 404
2. Wrong auth method → 400
3. Invalid collection → 404
4. Missing credentials → 422
5. Invalid cron → 422
```

### Scenario 5: State Transitions
**Available in CI: ✅ Yes**
```
1. pending_auth → active (after auth)
2. active → syncing (during sync)
3. syncing → active (after sync)
4. active → error (on failure)
```

## Environment Variables

### Required (Available in CI)
```bash
STRIPE_API_KEY=sk_test_...  # From GitHub Secrets
OPENAI_API_KEY=sk-...       # From GitHub Secrets
```

### Optional (Not in CI by default)
```bash
TEST_GITHUB_TOKEN=ghp_...   # For OAuth token tests
TEST_GOOGLE_ACCESS_TOKEN=... # For Google OAuth tests
```

## Implementation File Structure

```
public_api_tests/
├── test_source_connections.py      # Main test file (replaces original)
├── source_connection_tests/        # Modular test components
│   ├── __init__.py
│   ├── base.py                    # Base test class
│   ├── direct_auth.py             # Direct auth tests
│   ├── oauth_browser.py           # OAuth browser tests
│   ├── oauth_token.py             # Token injection tests
│   ├── error_handling.py          # Error scenario tests
│   └── list_operations.py         # List/filter tests
└── utils.py                        # Existing utilities
```

## Key Differences from Original

### What Changes
1. **Nested Authentication**: `authentication` object instead of flat `auth_fields`
2. **Field Names**: `readable_collection_id` instead of `collection`
3. **Response Structure**: Nested `auth`, `schedule`, `sync` objects
4. **Update Method**: PATCH instead of PUT
5. **List Response**: Includes `auth_method` field

### What Stays the Same
1. **Function Signature**: `test_source_connections()` maintains compatibility
2. **Return Values**: Still returns tuple of two connection IDs
3. **Stripe Testing**: Primary test using Stripe API key
4. **Error Scenarios**: Same error cases, different field names
5. **CI/CD Integration**: Works with existing GitHub Actions workflow

## Success Criteria

### Must Pass in CI
- ✅ Direct authentication with Stripe
- ✅ Error handling for all scenarios
- ✅ List and filter operations
- ✅ Response model validation

### Optional in CI
- ⚠️ OAuth browser (shell creation only)
- ⚠️ OAuth token (if tokens provided)
- ⚠️ Complete OAuth flow (requires user interaction)

## Example Test Output

```
🔄 Testing Source Connections - Nested Authentication API
  Using collection_id: 'test-collection-abc123'

📌 Direct Authentication (Stripe)
  ✅ Connection created with API key
  ✅ Status: active, Auth: direct
  ✅ Sync job started
  ✅ Job completed in 15s

📌 OAuth Browser Flow (Slack)
  ✅ Shell connection created
  ✅ Status: pending_auth
  ℹ️ OAuth flow cannot complete in CI

📌 Error Handling
  ✅ Invalid source returns 404
  ✅ Wrong auth method returns 400
  ✅ Missing fields returns 422

✅ Source Connections test completed successfully
   Connections created: 2
   Tests passed: 8/8
```

## Maintenance Notes

1. **Adding New Auth Methods**: Create new test class extending `SourceConnectionTestBase`
2. **Adding New Sources**: Update payloads in respective test classes
3. **CI Secrets**: Add new tokens to GitHub Secrets and workflow
4. **Debugging**: Use `show_backend_logs()` for CI debugging
5. **Cleanup**: Ensure all created resources are tracked for cleanup
