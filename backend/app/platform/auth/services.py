"""The services for handling OAuth2 authentication and token exchange for integrations."""

import base64
from urllib.parse import urlencode

import httpx

from app import schemas
from app.core.config import settings
from app.core.exceptions import NotFoundException, TokenRefreshError
from app.core.logging import logger
from app.platform.auth.schemas import OAuth2Settings, OAuth2TokenResponse
from app.platform.auth.settings import integration_settings

oauth2_service_logger = logger.with_prefix("OAuth2 Service: ").with_context(
    component="oauth2_service"
)


class OAuth2Service:
    """Service class for handling OAuth2 authentication and token exchange."""

    @staticmethod
    def generate_auth_url(oauth2_settings: OAuth2Settings) -> str:
        """Generate the OAuth2 authorization URL with the required query parameters.

        Args:
        ----
            oauth2_settings: The OAuth2 settings for the integration.

        Returns:
        -------
            str: The authorization URL.

        """
        redirect_uri = OAuth2Service._get_redirect_url(oauth2_settings.integration_short_name)

        params = {
            "response_type": "code",
            "client_id": oauth2_settings.client_id,
            "redirect_uri": redirect_uri,
            **(oauth2_settings.additional_frontend_params or {}),
        }

        if oauth2_settings.scope:
            params["scope"] = oauth2_settings.scope

        auth_url = f"{oauth2_settings.url}?{urlencode(params)}"

        return auth_url

    @staticmethod
    def generate_auth_url_for_trello() -> str:
        """Generate the authorization URL for Trello.

        This method could potentially be generalized to work with similar authorization flows.

        Returns
        -------
            str: The authorization URL.

        """
        integration_short_name = "trello"
        integration_config = integration_settings.get_by_short_name(integration_short_name)
        redirect_uri = OAuth2Service._get_redirect_url(integration_short_name)

        params = {
            "response_type": "token",
            "scope": "read,write",
            "name": integration_config.name,
            "expiration": "never",
            "return_url": redirect_uri,
            "key": integration_config.key,
        }

        auth_url = f"{integration_config.url}?{urlencode(params)}"

        return auth_url

    @staticmethod
    async def exchange_autorization_code_for_token(
        integration_short_name: str, code: str
    ) -> OAuth2TokenResponse:
        """Exchanges an authorization code for an access token.

        Args:
        ----
            integration_short_name (str): The short name of the integration.
            code (str): The authorization code received from the OAuth provider.

        Returns:
        -------
            OAuth2TokenResponse: The response containing the access token and other token details.

        Raises:
        ------
            NotFoundException: If the integration is not found

        """
        redirect_uri = OAuth2Service._get_redirect_url(integration_short_name)
        integration_config = integration_settings.get_by_short_name(integration_short_name)
        if not integration_config:
            raise NotFoundException(f"Integration {integration_short_name} not found.")

        client_id = integration_config.client_id
        client_secret = await key_vault.get_secret(integration_config.client_secret_keyvault_name)

        headers = {
            "Content-Type": integration_config.content_type,
        }

        payload = {
            "grant_type": integration_config.grant_type,
            "code": code,
            "redirect_uri": redirect_uri,
        }

        if integration_config.client_credential_location == "header":
            encoded_credentials = OAuth2Service._encode_client_credentials(client_id, client_secret)
            headers["Authorization"] = f"Basic {encoded_credentials}"

        else:
            payload["client_id"] = client_id
            payload["client_secret"] = client_secret

        async with httpx.AsyncClient() as client:
            response = await client.post(
                integration_config.backend_url, headers=headers, data=payload
            )

        response.raise_for_status()

        return OAuth2TokenResponse(**response.json())

    @staticmethod
    async def refresh_access_token(
        integration_short_name: str, user: schemas.User
    ) -> OAuth2TokenResponse:
        """Refreshes an access token using a refresh token.

        Rotates the refresh token if the integration is configured to do so.

        Args:
        ----
            integration_short_name (str): The short name of the integration.
            user (schemas.User): The user for whom to refresh the token.

        Returns:
        -------
            OAuth2TokenResponse: The response containing the new access token and other details.

        Raises:
        ------
            TokenRefreshError: If token refresh fails
            NotFoundException: If the integration is not found

        """
        try:
            # Get and validate refresh token
            refresh_token = await OAuth2Service._get_refresh_token(user, integration_short_name)

            # Get and validate integration config
            integration_config = OAuth2Service._get_integration_config(integration_short_name)

            # Get client credentials
            client_id, client_secret = await OAuth2Service._get_client_credentials(
                integration_config
            )

            # Prepare request parameters
            headers, payload = OAuth2Service._prepare_token_request(
                integration_config, refresh_token, client_id, client_secret
            )

            # Make request and handle response
            response = await OAuth2Service._make_token_request(
                integration_config.backend_url, headers, payload
            )

            # Handle rotating refresh tokens if needed
            oauth2_token_response = await OAuth2Service._handle_token_response(
                response, integration_config, user, integration_short_name
            )

            return oauth2_token_response

        except Exception as e:
            oauth2_service_logger.error(
                f"Token refresh failed for user {user.email} and "
                f"integration {integration_short_name}: {str(e)}"
            )
            raise

    @staticmethod
    async def _get_refresh_token(user: schemas.User, integration_short_name: str) -> str:
        """Get and validate refresh token exists.

        Args:
        ----
            user (schemas.User): The user to get the refresh token for.
            integration_short_name (str): The short name of the integration.

        Returns:
        -------
            str: The refresh token.

        Raises:
        ------
            TokenRefreshError: If no refresh token is found

        """
        refresh_token = await secrets_service.get_secret(user, integration_short_name)
        if not refresh_token:
            error_message = (
                f"No refresh token found for user {user.email} and "
                f"integration {integration_short_name}"
            )
            oauth2_service_logger.error(error_message)
            raise TokenRefreshError(error_message)
        return refresh_token

    @staticmethod
    def _get_integration_config(integration_short_name: str) -> schemas.Integration:
        """Get and validate integration configuration exists.

        Args:
        ----
            integration_short_name (str): The short name of the integration.

        Returns:
        -------
            schemas.Integration: The integration configuration.

        Raises:
        ------
            NotFoundException: If integration configuration is not found

        """
        integration_config = integration_settings.get_by_short_name(integration_short_name)
        if not integration_config:
            error_message = f"Configuration for {integration_short_name} not found"
            oauth2_service_logger.error(error_message)
            raise NotFoundException(error_message)
        return integration_config

    @staticmethod
    async def _get_client_credentials(integration_config: schemas.Integration) -> tuple[str, str]:
        """Get client credentials from configuration.

        Args:
        ----
            integration_config (schemas.Integration): The integration configuration.

        Returns:
        -------
            tuple[str, str]: The client ID and client secret.

        """
        client_id = integration_config.client_id
        client_secret = await key_vault.get_secret(integration_config.client_secret_keyvault_name)
        return client_id, client_secret

    @staticmethod
    def _prepare_token_request(
        integration_config: schemas.Integration,
        refresh_token: str,
        client_id: str,
        client_secret: str,
    ) -> tuple[dict, dict]:
        """Prepare headers and payload for token refresh request.

        Args:
        ----
            integration_config (schemas.Integration): The integration configuration.
            refresh_token (str): The refresh token.
            client_id (str): The client ID.
            client_secret (str): The client secret.

        Returns:
        -------
            tuple[dict, dict]: The headers and payload.

        """
        headers = {
            "Content-Type": integration_config.content_type,
        }

        payload = {
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
        }

        if integration_config.client_credential_location == "header":
            encoded_credentials = OAuth2Service._encode_client_credentials(client_id, client_secret)
            headers["Authorization"] = f"Basic {encoded_credentials}"
        else:
            payload["client_id"] = client_id
            payload["client_secret"] = client_secret

        return headers, payload

    @staticmethod
    async def _make_token_request(url: str, headers: dict, payload: dict) -> httpx.Response:
        """Make the token refresh request.

        Args:
        ----
            url (str): The URL to make the request to.
            headers (dict): The headers for the request.
            payload (dict): The payload for the request.

        Returns:
        -------
            httpx.Response: The response from the token refresh request.

        """
        async with httpx.AsyncClient() as client:
            response = await client.post(url, headers=headers, data=payload)
        response.raise_for_status()
        return response

    @staticmethod
    async def _handle_token_response(
        response: httpx.Response,
        integration_config: schemas.Integration,
        user: schemas.User,
        integration_short_name: str,
    ) -> OAuth2TokenResponse:
        """Handle the token response and update refresh token if needed.

        Args:
        ----
            response (httpx.Response): The response from the token refresh request.
            integration_config (schemas.Integration): The integration configuration.
            user (schemas.User): The user to update the refresh token for.
            integration_short_name (str): The short name of the integration.

        Returns:
        -------
            OAuth2TokenResponse: The response containing the new access token and other details.

        """
        oauth2_token_response = OAuth2TokenResponse(**response.json())

        if integration_config.auth_type == "oauth2_with_refresh_rotating":
            new_refresh_token = oauth2_token_response.refresh_token
            await secrets_service.set_secret(user, integration_short_name, new_refresh_token)

        return oauth2_token_response

    @staticmethod
    def _encode_client_credentials(client_id: str, client_secret: str) -> str:
        """Encodes the client ID and client secret in Base64.

        Args:
        ----
            client_id (str): The client ID.
            client_secret (str): The client secret.

        Returns:
        -------
            str: The Base64-encoded client credentials.

        """
        credentials = f"{client_id}:{client_secret}"
        credentials_bytes = credentials.encode("ascii")
        base64_bytes = base64.b64encode(credentials_bytes)
        base64_credentials = base64_bytes.decode("ascii")
        return base64_credentials

    @staticmethod
    def _get_redirect_url(integration_short_name: str) -> str:
        """Private method to generate the appropriate redirect URI based on environment.

        Args:
        ----
            integration_short_name: The short name of the integration.

        Returns:
        -------
            str: The redirect URI.

        """
        app_url = settings.app_url
        return f"{app_url}/auth/callback/{integration_short_name}"


oauth2_service = OAuth2Service()
