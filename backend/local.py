"""Local script for testing various source connectors (e.g. Asana, Notion) and verifying results."""

import asyncio
import uuid

import weaviate.classes as wvc
from weaviate.collections import Collection

from app import schemas
from app.platform.destinations.weaviate import WeaviateDestination
from app.platform.embedding_models.local_text2vec import LocalText2Vec
from app.platform.sources._base import BaseSource
from app.platform.sources.asana import AsanaSource
from app.platform.sources.notion import NotionSource
from app.vector_db.weaviate_service import WeaviateService


async def process_source_chunks(
    source: BaseSource, weaviate_dest: WeaviateDestination, buffer_size: int = 50
):
    """Helper to fetch chunks from a given source connector and optionally insert them into Weaviate in bulk.
    """
    chunks_buffer = []
    async for chunk in source.generate_chunks():
        chunks_buffer.append(chunk)

        # When buffer is full, bulk insert
        if len(chunks_buffer) >= buffer_size:
            await weaviate_dest.bulk_insert(chunks_buffer)
            print(f"Inserted {len(chunks_buffer)} chunks from {source.__class__.__name__}")
            chunks_buffer.clear()

    # If any remain after the loop, insert them as well
    if chunks_buffer:
        await weaviate_dest.bulk_insert(chunks_buffer)
        print(f"Inserted final {len(chunks_buffer)} chunks from {source.__class__.__name__}")

    return chunks_buffer


async def verify_chunks_in_weaviate(sync_id: uuid.UUID):
    """Check total chunk count in the corresponding Weaviate collection,
    and print some sample documents.
    """
    print("\n=== Verifying Sync Results ===")
    async with WeaviateService() as service:
        sanitized_sync_id = str(sync_id).replace("-", "_")
        collection: Collection = await service.get_weaviate_collection(
            f"Chunks_{sanitized_sync_id}"
        )

        # Count how many chunk objects are in this collection
        count = (await collection.aggregate.over_all(total_count=True)).total_count
        print(f"\nTotal documents in 'Chunks_{sanitized_sync_id}' collection: {count}")

        # Fetch some sample documents (no filter)
        results = await collection.query.fetch_objects(limit=5, include_vector=False)
        print("\nSample objects:")
        for obj in results.objects:
            print(f"\nName: {obj.properties.get('name')}")
            print(f"Source: {obj.properties.get('source_name')}")
            print(f"Created: {obj.metadata.creation_time}")
            print(f"Breadcrumbs: {obj.properties.get('breadcrumbs')}")


async def verify_asana_tasks_in_weaviate(sync_id: uuid.UUID):
    """Example of a more connector-specific verification for Asana:
    filtering tasks using Weaviate's property filter and printing details.
    """
    print("\n=== Verifying Asana Tasks in Weaviate ===")
    async with WeaviateService() as service:
        sanitized_sync_id = str(sync_id).replace("-", "_")
        collection: Collection = await service.get_weaviate_collection(
            f"Chunks_{sanitized_sync_id}"
        )

        # Query tasks with filters (e.g. resource_subtype == default_task)
        tasks = await collection.query.fetch_objects(
            limit=5,
            filters=wvc.query.Filter.by_property("resource_subtype").equal("default_task"),
            return_metadata=wvc.query.MetadataQuery(creation_time=True),
        )

        print("\nSample tasks:")
        for task in tasks.objects:
            print(f"Task: {task.properties.get('name')}")
            print(f"Created: {task.metadata.creation_time}")
            print(f"Completed: {task.properties.get('completed')}")
            print(f"Due at: {task.properties.get('due_at')}")
            print("-----")


async def main():
    """Entrypoint to test multiple connectors (Asana, Notion, Dropbox, etc.) end-to-end."""
    # Create a test user and a unique sync ID for this sync run
    user = schemas.User(
        id=uuid.uuid4(),
        email="test@test.com",
        full_name="Test User",
        organization_id=uuid.uuid4(),
    )
    sync_id = uuid.uuid4()

    # Initialize an embedding model
    embedding_model = LocalText2Vec()

    # Create a Weaviate destination for storing chunks
    weaviate_dest = await WeaviateDestination.create(sync_id, embedding_model)

    # -------------------------------------------------------------------------
    # Test Asana Source Connector
    # -------------------------------------------------------------------------
    print("=== Testing Asana Connector ===")
    access_token = "..."
    asana_source = await AsanaSource.create(access_token)
    asana_chunks = await process_source_chunks(asana_source, weaviate_dest, buffer_size=50)
    print(f"Asana source generated {len(asana_chunks)} chunks total.\n")

    # -------------------------------------------------------------------------
    # Test Notion Source Connector
    # -------------------------------------------------------------------------
    print("=== Testing Notion Connector ===")
    notion_source = await NotionSource.create(user, sync_id)
    notion_chunks = await process_source_chunks(notion_source, weaviate_dest, buffer_size=50)
    print(f"Notion source generated {len(notion_chunks)} chunks total.\n")

    # -------------------------------------------------------------------------
    # Test Dropbox Source Connector
    # -------------------------------------------------------------------------
    print("=== Testing Dropbox Connector ===")
    from app.platform.sources.dropbox import DropboxSource

    dropbox_source = await DropboxSource.create(user, sync_id)
    dropbox_chunks = await process_source_chunks(dropbox_source, weaviate_dest, buffer_size=50)
    print(f"Dropbox source generated {len(dropbox_chunks)} chunks total.\n")

    # Optionally, verify chunks inserted
    await verify_chunks_in_weaviate(sync_id)

    # Optionally, add more connector-specific verifications here (like verify_asana_tasks_in_weaviate)
    # await verify_dropbox_folders_in_weaviate(sync_id)  # e.g. a function you might create


if __name__ == "__main__":
    asyncio.run(main())
