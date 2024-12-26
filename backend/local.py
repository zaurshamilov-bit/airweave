"""Local script for testing."""
import asyncio
import uuid

import weaviate.classes as wvc
from weaviate.collections import Collection

from app import schemas
from app.platform.destinations.weaviate import WeaviateDestination
from app.platform.embedding_models.local_text2vec import LocalText2Vec
from app.platform.sources.asana import AsanaSource
from app.vector_db.weaviate_service import WeaviateService


async def main():
    """Entrypoint for local script."""
    # Create test user
    user = schemas.User(
        id=uuid.uuid4(),
        email="test@test.com",
        full_name="Test User",
        organization_id=uuid.uuid4(),
    )
    sync_id = uuid.uuid4()

    # Initialize embedding model
    embedding_model = LocalText2Vec()

    # Initialize source and destination
    asana_source = await AsanaSource.create(user, sync_id)
    weaviate_dest = await WeaviateDestination.create(user, sync_id, embedding_model)

    # Buffer for batch processing
    chunk_buffer = []
    buffer_size = 50  # Adjust based on your needs

    # Process chunks
    async for chunk in asana_source.generate_chunks():
        chunk_buffer.append(chunk)

        # When buffer is full, bulk insert
        if len(chunk_buffer) >= buffer_size:
            await weaviate_dest.bulk_insert(chunk_buffer)
            print(f"Inserted {len(chunk_buffer)} chunks")
            chunk_buffer = []

    # Insert any remaining chunks
    if chunk_buffer:
        await weaviate_dest.bulk_insert(chunk_buffer)
        print(f"Inserted final {len(chunk_buffer)} chunks")

    # Verify the sync
    print("\n=== Verifying Sync Results ===")
    async with WeaviateService() as service:
        sanitized_sync_id = str(sync_id).replace("-", "_")
        collection: Collection = await service.get_weaviate_collection(f"Chunks_{sanitized_sync_id}")

        # Get total count - using the correct method from docs
        count = (await collection.aggregate.over_all(total_count=True)).total_count
        print(f"\nTotal documents: {count}")

        # Check sample documents with metadata
        results = await collection.query.fetch_objects(
            limit=5,
            include_vector=False,
            return_metadata=wvc.query.MetadataQuery(
                creation_time=True,
                last_update_time=True
            )
        )

        print("\nSample documents:")
        for obj in results.objects:
            print(f"\nName: {obj.properties.get('name')}")
            print(f"Source: {obj.properties.get('source_name')}")
            print(f"Created: {obj.metadata.creation_time}")
            print(f"Breadcrumbs: {obj.properties.get('breadcrumbs')}")

        # Query for tasks with filters
        tasks = await collection.query.fetch_objects(
            limit=5,
            filters=wvc.query.Filter.by_property("resource_subtype").equal("default_task"),
            return_metadata=wvc.query.MetadataQuery(creation_time=True)
        )

        print("\nSample tasks:")
        for task in tasks.objects:
            print(f"\nTask: {task.properties.get('name')}")
            print(f"Created: {task.metadata.creation_time}")
            print(f"Completed: {task.properties.get('completed')}")
            print(f"Due at: {task.properties.get('due_at')}")


if __name__ == "__main__":
    asyncio.run(main())
