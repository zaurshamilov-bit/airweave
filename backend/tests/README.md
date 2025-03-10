# Airweave Testing Framework

## Overview

This document outlines the testing framework for Airweave, covering unit tests, integration tests, and end-to-end (E2E) tests. The framework is designed to ensure code quality, prevent regressions, and validate the platform's functionality across all layers.

## Testing Framework Structure

```
airweave/
├── backend/
│   ├── tests/                           # Main test directory
│   │   ├── conftest.py                  # Pytest fixtures and configuration
│   │   ├── docker/                      # Docker compose files for testing
│   │   │   └── docker-compose.test.yml  # Test environment definition
│   │   ├── unit/                        # Unit tests
│   │   │   ├── crud/                    # CRUD operation tests
│   │   │   ├── api/                     # API endpoint tests
│   │   │   ├── platform/                # Platform component tests
│   │   │   │   └── ...                  # Tests for various platform components
│   │   ├── integration/                 # Integration tests
│   │   │   ├── crud/                    # Database integration tests
│   │   │   ├── api/                     # API integration tests
│   │   │   └── ...
│   │   ├── e2e/                         # End-to-end tests
│   │   │   ├── conftest.py              # E2E-specific fixtures
│   │   │   ├── runner.py                # E2E test runner
│   │   │   ├── smoke/                   # Smoke tests
│   │   │   ├── scenarios/               # Complex scenario tests
│   │   │   └── ...
│   │   └── helpers/                     # Test helpers and utilities
│   │       ├── docker.py                # Docker compose management
│   │       └── ...                      # Other helpers
│   └── ...
└── ...
```

## Quick Start

### Running Tests

```bash
# Run all tests
poetry run pytest

# Run only unit tests
poetry run pytest tests/unit

# Run only integration tests
poetry run pytest tests/integration

# Run only E2E tests
poetry run pytest tests/e2e

# Run with coverage report
poetry run pytest --cov=app --cov-report=term-missing

# Run a specific test file
poetry run pytest tests/unit/crud/test_source.py

# Run a specific test function
poetry run pytest tests/unit/crud/test_source.py::test_create_source
```

### Setting Up for Integration and E2E Tests

Integration and E2E tests require a database and other services. The framework provides multiple ways to set this up:

1. **For integration tests**: A local PostgreSQL database with test credentials

2. **For E2E tests**: A Docker Compose environment with all necessary services

   ```bash
   # Tests will automatically set up and tear down the environment
   poetry run pytest tests/e2e
   ```

## Test Types

### 1. Unit Tests

Unit tests focus on testing individual components in isolation, ensuring specific behaviors function correctly. They use mock objects and fixtures to isolate the code being tested from external dependencies.

Key characteristics:
- Fast (milliseconds)
- No external dependencies
- Mock database and external services
- Test individual functions/methods

### 2. Integration Tests

Integration tests verify that components work correctly together. They test real database interactions, API endpoints with the database, and other component integrations.

Key characteristics:
- Moderately fast (milliseconds to seconds)
- Uses real database connections
- Tests component interactions
- Transaction rollbacks for test isolation

### 3. End-to-End (E2E) Tests

E2E tests validate complete user workflows through the entire application. They test the system as a black box, ensuring all components work together correctly.

Key characteristics:
- Slower (seconds to minutes)
- Uses Docker Compose to set up all services
- Tests full user workflows
- Validates system behavior from user perspective

## Docker Environment Management

The testing framework includes two main components for managing Docker environments:

### DockerComposeManager

Located in `tests/helpers/docker.py`, this component:

- Manages Docker Compose environments for tests
- Handles starting and stopping services
- Provides utilities for health checks and service interaction
- Offers a consistent interface for both integration and E2E tests
- Allows minimal service operation mode for faster tests

### E2ETestRunner

Located in `tests/e2e/runner.py`, this component:

- Provides a thin wrapper around DockerComposeManager
- Offers a high-level interface specifically for E2E tests
- Manages the test environment lifecycle (setup and teardown)
- Contains utilities specifically for E2E test scenarios

The E2E test environment is defined in `tests/docker/docker-compose.test.yml` and includes:

- PostgreSQL database
- Weaviate vector store
- Neo4j graph database
- Backend API service

## Best Practices

### General
- Write tests before code (TDD) whenever possible
- Keep tests independent
- Use descriptive names for test functions
- Follow the Arrange-Act-Assert pattern
- Test edge cases and error conditions

### Project-Specific
- Use the correct test markers (`@pytest.mark.unit`, `@pytest.mark.integration`, `@pytest.mark.e2e`)
- Leverage test fixtures for common setup
- Use the provided helpers for Docker and environment management
- For database tests, always use transaction rollbacks for isolation

## CI/CD Integration

The tests are integrated with the GitHub Actions CI/CD pipeline:

1. Unit and integration tests run on every PR and push to main/develop
2. E2E tests run only on push to main/develop
3. Coverage reports are generated and uploaded to Codecov

See `.github/workflows/tests.yml` for the implementation details.

## Adding New Tests

### Adding a Unit Test
1. Create a new test file in the appropriate directory under `tests/unit/`
2. Use the `@pytest.mark.unit` decorator
3. Use mocks for external dependencies
4. Write focused tests for individual functions

### Adding an Integration Test
1. Create a new test file in the appropriate directory under `tests/integration/`
2. Use the `@pytest.mark.integration` decorator
3. Use the `db_session` fixture for database access
4. Add the `skip_if_no_db` fixture to skip if database is unavailable

### Adding an E2E Test
1. Create a new test file in the appropriate directory under `tests/e2e/`
2. Use the `@pytest.mark.e2e` decorator
3. Use the `e2e_environment` fixture to set up and tear down services
4. Use the `e2e_api_url` fixture to get the base URL for API requests
5. Test complete user workflows

## Maintenance and Troubleshooting

### Common Issues

1. **Database Connection Errors**:
   - Check if PostgreSQL is running
   - Verify database credentials
   - Use `skip_if_no_db` fixture in integration tests

2. **Docker Issues**:
   - Ensure Docker and Docker Compose are installed
   - Check if ports are available
   - Inspect container logs with the `get_container_logs` method
   - Verify Docker Compose file is correctly configured

3. **Test Failures**:
   - Check logs for error details
   - Use `pytest -v` for verbose output
   - Look for service health check failures

For more detailed information about E2E tests, see the README in the `tests/e2e/` directory.
