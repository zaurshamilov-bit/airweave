"""Configuration and fixtures for end-to-end tests."""

import logging
from typing import Generator

import pytest

from tests.e2e.runner import E2ETestRunner

logger = logging.getLogger(__name__)


@pytest.fixture(scope="module")
def e2e_environment() -> Generator[E2ETestRunner, None, None]:
    """Set up and tear down the E2E test environment.

    This fixture:
    1. Starts all services using docker-compose.test.yml
    2. Waits for services to be ready
    3. Yields the runner for additional operations
    4. Stops all services when tests complete

    Yields:
        The E2ETestRunner instance for additional operations
    """
    # Create runner with minimal mode (postgres and backend only)
    # This avoids issues with Weaviate and Neo4j that can be flaky in tests
    runner = E2ETestRunner(use_minimal=True)

    try:
        # Start services
        logger.info("Starting E2E test environment")
        runner.setup()

        # Yield runner for additional operations if needed
        yield runner
    except Exception as e:
        logger.error(f"Error during E2E environment setup: {e}")
        raise
    finally:
        # Always try to clean up, even if setup failed
        try:
            logger.info("Tearing down E2E test environment")
            runner.teardown()
        except Exception as e:
            logger.error(f"Error during E2E environment teardown: {e}")


@pytest.fixture(scope="module")
def e2e_api_url() -> str:
    """Return the base URL for API requests in E2E tests."""
    return "http://localhost:8001/"
