"""Outlook Mail source implementation.

Simplified version that retrieves:
  - All mail folders (hierarchical discovery)
  - Messages from all folders
  - Attachments

Follows the same structure as the Gmail connector implementation.
"""

import base64
from datetime import datetime
from typing import Any, AsyncGenerator, Dict, List, Optional

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from airweave.core.logging import logger
from airweave.platform.auth.schemas import AuthType
from airweave.platform.decorators import source
from airweave.platform.entities._base import Breadcrumb, ChunkEntity
from airweave.platform.entities.outlook_mail import (
    OutlookAttachmentEntity,
    OutlookMailFolderEntity,
    OutlookMessageEntity,
)
from airweave.platform.sources._base import BaseSource


@source(
    name="Outlook Mail",
    short_name="outlook_mail",
    auth_type=AuthType.oauth2_with_refresh_rotating,
    auth_config_class="OutlookMailAuthConfig",
    config_class="OutlookMailConfig",
    labels=["Communication", "Email"],
)
class OutlookMailSource(BaseSource):
    """Outlook Mail source connector integrates with the Microsoft Graph API to extract email data.

    Synchronizes data from Outlook mailboxes.

    It provides comprehensive access to mail folders, messages, and
    attachments with hierarchical folder organization and content processing capabilities.
    """

    GRAPH_BASE_URL = "https://graph.microsoft.com/v1.0"

    def get_default_cursor_field(self) -> Optional[str]:
        """Get the default cursor field for Outlook Mail source.

        Outlook uses 'lastModifiedDateTime' and delta tokens for incremental sync.
        """
        return "lastModifiedDateTime"

    def validate_cursor_field(self, cursor_field: str) -> None:
        """Validate if the given cursor field is valid for Outlook Mail."""
        valid_fields = ["lastModifiedDateTime", "deltaToken"]

        if cursor_field not in valid_fields:
            error_msg = (
                f"Invalid cursor field '{cursor_field}' for Outlook Mail source. "
                f"Valid fields: {', '.join(valid_fields)}"
            )
            self.logger.error(error_msg)
            raise ValueError(error_msg)

    def _prepare_sync_context(
        self,
    ) -> tuple[str, Optional[str], Optional[str]]:
        """Prepare sync context and return cursor field, delta token, and last modified timestamp.

        Returns:
            Tuple of (cursor_field, delta_token, last_modified)
        """
        # Clean up expired tokens first
        self._cleanup_expired_tokens()

        # Get cursor data for incremental sync
        cursor_data = self._get_cursor_data()
        cursor_field = self.get_effective_cursor_field()
        if not cursor_field:
            cursor_field = self.get_default_cursor_field()

        # Validate the cursor field - will raise ValueError if invalid
        if cursor_field != self.get_default_cursor_field():
            self.validate_cursor_field(cursor_field)

        # Extract sync tokens
        delta_token = cursor_data.get("deltaToken")
        last_modified = cursor_data.get("lastModifiedDateTime")

        if delta_token:
            self.logger.info(
                f"Found delta token for field '{cursor_field}'. "
                f"Will perform DELTA sync using Microsoft Graph delta query."
            )
        elif last_modified:
            self.logger.info(
                f"Found cursor data for field '{cursor_field}': {last_modified}. "
                f"Will perform INCREMENTAL sync using date filtering."
            )
        else:
            self.logger.info(
                f"No cursor data found for field '{cursor_field}'. "
                f"Will perform FULL sync (first sync or cursor reset)."
            )

        return cursor_field, delta_token, last_modified

    @classmethod
    async def create(
        cls, access_token: str, config: Optional[Dict[str, Any]] = None
    ) -> "OutlookMailSource":
        """Create a new Outlook Mail source instance with the provided OAuth access token."""
        logger.info("Creating new OutlookMailSource instance")
        instance = cls()
        instance.access_token = access_token
        logger.info(f"OutlookMailSource instance created with config: {config}")
        return instance

    async def _setup_initial_delta_sync(
        self,
        client: httpx.AsyncClient,
        folder_entity: OutlookMailFolderEntity,
        folder_breadcrumb: Breadcrumb,
    ) -> Optional[str]:
        """Set up initial delta sync by making a delta request without a token.

        This is needed to get the first delta token for future incremental syncs.

        Returns:
            Delta token if successful, None otherwise
        """
        folder_name = folder_entity.display_name
        self.logger.info(f"Setting up initial delta sync for folder: {folder_name}")

        try:
            # Make initial delta request to get the delta token
            url = f"{self.GRAPH_BASE_URL}/me/mailFolders/{folder_entity.entity_id}/messages/delta"
            params = {"$top": 1}  # Just get one message to establish the delta link

            data = await self._get_with_auth(client, url, params=params)

            # Extract delta token from the response
            if "@odata.deltaLink" in data:
                delta_link = data["@odata.deltaLink"]
                if "deltatoken=" in delta_link:
                    delta_token = delta_link.split("deltatoken=")[1].split("&")[0]
                    self.logger.info(
                        f"Successfully obtained initial delta token for folder {folder_name}"
                    )

                    # Store the delta token in cursor data
                    if data.get("value"):
                        last_message = data["value"][0]
                        last_modified = last_message.get("lastModifiedDateTime", "")
                        if last_modified:
                            self._update_cursor_data(
                                delta_token, last_modified, folder_entity.entity_id
                            )
                            self.logger.info(
                                f"Updated cursor with initial delta token for folder {folder_name}"
                            )

                    return delta_token

            self.logger.warning(
                f"Could not extract delta token from response for folder {folder_name}"
            )
            return None

        except Exception as e:
            self.logger.error(
                f"Error setting up initial delta sync for folder {folder_name}: {str(e)}"
            )
            return None

    def _update_cursor_data(self, delta_token: str, last_modified: str, folder_id: str):
        """Update cursor with delta token and last modified timestamp."""
        if not hasattr(self, "cursor") or self.cursor is None:
            self.logger.debug("No cursor available, skipping cursor update")
            return

        cursor_field = self.get_effective_cursor_field()
        if not cursor_field:
            cursor_field = self.get_default_cursor_field()

        self.cursor.cursor_data.update(
            {
                "deltaToken": delta_token,
                "lastModifiedDateTime": last_modified,
                "folderId": folder_id,
                "lastSyncTime": datetime.utcnow().isoformat(),
            }
        )

        self.logger.debug(f"Updated cursor data: {self.cursor.cursor_data}")

    def _get_cursor_data(self) -> Dict[str, Any]:
        """Get cursor data for incremental sync."""
        if hasattr(self, "cursor") and self.cursor:
            return getattr(self.cursor, "cursor_data", {})
        return {}

    def _validate_delta_token(self, delta_token: str) -> bool:
        """Validate if a delta token is still valid.

        This is a basic validation - the actual validation happens when using the token.
        """
        if not delta_token:
            return False

        # Basic format validation (delta tokens are typically long strings)
        if len(delta_token) < 10:
            return False

        return True

    def _cleanup_expired_tokens(self):
        """Clean up expired or invalid delta tokens from cursor data."""
        cursor_data = self._get_cursor_data()
        delta_token = cursor_data.get("deltaToken")

        if delta_token and not self._validate_delta_token(delta_token):
            self.logger.info("Cleaning up invalid delta token")
            cursor_data.pop("deltaToken", None)

            # Keep the last modified time for fallback
            if "lastModifiedDateTime" in cursor_data:
                self.logger.info("Keeping lastModifiedDateTime for fallback sync")

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        reraise=True,
    )
    async def _get_with_auth(
        self, client: httpx.AsyncClient, url: str, params: Optional[dict] = None
    ) -> dict:
        """Make an authenticated GET request to Microsoft Graph API."""
        self.logger.debug(f"Making authenticated GET request to: {url} with params: {params}")

        # Get fresh token (will refresh if needed)
        access_token = await self.get_access_token()
        headers = {"Authorization": f"Bearer {access_token}"}

        try:
            response = await client.get(url, headers=headers, params=params)

            # Handle 401 errors by refreshing token and retrying
            if response.status_code == 401:
                self.logger.warning(
                    f"Got 401 Unauthorized from Microsoft Graph API at {url}, refreshing token..."
                )
                await self.refresh_on_unauthorized()

                # Get new token and retry
                access_token = await self.get_access_token()
                headers = {"Authorization": f"Bearer {access_token}"}
                response = await client.get(url, headers=headers, params=params)

            response.raise_for_status()
            data = response.json()
            self.logger.debug(f"Received response from {url} - Status: {response.status_code}")
            return data
        except Exception as e:
            self.logger.error(f"Error in API request to {url}: {str(e)}")
            raise

    async def _process_folder_messages(
        self,
        client: httpx.AsyncClient,
        folder_entity: OutlookMailFolderEntity,
        folder_breadcrumb: Breadcrumb,
    ) -> AsyncGenerator[ChunkEntity, None]:
        """Process messages in a folder and handle errors gracefully."""
        self.logger.info(f"Processing messages in folder: {folder_entity.display_name}")
        try:
            async for entity in self._generate_message_entities(
                client, folder_entity, folder_breadcrumb
            ):
                yield entity
        except Exception as e:
            self.logger.error(
                f"Error processing messages in folder {folder_entity.display_name}: {str(e)}"
            )
            # Continue with other folders even if one fails

    async def _process_child_folders(
        self,
        client: httpx.AsyncClient,
        folder_entity: OutlookMailFolderEntity,
        parent_breadcrumbs: List[Breadcrumb],
        folder_breadcrumb: Breadcrumb,
    ) -> AsyncGenerator[OutlookMailFolderEntity, None]:
        """Process child folders recursively and handle errors gracefully."""
        if folder_entity.child_folder_count > 0:
            self.logger.info(
                f"Folder {folder_entity.display_name} has "
                f"{folder_entity.child_folder_count} child folders, recursively processing"
            )
            try:
                async for child_entity in self._generate_folder_entities(
                    client,
                    folder_entity.entity_id,
                    parent_breadcrumbs + [folder_breadcrumb],
                ):
                    yield child_entity
            except Exception as e:
                self.logger.error(
                    f"Error processing child folders of {folder_entity.display_name}: {str(e)}"
                )
                # Continue with other folders even if one fails

    async def _generate_folder_entities(
        self,
        client: httpx.AsyncClient,
        folder_id: Optional[str] = None,
        parent_breadcrumbs: Optional[List[Breadcrumb]] = None,
    ) -> AsyncGenerator[OutlookMailFolderEntity, None]:
        """Recursively generate OutlookMailFolderEntity objects.

        Traverses the mail folder hierarchy via Microsoft Graph.
        """
        if parent_breadcrumbs is None:
            parent_breadcrumbs = []

        # Decide the endpoint: top-level vs. child folders
        if folder_id:
            url = f"{self.GRAPH_BASE_URL}/me/mailFolders/{folder_id}/childFolders"
            self.logger.info(f"Fetching child folders for folder ID: {folder_id}")
        else:
            # top-level mail folders
            url = f"{self.GRAPH_BASE_URL}/me/mailFolders"
            self.logger.info("Fetching top-level mail folders")

        try:
            while url:
                self.logger.debug(f"Making request to: {url}")
                data = await self._get_with_auth(client, url)
                folders = data.get("value", [])
                self.logger.info(f"Retrieved {len(folders)} folders")

                for folder in folders:
                    # Create and yield folder entity
                    folder_entity = OutlookMailFolderEntity(
                        entity_id=folder["id"],
                        breadcrumbs=parent_breadcrumbs,
                        display_name=folder["displayName"],
                        parent_folder_id=folder.get("parentFolderId"),
                        child_folder_count=folder.get("childFolderCount", 0),
                        total_item_count=folder.get("totalItemCount", 0),
                        unread_item_count=folder.get("unreadItemCount", 0),
                        well_known_name=folder.get("wellKnownName"),
                    )

                    self.logger.info(
                        f"Processing folder: {folder_entity.display_name} "
                        f"(ID: {folder_entity.entity_id}, Items: {folder_entity.total_item_count})"
                    )
                    yield folder_entity

                    # Build breadcrumb for this folder
                    folder_breadcrumb = Breadcrumb(
                        entity_id=folder_entity.entity_id,
                        name=folder_entity.display_name,
                        type="folder",
                    )

                    # Process messages in this folder
                    async for entity in self._process_folder_messages(
                        client, folder_entity, folder_breadcrumb
                    ):
                        yield entity

                    # Process child folders recursively
                    async for child_entity in self._process_child_folders(
                        client, folder_entity, parent_breadcrumbs, folder_breadcrumb
                    ):
                        yield child_entity

                # Handle pagination
                next_link = data.get("@odata.nextLink")
                if next_link:
                    self.logger.debug(f"Following pagination link: {next_link}")
                url = next_link if next_link else None

        except Exception as e:
            self.logger.error(f"Error fetching folders: {str(e)}")
            raise

    def _build_url_and_params(
        self, folder_id: str, delta_token: Optional[str], since_timestamp: Optional[datetime]
    ) -> tuple[str, Optional[dict]]:
        """Build the URL and parameters for the message request."""
        if delta_token:
            url = (
                f"{self.GRAPH_BASE_URL}/me/mailFolders/{folder_id}/messages/delta"
                f"?$deltatoken={delta_token}"
            )
            return url, None
        elif since_timestamp:
            url = f"{self.GRAPH_BASE_URL}/me/mailFolders/{folder_id}/messages"
            params = {
                "$filter": f"lastModifiedDateTime gt {since_timestamp.isoformat()}Z",
                "$top": 50,
            }
            return url, params
        else:
            url = f"{self.GRAPH_BASE_URL}/me/mailFolders/{folder_id}/messages"
            return url, {"$top": 50}

    def _log_sync_mode(
        self, folder_name: str, delta_token: Optional[str], since_timestamp: Optional[datetime]
    ):
        """Log the sync mode being used."""
        if delta_token:
            self.logger.info(f"Using delta token for incremental sync in folder: {folder_name}")
        elif since_timestamp:
            self.logger.info(
                f"Using date filter for incremental sync since {since_timestamp} "
                f"in folder {folder_name}"
            )
        else:
            self.logger.info(f"Performing full sync in folder: {folder_name}")

    def _extract_delta_token(self, data: dict) -> Optional[str]:
        """Extract delta token from API response."""
        if "@odata.deltaLink" in data:
            delta_link = data["@odata.deltaLink"]
            if "deltatoken=" in delta_link:
                return delta_link.split("deltatoken=")[1].split("&")[0]
        return None

    def _handle_delta_token_error(
        self, data: dict, delta_token: str, folder_entity, folder_breadcrumb
    ):
        """Handle delta token errors and return True if error was handled."""
        if delta_token and "error" in data:
            error_code = data["error"].get("code", "")
            if error_code in [
                "InvalidAuthenticationToken",
                "DeltaTokenExpired",
                "InvalidDeltaToken",
            ]:
                self.logger.warning(f"Delta token error: {error_code}, handling expiration")
                return True
        return False

    async def _process_message_batch(
        self,
        client: httpx.AsyncClient,
        messages: list,
        folder_name: str,
        folder_breadcrumb: Breadcrumb,
        folder_entity: OutlookMailFolderEntity,
    ) -> AsyncGenerator[ChunkEntity, None]:
        """Process a batch of messages and yield entities."""
        for msg_idx, message_data in enumerate(messages):
            message_id = message_data.get("id", "unknown")
            self.logger.debug(
                f"Processing message #{msg_idx + 1}/{len(messages)} (ID: {message_id}) "
                f"in folder {folder_name}"
            )

            # Check if this is a deletion (delta query specific)
            if message_data.get("@removed"):
                self.logger.info(f"Message {message_id} was deleted, creating deletion entity")
                deletion_entity = self._create_deletion_entity(message_data, folder_breadcrumb)
                if deletion_entity:
                    yield deletion_entity
                continue

            # If message doesn't have full data, fetch it
            if "body" not in message_data:
                self.logger.debug(f"Fetching full message details for {message_id}")
                message_url = f"{self.GRAPH_BASE_URL}/me/messages/{message_id}"
                message_data = await self._get_with_auth(client, message_url)

            # Process the message
            try:
                async for entity in self._process_message(
                    client, message_data, folder_name, folder_breadcrumb
                ):
                    yield entity
            except Exception as e:
                self.logger.error(f"Error processing message {message_id}: {str(e)}")
                # Continue with other messages even if one fails

    async def _get_messages_delta(
        self,
        client: httpx.AsyncClient,
        folder_entity: OutlookMailFolderEntity,
        folder_breadcrumb: Breadcrumb,
        delta_token: Optional[str] = None,
        since_timestamp: Optional[datetime] = None,
    ) -> AsyncGenerator[ChunkEntity, None]:
        """Get messages using delta query for incremental sync."""
        folder_name = folder_entity.display_name
        folder_id = folder_entity.entity_id

        # Build URL and parameters
        url, params = self._build_url_and_params(folder_id, delta_token, since_timestamp)
        self._log_sync_mode(folder_name, delta_token, since_timestamp)

        page_count = 0
        message_count = 0
        next_delta_token = None

        try:
            while url:
                page_count += 1
                self.logger.info(
                    f"Fetching message list page #{page_count} for folder {folder_name}"
                )

                data = await self._get_with_auth(client, url, params=params)
                messages = data.get("value", [])
                self.logger.info(
                    f"Found {len(messages)} messages on page {page_count} in folder {folder_name}"
                )

                # Extract delta token if available
                next_delta_token = self._extract_delta_token(data)

                # Check for delta token errors
                if self._handle_delta_token_error(
                    data, delta_token, folder_entity, folder_breadcrumb
                ):
                    async for entity in self._handle_delta_token_expiration(
                        client, folder_entity, folder_breadcrumb, delta_token
                    ):
                        yield entity
                    return

                # Process messages
                async for entity in self._process_message_batch(
                    client, messages, folder_name, folder_breadcrumb, folder_entity
                ):
                    yield entity
                    message_count += 1

                # Handle pagination
                url = data.get("@odata.nextLink")
                if url:
                    self.logger.debug("Following pagination to next page")
                    params = None  # params are included in the nextLink
                else:
                    self.logger.info(
                        f"Completed folder {folder_name}. "
                        f"Processed {message_count} messages in {page_count} pages."
                    )
                    break

            # Update cursor with delta token if we have one
            if next_delta_token and messages:
                # Get the last modified time from the last message processed
                last_message = messages[-1]  # Get the last message from the batch
                if not last_message.get("@removed"):
                    last_modified = last_message.get("lastModifiedDateTime", "")
                    if last_modified:
                        self._update_cursor_data(
                            next_delta_token, last_modified, folder_entity.entity_id
                        )
                        self.logger.info(
                            f"Updated cursor with delta token for folder {folder_name}"
                        )

        except Exception as e:
            self.logger.error(
                f"Error processing messages in folder {folder_entity.display_name}: {str(e)}"
            )
            raise

    def _should_skip_folder(self, folder_entity: OutlookMailFolderEntity) -> bool:
        """Check if folder should be skipped due to no messages."""
        if folder_entity.total_item_count == 0:
            self.logger.debug(f"Skipping folder {folder_entity.display_name} - no messages")
            return True
        return False

    def _log_folder_start(self, folder_entity: OutlookMailFolderEntity):
        """Log the start of message generation for a folder."""
        self.logger.info(
            f"Starting message generation for folder: {folder_entity.display_name} "
            f"({folder_entity.total_item_count} items)"
        )

    def _get_sync_tokens(self) -> tuple[Optional[str], Optional[str]]:
        """Get delta token and last modified timestamp from cursor data."""
        cursor_data = self._get_cursor_data()
        return cursor_data.get("deltaToken"), cursor_data.get("lastModifiedDateTime")

    async def _sync_with_delta_token(
        self,
        client: httpx.AsyncClient,
        folder_entity: OutlookMailFolderEntity,
        folder_breadcrumb: Breadcrumb,
        delta_token: str,
    ) -> AsyncGenerator[ChunkEntity, None]:
        """Sync messages using delta token."""
        self.logger.info(
            f"Using delta token for incremental sync in folder {folder_entity.display_name}"
        )
        async for entity in self._get_messages_delta(
            client, folder_entity, folder_breadcrumb, delta_token=delta_token
        ):
            yield entity

    async def _sync_with_date_filter(
        self,
        client: httpx.AsyncClient,
        folder_entity: OutlookMailFolderEntity,
        folder_breadcrumb: Breadcrumb,
        last_modified: str,
    ) -> AsyncGenerator[ChunkEntity, None]:
        """Sync messages using date filtering."""
        try:
            since_timestamp = datetime.fromisoformat(last_modified.replace("Z", "+00:00"))
            self.logger.info(
                f"Using date filter for incremental sync since {since_timestamp} "
                f"in folder {folder_entity.display_name}"
            )

            # First, try to set up delta sync for future runs
            new_delta_token = await self._setup_initial_delta_sync(
                client, folder_entity, folder_breadcrumb
            )
            if new_delta_token:
                self.logger.info(
                    f"Successfully set up delta sync for future runs in folder "
                    f"{folder_entity.display_name}"
                )

            # Then perform the current sync using date filtering
            async for entity in self._get_messages_delta(
                client, folder_entity, folder_breadcrumb, since_timestamp=since_timestamp
            ):
                yield entity
        except (ValueError, TypeError) as e:
            self.logger.warning(
                f"Error parsing last modified timestamp {last_modified}: {str(e)}, "
                f"falling back to full sync"
            )
            async for entity in self._get_messages_delta(client, folder_entity, folder_breadcrumb):
                yield entity

    async def _sync_with_full_sync(
        self,
        client: httpx.AsyncClient,
        folder_entity: OutlookMailFolderEntity,
        folder_breadcrumb: Breadcrumb,
    ) -> AsyncGenerator[ChunkEntity, None]:
        """Sync messages using full sync."""
        self.logger.info(f"Performing full sync in folder {folder_entity.display_name}")

        # Try to set up delta sync for future runs
        new_delta_token = await self._setup_initial_delta_sync(
            client, folder_entity, folder_breadcrumb
        )
        if new_delta_token:
            self.logger.info(
                f"Successfully set up delta sync for future runs in folder "
                f"{folder_entity.display_name}"
            )

        async for entity in self._get_messages_delta(client, folder_entity, folder_breadcrumb):
            yield entity

    async def _generate_message_entities(
        self,
        client: httpx.AsyncClient,
        folder_entity: OutlookMailFolderEntity,
        folder_breadcrumb: Breadcrumb,
    ) -> AsyncGenerator[ChunkEntity, None]:
        """Generate OutlookMessageEntity objects and their attachments for a given folder."""
        # Skip folders with no messages
        if self._should_skip_folder(folder_entity):
            return

        self._log_folder_start(folder_entity)

        # Get sync tokens
        delta_token, last_modified = self._get_sync_tokens()

        # Determine sync mode and execute
        if delta_token:
            async for entity in self._sync_with_delta_token(
                client, folder_entity, folder_breadcrumb, delta_token
            ):
                yield entity
        elif last_modified:
            async for entity in self._sync_with_date_filter(
                client, folder_entity, folder_breadcrumb, last_modified
            ):
                yield entity
        else:
            async for entity in self._sync_with_full_sync(client, folder_entity, folder_breadcrumb):
                yield entity

    async def _handle_delta_token_expiration(
        self,
        client: httpx.AsyncClient,
        folder_entity: OutlookMailFolderEntity,
        folder_breadcrumb: Breadcrumb,
        expired_token: str,
    ) -> AsyncGenerator[ChunkEntity, None]:
        """Handle expired delta token by falling back to date filtering.

        This is called when a delta token expires or becomes invalid.
        """
        self.logger.warning(
            f"Delta token expired for folder {folder_entity.display_name}, "
            "falling back to date filtering"
        )

        # Clear the expired delta token
        cursor_data = self._get_cursor_data()
        if cursor_data.get("deltaToken") == expired_token:
            cursor_data.pop("deltaToken", None)
            self.logger.info(f"Cleared expired delta token for folder {folder_entity.display_name}")

        # Try to get last modified time for fallback
        last_modified = cursor_data.get("lastModifiedDateTime")
        if last_modified:
            try:
                since_timestamp = datetime.fromisoformat(last_modified.replace("Z", "+00:00"))
                self.logger.info(
                    f"Using date filter fallback since {since_timestamp} "
                    f"for folder {folder_entity.display_name}"
                )

                # Set up new delta sync for future runs
                new_delta_token = await self._setup_initial_delta_sync(
                    client, folder_entity, folder_breadcrumb
                )
                if new_delta_token:
                    self.logger.info(
                        f"Successfully set up new delta sync after token expiration "
                        f"for folder {folder_entity.display_name}"
                    )

                # Perform sync using date filtering
                async for entity in self._get_messages_delta(
                    client, folder_entity, folder_breadcrumb, since_timestamp=since_timestamp
                ):
                    yield entity
                return
            except (ValueError, TypeError) as e:
                self.logger.warning(
                    f"Error parsing last modified timestamp {last_modified}: {str(e)}"
                )

        # Final fallback to full sync
        self.logger.info(f"Performing full sync fallback for folder {folder_entity.display_name}")
        async for entity in self._get_messages_delta(client, folder_entity, folder_breadcrumb):
            yield entity

    def _create_deletion_entity(
        self, message_data: Dict, folder_breadcrumb: Breadcrumb
    ) -> Optional[ChunkEntity]:
        """Create a deletion entity for a removed message.

        This is used when delta queries return @removed messages.
        """
        try:
            message_id = message_data.get("id")
            if not message_id:
                return None

            # Create a deletion entity to track removed messages
            deletion_entity = OutlookMessageEntity(
                entity_id=f"{message_id}_deleted",
                breadcrumbs=[folder_breadcrumb],
                folder_name=folder_breadcrumb.name,
                subject=message_data.get("subject", "Deleted Message"),
                sender=None,
                to_recipients=[],
                cc_recipients=[],
                sent_date=None,
                received_date=None,
                body_preview="",
                body_content="",
                is_read=False,
                is_draft=False,
                importance=None,
                has_attachments=False,
                internet_message_id=None,
                # Add deletion metadata
                metadata={
                    "deletion_status": "removed",
                    "original_message_id": message_id,
                    "deletion_detected_at": datetime.utcnow().isoformat(),
                    "source": "outlook_mail_delta",
                },
            )

            self.logger.info(f"Created deletion entity for removed message {message_id}")
            return deletion_entity

        except Exception as e:
            self.logger.error(f"Error creating deletion entity: {str(e)}")
            return None

    async def _process_message(
        self,
        client: httpx.AsyncClient,
        message_data: Dict,
        folder_name: str,
        folder_breadcrumb: Breadcrumb,
    ) -> AsyncGenerator[ChunkEntity, None]:
        """Process a message and its attachments."""
        message_id = message_data["id"]
        self.logger.debug(f"Processing message ID: {message_id} in folder: {folder_name}")

        # Extract message fields
        subject = message_data.get("subject")
        sender = (
            message_data.get("from", {}).get("emailAddress", {}).get("address")
            if message_data.get("from")
            else None
        )
        to_recipients = [
            r.get("emailAddress", {}).get("address")
            for r in message_data.get("toRecipients", [])
            if r.get("emailAddress")
        ]
        cc_recipients = [
            r.get("emailAddress", {}).get("address")
            for r in message_data.get("ccRecipients", [])
            if r.get("emailAddress")
        ]

        # Parse dates
        sent_date = None
        received_date = None
        try:
            if message_data.get("sentDateTime"):
                sent_date = datetime.fromisoformat(
                    message_data["sentDateTime"].replace("Z", "+00:00")
                )
            if message_data.get("receivedDateTime"):
                received_date = datetime.fromisoformat(
                    message_data["receivedDateTime"].replace("Z", "+00:00")
                )
        except (ValueError, TypeError) as e:
            self.logger.warning(f"Error parsing dates for message {message_id}: {str(e)}")

        # Extract body content
        body_content = ""
        body_preview = message_data.get("bodyPreview", "")
        if message_data.get("body"):
            body_content = message_data["body"].get("content", "")

        self.logger.debug(f"Creating message entity for message {message_id}")

        # Create message entity
        message_entity = OutlookMessageEntity(
            entity_id=message_id,
            breadcrumbs=[folder_breadcrumb],
            folder_name=folder_name,
            subject=subject,
            sender=sender,
            to_recipients=to_recipients,
            cc_recipients=cc_recipients,
            sent_date=sent_date,
            received_date=received_date,
            body_preview=body_preview,
            body_content=body_content,
            is_read=message_data.get("isRead", False),
            is_draft=message_data.get("isDraft", False),
            importance=message_data.get("importance"),
            has_attachments=message_data.get("hasAttachments", False),
            internet_message_id=message_data.get("internetMessageId"),
        )

        yield message_entity
        self.logger.debug(f"Message entity yielded for {message_id}")

        # Create message breadcrumb for attachments
        message_breadcrumb = Breadcrumb(
            entity_id=message_id,
            name=subject or f"Message {message_id}",
            type="message",
        )

        # Process attachments if the message has any
        if message_entity.has_attachments:
            self.logger.debug(f"Message {message_id} has attachments, processing them")
            attachment_count = 0
            try:
                async for attachment_entity in self._process_attachments(
                    client, message_id, [folder_breadcrumb, message_breadcrumb]
                ):
                    attachment_count += 1
                    self.logger.debug(
                        f"Yielding attachment #{attachment_count} from message {message_id}"
                    )
                    yield attachment_entity
                self.logger.debug(
                    f"Processed {attachment_count} attachments for message {message_id}"
                )
            except Exception as e:
                self.logger.error(
                    f"Error processing attachments for message {message_id}: {str(e)}"
                )
                # Continue with message processing even if attachments fail

    async def _create_content_stream(self, binary_data: bytes):
        """Create an async generator for binary content."""
        yield binary_data

    async def _fetch_attachment_content(
        self, client: httpx.AsyncClient, message_id: str, attachment_id: str
    ) -> Optional[str]:
        """Fetch attachment content from Microsoft Graph API."""
        self.logger.debug(f"Fetching content for attachment {attachment_id}")
        attachment_url = (
            f"{self.GRAPH_BASE_URL}/me/messages/{message_id}/attachments/{attachment_id}"
        )
        attachment_data = await self._get_with_auth(client, attachment_url)
        return attachment_data.get("contentBytes")

    async def _process_single_attachment(
        self,
        client: httpx.AsyncClient,
        attachment: Dict,
        message_id: str,
        breadcrumbs: List[Breadcrumb],
        att_idx: int,
        total_attachments: int,
    ) -> Optional[OutlookAttachmentEntity]:
        """Process a single attachment and return the processed entity."""
        attachment_id = attachment["id"]
        attachment_type = attachment.get("@odata.type", "")
        attachment_name = attachment.get("name", "unknown")

        self.logger.debug(
            f"Processing attachment #{att_idx + 1}/{total_attachments} "
            f"(ID: {attachment_id}, Name: {attachment_name}, Type: {attachment_type})"
        )

        # Only process file attachments
        if "#microsoft.graph.fileAttachment" not in attachment_type:
            self.logger.debug(
                f"Skipping non-file attachment: {attachment_name} (type: {attachment_type})"
            )
            return None

        try:
            # Get attachment content if not already included
            content_bytes = attachment.get("contentBytes")
            if not content_bytes:
                content_bytes = await self._fetch_attachment_content(
                    client, message_id, attachment_id
                )

                if not content_bytes:
                    self.logger.warning(f"No content found for attachment {attachment_name}")
                    return None

            # Create file entity
            file_entity = OutlookAttachmentEntity(
                entity_id=f"{message_id}_attachment_{attachment_id}",
                breadcrumbs=breadcrumbs,
                file_id=attachment_id,
                name=attachment_name,
                mime_type=attachment.get("contentType"),
                size=attachment.get("size", 0),
                download_url=f"outlook://attachment/{message_id}/{attachment_id}",
                message_id=message_id,
                attachment_id=attachment_id,
                content_type=attachment.get("contentType"),
                is_inline=attachment.get("isInline", False),
                content_id=attachment.get("contentId"),
                metadata={
                    "source": "outlook_mail",
                    "message_id": message_id,
                    "attachment_id": attachment_id,
                },
            )

            # Decode the base64 data
            try:
                binary_data = base64.b64decode(content_bytes)
            except Exception as e:
                self.logger.error(f"Error decoding attachment content: {str(e)}")
                return None

            # Process using the BaseSource method
            self.logger.debug(
                f"Processing file entity for {attachment_name} with direct content stream"
            )
            processed_entity = await self.process_file_entity_with_content(
                file_entity=file_entity,
                content_stream=self._create_content_stream(binary_data),
                metadata={"source": "outlook_mail", "message_id": message_id},
            )

            if processed_entity:
                self.logger.debug(f"Successfully processed attachment: {attachment_name}")
                return processed_entity
            else:
                self.logger.warning(f"Processing failed for attachment: {attachment_name}")
                return None

        except Exception as e:
            self.logger.error(f"Error processing attachment {attachment_id}: {str(e)}")
            return None

    async def _process_attachments(
        self,
        client: httpx.AsyncClient,
        message_id: str,
        breadcrumbs: List[Breadcrumb],
    ) -> AsyncGenerator[OutlookAttachmentEntity, None]:
        """Process message attachments using the standard file processing pipeline."""
        self.logger.debug(f"Processing attachments for message {message_id}")

        url = f"{self.GRAPH_BASE_URL}/me/messages/{message_id}/attachments"

        try:
            while url:
                self.logger.debug(f"Making request to: {url}")
                data = await self._get_with_auth(client, url)
                attachments = data.get("value", [])
                self.logger.debug(
                    f"Retrieved {len(attachments)} attachments for message {message_id}"
                )

                for att_idx, attachment in enumerate(attachments):
                    processed_entity = await self._process_single_attachment(
                        client, attachment, message_id, breadcrumbs, att_idx, len(attachments)
                    )
                    if processed_entity:
                        yield processed_entity

                # Handle pagination
                url = data.get("@odata.nextLink")
                if url:
                    self.logger.debug("Following pagination link")

        except Exception as e:
            self.logger.error(f"Error processing attachments for message {message_id}: {str(e)}")
            # Don't re-raise - continue with other messages even if attachments fail

    async def generate_entities(self) -> AsyncGenerator[ChunkEntity, None]:
        """Generate all Outlook mail entities: Folders, Messages and Attachments incrementally."""
        self.logger.info("===== STARTING OUTLOOK MAIL ENTITY GENERATION =====")
        entity_count = 0

        # Prepare sync context
        cursor_field, delta_token, last_modified = self._prepare_sync_context()

        try:
            async with httpx.AsyncClient() as client:
                self.logger.info("HTTP client created, starting entity generation")

                # Start with top-level folders and recursively process all folders and contents
                async for entity in self._generate_folder_entities(client):
                    entity_count += 1
                    entity_type = type(entity).__name__
                    self.logger.info(
                        f"Yielding entity #{entity_count}: {entity_type} with ID {entity.entity_id}"
                    )
                    yield entity

        except Exception as e:
            self.logger.error(f"Error in entity generation: {str(e)}", exc_info=True)
            raise
        finally:
            self.logger.info(
                f"===== OUTLOOK MAIL ENTITY GENERATION COMPLETE: {entity_count} entities ====="
            )
