"""Docker container management utilities for integration and E2E tests.

This module provides utilities to manage Docker Compose environments for testing.
"""

import logging
import os
import subprocess
import time
from typing import Dict, List, Optional, Union

import requests
from requests.exceptions import RequestException

logger = logging.getLogger(__name__)


class DockerComposeManager:
    """A manager for Docker Compose environments in tests.

    This class provides methods to start and stop Docker Compose environments
    for integration and E2E tests.
    """

    def __init__(
        self,
        compose_file: str = "docker/docker-compose.test.yml",
        project_name: Optional[str] = None,
        env_vars: Optional[Dict[str, str]] = None,
        minimal_services: bool = False,
    ):
        """Initialize a Docker Compose manager.

        Args:
            compose_file: Path to the docker-compose file, relative to tests directory
            project_name: Optional project name for docker-compose
            env_vars: Optional environment variables to pass to docker-compose
            minimal_services: If True, only start essential services like databases
        """
        # Get the tests directory
        self.tests_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

        # Full path to the compose file
        self.compose_file = os.path.join(self.tests_dir, compose_file)

        # Make sure file exists
        if not os.path.exists(self.compose_file):
            raise FileNotFoundError(f"Compose file not found: {self.compose_file}")

        self.project_name = project_name or f"airweave-test-{int(time.time())}"
        self.env_vars = env_vars or {}
        self.minimal_services = minimal_services

        # Store working directory
        self.cwd = os.getcwd()

        # Flag to track if services are running
        self.is_running = False

        logger.info(
            f"Initialized Docker Compose manager with file: {self.compose_file} "
            f"(project: {self.project_name})"
        )

    def start(self, services: Optional[List[str]] = None, wait_for_services: bool = True) -> None:
        """Start services using docker-compose.

        Args:
            services: Optional list of specific services to start. If None, will use
                minimal_services setting.
            wait_for_services: Whether to wait for services to be ready
        """
        logger.info(f"Starting services with docker-compose file: {self.compose_file}")

        # Change to tests directory
        os.chdir(self.tests_dir)

        try:
            # Set environment variables
            env = os.environ.copy()
            env.update(self.env_vars)

            # Build command
            cmd = ["docker-compose", "-f", self.compose_file, "-p", self.project_name, "up", "-d"]

            # Determine which services to start
            if services is None and self.minimal_services:
                # Start only essential services (postgres and backend)
                logger.info("Starting minimal services (postgres and backend)...")
                services = ["postgres", "backend"]
                cmd.extend(services)
            elif services:
                # Start specified services
                logger.info(f"Starting specific services: {', '.join(services)}...")
                cmd.extend(services)
            else:
                # Start all services
                logger.info("Starting all services...")

            # Execute command
            # First, pull the images to ensure they're up to date
            logger.info("Pulling Docker images...")
            pull_cmd = ["docker-compose", "-f", self.compose_file, "-p", self.project_name, "pull"]
            if services:
                pull_cmd.extend(services)
            subprocess.run(pull_cmd, check=True, env=env)

            # Then start the services
            subprocess.run(cmd, check=True, env=env)
            self.is_running = True

            # Wait for services to be ready
            if wait_for_services:
                self.wait_for_services()

        except subprocess.CalledProcessError as e:
            logger.error(f"Error starting Docker Compose: {e}")
            # Try to collect logs to help diagnose the issue
            try:
                logs = subprocess.run(
                    ["docker-compose", "-f", self.compose_file, "-p", self.project_name, "logs"],
                    capture_output=True,
                    text=True,
                    check=False,
                ).stdout
                logger.error(f"Container logs:\n{logs}")
            except Exception as ex:
                logger.error(f"Failed to get logs: {ex}")
            raise
        finally:
            # Change back to original working directory
            os.chdir(self.cwd)

    def stop(self, remove_volumes: bool = True) -> None:
        """Stop services using docker-compose.

        Args:
            remove_volumes: Whether to remove volumes when stopping
        """
        if not self.is_running:
            logger.info("Services are not running, nothing to stop")
            return

        logger.info("Stopping Docker Compose services")

        # Change to tests directory
        os.chdir(self.tests_dir)

        try:
            # Build command
            cmd = ["docker-compose", "-f", self.compose_file, "-p", self.project_name, "down"]

            # Add volume cleanup if requested
            if remove_volumes:
                cmd.append("-v")

            # Execute command
            subprocess.run(cmd, check=True)
            self.is_running = False
            logger.info("All services have been stopped")

        except subprocess.CalledProcessError as e:
            logger.error(f"Error stopping Docker Compose: {e}")
            raise
        finally:
            # Change back to original working directory
            os.chdir(self.cwd)

    def _check_service_health(self, service):
        """Check if a single service is healthy.

        Args:
            service: Service health check configuration

        Returns:
            bool: True if service is healthy, False otherwise
        """
        service_name = service["name"]
        service_url = service["url"]
        expected_status = service["expected_status"]

        try:
            response = requests.get(service_url, timeout=2)
            if response.status_code != expected_status:
                logger.debug(
                    f"Service {service_name} not ready: "
                    + f"status code {response.status_code} "
                    + f"(expected {expected_status})"
                )
                return False
            return True
        except RequestException as e:
            logger.debug(f"Service {service_name} not ready: connection failed")
            logger.debug(f"Error: {e}")
            return False

    def _collect_container_logs(self):
        """Collect logs from all containers.

        Returns:
            dict: Dictionary of container ID to logs
        """
        logs = {}
        os.chdir(self.tests_dir)

        try:
            # Get logs for all containers
            container_list = (
                subprocess.run(
                    [
                        "docker-compose",
                        "-f",
                        self.compose_file,
                        "-p",
                        self.project_name,
                        "ps",
                        "-q",
                    ],
                    capture_output=True,
                    text=True,
                    check=False,
                )
                .stdout.strip()
                .split("\n")
            )

            for container_id in container_list:
                if container_id:
                    # Run inspect but don't use the result
                    _ = subprocess.run(
                        ["docker", "inspect", container_id],
                        capture_output=True,
                        text=True,
                        check=False,
                    ).stdout
                    container_logs = subprocess.run(
                        ["docker", "logs", container_id],
                        capture_output=True,
                        text=True,
                        check=False,
                    ).stdout
                    logs[container_id] = container_logs
        except Exception as e:
            logger.error(f"Failed to get logs: {e}")
        finally:
            os.chdir(self.cwd)

        return logs

    def wait_for_services(self, timeout: int = 120) -> None:
        """Wait for all services to be ready.

        Args:
            timeout: Maximum time to wait in seconds

        Raises:
            TimeoutError: If services don't become ready within timeout
        """
        logger.info(f"Waiting for services to be ready (timeout: {timeout}s)")

        # Define service health check endpoints
        health_checks = [
            {
                "name": "backend",
                "url": "http://localhost:8001/health",
                "expected_status": 200,
            }
        ]

        # Wait for all services to be ready
        start_time = time.time()
        services_ready = False

        while time.time() - start_time < timeout and not services_ready:
            pending_services = []

            for service in health_checks:
                if not self._check_service_health(service):
                    pending_services.append(service["name"])

            if not pending_services:
                services_ready = True
                logger.info("All services are ready")
                break

            logger.debug(f"Waiting for services: {', '.join(pending_services)}")
            time.sleep(2)

        if not services_ready:
            # Get logs to help diagnose issues
            logs = self._collect_container_logs()

            pending_services_str = ", ".join(
                [s["name"] for s in health_checks if s["name"] in pending_services]
            )
            error_msg = f"Services not ready within timeout: {pending_services_str}"
            if logs:
                error_msg += "\nContainer logs:\n"
                for container_id, container_logs in logs.items():
                    error_msg += f"\n--- Container {container_id} ---\n{container_logs}\n"

            raise TimeoutError(error_msg)

    def get_service_url(self, service_name: str, port: int) -> str:
        """Get the URL for a service.

        Args:
            service_name: Name of the service in docker-compose
            port: Port number to connect to

        Returns:
            URL for the service (http://localhost:port)
        """
        return f"http://localhost:{port}"

    def get_connection_string(self, service_name: str = "postgres") -> str:
        """Get a database connection string for the specified service.

        Args:
            service_name: Name of the database service

        Returns:
            SQLAlchemy connection string
        """
        # Default connection strings for common services
        if service_name == "postgres":
            return "postgresql+asyncpg://test:test@localhost:5433/test_db"
        elif service_name == "neo4j":
            return "neo4j://localhost:7688"
        else:
            raise ValueError(f"Unknown service: {service_name}")

    def get_container_logs(self, service_name: str) -> str:
        """Get logs for a specific service.

        Args:
            service_name: Name of the service in docker-compose

        Returns:
            Container logs as a string
        """
        logger.info(f"Getting logs for service: {service_name}")
        os.chdir(self.tests_dir)
        try:
            logs = subprocess.run(
                [
                    "docker-compose",
                    "-f",
                    self.compose_file,
                    "-p",
                    self.project_name,
                    "logs",
                    service_name,
                ],
                capture_output=True,
                text=True,
                check=False,
            ).stdout
            return logs
        except Exception as e:
            logger.error(f"Failed to get logs: {e}")
            return f"Failed to get logs: {e}"
        finally:
            os.chdir(self.cwd)

    def execute_command(self, service_name: str, command: Union[str, List[str]]) -> str:
        """Execute a command in a running service container.

        Args:
            service_name: Name of the service in docker-compose
            command: Command to execute

        Returns:
            Command output as a string
        """
        logger.info(
            f"Executing in {service_name}: "
            f"{' '.join(command) if isinstance(command, list) else command}"
        )
        os.chdir(self.tests_dir)
        try:
            if isinstance(command, list):
                cmd = command
            else:
                cmd = [command]

            output = subprocess.run(
                [
                    "docker-compose",
                    "-f",
                    self.compose_file,
                    "-p",
                    self.project_name,
                    "exec",
                    "-T",
                    service_name,
                ]
                + cmd,
                capture_output=True,
                text=True,
                check=True,
            ).stdout
            return output
        except subprocess.CalledProcessError as e:
            logger.error(f"Command failed: {e}")
            logger.error(f"Error output: {e.stderr}")
            raise
        finally:
            os.chdir(self.cwd)

    def run_host_command(self, command: List[str]) -> subprocess.CompletedProcess:
        """Execute a command on the host machine.

        This is for commands that should run on the host, not in containers.

        Args:
            command: Command to execute

        Returns:
            A CompletedProcess instance with the command result
        """
        logger.info(f"Executing host command: {' '.join(command)}")

        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=False,
        )

        if result.returncode != 0:
            logger.warning(f"Command failed with exit code {result.returncode}")
            logger.warning(f"Command stderr: {result.stderr}")

        return result
