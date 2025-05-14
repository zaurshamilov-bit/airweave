"""This module contains the service classes for managing secrets."""

from azure.identity.aio import ClientSecretCredential, DefaultAzureCredential
from azure.keyvault.secrets.aio import SecretClient

from airweave.core.config import settings


class AzureKeyVault:
    """Wrapper class for interacting with Azure Key Vault."""

    def __init__(self):
        """Creates a new instance of the AzureKeyVault class."""
        self.vault_url = f"https://{settings.AZURE_KEYVAULT_NAME}.vault.azure.net/"
        if settings.AZURE_CLIENT_ID and settings.AZURE_CLIENT_SECRET and settings.AZURE_TENANT_ID:
            self.credential = ClientSecretCredential(
                tenant_id=settings.AZURE_TENANT_ID,
                client_id=settings.AZURE_CLIENT_ID,
                client_secret=settings.AZURE_CLIENT_SECRET,
            )
        else:
            self.credential = DefaultAzureCredential()
        self.client = SecretClient(vault_url=self.vault_url, credential=self.credential)

    async def get_secret(self, secret_name: str) -> str:
        """Retrieves a secret from Azure Key Vault.

        Args:
            secret_name (str): The name of the secret to retrieve.

        Returns:
            str: The value of the secret.
        """
        secret = await self.client.get_secret(secret_name)
        return secret.value

    async def set_secret(self, secret_name: str, secret_value: str) -> None:
        """Sets a secret in Azure Key Vault.

        Args:
            secret_name (str): The name of the secret to set.
            secret_value (str): The value of the secret.
        """
        await self.client.set_secret(secret_name, secret_value)

    async def delete_secret(self, secret_name: str) -> None:
        """Deletes a secret from Azure Key Vault.

        Args:
            secret_name (str): The name of the secret to delete.
        """
        await self.client.delete_secret(secret_name)
