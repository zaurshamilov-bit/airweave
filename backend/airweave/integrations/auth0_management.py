"""Auth0 Management API client for organization management."""

from typing import Dict, List

import httpx

from airweave.core.config import settings
from airweave.core.logging import logger


class Auth0ManagementClient:
    """Client for Auth0 Management API operations."""

    def __init__(self):
        """Initialize the Auth0 Management Client."""
        self.domain = settings.AUTH0_DOMAIN
        self.client_id = settings.AUTH0_M2M_CLIENT_ID
        self.client_secret = settings.AUTH0_M2M_CLIENT_SECRET
        self.audience = f"https://{self.domain}/api/v2/"
        self._enabled = bool(self.client_id and self.client_secret)

    @property
    def enabled(self) -> bool:
        """Whether Auth0 Management API integration is enabled."""
        return self._enabled

    async def _get_management_token(self) -> str:
        """Get Auth0 Management API access token."""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"https://{self.domain}/oauth/token",
                    json={
                        "client_id": self.client_id,
                        "client_secret": self.client_secret,
                        "audience": self.audience,
                        "grant_type": "client_credentials",
                    },
                    timeout=20.0,
                )
                response.raise_for_status()
                data = response.json()
                token = data["access_token"]
                logger.info("Successfully obtained Auth0 Management API token")
                return token
        except Exception as e:
            logger.error(f"Failed to get Auth0 Management API token: {e}")
            raise

    async def get_user_organizations(self, auth0_user_id: str) -> List[Dict]:
        """Get organizations a user belongs to."""
        try:
            token = await self._get_management_token()
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"https://{self.domain}/api/v2/users/{auth0_user_id}/organizations",
                    headers={"Authorization": f"Bearer {token}"},
                    timeout=20.0,
                )
                response.raise_for_status()
                return response.json()
        except Exception as e:
            logger.error(f"Failed to get user organizations from Auth0: {e}")
            return []

    async def create_organization(self, name: str, display_name: str) -> Dict:
        """Create a new Auth0 organization."""
        try:
            token = await self._get_management_token()
            async with httpx.AsyncClient() as client:
                # Auth0 org names must be lowercase and URL-safe
                org_name = name.lower().replace(" ", "-").replace("_", "-")

                response = await client.post(
                    f"https://{self.domain}/api/v2/organizations",
                    headers={"Authorization": f"Bearer {token}"},
                    json={"name": org_name, "display_name": display_name},
                    timeout=20.0,
                )
                response.raise_for_status()
                org_data = response.json()
                logger.info(f"Successfully created Auth0 organization: {org_data['id']}")
                return org_data
        except Exception as e:
            logger.error(f"Failed to create Auth0 organization: {e}")
            raise

    async def delete_organization(self, org_id: str) -> None:
        """Delete an Auth0 organization."""
        try:
            token = await self._get_management_token()
            async with httpx.AsyncClient() as client:
                response = await client.delete(
                    f"https://{self.domain}/api/v2/organizations/{org_id}",
                    headers={"Authorization": f"Bearer {token}"},
                    timeout=20.0,
                )
                response.raise_for_status()
                logger.info(f"Successfully deleted Auth0 organization: {org_id}")
        except Exception as e:
            logger.error(f"Failed to delete Auth0 organization: {e}")
            raise

    async def add_user_to_organization(self, org_id: str, user_id: str) -> None:
        """Add user to Auth0 organization."""
        try:
            token = await self._get_management_token()
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"https://{self.domain}/api/v2/organizations/{org_id}/members",
                    headers={"Authorization": f"Bearer {token}"},
                    json={"members": [user_id]},
                    timeout=20.0,
                )
                response.raise_for_status()
                logger.info(f"Successfully added user {user_id} to Auth0 organization {org_id}")
        except Exception as e:
            logger.error(f"Failed to add user to Auth0 organization: {e}")
            raise

    async def invite_user_to_organization(
        self, org_id: str, email: str, role: str = "member"
    ) -> Dict:
        """Send Auth0 organization invitation."""
        try:
            token = await self._get_management_token()
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"https://{self.domain}/api/v2/organizations/{org_id}/invitations",
                    headers={"Authorization": f"Bearer {token}"},
                    json={
                        "inviter": {"name": "Airweave Platform"},
                        "invitee": {"email": email},
                        "client_id": settings.AUTH0_CLIENT_ID,
                        "app_metadata": {"role": role},
                    },
                    timeout=10.0,
                )
                response.raise_for_status()
                invitation_data = response.json()
                logger.info(
                    f"Successfully sent Auth0 invitation to {email} for organization {org_id}"
                )
                return invitation_data
        except Exception as e:
            logger.error(f"Failed to send Auth0 invitation: {e}")
            raise

    async def get_pending_invitations(self, org_id: str) -> List[Dict]:
        """Get pending invitations for organization."""
        try:
            token = await self._get_management_token()
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"https://{self.domain}/api/v2/organizations/{org_id}/invitations",
                    headers={"Authorization": f"Bearer {token}"},
                    timeout=10.0,
                )
                response.raise_for_status()
                return response.json()
        except Exception as e:
            logger.error(f"Failed to get pending invitations from Auth0: {e}")
            return []


auth0_management_client = None
if settings.AUTH_ENABLED:
    auth0_management_client = Auth0ManagementClient()
