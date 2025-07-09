"""Composio Test Auth Provider - provides authentication services for other integrations."""

from typing import Any, Dict, Optional

import httpx

from airweave.platform.auth.schemas import AuthType
from airweave.platform.auth_providers._base import BaseAuthProvider
from airweave.platform.decorators import auth_provider


@auth_provider(
    name="Composio Auth Provider",
    short_name="composio",
    auth_type=AuthType.api_key,
    auth_config_class="ComposioAuthConfig",
    config_class="ComposioConfig",
)
class ComposioAuthProvider(BaseAuthProvider):
    """Composio authentication provider."""

    def __init__(self, api_key: str, environment: str = "production", timeout: int = 30):
        """Initialize Composio test auth provider.

        Args:
            api_key: API key for the auth provider
            environment: Environment to use
            timeout: Request timeout in seconds
        """
        super().__init__()
        self.api_key = api_key
        self.environment = environment
        self.timeout = timeout

    @classmethod
    async def create(
        cls, credentials: Optional[Any] = None, config: Optional[Dict[str, Any]] = None
    ) -> "ComposioAuthProvider":
        """Create a new Composio auth provider instance.

        Args:
            credentials: Auth credentials containing api_key
            config: Configuration parameters

        Returns:
            A Composio test auth provider instance
        """
        return cls(api_key=credentials.api_key)

    async def _get_with_auth(
        self, client: httpx.AsyncClient, url: str, params: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Make authenticated API request using Personal Access Token.

        Args:
            client: HTTP client
            url: API endpoint URL
            params: Optional query parameters

        Returns:
            JSON response
        """
        pass

    async def get_creds_for_source(self, source_short_name: str) -> Dict[str, Any]:
        """Get credentials for a specific source integration.

        Args:
            source_short_name: The short name of the source to get credentials for

        Returns:
            Credentials dictionary for the source
        """
        pass
