"""Pipedream configuration classes for auth provider integration."""

from typing import Optional

from pydantic import BaseModel, Field


class PipedreamAuthConfig(BaseModel):
    """Configuration for authenticating with Pipedream API.

    Pipedream uses OAuth2 client credentials flow for API authentication.
    The access tokens expire after 3600 seconds (1 hour).
    """

    client_id: str = Field(..., description="Pipedream OAuth client ID")

    client_secret: str = Field(
        ..., description="Pipedream OAuth client secret", json_schema_extra={"sensitive": True}
    )


class PipedreamConfig(BaseModel):
    """Configuration for accessing a specific Pipedream connected account.

    This specifies which account to retrieve credentials from when
    creating source connections through Pipedream.

    Note: Credentials are only accessible when using custom OAuth clients
    in Pipedream, not the default Pipedream OAuth clients.
    """

    project_id: str = Field(..., description="Pipedream project ID (e.g., proj_JPsD74a)")

    account_id: str = Field(..., description="Pipedream account ID (e.g., apn_gyha5Ky)")

    environment: str = Field(
        default="production", description="Pipedream environment (production or development)"
    )

    external_user_id: Optional[str] = Field(
        None, description="External user ID associated with the account"
    )
