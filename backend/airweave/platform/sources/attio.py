"""Attio source implementation.

Attio is a flexible CRM platform. We extract:
- Objects (Companies, People, Deals, etc.)
- Lists (Custom collections)
- Records (Individual entries in objects/lists)
- Notes (Attached to records)
- Comments (On notes)
"""

from typing import Any, AsyncGenerator, Dict, List, Optional

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from airweave.platform.configs.auth import AttioAuthConfig
from airweave.platform.decorators import source
from airweave.platform.entities._base import Breadcrumb, ChunkEntity
from airweave.platform.entities.attio import (
    AttioCommentEntity,
    AttioListEntity,
    AttioNoteEntity,
    AttioObjectEntity,
    AttioRecordEntity,
)
from airweave.platform.sources._base import BaseSource
from airweave.schemas.source_connection import AuthenticationMethod


@source(
    name="Attio",
    short_name="attio",
    auth_methods=[AuthenticationMethod.DIRECT, AuthenticationMethod.AUTH_PROVIDER],
    oauth_type=None,
    auth_config_class="AttioAuthConfig",
    config_class="AttioConfig",
    labels=["CRM"],
    supports_continuous=False,
)
class AttioSource(BaseSource):
    """Attio source connector integrates with the Attio API to extract CRM data.

    Synchronizes your Attio workspace including objects, lists, records, notes, and comments.
    """

    BASE_URL = "https://api.attio.com/v2"

    @classmethod
    async def create(
        cls, attio_auth_config: AttioAuthConfig, config: Optional[Dict[str, Any]] = None
    ) -> "AttioSource":
        """Create a new Attio source instance.

        Args:
            attio_auth_config: Authentication configuration with API key
            config: Optional configuration parameters

        Returns:
            Configured AttioSource instance
        """
        instance = cls()
        instance.api_key = attio_auth_config.api_key
        return instance

    @retry(
        stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10), reraise=True
    )
    async def _get_with_auth(
        self, client: httpx.AsyncClient, url: str, params: Optional[Dict[str, Any]] = None
    ) -> Dict:
        """Make authenticated GET request to Attio API.

        Args:
            client: HTTP client
            url: API endpoint URL
            params: Optional query parameters

        Returns:
            JSON response data

        Raises:
            httpx.HTTPStatusError: On HTTP errors
        """
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Accept": "application/json",
        }

        try:
            response = await client.get(url, headers=headers, params=params, timeout=20.0)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            self.logger.error(f"HTTP error from Attio API: {e.response.status_code} for {url}")
            raise
        except Exception as e:
            self.logger.error(f"Unexpected error accessing Attio API: {url}, {str(e)}")
            raise

    @retry(
        stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10), reraise=True
    )
    async def _post_with_auth(
        self, client: httpx.AsyncClient, url: str, json_data: Optional[Dict[str, Any]] = None
    ) -> Dict:
        """Make authenticated POST request to Attio API.

        Args:
            client: HTTP client
            url: API endpoint URL
            json_data: Optional JSON body

        Returns:
            JSON response data

        Raises:
            httpx.HTTPStatusError: On HTTP errors
        """
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

        try:
            response = await client.post(url, headers=headers, json=json_data or {}, timeout=20.0)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            self.logger.error(f"HTTP error from Attio API: {e.response.status_code} for {url}")
            raise
        except Exception as e:
            self.logger.error(f"Unexpected error accessing Attio API: {url}, {str(e)}")
            raise

    async def _get_all_pages(
        self, client: httpx.AsyncClient, url: str, data_key: str = "data"
    ) -> List[Dict]:
        """Fetch all pages from a paginated Attio endpoint (GET).

        Args:
            client: HTTP client
            url: Base API endpoint URL
            data_key: Key in response containing the data array

        Returns:
            List of all items across all pages
        """
        all_items = []
        offset = 0
        limit = 100

        while True:
            params = {"offset": offset, "limit": limit}
            response = await self._get_with_auth(client, url, params)

            items = response.get(data_key, [])
            if not items:
                break

            all_items.extend(items)

            # Check if we've reached the end
            if len(items) < limit:
                break

            offset += limit

        return all_items

    async def _query_all_pages(
        self, client: httpx.AsyncClient, url: str, data_key: str = "data"
    ) -> List[Dict]:
        """Fetch all pages from a paginated Attio endpoint (POST query).

        Args:
            client: HTTP client
            url: Query API endpoint URL
            data_key: Key in response containing the data array

        Returns:
            List of all items across all pages
        """
        all_items = []
        offset = 0
        limit = 100

        while True:
            query_body = {"offset": offset, "limit": limit}
            response = await self._post_with_auth(client, url, query_body)

            items = response.get(data_key, [])
            if not items:
                break

            all_items.extend(items)

            # Check if we've reached the end
            if len(items) < limit:
                break

            offset += limit

        return all_items

    async def _query_all_pages_optional(
        self, client: httpx.AsyncClient, url: str, data_key: str = "data"
    ) -> List[Dict]:
        """Fetch all pages from optional nested resources (notes/comments).

        Returns empty list on 404 without retrying.

        Args:
            client: HTTP client
            url: Query API endpoint URL
            data_key: Key in response containing the data array

        Returns:
            List of all items across all pages, or empty list if not found
        """
        all_items = []
        offset = 0
        limit = 100

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

        while True:
            query_body = {"offset": offset, "limit": limit}

            try:
                response = await client.post(url, headers=headers, json=query_body, timeout=20.0)
                response.raise_for_status()
                data = response.json()
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 404:
                    # No notes/comments for this resource, return empty
                    return []
                self.logger.error(f"HTTP error from Attio API: {e.response.status_code} for {url}")
                raise
            except Exception as e:
                self.logger.error(f"Unexpected error accessing Attio API: {url}, {str(e)}")
                raise

            items = data.get(data_key, [])
            if not items:
                break

            all_items.extend(items)

            # Check if we've reached the end
            if len(items) < limit:
                break

            offset += limit

        return all_items

    async def _generate_object_entities(
        self, client: httpx.AsyncClient
    ) -> AsyncGenerator[ChunkEntity, None]:
        """Generate Attio Object entities (Companies, People, Deals, etc.).

        Yields:
            AttioObjectEntity instances
        """
        self.logger.info("Fetching Attio objects...")
        url = f"{self.BASE_URL}/objects"
        objects = await self._get_all_pages(client, url, data_key="data")

        for obj in objects:
            object_id = obj.get("id", {}).get("object_id")
            if not object_id:
                continue

            self.logger.debug(f"Generating object entity: {object_id}")

            yield AttioObjectEntity(
                entity_id=object_id,
                breadcrumbs=[],
                object_id=object_id,
                singular_noun=obj.get("singular_noun", ""),
                plural_noun=obj.get("plural_noun", ""),
                api_slug=obj.get("api_slug", ""),
                icon=obj.get("icon"),
                created_at=obj.get("created_at"),
            )

    async def _generate_list_entities(
        self, client: httpx.AsyncClient
    ) -> AsyncGenerator[ChunkEntity, None]:
        """Generate Attio List entities.

        Yields:
            AttioListEntity instances
        """
        self.logger.info("Fetching Attio lists...")
        url = f"{self.BASE_URL}/lists"
        lists = await self._get_all_pages(client, url, data_key="data")

        for lst in lists:
            list_id = lst.get("id", {}).get("list_id")
            if not list_id:
                continue

            self.logger.debug(f"Generating list entity: {list_id}")

            # Handle parent_object - API returns list, but we need string
            parent_object = lst.get("parent_object")
            if isinstance(parent_object, list):
                parent_object = ", ".join(parent_object) if parent_object else None

            yield AttioListEntity(
                entity_id=list_id,
                breadcrumbs=[],
                list_id=list_id,
                name=lst.get("name", ""),
                workspace_id=lst.get("workspace_id", ""),
                parent_object=parent_object,
                created_at=lst.get("created_at"),
            )

    async def _generate_record_entities_for_object(
        self,
        client: httpx.AsyncClient,
        object_slug: str,
        object_name: str,
        object_breadcrumb: Breadcrumb,
    ) -> AsyncGenerator[ChunkEntity, None]:
        """Generate record entities for a specific object.

        Args:
            client: HTTP client
            object_slug: API slug of the object (e.g., 'companies', 'people')
            object_name: Name of the object
            object_breadcrumb: Breadcrumb for the parent object

        Yields:
            AttioRecordEntity instances
        """
        self.logger.debug(f"Fetching records for object: {object_slug}")
        url = f"{self.BASE_URL}/objects/{object_slug}/records/query"

        try:
            records = await self._query_all_pages(client, url, data_key="data")
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                self.logger.warning(f"Object {object_slug} not found or not accessible, skipping")
                return
            raise

        for record in records:
            record_id = record.get("id", {}).get("record_id")
            if not record_id:
                continue

            # Extract attributes from the values field
            values = record.get("values", {})

            # Try to extract common fields
            name = None
            description = None
            email_addresses = []
            phone_numbers = []
            domains = []
            categories = []
            attributes = {}

            for attr_key, attr_values in values.items():
                if not attr_values:
                    continue

                # Extract first value for common fields
                first_val = attr_values[0] if isinstance(attr_values, list) else attr_values

                # Detect field types by name
                if "name" in attr_key.lower() or "title" in attr_key.lower():
                    if isinstance(first_val, dict):
                        name = first_val.get("value") or first_val.get("text")
                    else:
                        name = str(first_val)

                elif "description" in attr_key.lower() or "notes" in attr_key.lower():
                    if isinstance(first_val, dict):
                        description = first_val.get("value") or first_val.get("text")
                    else:
                        description = str(first_val)

                elif "email" in attr_key.lower():
                    # Keep as dicts, filter out None/empty
                    email_addresses = [
                        v for v in attr_values if v is not None and isinstance(v, dict)
                    ]

                elif "phone" in attr_key.lower():
                    # Keep as dicts, filter out None/empty
                    phone_numbers = [
                        v for v in attr_values if v is not None and isinstance(v, dict)
                    ]

                elif "domain" in attr_key.lower():
                    # Extract strings from dicts or use strings directly
                    domains = [
                        v.get("domain") if isinstance(v, dict) else v
                        for v in attr_values
                        if v is not None
                        and (isinstance(v, dict) and v.get("domain") or isinstance(v, str))
                    ]

                elif "category" in attr_key.lower() or "tag" in attr_key.lower():
                    # Extract strings from dicts or use strings directly
                    categories = [
                        v.get("value") if isinstance(v, dict) else v
                        for v in attr_values
                        if v is not None
                        and (isinstance(v, dict) and v.get("value") or isinstance(v, str))
                    ]

                # Store all attributes for searchability
                attributes[attr_key] = attr_values

            yield AttioRecordEntity(
                entity_id=record_id,
                breadcrumbs=[object_breadcrumb],
                record_id=record_id,
                object_id=object_slug,
                parent_object_name=object_name,
                name=name,
                description=description,
                email_addresses=email_addresses,
                phone_numbers=phone_numbers,
                domains=domains,
                categories=categories,
                attributes=attributes,
                created_at=record.get("created_at"),
                updated_at=record.get("updated_at"),
            )

    async def _generate_record_entities_for_list(
        self,
        client: httpx.AsyncClient,
        list_id: str,
        list_name: str,
        list_breadcrumb: Breadcrumb,
    ) -> AsyncGenerator[ChunkEntity, None]:
        """Generate record entities for a specific list.

        Args:
            client: HTTP client
            list_id: ID of the list
            list_name: Name of the list
            list_breadcrumb: Breadcrumb for the parent list

        Yields:
            AttioRecordEntity instances
        """
        self.logger.debug(f"Fetching records for list: {list_id}")
        url = f"{self.BASE_URL}/lists/{list_id}/records/query"

        try:
            records = await self._query_all_pages(client, url, data_key="data")
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                self.logger.warning(f"List {list_id} not found or not accessible, skipping")
                return
            raise

        for record in records:
            record_id = record.get("id", {}).get("record_id")
            if not record_id:
                continue

            # Extract attributes from the values field
            values = record.get("values", {})

            # Try to extract common fields (same logic as objects)
            name = None
            description = None
            attributes = {}

            for attr_key, attr_values in values.items():
                if not attr_values:
                    continue

                first_val = attr_values[0] if isinstance(attr_values, list) else attr_values

                if "name" in attr_key.lower() or "title" in attr_key.lower():
                    if isinstance(first_val, dict):
                        name = first_val.get("value") or first_val.get("text")
                    else:
                        name = str(first_val)

                elif "description" in attr_key.lower():
                    if isinstance(first_val, dict):
                        description = first_val.get("value") or first_val.get("text")
                    else:
                        description = str(first_val)

                attributes[attr_key] = attr_values

            yield AttioRecordEntity(
                entity_id=record_id,
                breadcrumbs=[list_breadcrumb],
                record_id=record_id,
                list_id=list_id,
                parent_object_name=list_name,
                name=name,
                description=description,
                attributes=attributes,
                created_at=record.get("created_at"),
                updated_at=record.get("updated_at"),
            )

    async def _generate_note_entities_for_record(
        self,
        client: httpx.AsyncClient,
        parent_object_or_list_id: str,
        record_id: str,
        record_breadcrumbs: List[Breadcrumb],
    ) -> AsyncGenerator[ChunkEntity, None]:
        """Generate note entities for a specific record.

        Args:
            client: HTTP client
            parent_object_or_list_id: ID of parent object or list
            record_id: ID of the record
            record_breadcrumbs: Breadcrumbs leading to this record

        Yields:
            AttioNoteEntity instances
        """
        self.logger.debug(f"Fetching notes for record: {record_id}")

        # Try object endpoint first, then list endpoint (using query POST)
        urls_to_try = [
            f"{self.BASE_URL}/objects/{parent_object_or_list_id}/records/{record_id}/notes/query",
            f"{self.BASE_URL}/lists/{parent_object_or_list_id}/records/{record_id}/notes/query",
        ]

        notes = []
        for url in urls_to_try:
            notes = await self._query_all_pages_optional(client, url, data_key="data")
            if notes:  # Found notes, don't try other URLs
                self.logger.debug(f"Found {len(notes)} notes for record {record_id}")
                break

        if not notes:
            self.logger.debug(f"No notes found for record {record_id}")

        for note in notes:
            note_id = note.get("id", {}).get("note_id")
            if not note_id:
                continue

            yield AttioNoteEntity(
                entity_id=note_id,
                breadcrumbs=record_breadcrumbs,
                note_id=note_id,
                parent_record_id=record_id,
                parent_object=parent_object_or_list_id,
                title=note.get("title"),
                content=note.get("content", ""),
                format=note.get("format"),
                author=note.get("author"),
                created_at=note.get("created_at"),
                updated_at=note.get("updated_at"),
            )

    async def _generate_comment_entities_for_note(
        self,
        client: httpx.AsyncClient,
        parent_object_or_list_id: str,
        record_id: str,
        note_id: str,
        note_breadcrumbs: List[Breadcrumb],
    ) -> AsyncGenerator[ChunkEntity, None]:
        """Generate comment entities for a specific note.

        Args:
            client: HTTP client
            parent_object_or_list_id: ID of parent object or list
            record_id: ID of the record
            note_id: ID of the note
            note_breadcrumbs: Breadcrumbs leading to this note

        Yields:
            AttioCommentEntity instances
        """
        self.logger.debug(f"Fetching comments for note: {note_id}")

        # Try object endpoint first, then list endpoint
        urls_to_try = [
            f"{self.BASE_URL}/objects/{parent_object_or_list_id}/records/{record_id}/notes/{note_id}/comments/query",
            f"{self.BASE_URL}/lists/{parent_object_or_list_id}/records/{record_id}/notes/{note_id}/comments/query",
        ]

        comments = []
        for url in urls_to_try:
            comments = await self._query_all_pages_optional(client, url, data_key="data")
            if comments:  # Found comments, don't try other URLs
                self.logger.debug(f"Found {len(comments)} comments for note {note_id}")
                break

        if not comments:
            self.logger.debug(f"No comments found for note {note_id}")

        for comment in comments:
            comment_id = comment.get("id", {}).get("comment_id")
            if not comment_id:
                continue

            yield AttioCommentEntity(
                entity_id=comment_id,
                breadcrumbs=note_breadcrumbs,
                comment_id=comment_id,
                parent_note_id=note_id,
                parent_record_id=record_id,
                text=comment.get("text", ""),
                author=comment.get("author", {}),
                created_at=comment.get("created_at"),
                is_resolved=comment.get("is_resolved", False),
            )

    async def generate_entities(self) -> AsyncGenerator[ChunkEntity, None]:
        """Generate all entities from Attio.

        This is the main entry point called by the sync engine.

        Yields:
            All Attio entities (objects, lists, records, notes)
        """
        self.logger.info("Starting Attio sync...")

        async with self.http_client() as client:
            # Generate objects first
            object_map = {}  # Store objects for later use
            async for obj in self._generate_object_entities(client):
                yield obj
                object_map[obj.entity_id] = obj

            # Generate lists
            list_map = {}  # Store lists for later use
            async for lst in self._generate_list_entities(client):
                yield lst
                list_map[lst.entity_id] = lst

            # Generate records for each object
            for object_id, obj in object_map.items():
                object_breadcrumb = Breadcrumb(
                    entity_id=object_id, name=obj.singular_noun, type="object"
                )

                # Use api_slug for the API endpoint, not object_id
                async for record in self._generate_record_entities_for_object(
                    client, obj.api_slug, obj.singular_noun, object_breadcrumb
                ):
                    yield record

                    # Generate notes for this record
                    record_breadcrumb = Breadcrumb(
                        entity_id=record.record_id,
                        name=record.name or record.record_id,
                        type="record",
                    )
                    record_breadcrumbs = [object_breadcrumb, record_breadcrumb]

                    async for note in self._generate_note_entities_for_record(
                        client, obj.api_slug, record.record_id, record_breadcrumbs
                    ):
                        yield note

                        # Generate comments for this note
                        note_breadcrumb = Breadcrumb(
                            entity_id=note.note_id,
                            name=note.title or note.note_id,
                            type="note",
                        )
                        note_breadcrumbs = record_breadcrumbs + [note_breadcrumb]

                        async for comment in self._generate_comment_entities_for_note(
                            client, obj.api_slug, record.record_id, note.note_id, note_breadcrumbs
                        ):
                            yield comment

            # Generate records for each list
            for list_id, lst in list_map.items():
                list_breadcrumb = Breadcrumb(entity_id=list_id, name=lst.name, type="list")

                async for record in self._generate_record_entities_for_list(
                    client, list_id, lst.name, list_breadcrumb
                ):
                    yield record

                    # Generate notes for this record
                    record_breadcrumb = Breadcrumb(
                        entity_id=record.record_id,
                        name=record.name or record.record_id,
                        type="record",
                    )
                    record_breadcrumbs = [list_breadcrumb, record_breadcrumb]

                    async for note in self._generate_note_entities_for_record(
                        client, list_id, record.record_id, record_breadcrumbs
                    ):
                        yield note

                        # Generate comments for this note
                        note_breadcrumb = Breadcrumb(
                            entity_id=note.note_id,
                            name=note.title or note.note_id,
                            type="note",
                        )
                        note_breadcrumbs = record_breadcrumbs + [note_breadcrumb]

                        async for comment in self._generate_comment_entities_for_note(
                            client, list_id, record.record_id, note.note_id, note_breadcrumbs
                        ):
                            yield comment

        self.logger.info("Attio sync completed successfully")

    async def validate(self) -> bool:
        """Verify credentials by pinging the Attio API.

        Returns:
            True if credentials are valid, False otherwise
        """
        try:
            async with self.http_client() as client:
                # Test by fetching objects (should work with any valid API key)
                url = f"{self.BASE_URL}/objects"
                await self._get_with_auth(client, url, params={"limit": 1})
                return True
        except Exception as e:
            self.logger.error(f"Attio credential validation failed: {str(e)}")
            return False
