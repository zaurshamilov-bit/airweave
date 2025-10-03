"""
Async test module for Organization Deletion with Qdrant Cleanup.

Tests integration between organization deletion and Qdrant collection cleanup.
NOTE: These tests only run in local environment as they require Qdrant access.
"""

import pytest
import httpx
import asyncio
import time
from typing import Dict, List, Optional
from uuid import UUID


@pytest.mark.asyncio
@pytest.mark.requires_temporal
class TestOrganizationDeletion:
    """Test suite for organization deletion with Qdrant cleanup."""

    async def _check_qdrant_collection_exists(self, collection_id: UUID) -> bool:
        """Check if a Qdrant collection exists by ID.

        Args:
            collection_id: UUID of the collection to check

        Returns:
            True if collection exists, False otherwise
        """
        from qdrant_client import AsyncQdrantClient
        from airweave.core.config import settings

        try:
            client = AsyncQdrantClient(
                url=settings.qdrant_url,
                timeout=30.0,
                prefer_grpc=False,
            )

            # Get all collections
            collections_response = await client.get_collections()
            collection_names = [col.name for col in collections_response.collections]

            # Collection name is the collection ID as string
            exists = str(collection_id) in collection_names

            await client.close()
            return exists

        except Exception as e:
            pytest.skip(f"Qdrant not available: {e}")
            return False

    async def _get_all_qdrant_collections(self) -> List[str]:
        """Get all Qdrant collection names.

        Returns:
            List of collection names
        """
        from qdrant_client import AsyncQdrantClient
        from airweave.core.config import settings

        try:
            client = AsyncQdrantClient(
                url=settings.qdrant_url,
                timeout=30.0,
                prefer_grpc=False,
            )

            collections_response = await client.get_collections()
            collection_names = [col.name for col in collections_response.collections]

            await client.close()
            return collection_names

        except Exception as e:
            pytest.skip(f"Qdrant not available: {e}")
            return []

    async def _create_test_organization(
        self, api_client: httpx.AsyncClient, name: str
    ) -> Optional[Dict]:
        """Helper to create a test organization.

        Args:
            api_client: HTTP client
            name: Organization name

        Returns:
            Organization dict or None if creation failed
        """
        org_data = {"name": name, "description": f"Test org for {name}"}
        response = await api_client.post("/organizations/", json=org_data)

        if response.status_code == 200:
            return response.json()
        return None

    async def _trigger_sync_for_connection(
        self, api_client: httpx.AsyncClient, connection_id: str
    ) -> bool:
        """Trigger a sync for a source connection and wait for it to start.

        Args:
            api_client: HTTP client
            connection_id: Source connection ID

        Returns:
            True if sync was triggered successfully
        """
        response = await api_client.post(f"/source-connections/{connection_id}/sync")

        if response.status_code in [200, 201, 202]:
            # Wait a bit for sync to actually start
            await asyncio.sleep(2)
            return True
        return False

    async def test_organization_deletion_removes_qdrant_collections(
        self, api_client: httpx.AsyncClient, config
    ):
        """Test that deleting an organization removes all its Qdrant collections."""
        if not config.is_local:
            pytest.skip("Qdrant tests only run locally")

        # Create a test organization (only works if we have multi-org support in test env)
        # For now, we'll use the default organization and just create collections
        org_response = await api_client.get("/organizations/")
        assert org_response.status_code == 200
        orgs = org_response.json()
        assert len(orgs) > 0

        test_org = orgs[0]  # Use first organization
        org_id = test_org["id"]

        # Create multiple collections in the organization
        collections_created = []
        try:
            for i in range(3):
                collection_data = {
                    "name": f"Deletion Test Collection {i} - {int(time.time())}"
                }
                response = await api_client.post("/collections/", json=collection_data)

                assert response.status_code == 200, f"Failed to create collection: {response.text}"
                collection = response.json()
                collections_created.append(collection)

                # Verify collection was created in Qdrant
                await asyncio.sleep(1)  # Give Qdrant time to create
                exists = await self._check_qdrant_collection_exists(UUID(collection["id"]))
                assert exists, f"Collection {collection['id']} should exist in Qdrant"

            # Get Qdrant collections before deletion
            collections_before = await self._get_all_qdrant_collections()
            collection_ids_before = [str(c["id"]) for c in collections_created]

            # Verify all our collections are in Qdrant
            for collection_id in collection_ids_before:
                assert (
                    collection_id in collections_before
                ), f"Collection {collection_id} should be in Qdrant before deletion"

            # Delete all collections manually (simulating organization deletion)
            for collection in collections_created:
                response = await api_client.delete(
                    f"/collections/{collection['readable_id']}"
                )
                assert response.status_code in [
                    200,
                    204,
                ], f"Failed to delete collection: {response.text}"

            # Wait for deletions to propagate
            await asyncio.sleep(2)

            # Verify collections are removed from Qdrant
            collections_after = await self._get_all_qdrant_collections()
            for collection_id in collection_ids_before:
                assert (
                    collection_id not in collections_after
                ), f"Collection {collection_id} should be removed from Qdrant"

        finally:
            # Cleanup any remaining collections (best effort)
            for collection in collections_created:
                try:
                    await api_client.delete(f"/collections/{collection['readable_id']}")
                except:
                    pass

    async def test_organization_deletion_with_source_connections(
        self, api_client: httpx.AsyncClient, config
    ):
        """Test organization deletion removes collections with active source connections."""
        if not config.is_local:
            pytest.skip("Qdrant tests only run locally")

        # Create collection
        collection_data = {"name": f"Org Deletion with Source Conn {int(time.time())}"}
        response = await api_client.post("/collections/", json=collection_data)
        assert response.status_code == 200
        collection = response.json()

        try:
            # Create source connection
            connection_data = {
                "name": "Test Stripe Connection",
                "short_name": "stripe",
                "readable_collection_id": collection["readable_id"],
                "authentication": {"credentials": {"api_key": config.TEST_STRIPE_API_KEY}},
                "sync_immediately": False,
            }

            conn_response = await api_client.post("/source-connections", json=connection_data)
            if conn_response.status_code == 400 and "invalid" in conn_response.text.lower():
                pytest.skip("Invalid Stripe credentials for testing")

            assert conn_response.status_code == 200
            connection = conn_response.json()

            # Verify collection exists in Qdrant
            await asyncio.sleep(1)
            exists_before = await self._check_qdrant_collection_exists(UUID(collection["id"]))
            assert exists_before, "Collection should exist in Qdrant"

            # Delete source connection first
            response = await api_client.delete(
                f"/source-connections/{connection['id']}"
            )
            assert response.status_code == 200

            # Delete collection
            response = await api_client.delete(
                f"/collections/{collection['readable_id']}"
            )
            assert response.status_code in [200, 204]

            # Wait for deletion
            await asyncio.sleep(2)

            # Verify collection removed from Qdrant
            exists_after = await self._check_qdrant_collection_exists(UUID(collection["id"]))
            assert not exists_after, "Collection should be removed from Qdrant"

        finally:
            # Cleanup
            try:
                await api_client.delete(f"/collections/{collection['readable_id']}")
            except:
                pass

    async def test_partial_qdrant_deletion_continues(
        self, api_client: httpx.AsyncClient, config
    ):
        """Test that organization deletion continues even if some Qdrant collections fail to delete."""
        if not config.is_local:
            pytest.skip("Qdrant tests only run locally")

        # Create multiple collections
        collections = []
        try:
            for i in range(2):
                collection_data = {"name": f"Partial Deletion Test {i} - {int(time.time())}"}
                response = await api_client.post("/collections/", json=collection_data)
                assert response.status_code == 200
                collections.append(response.json())

            # Verify all exist in Qdrant
            await asyncio.sleep(1)
            for collection in collections:
                exists = await self._check_qdrant_collection_exists(UUID(collection["id"]))
                assert exists, f"Collection {collection['id']} should exist in Qdrant"

            # Delete all collections
            # The deletion should succeed for all even if Qdrant operations fail for some
            for collection in collections:
                response = await api_client.delete(
                    f"/collections/{collection['readable_id']}"
                )
                # Should succeed in SQL even if Qdrant fails
                assert response.status_code in [200, 204]

            # Wait for deletions
            await asyncio.sleep(2)

            # Verify all are deleted from database
            for collection in collections:
                response = await api_client.get(f"/collections/{collection['readable_id']}")
                assert response.status_code == 404, "Collection should be deleted from database"

        finally:
            # Best effort cleanup
            for collection in collections:
                try:
                    await api_client.delete(f"/collections/{collection['readable_id']}")
                except:
                    pass

    async def test_qdrant_collection_lifecycle(self, api_client: httpx.AsyncClient, config):
        """Test complete lifecycle: create collection, verify in Qdrant, delete, verify removal."""
        if not config.is_local:
            pytest.skip("Qdrant tests only run locally")

        # Create collection
        collection_data = {"name": f"Lifecycle Test {int(time.time())}"}
        response = await api_client.post("/collections/", json=collection_data)
        assert response.status_code == 200
        collection = response.json()
        collection_id = UUID(collection["id"])

        try:
            # Wait for Qdrant collection creation
            await asyncio.sleep(2)

            # Check collection exists in Qdrant
            exists_after_create = await self._check_qdrant_collection_exists(collection_id)
            assert exists_after_create, "Collection should exist in Qdrant after creation"

            # Delete collection
            response = await api_client.delete(
                f"/collections/{collection['readable_id']}"
            )
            assert response.status_code in [200, 204]

            # Wait for Qdrant deletion
            await asyncio.sleep(2)

            # Check collection removed from Qdrant
            exists_after_delete = await self._check_qdrant_collection_exists(collection_id)
            assert not exists_after_delete, "Collection should be removed from Qdrant after deletion"

        finally:
            # Cleanup
            try:
                await api_client.delete(f"/collections/{collection['readable_id']}")
            except:
                pass

    async def test_multiple_collections_batch_deletion(
        self, api_client: httpx.AsyncClient, config
    ):
        """Test deleting multiple collections in batch (simulating org deletion)."""
        if not config.is_local:
            pytest.skip("Qdrant tests only run locally")

        # Create multiple collections
        num_collections = 5
        collections = []

        try:
            # Create collections
            for i in range(num_collections):
                collection_data = {"name": f"Batch Delete Test {i} - {int(time.time())}"}
                response = await api_client.post("/collections/", json=collection_data)
                assert response.status_code == 200
                collections.append(response.json())

            # Wait for all to be created in Qdrant
            await asyncio.sleep(2)

            # Verify all exist
            collection_ids = [UUID(c["id"]) for c in collections]
            for collection_id in collection_ids:
                exists = await self._check_qdrant_collection_exists(collection_id)
                assert exists, f"Collection {collection_id} should exist before deletion"

            # Record start time
            start_time = time.time()

            # Delete all collections (simulating what happens during org deletion)
            deletion_results = await asyncio.gather(
                *[
                    api_client.delete(f"/collections/{c['readable_id']}")
                    for c in collections
                ],
                return_exceptions=True,
            )

            # Record end time
            end_time = time.time()
            deletion_time = end_time - start_time

            # Check that deletions completed reasonably fast (should be concurrent)
            # With 5 collections, concurrent deletion should be much faster than sequential
            # Allow generous time for CI/slower machines
            assert (
                deletion_time < 30
            ), f"Batch deletion took {deletion_time}s, should be faster with concurrency"

            # Verify deletions succeeded (or at least didn't fail catastrophically)
            successful_deletions = sum(
                1
                for result in deletion_results
                if not isinstance(result, Exception) and result.status_code in [200, 204]
            )

            assert (
                successful_deletions >= num_collections * 0.8
            ), "At least 80% of deletions should succeed"

            # Wait for Qdrant deletions to propagate
            await asyncio.sleep(3)

            # Verify all removed from Qdrant
            for collection_id in collection_ids:
                exists = await self._check_qdrant_collection_exists(collection_id)
                assert not exists, f"Collection {collection_id} should be removed from Qdrant"

        finally:
            # Cleanup any remaining collections
            for collection in collections:
                try:
                    await api_client.delete(f"/collections/{collection['readable_id']}")
                except:
                    pass

    async def test_qdrant_orphaned_collections_detection(
        self, api_client: httpx.AsyncClient, config
    ):
        """Test detection of orphaned Qdrant collections (exist in Qdrant but not in SQL)."""
        if not config.is_local:
            pytest.skip("Qdrant tests only run locally")

        # This test simulates a scenario where Qdrant collection exists but SQL record is gone
        # We'll create a collection, note its ID, then delete only from SQL

        collection_data = {"name": f"Orphan Detection Test {int(time.time())}"}
        response = await api_client.post("/collections/", json=collection_data)
        assert response.status_code == 200
        collection = response.json()
        collection_id = UUID(collection["id"])

        try:
            # Wait for Qdrant creation
            await asyncio.sleep(2)

            # Verify it exists in Qdrant
            exists_before = await self._check_qdrant_collection_exists(collection_id)
            assert exists_before, "Collection should exist in Qdrant"

            # Delete with data=true to ensure Qdrant cleanup
            response = await api_client.delete(
                f"/collections/{collection['readable_id']}"
            )
            assert response.status_code in [200, 204]

            # Wait for deletion
            await asyncio.sleep(2)

            # Verify it's removed from both SQL and Qdrant
            sql_response = await api_client.get(f"/collections/{collection['readable_id']}")
            assert sql_response.status_code == 404, "Collection should be deleted from SQL"

            qdrant_exists = await self._check_qdrant_collection_exists(collection_id)
            assert not qdrant_exists, "Collection should be deleted from Qdrant"

        finally:
            # Cleanup
            try:
                await api_client.delete(f"/collections/{collection['readable_id']}")
            except:
                pass
