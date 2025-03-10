# End-to-End (E2E) Tests for Airweave

This directory contains end-to-end tests for the Airweave platform. These tests verify that the entire system works correctly by testing the API endpoints with real HTTP requests against a running instance of the application.

## Overview

The E2E tests:

1. Start all required services using Docker Compose
2. Wait for services to be ready
3. Run tests against the live API
4. Tear down all services when tests complete

## Requirements

- Docker and Docker Compose
- Python 3.11+
- Poetry

## Running E2E Tests

To run all E2E tests:

```bash
cd backend
poetry run pytest tests/e2e -v
```

To run a specific E2E test:

```bash
cd backend
poetry run pytest tests/e2e/test_source_crud.py -v
```

## Architecture

The E2E test infrastructure consists of several key components:

### 1. Docker Configuration

- **Location**: `tests/docker/docker-compose.test.yml`
- **Purpose**: Defines all services needed for E2E testing
- **Services**:
  - PostgreSQL database
  - Weaviate vector store
  - Neo4j graph database
  - Backend API service

### 2. Docker Management

- **Component**: `DockerComposeManager` in `tests/helpers/docker.py`
- **Purpose**: Handles Docker Compose operations and service interactions
- **Features**:
  - Starting and stopping services
  - Health checks
  - Log access
  - Service URL and connection string generation
  - Command execution

### 3. E2E Test Runner

- **Component**: `E2ETestRunner` in `tests/e2e/runner.py`
- **Purpose**: Thin wrapper around DockerComposeManager for E2E-specific needs
- **Role**: Provides a consistent interface for E2E tests to interact with the Docker environment

### 4. Pytest Fixtures

- **Location**: `tests/e2e/conftest.py`
- **Key Fixtures**:
  - `e2e_environment`: Sets up and tears down the test environment
  - `e2e_api_url`: Provides the base URL for API requests

## Writing E2E Tests

When writing E2E tests:

1. Use the `e2e_environment` fixture to ensure services are running
2. Use the `e2e_api_url` fixture to get the base URL for API requests
3. Make HTTP requests to the API endpoints
4. Write assertions to verify the responses

Follow this pattern for test organization:

- **Smoke Tests**: Basic functionality verification (`tests/e2e/smoke/`)
- **Scenario Tests**: Complex user workflows (`tests/e2e/scenarios/`)
- **Feature-specific Tests**: Tests for specific features (direct in `tests/e2e/`)

## Minimal Mode

For faster test runs, the E2E environment can be started in "minimal mode":

```python
@pytest.fixture(scope="module")
def e2e_environment() -> Generator[E2ETestRunner, None, None]:
    # Create runner with minimal mode (postgres and backend only)
    runner = E2ETestRunner(use_minimal=True)
    # ...
```

This starts only the essential services (PostgreSQL and backend API), which is often sufficient for many API tests and reduces resource usage.

## Debugging

If tests fail, you can:

1. Check the logs using the runner:
   ```python
   def test_something(e2e_environment):
       # If a test fails, you can get logs
       logs = e2e_environment.get_container_logs("backend")
       print(logs)
   ```

2. Run the tests with more verbose output:
   ```bash
   poetry run pytest tests/e2e -vv
   ```

3. Inspect the Docker container status manually during test development:
   ```bash
   docker ps
   docker logs <container_id>
   ```

## CI/CD Integration

These tests are integrated into the CI/CD pipeline in GitHub Actions. See the workflow configuration in `.github/workflows/test.yml` for details.
