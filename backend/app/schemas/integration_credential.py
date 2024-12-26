"""Schemas for integration credentials."""


from pydantic import BaseModel

from app.models.integration_credential import IntegrationType


class IntegrationCredentialBase(BaseModel):
    """Base class for integration credentials."""

    name: str
    integration_short_name: str
    description: str | None
    integration_type: IntegrationType
    auth_credential_type: str


class IntegrationCredentialCreate(IntegrationCredentialBase):
    """Create class for integration credentials."""

    decrypted_credentials: dict

class IntegrationCredentialCreateEncrypted(IntegrationCredentialBase):
    """Create class for integration credentials."""

    encrypted_credentials: dict


class IntegrationCredentialUpdate(IntegrationCredentialCreateEncrypted):
    """Update class for integration credentials."""

    pass


class IntegrationCredentialInDB(IntegrationCredentialBase):
    """Base class for integration credentials in the database."""

    encrypted_credentials: dict


class IntegrationCredential(IntegrationCredentialInDB):
    """Integration credential."""

    decrypted_credentials: dict
