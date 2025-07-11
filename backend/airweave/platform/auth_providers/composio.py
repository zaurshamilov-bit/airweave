"""Composio Test Auth Provider - provides authentication services for other integrations."""

from typing import Any, Dict, List, Optional

import httpx
from fastapi import HTTPException

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
        instance = cls()
        instance.api_key = credentials["api_key"]
        instance.integration_id = config["integration_id"]
        instance.account_id = config["account_id"]
        return instance

    async def _get_with_auth(
        self, client: httpx.AsyncClient, url: str, params: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Make authenticated API request using Composio API key.

        Args:
            client: HTTP client
            url: API endpoint URL
            params: Optional query parameters

        Returns:
            JSON response

        Raises:
            httpx.HTTPStatusError: If the request fails
        """
        headers = {"x-api-key": self.api_key}

        try:
            response = await client.get(url, headers=headers, params=params)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            self.logger.error(f"HTTP error from Composio API: {e.response.status_code} for {url}")
            raise
        except Exception as e:
            self.logger.error(f"Unexpected error accessing Composio API: {url}, {str(e)}")
            raise

    async def get_creds_for_source(
        self, source_short_name: str, source_auth_config_fields: List[str]
    ) -> Dict[str, Any]:
        """Get credentials for a specific source integration.

        Args:
            source_short_name: The short name of the source to get credentials for
            source_auth_config_fields: The fields required for the source auth config

        Returns:
            Credentials dictionary for the source

        Raises:
            HTTPException: If no credentials found for the source
        """
        async with httpx.AsyncClient() as client:
            # Get connected accounts (actual user connections)
            connected_accounts_response = await self._get_with_auth(
                client,
                "https://backend.composio.dev/api/v3/connected_accounts",
            )

            source_connected_accounts = [
                connected_account
                for connected_account in connected_accounts_response.get("items", [])
                if connected_account.get("toolkit", {}).get("slug") == source_short_name
            ]

            if not source_connected_accounts:
                raise HTTPException(
                    status_code=404,
                    detail=f"No connected accounts found for source "
                    f"'{source_short_name}' in Composio.",
                )

            # find the matching connection in Composio
            source_creds_dict = None
            for connected_account in source_connected_accounts:
                account_id = connected_account.get("id")
                integration_id = connected_account.get("auth_config", {}).get("id")
                if integration_id == self.integration_id and account_id == self.account_id:
                    source_creds_dict = connected_account.get("state", {}).get("val")

            if not source_creds_dict:
                raise HTTPException(
                    status_code=404,
                    detail=f"No matching connection in Composio with integration_id="
                    f"'{self.integration_id}' and account_id='{self.account_id}' "
                    f"for source '{source_short_name}'.",
                )

            # Check if all required fields are present in the credentials
            missing_fields = []
            found_credentials = {}

            for field in source_auth_config_fields:
                if field in source_creds_dict:
                    found_credentials[field] = source_creds_dict[field]
                else:
                    missing_fields.append(field)

            if missing_fields:
                available_fields = list(source_creds_dict.keys())
                raise HTTPException(
                    status_code=422,
                    detail=f"Missing required auth fields for source '{source_short_name}': "
                    f"{missing_fields}. "
                    f"Required fields: {source_auth_config_fields}. "
                    f"Available fields in Composio credentials: {available_fields}",
                )

            # TODO: slug name might not always be equal to the source short name maybe need mapping
            # TODO: pagination
            # TODO: when refreshing the token, we should use the auth provider not the oauth refresh
            # TODO: how is this going to work for BYOC?
            # TODO: endpoin to find all connections (account + integration combination) for a source

            # when you just run a source and the credentials came from an auth provider
            # refreshing will not work

            return found_credentials
