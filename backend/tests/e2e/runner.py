"""E2E test runner for Airweave.

This module provides utilities to run end-to-end tests with docker-compose.
"""

import logging
import subprocess
from typing import List

from ..helpers.docker import DockerComposeManager

logger = logging.getLogger(__name__)


class E2ETestRunner:
    """Runner for E2E tests that manages docker-compose services.

    This is a thin wrapper around DockerComposeManager that provides
    a consistent interface for E2E tests. All Docker-specific functionality
    is delegated to the DockerComposeManager.
    """

    def __init__(
        self, compose_file: str = "docker/docker-compose.test.yml", use_minimal: bool = False
    ):
        """Initialize the E2E test runner.

        Args:
            compose_file: Path to the docker-compose file for testing, relative to tests directory
            use_minimal: If True, only start the database and backend services
        """
        # Create a unique project name for this test run
        project_name = (
            f"airweave-e2e-{int(subprocess.check_output(['date', '+%s']).decode().strip())}"
        )

        # Initialize the Docker Compose manager
        self.docker = DockerComposeManager(
            compose_file=compose_file, project_name=project_name, minimal_services=use_minimal
        )

        logger.info(f"Initialized E2E test runner with compose file: {compose_file}")

    def setup(self) -> None:
        """Start all services for E2E tests."""
        logger.info("Starting services for E2E tests")
        try:
            self.docker.start()
            logger.info("All services are running and ready")
        except Exception as e:
            logger.error(f"Error during service startup: {e}")
            self.teardown()  # Clean up any started services
            raise

    def teardown(self) -> None:
        """Stop all services after tests."""
        logger.info("Stopping services")
        try:
            self.docker.stop(remove_volumes=True)
        except Exception as e:
            logger.error(f"Error during service teardown: {e}")
            raise

    def execute_command(self, command: List[str]) -> subprocess.CompletedProcess:
        """Execute a command on the host machine.

        This is a pass-through to docker.run_host_command.

        Args:
            command: Command to execute

        Returns:
            A CompletedProcess instance with the command result
        """
        return self.docker.run_host_command(command)

    def get_container_logs(self, service_name: str) -> str:
        """Get logs from a container.

        Args:
            service_name: Name of the service to get logs from

        Returns:
            Container logs as a string
        """
        return self.docker.get_container_logs(service_name)

    def exec_in_container(self, service_name: str, command: List[str]) -> str:
        """Execute a command inside a running container.

        Args:
            service_name: Name of the service
            command: Command to execute

        Returns:
            Command output as a string
        """
        return self.docker.execute_command(service_name, command)

    def get_service_url(self, service_name: str, port: int) -> str:
        """Get URL for a service.

        Args:
            service_name: Name of the service
            port: Port number

        Returns:
            URL for the service
        """
        return self.docker.get_service_url(service_name, port)

    def get_connection_string(self, service_name: str = "postgres") -> str:
        """Get database connection string.

        Args:
            service_name: Name of the database service

        Returns:
            SQLAlchemy connection string
        """
        return self.docker.get_connection_string(service_name)
