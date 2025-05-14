"""This module contains the service classes for managing secrets."""

from azure.identity.aio import ClientSecretCredential, DefaultAzureCredential
from azure.keyvault.secrets.aio import SecretClient

from airweave.core.config import settings

vault_url = f"https://{settings.AZURE_KEYVAULT_NAME}.vault.azure.net/"
if settings.AZURE_CLIENT_ID and settings.AZURE_CLIENT_SECRET and settings.AZURE_TENANT_ID:
    credential = ClientSecretCredential(
        tenant_id=settings.AZURE_TENANT_ID,
        client_id=settings.AZURE_CLIENT_ID,
        client_secret=settings.AZURE_CLIENT_SECRET,
    )
else:
    credential = DefaultAzureCredential()

secret_client = SecretClient(vault_url=vault_url, credential=credential)
