"""SharePoint bongo implementation.

Creates, updates, and deletes test files via the Microsoft Graph API.
"""

import asyncio
import time
import uuid
from typing import Any, Dict, List, Optional

import httpx
from monke.bongos.base_bongo import BaseBongo
from monke.utils.logging import get_logger


class SharePointBongo(BaseBongo):
    """Bongo for SharePoint that creates test files for E2E testing.

    Key responsibilities:
    - Create test folder in default document library
    - Upload test files with embedded verification tokens
    - Update files to test incremental sync
    - Delete files to test deletion detection
    - Clean up all test data
    """

    connector_type = "sharepoint"

    GRAPH_BASE_URL = "https://graph.microsoft.com/v1.0"

    def __init__(self, credentials: Dict[str, Any], **kwargs):
        """Initialize the SharePoint bongo.

        Args:
            credentials: Dict with "access_token"
            **kwargs: Configuration from test config file
        """
        super().__init__(credentials)

        # Initialize logger FIRST before using it
        self.logger = get_logger(f"{self.connector_type}_bongo")

        # Debug: Log available credential fields
        self.logger.info(
            f"Received credentials with fields: {list(credentials.keys())}"
        )

        # Try to get access_token
        if "access_token" not in credentials:
            self.logger.error(
                f"No 'access_token' in credentials. Available: {list(credentials.keys())}"
            )
            raise ValueError(
                f"Missing 'access_token' in credentials. "
                f"Available fields: {list(credentials.keys())}"
            )

        self.access_token: str = credentials["access_token"]

        # Log token preview for debugging (first/last few chars)
        if self.access_token:
            token_preview = (
                f"{self.access_token[:10]}...{self.access_token[-10:]}"
                if len(self.access_token) > 20
                else "SHORT_TOKEN"
            )
            self.logger.info(f"Access token preview: {token_preview}")

        # Test configuration
        self.entity_count: int = int(kwargs.get("entity_count", 5))
        self.openai_model: str = kwargs.get("openai_model", "gpt-4.1-mini")
        self.rate_limit_delay_ms: int = int(kwargs.get("rate_limit_delay_ms", 500))

        # Simple rate limiting
        self.last_request_time = 0.0
        self.min_delay = self.rate_limit_delay_ms / 1000.0  # Convert to seconds

        # Runtime state - track created entities
        self._site_id: Optional[str] = None
        self._drive_id: Optional[str] = None
        self._test_folder_id: Optional[str] = None
        self._test_folder_name = f"Monke_Test_{uuid.uuid4().hex[:8]}"
        self._files: List[Dict[str, Any]] = []

    async def _rate_limit(self):
        """Simple rate limiting."""
        now = time.time()
        elapsed = now - self.last_request_time
        if elapsed < self.min_delay:
            await asyncio.sleep(self.min_delay - elapsed)
        self.last_request_time = time.time()

    def _headers(self) -> Dict[str, str]:
        """Return auth headers for API requests."""
        return {
            "Authorization": f"Bearer {self.access_token}",
            "Accept": "application/json",
        }

    async def _verify_token(self, client: httpx.AsyncClient) -> bool:
        """Verify the access token is valid by making a test request.

        Returns:
            True if token is valid, False otherwise
        """
        try:
            self.logger.info("🔍 Verifying SharePoint access token...")
            resp = await client.get(
                f"{self.GRAPH_BASE_URL}/me",
                headers=self._headers(),
                timeout=10.0,
            )

            if resp.status_code == 200:
                self.logger.info("✅ Access token is valid")
                return True
            elif resp.status_code == 401:
                self.logger.error("❌ Access token is invalid or expired (401)")
                try:
                    error_body = resp.json()
                    self.logger.error(f"Error details: {error_body}")
                except Exception:
                    self.logger.error(f"Error response: {resp.text}")
                return False
            else:
                self.logger.warning(f"Unexpected response code: {resp.status_code}")
                return False

        except Exception as e:
            self.logger.error(f"Error verifying token: {e}")
            return False

    async def _ensure_site(self, client: httpx.AsyncClient) -> str:
        """Ensure we have access to the root SharePoint site.

        Returns:
            Site ID
        """
        if self._site_id:
            return self._site_id

        self.logger.info("Getting root SharePoint site...")
        await self._rate_limit()

        resp = await client.get(
            f"{self.GRAPH_BASE_URL}/sites/root",
            headers=self._headers(),
        )
        resp.raise_for_status()
        site_data = resp.json()

        self._site_id = site_data["id"]
        site_name = site_data.get("displayName", "Root Site")
        self.logger.info(f"Using site: {site_name} (ID: {self._site_id})")

        return self._site_id

    async def _ensure_drive(self, client: httpx.AsyncClient) -> str:
        """Ensure we have the default document library.

        Returns:
            Drive ID
        """
        if self._drive_id:
            return self._drive_id

        site_id = await self._ensure_site(client)

        self.logger.info("Getting default document library...")
        await self._rate_limit()

        resp = await client.get(
            f"{self.GRAPH_BASE_URL}/sites/{site_id}/drive",
            headers=self._headers(),
        )
        resp.raise_for_status()
        drive_data = resp.json()

        self._drive_id = drive_data["id"]
        drive_name = drive_data.get("name", "Documents")
        self.logger.info(f"Using drive: {drive_name} (ID: {self._drive_id})")

        return self._drive_id

    async def _ensure_test_folder(self, client: httpx.AsyncClient) -> str:
        """Ensure test folder exists in the drive.

        Returns:
            Folder ID
        """
        if self._test_folder_id:
            return self._test_folder_id

        drive_id = await self._ensure_drive(client)

        self.logger.info(f"Creating test folder: {self._test_folder_name}")
        await self._rate_limit()

        # Create folder in the root of the drive
        resp = await client.post(
            f"{self.GRAPH_BASE_URL}/drives/{drive_id}/root/children",
            headers={**self._headers(), "Content-Type": "application/json"},
            json={
                "name": self._test_folder_name,
                "folder": {},
                "@microsoft.graph.conflictBehavior": "rename",
            },
        )
        resp.raise_for_status()
        folder_data = resp.json()

        self._test_folder_id = folder_data["id"]
        self.logger.info(f"Test folder created: {self._test_folder_id}")

        return self._test_folder_id

    async def _upload_file(
        self,
        client: httpx.AsyncClient,
        filename: str,
        content: str,
        folder_id: str,
    ) -> Dict[str, Any]:
        """Upload a file to SharePoint.

        Args:
            client: HTTP client
            filename: Name of the file
            content: File content as string
            folder_id: Parent folder ID

        Returns:
            File metadata from API
        """
        drive_id = await self._ensure_drive(client)

        self.logger.debug(f"Uploading file: {filename}")
        await self._rate_limit()

        # Use simple upload for small files (< 4MB)
        content_bytes = content.encode("utf-8")

        resp = await client.put(
            f"{self.GRAPH_BASE_URL}/drives/{drive_id}/items/{folder_id}:/{filename}:/content",
            headers={
                "Authorization": f"Bearer {self.access_token}",
                "Content-Type": "text/plain",
            },
            content=content_bytes,
        )
        resp.raise_for_status()
        file_data = resp.json()

        self.logger.debug(f"File uploaded: {filename} (ID: {file_data['id']})")
        return file_data

    async def _delete_file(self, client: httpx.AsyncClient, file_id: str):
        """Delete a file from SharePoint.

        Args:
            client: HTTP client
            file_id: ID of the file to delete
        """
        drive_id = await self._ensure_drive(client)

        self.logger.debug(f"Deleting file: {file_id}")
        await self._rate_limit()

        resp = await client.delete(
            f"{self.GRAPH_BASE_URL}/drives/{drive_id}/items/{file_id}",
            headers=self._headers(),
        )
        # 204 No Content is success for DELETE
        if resp.status_code not in (204, 404):
            resp.raise_for_status()

        self.logger.debug(f"File deleted: {file_id}")

    async def _update_file_content(
        self,
        client: httpx.AsyncClient,
        file_id: str,
        new_content: str,
    ):
        """Update file content.

        Args:
            client: HTTP client
            file_id: ID of the file to update
            new_content: New content for the file
        """
        drive_id = await self._ensure_drive(client)

        self.logger.debug(f"Updating file: {file_id}")
        await self._rate_limit()

        content_bytes = new_content.encode("utf-8")

        resp = await client.put(
            f"{self.GRAPH_BASE_URL}/drives/{drive_id}/items/{file_id}/content",
            headers={
                "Authorization": f"Bearer {self.access_token}",
                "Content-Type": "text/plain",
            },
            content=content_bytes,
        )
        resp.raise_for_status()

        self.logger.debug(f"File updated: {file_id}")

    async def create_entities(self) -> List[Dict[str, Any]]:
        """Create test files in SharePoint.

        Returns:
            List of created file descriptors with verification tokens
        """
        self.logger.info(f"🥁 Creating {self.entity_count} test files in SharePoint")

        from monke.generation.sharepoint import generate_sharepoint_file

        all_entities: List[Dict[str, Any]] = []

        async with httpx.AsyncClient(timeout=30.0) as client:
            # Verify token before proceeding
            is_valid = await self._verify_token(client)
            if not is_valid:
                raise RuntimeError(
                    "SharePoint access token is invalid or expired. "
                    "Please reconnect your SharePoint account in Composio."
                )
            # Ensure we have a test folder
            folder_id = await self._ensure_test_folder(client)

            # Create test files
            for i in range(self.entity_count):
                # Generate unique token for this file
                file_token = str(uuid.uuid4())[:8]

                self.logger.info(
                    f"Creating file {i + 1}/{self.entity_count} with token {file_token}"
                )

                # Generate content
                filename, content, mime_type = await generate_sharepoint_file(
                    self.openai_model, file_token
                )

                # Upload the file
                file_data = await self._upload_file(
                    client, filename, content, folder_id
                )

                # Track the file
                file_descriptor = {
                    "type": "file",
                    "id": file_data["id"],
                    "name": filename,
                    "token": file_token,
                    "expected_content": file_token,
                    "path": f"sharepoint/file/{file_data['id']}",
                    "content": content,  # Store for updates
                }
                self._files.append(file_descriptor)
                all_entities.append(file_descriptor)

                self.logger.info(f"✅ Created file: {filename} (token: {file_token})")

        self.logger.info(f"✅ Created {len(self._files)} files in SharePoint")

        self.created_entities = all_entities
        return all_entities

    async def update_entities(self) -> List[Dict[str, Any]]:
        """Update test files to test incremental sync.

        Returns:
            List of updated file descriptors
        """
        self.logger.info("🥁 Updating test files for incremental sync")

        if not self._files:
            return []

        from monke.generation.sharepoint import generate_sharepoint_file

        updated_entities: List[Dict[str, Any]] = []
        count = min(2, len(self._files))  # Update first 2 files

        async with httpx.AsyncClient(timeout=30.0) as client:
            for i in range(count):
                file = self._files[i]

                # Generate new content with SAME token
                filename, new_content, mime_type = await generate_sharepoint_file(
                    self.openai_model, file["token"]
                )

                # Update the file
                await self._update_file_content(client, file["id"], new_content)

                # Update our tracking
                file["content"] = new_content
                updated_entities.append(file)

                self.logger.info(
                    f"✅ Updated file: {file['name']} (token: {file['token']})"
                )

        self.logger.info(f"✅ Updated {len(updated_entities)} files")
        return updated_entities

    async def delete_specific_entities(
        self, entities: List[Dict[str, Any]]
    ) -> List[str]:
        """Delete specific files by ID.

        Args:
            entities: List of file descriptors to delete

        Returns:
            List of deleted file IDs
        """
        self.logger.info(f"🥁 Deleting {len(entities)} specific files")

        deleted_ids: List[str] = []

        async with httpx.AsyncClient(timeout=30.0) as client:
            for entity in entities:
                try:
                    await self._delete_file(client, entity["id"])
                    deleted_ids.append(entity["id"])
                    self.logger.info(f"✅ Deleted file: {entity['name']}")

                    # Remove from our tracking
                    self._files = [f for f in self._files if f["id"] != entity["id"]]
                except Exception as e:
                    self.logger.error(f"Failed to delete file {entity['id']}: {e}")

        self.logger.info(f"✅ Deleted {len(deleted_ids)} files")
        return deleted_ids

    async def delete_entities(self) -> List[str]:
        """Delete all created test files.

        Returns:
            List of deleted file IDs
        """
        self.logger.info("🥁 Deleting all test files")

        deleted_ids: List[str] = []

        async with httpx.AsyncClient(timeout=30.0) as client:
            for file in self._files:
                try:
                    await self._delete_file(client, file["id"])
                    deleted_ids.append(file["id"])
                    self.logger.debug(f"Deleted file: {file['name']}")
                except Exception as e:
                    self.logger.warning(f"Failed to delete file {file['id']}: {e}")

        self.logger.info(f"✅ Deleted {len(deleted_ids)} files")
        self._files = []
        return deleted_ids

    async def cleanup(self):
        """Comprehensive cleanup of all test data."""
        self.logger.info("🧹 Starting comprehensive SharePoint cleanup")

        cleanup_stats = {
            "files_deleted": 0,
            "folders_deleted": 0,
            "errors": 0,
        }

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                # 1. Delete any remaining files
                if self._files:
                    for file in self._files:
                        try:
                            await self._delete_file(client, file["id"])
                            cleanup_stats["files_deleted"] += 1
                        except Exception as e:
                            self.logger.warning(
                                f"Failed to delete file {file['id']}: {e}"
                            )
                            cleanup_stats["errors"] += 1

                # 2. Delete the test folder
                if self._test_folder_id and self._drive_id:
                    try:
                        self.logger.info(
                            f"Deleting test folder: {self._test_folder_name}"
                        )
                        await self._rate_limit()

                        resp = await client.delete(
                            f"{self.GRAPH_BASE_URL}/drives/{self._drive_id}/items/{self._test_folder_id}",
                            headers=self._headers(),
                        )
                        if resp.status_code in (204, 404):
                            cleanup_stats["folders_deleted"] += 1
                            self.logger.info("Test folder deleted")
                    except Exception as e:
                        self.logger.warning(f"Failed to delete test folder: {e}")
                        cleanup_stats["errors"] += 1

                # 3. Find and clean up any orphaned test folders
                if self._drive_id:
                    try:
                        self.logger.info("Looking for orphaned test folders...")
                        await self._rate_limit()

                        resp = await client.get(
                            f"{self.GRAPH_BASE_URL}/drives/{self._drive_id}/root/children",
                            headers=self._headers(),
                            params={"$filter": "startswith(name,'Monke_Test_')"},
                        )
                        if resp.status_code == 200:
                            orphaned = resp.json().get("value", [])
                            for folder in orphaned:
                                try:
                                    await self._rate_limit()
                                    del_resp = await client.delete(
                                        f"{self.GRAPH_BASE_URL}/drives/{self._drive_id}/items/{folder['id']}",
                                        headers=self._headers(),
                                    )
                                    if del_resp.status_code in (204, 404):
                                        cleanup_stats["folders_deleted"] += 1
                                        self.logger.info(
                                            f"Deleted orphaned folder: {folder['name']}"
                                        )
                                except Exception as e:
                                    cleanup_stats["errors"] += 1
                                    self.logger.warning(
                                        f"Failed to delete orphaned folder: {e}"
                                    )
                    except Exception as e:
                        self.logger.warning(
                            f"Failed to search for orphaned folders: {e}"
                        )

            self.logger.info(
                f"🧹 Cleanup completed: {cleanup_stats['files_deleted']} files, "
                f"{cleanup_stats['folders_deleted']} folders deleted, "
                f"{cleanup_stats['errors']} errors"
            )

        except Exception as e:
            self.logger.error(f"❌ Error during cleanup: {e}")
            # Don't re-raise - cleanup is best-effort
