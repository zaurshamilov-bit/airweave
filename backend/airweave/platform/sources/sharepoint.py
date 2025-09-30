"""SharePoint source implementation using Microsoft Graph API.

Retrieves data from SharePoint, including:
 - Users in the organization
 - Groups in the organization
 - Sites (starting from root site)
 - Drives (document libraries) within sites
 - DriveItems (files and folders) within drives

Reference:
  https://learn.microsoft.com/en-us/graph/sharepoint-concept-overview
  https://learn.microsoft.com/en-us/graph/api/resources/site
  https://learn.microsoft.com/en-us/graph/api/resources/drive
"""

from collections import deque
from typing import Any, AsyncGenerator, Dict, Optional

import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from airweave.platform.decorators import source
from airweave.platform.entities._base import Breadcrumb, ChunkEntity
from airweave.platform.entities.sharepoint import (
    SharePointDriveEntity,
    SharePointDriveItemEntity,
    SharePointGroupEntity,
    SharePointSiteEntity,
    SharePointUserEntity,
)
from airweave.platform.sources._base import BaseSource
from airweave.schemas.source_connection import AuthenticationMethod, OAuthType


@source(
    name="SharePoint",
    short_name="sharepoint",
    auth_methods=[
        AuthenticationMethod.OAUTH_BROWSER,
        AuthenticationMethod.OAUTH_TOKEN,
        AuthenticationMethod.AUTH_PROVIDER,
    ],
    oauth_type=OAuthType.WITH_ROTATING_REFRESH,
    auth_config_class=None,
    config_class="SharePointConfig",
    labels=["File Storage", "Collaboration"],
    supports_continuous=False,
)
class SharePointSource(BaseSource):
    """SharePoint source connector integrates with the Microsoft Graph API.

    Synchronizes data from SharePoint including sites, document libraries,
    files, users, and groups.

    It provides comprehensive access to SharePoint resources with intelligent
    error handling and rate limiting.
    """

    GRAPH_BASE_URL = "https://graph.microsoft.com/v1.0"

    @classmethod
    async def create(
        cls, access_token: str, config: Optional[Dict[str, Any]] = None
    ) -> "SharePointSource":
        """Create a new SharePoint source instance with the provided OAuth access token."""
        instance = cls()
        instance.access_token = access_token
        return instance

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((httpx.ConnectTimeout, httpx.ReadTimeout)),
        reraise=True,
    )
    async def _get_with_auth(
        self, client: httpx.AsyncClient, url: str, params: Optional[Dict] = None
    ) -> Dict:
        """Make an authenticated GET request to Microsoft Graph API with retry logic."""
        # Get fresh token (will refresh if needed)
        access_token = await self.get_access_token()
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json",
        }

        try:
            resp = await client.get(url, headers=headers, params=params, timeout=30.0)

            # Handle 401 errors by refreshing token and retrying
            if resp.status_code == 401:
                self.logger.warning(
                    f"Got 401 Unauthorized from Microsoft Graph API at {url}, refreshing token..."
                )
                await self.refresh_on_unauthorized()

                # Get new token and retry
                access_token = await self.get_access_token()
                headers = {
                    "Authorization": f"Bearer {access_token}",
                    "Accept": "application/json",
                }
                resp = await client.get(url, headers=headers, params=params, timeout=30.0)

            resp.raise_for_status()
            return resp.json()
        except httpx.ConnectTimeout:
            self.logger.error(f"Connection timeout accessing Microsoft Graph API: {url}")
            raise
        except httpx.ReadTimeout:
            self.logger.error(f"Read timeout accessing Microsoft Graph API: {url}")
            raise
        except httpx.HTTPStatusError as e:
            self.logger.error(
                f"HTTP status error {e.response.status_code} from Microsoft Graph API: {url}"
            )
            # Log the response body for debugging
            try:
                error_body = e.response.json()
                self.logger.error(f"Error response body: {error_body}")
            except Exception:
                self.logger.error(f"Error response text: {e.response.text}")
            raise
        except Exception as e:
            self.logger.error(f"Unexpected error accessing Microsoft Graph API: {url}, {str(e)}")
            raise

    async def _generate_user_entities(
        self, client: httpx.AsyncClient
    ) -> AsyncGenerator[SharePointUserEntity, None]:
        """Generate SharePointUserEntity objects for users in the organization."""
        self.logger.info("Starting user entity generation")
        url = f"{self.GRAPH_BASE_URL}/users"
        params = {
            "$top": 100,
            "$select": (
                "id,displayName,userPrincipalName,mail,jobTitle,department,"
                "officeLocation,mobilePhone,businessPhones,accountEnabled"
            ),
        }
        user_count = 0

        try:
            while url:
                self.logger.debug(f"Fetching users from: {url}")
                data = await self._get_with_auth(client, url, params=params)
                users = data.get("value", [])
                self.logger.info(f"Retrieved {len(users)} users")

                for user_data in users:
                    user_count += 1
                    user_id = user_data.get("id")
                    display_name = user_data.get("displayName", "Unknown User")

                    self.logger.debug(f"Processing user #{user_count}: {display_name}")

                    yield SharePointUserEntity(
                        entity_id=user_id,
                        breadcrumbs=[],
                        display_name=display_name,
                        user_principal_name=user_data.get("userPrincipalName"),
                        mail=user_data.get("mail"),
                        job_title=user_data.get("jobTitle"),
                        department=user_data.get("department"),
                        office_location=user_data.get("officeLocation"),
                        mobile_phone=user_data.get("mobilePhone"),
                        business_phones=user_data.get("businessPhones"),
                        account_enabled=user_data.get("accountEnabled"),
                    )

                # Handle pagination
                url = data.get("@odata.nextLink")
                if url:
                    self.logger.debug("Following pagination to next page")
                    params = None  # params are included in the nextLink

            self.logger.info(f"Completed user generation. Total users: {user_count}")

        except Exception as e:
            self.logger.error(f"Error generating user entities: {str(e)}")
            raise

    async def _generate_group_entities(
        self, client: httpx.AsyncClient
    ) -> AsyncGenerator[SharePointGroupEntity, None]:
        """Generate SharePointGroupEntity objects for groups in the organization."""
        self.logger.info("Starting group entity generation")
        url = f"{self.GRAPH_BASE_URL}/groups"
        params = {
            "$top": 100,
            "$select": (
                "id,displayName,description,mail,mailEnabled,securityEnabled,"
                "groupTypes,visibility,createdDateTime"
            ),
        }
        group_count = 0

        try:
            while url:
                self.logger.debug(f"Fetching groups from: {url}")
                data = await self._get_with_auth(client, url, params=params)
                groups = data.get("value", [])
                self.logger.info(f"Retrieved {len(groups)} groups")

                for group_data in groups:
                    group_count += 1
                    group_id = group_data.get("id")
                    display_name = group_data.get("displayName", "Unknown Group")

                    self.logger.debug(f"Processing group #{group_count}: {display_name}")

                    # Parse created datetime
                    created_datetime = None
                    if group_data.get("createdDateTime"):
                        try:
                            created_str = group_data["createdDateTime"]
                            if created_str.endswith("Z"):
                                created_str = created_str.replace("Z", "+00:00")
                            from datetime import datetime

                            created_datetime = datetime.fromisoformat(created_str)
                        except (ValueError, TypeError) as e:
                            self.logger.warning(
                                f"Error parsing created datetime for group {group_id}: {str(e)}"
                            )

                    yield SharePointGroupEntity(
                        entity_id=group_id,
                        breadcrumbs=[],
                        display_name=display_name,
                        description=group_data.get("description"),
                        mail=group_data.get("mail"),
                        mail_enabled=group_data.get("mailEnabled"),
                        security_enabled=group_data.get("securityEnabled"),
                        group_types=group_data.get("groupTypes", []),
                        visibility=group_data.get("visibility"),
                        created_datetime=created_datetime,
                    )

                # Handle pagination
                url = data.get("@odata.nextLink")
                if url:
                    self.logger.debug("Following pagination to next page")
                    params = None  # params are included in the nextLink

            self.logger.info(f"Completed group generation. Total groups: {group_count}")

        except Exception as e:
            self.logger.error(f"Error generating group entities: {str(e)}")
            raise

    async def _generate_site_entities(
        self, client: httpx.AsyncClient
    ) -> AsyncGenerator[SharePointSiteEntity, None]:
        """Generate SharePointSiteEntity objects starting from the root site."""
        self.logger.info("Starting site entity generation")

        try:
            # Get the root site
            url = f"{self.GRAPH_BASE_URL}/sites/root"
            self.logger.debug(f"Fetching root site from: {url}")
            site_data = await self._get_with_auth(client, url)

            site_id = site_data.get("id")
            display_name = site_data.get("displayName", "Root Site")

            self.logger.info(f"Processing root site: {display_name} (ID: {site_id})")

            # Parse timestamps
            created_datetime = self._parse_datetime(site_data.get("createdDateTime"))
            last_modified_datetime = self._parse_datetime(site_data.get("lastModifiedDateTime"))

            yield SharePointSiteEntity(
                entity_id=site_id,
                breadcrumbs=[],
                display_name=display_name,
                name=site_data.get("name"),
                description=site_data.get("description"),
                web_url=site_data.get("webUrl"),
                created_datetime=created_datetime,
                last_modified_datetime=last_modified_datetime,
                is_personal_site=site_data.get("isPersonalSite"),
                site_collection=site_data.get("siteCollection"),
            )

        except Exception as e:
            self.logger.error(f"Error generating site entities: {str(e)}")
            raise

    def _parse_datetime(self, dt_str: Optional[str]):
        """Parse datetime string from Microsoft Graph API format."""
        if not dt_str:
            return None
        try:
            from datetime import datetime

            if dt_str.endswith("Z"):
                dt_str = dt_str.replace("Z", "+00:00")
            return datetime.fromisoformat(dt_str)
        except (ValueError, TypeError) as e:
            self.logger.warning(f"Error parsing datetime {dt_str}: {str(e)}")
            return None

    async def _generate_drive_entities(
        self, client: httpx.AsyncClient, site_id: str, site_name: str
    ) -> AsyncGenerator[SharePointDriveEntity, None]:
        """Generate SharePointDriveEntity objects for drives in a site."""
        self.logger.info(f"Starting drive entity generation for site: {site_name}")
        url = f"{self.GRAPH_BASE_URL}/sites/{site_id}/drives"
        params = {"$top": 100}
        drive_count = 0

        try:
            while url:
                self.logger.debug(f"Fetching drives from: {url}")
                data = await self._get_with_auth(client, url, params=params)
                drives = data.get("value", [])
                self.logger.info(f"Retrieved {len(drives)} drives for site {site_name}")

                for drive_data in drives:
                    drive_count += 1
                    drive_id = drive_data.get("id")
                    drive_name = drive_data.get("name", "Unknown Drive")

                    self.logger.debug(f"Processing drive #{drive_count}: {drive_name}")

                    # Create site breadcrumb
                    site_breadcrumb = Breadcrumb(
                        entity_id=site_id, name=site_name[:50], type="site"
                    )

                    yield SharePointDriveEntity(
                        entity_id=drive_id,
                        breadcrumbs=[site_breadcrumb],
                        name=drive_name,
                        description=drive_data.get("description"),
                        drive_type=drive_data.get("driveType"),
                        web_url=drive_data.get("webUrl"),
                        created_datetime=self._parse_datetime(drive_data.get("createdDateTime")),
                        last_modified_datetime=self._parse_datetime(
                            drive_data.get("lastModifiedDateTime")
                        ),
                        owner=drive_data.get("owner"),
                        quota=drive_data.get("quota"),
                        site_id=site_id,
                    )

                # Handle pagination
                url = data.get("@odata.nextLink")
                if url:
                    self.logger.debug("Following pagination to next page")
                    params = None  # params are included in the nextLink

            self.logger.info(
                f"Completed drive generation for site {site_name}. Total drives: {drive_count}"
            )

        except Exception as e:
            self.logger.error(f"Error generating drive entities for site {site_name}: {str(e)}")
            raise

    async def _list_drive_items(
        self,
        client: httpx.AsyncClient,
        drive_id: str,
        folder_id: Optional[str] = None,
    ) -> AsyncGenerator[Dict, None]:
        """List items in a drive using pagination.

        Args:
            client: HTTP client
            drive_id: ID of the drive
            folder_id: ID of specific folder, or None for root
        """
        if folder_id:
            url = f"{self.GRAPH_BASE_URL}/drives/{drive_id}/items/{folder_id}/children"
        else:
            url = f"{self.GRAPH_BASE_URL}/drives/{drive_id}/root/children"

        params = {
            "$top": 100,
            "$select": (
                "id,name,size,createdDateTime,lastModifiedDateTime,webUrl,"
                "file,folder,parentReference,createdBy,lastModifiedBy"
            ),
        }

        try:
            while url:
                data = await self._get_with_auth(client, url, params=params)

                for item in data.get("value", []):
                    self.logger.debug(f"Found drive item: {item.get('name')}")
                    yield item

                # Handle pagination using @odata.nextLink
                url = data.get("@odata.nextLink")
                if url:
                    params = None  # nextLink already includes parameters
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 403:
                self.logger.warning(f"Access denied to folder {folder_id}, skipping")
                return
            elif e.response.status_code == 404:
                self.logger.warning(f"Folder {folder_id} not found, skipping")
                return
            else:
                raise

    async def _get_download_url(
        self, client: httpx.AsyncClient, drive_id: str, item_id: str
    ) -> Optional[str]:
        """Get the download URL for a specific file item.

        Returns a Graph API content endpoint URL that can be used with the access token.
        """
        try:
            # Use the Graph API /content endpoint
            return f"{self.GRAPH_BASE_URL}/drives/{drive_id}/items/{item_id}/content"
        except Exception as e:
            self.logger.error(f"Failed to get download URL for item {item_id}: {e}")
            return None

    async def _list_all_drive_items_recursively(
        self,
        client: httpx.AsyncClient,
        drive_id: str,
        site_id: str,
    ) -> AsyncGenerator[Dict, None]:
        """Recursively list all items in a drive using BFS approach."""
        # Queue of folder IDs to process (None = root folder)
        folder_queue = deque([None])
        processed_folders = set()  # Avoid infinite loops

        while folder_queue:
            current_folder_id = folder_queue.popleft()

            # Skip if we've already processed this folder
            if current_folder_id in processed_folders:
                continue
            processed_folders.add(current_folder_id)

            try:
                async for item in self._list_drive_items(client, drive_id, current_folder_id):
                    # Add site_id to item for later reference
                    item["_site_id"] = site_id
                    item["_drive_id"] = drive_id
                    yield item

                    # If this item is a folder, add it to the queue for processing
                    if "folder" in item and len(folder_queue) < 100:  # Limit queue size
                        folder_queue.append(item["id"])
            except Exception as e:
                self.logger.error(f"Error processing folder {current_folder_id}: {e}")
                continue

    def _build_file_entity(
        self,
        item: Dict,
        drive_name: str,
        site_id: str,
        drive_id: str,
        site_breadcrumb: Breadcrumb,
        drive_breadcrumb: Breadcrumb,
        download_url: Optional[str] = None,
    ) -> Optional[SharePointDriveItemEntity]:
        """Build a SharePointDriveItemEntity from a Graph API DriveItem response.

        Returns None for items that should be skipped.
        """
        # Skip if this is a folder without downloadable content
        if "folder" in item:
            self.logger.debug(f"Skipping folder: {item.get('name', 'Untitled')}")
            return None

        # Skip if no download URL provided
        if not download_url:
            self.logger.warning(f"No download URL for file: {item.get('name', 'Untitled')}")
            return None

        # Extract file information
        file_info = item.get("file", {})
        parent_ref = item.get("parentReference", {})

        entity = SharePointDriveItemEntity(
            entity_id=item["id"],
            breadcrumbs=[site_breadcrumb, drive_breadcrumb],
            name=item.get("name"),
            description=item.get("description"),
            web_url=item.get("webUrl"),
            created_datetime=self._parse_datetime(item.get("createdDateTime")),
            last_modified_datetime=self._parse_datetime(item.get("lastModifiedDateTime")),
            size=item.get("size"),
            file=file_info,
            folder=item.get("folder"),
            parent_reference=parent_ref,
            created_by=item.get("createdBy"),
            last_modified_by=item.get("lastModifiedBy"),
            site_id=site_id,
            drive_id=drive_id,
            # Required FileEntity fields
            file_id=item["id"],
            download_url=download_url,
            mime_type=file_info.get("mimeType"),
            metadata={
                "source": "sharepoint",
                "site_id": site_id,
                "drive_id": drive_id,
            },
        )

        # Add additional properties for file processing
        if entity.airweave_system_metadata:
            entity.airweave_system_metadata.total_size = item.get("size", 0)

        return entity

    async def _generate_drive_item_entities(
        self,
        client: httpx.AsyncClient,
        drive_id: str,
        drive_name: str,
        site_id: str,
        site_name: str,
        site_breadcrumb: Breadcrumb,
    ) -> AsyncGenerator[ChunkEntity, None]:
        """Generate SharePointDriveItemEntity objects for files in the drive."""
        self.logger.info(f"Starting file generation for drive: {drive_name}")
        file_count = 0

        # Create drive breadcrumb
        drive_breadcrumb = Breadcrumb(entity_id=drive_id, name=drive_name[:50], type="drive")

        async for item in self._list_all_drive_items_recursively(client, drive_id, site_id):
            try:
                # Skip folders early
                if "folder" in item:
                    continue

                # Fetch the download URL
                download_url = await self._get_download_url(client, drive_id, item["id"])

                # Build the entity with the download URL
                file_entity = self._build_file_entity(
                    item,
                    drive_name,
                    site_id,
                    drive_id,
                    site_breadcrumb,
                    drive_breadcrumb,
                    download_url,
                )

                if not file_entity:
                    continue

                # Process the file entity (download and process content)
                if file_entity.download_url:
                    processed_entity = await self.process_file_entity(file_entity=file_entity)
                    if processed_entity:
                        yield processed_entity
                        file_count += 1
                        self.logger.info(f"Processed file {file_count}: {file_entity.name}")
                else:
                    self.logger.warning(f"No download URL available for {file_entity.name}")

            except Exception as e:
                self.logger.error(f"Failed to process item {item.get('name', 'unknown')}: {str(e)}")
                # Continue processing other items
                continue

        self.logger.info(f"Total files processed in drive {drive_name}: {file_count}")

    async def generate_entities(self) -> AsyncGenerator[ChunkEntity, None]:
        """Generate all SharePoint entities.

        Yields entities in the following order:
          - SharePointUserEntity for users in the organization
          - SharePointGroupEntity for groups in the organization
          - SharePointSiteEntity for the root site
          - SharePointDriveEntity for each drive in the site
          - SharePointDriveItemEntity for each file in each drive
        """
        self.logger.info("===== STARTING SHAREPOINT ENTITY GENERATION =====")
        entity_count = 0

        try:
            async with self.http_client() as client:
                self.logger.info("HTTP client created, starting entity generation")

                # 1) Generate user entities
                self.logger.info("Generating user entities...")
                async for user_entity in self._generate_user_entities(client):
                    entity_count += 1
                    self.logger.debug(
                        f"Yielding entity #{entity_count}: User - {user_entity.display_name}"
                    )
                    yield user_entity

                # 2) Generate group entities
                self.logger.info("Generating group entities...")
                async for group_entity in self._generate_group_entities(client):
                    entity_count += 1
                    self.logger.debug(
                        f"Yielding entity #{entity_count}: Group - {group_entity.display_name}"
                    )
                    yield group_entity

                # 3) Generate site entities (start with root site)
                self.logger.info("Generating site entities...")
                site_entity = None
                async for site in self._generate_site_entities(client):
                    entity_count += 1
                    self.logger.debug(
                        f"Yielding entity #{entity_count}: Site - {site.display_name}"
                    )
                    yield site
                    site_entity = site
                    break  # For now, just process root site

                if not site_entity:
                    self.logger.error("No site found")
                    return

                # Create site breadcrumb for drives and files
                site_id = site_entity.entity_id
                site_name = site_entity.display_name or "SharePoint"
                site_breadcrumb = Breadcrumb(entity_id=site_id, name=site_name[:50], type="site")

                # 4) Generate drive entities for the site
                self.logger.info(f"Generating drive entities for site: {site_name}")
                async for drive_entity in self._generate_drive_entities(client, site_id, site_name):
                    entity_count += 1
                    self.logger.debug(
                        f"Yielding entity #{entity_count}: Drive - {drive_entity.name}"
                    )
                    yield drive_entity

                    # 5) Generate file entities for each drive
                    drive_id = drive_entity.entity_id
                    drive_name = drive_entity.name or "Document Library"

                    self.logger.info(
                        f"Starting to process files from drive: {drive_id} ({drive_name})"
                    )

                    async for file_entity in self._generate_drive_item_entities(
                        client, drive_id, drive_name, site_id, site_name, site_breadcrumb
                    ):
                        entity_count += 1
                        entity_type = type(file_entity).__name__
                        self.logger.debug(
                            f"Yielding entity #{entity_count}: {entity_type} - "
                            f"{getattr(file_entity, 'name', 'unnamed')}"
                        )
                        yield file_entity

        except Exception as e:
            self.logger.error(f"Error in entity generation: {str(e)}", exc_info=True)
            raise
        finally:
            self.logger.info(
                f"===== SHAREPOINT ENTITY GENERATION COMPLETE: {entity_count} entities ====="
            )

    async def validate(self) -> bool:
        """Verify SharePoint OAuth2 token by pinging the sites endpoint."""
        return await self._validate_oauth2(
            ping_url=f"{self.GRAPH_BASE_URL}/sites/root",
            headers={"Accept": "application/json"},
            timeout=10.0,
        )
