"""Web fetcher transformer using Firecrawl."""

import asyncio
import hashlib
import os
import random
from typing import List
from uuid import uuid4

import aiofiles
from firecrawl import AsyncFirecrawlApp

from airweave.core.config import settings
from airweave.core.logging import logger
from airweave.platform.decorators import transformer
from airweave.platform.entities._base import WebEntity
from airweave.platform.entities.web import WebFileEntity

# Add to the module level or as a class
_shared_firecrawl_client = None


async def get_firecrawl_client():
    """Get or create the shared Firecrawl client instance."""
    global _shared_firecrawl_client
    if _shared_firecrawl_client is None:
        firecrawl_api_key = getattr(settings, "FIRECRAWL_API_KEY", None)
        if not firecrawl_api_key:
            raise ValueError("FIRECRAWL_API_KEY must be configured to use web fetcher")
        _shared_firecrawl_client = AsyncFirecrawlApp(api_key=firecrawl_api_key)
    return _shared_firecrawl_client


async def _retry_with_backoff(func, *args, max_retries=3, entity_context="", **kwargs):
    """Retry a function with exponential backoff.

    Args:
        func: The async function to retry
        *args: Arguments to pass to the function
        max_retries: Maximum number of retry attempts
        entity_context: Optional context string for entity identification in logs
        **kwargs: Keyword arguments to pass to the function

    Returns:
        The result of the function call

    Raises:
        The last exception if all retries fail
    """
    last_exception = None
    context_prefix = f"{entity_context} " if entity_context else ""

    for attempt in range(max_retries + 1):  # +1 for initial attempt
        try:
            return await func(*args, **kwargs)
        except Exception as e:
            last_exception = e

            # Log the full error details
            error_type = type(e).__name__
            error_msg = str(e)

            # Don't retry on certain permanent errors
            if any(
                permanent_error in error_msg.lower()
                for permanent_error in [
                    "invalid api key",
                    "unauthorized",
                    "forbidden",
                    "not found",
                    "bad request",
                    "invalid url",
                ]
            ):
                logger.error(
                    f"{context_prefix}Non-retryable error for web scraping: "
                    f"{error_type}: {error_msg}"
                )
                raise e

            if attempt < max_retries:
                # Calculate delay with exponential backoff and jitter
                base_delay = 2**attempt  # 1s, 2s, 4s
                jitter = random.uniform(0.1, 0.5)  # Add randomness
                delay = base_delay + jitter

                logger.warning(
                    f"{context_prefix}Web scraping attempt {attempt + 1}/{max_retries + 1} "
                    f"failed with {error_type}: {error_msg}. Retrying in {delay:.2f}s..."
                )
                await asyncio.sleep(delay)
            else:
                logger.error(
                    f"{context_prefix}All {max_retries + 1} web scraping attempts failed. "
                    f"Final error {error_type}: {error_msg}"
                )

    # Re-raise the last exception if all retries failed
    raise last_exception


@transformer(name="Web Fetcher")
async def web_fetcher(web_entity: WebEntity) -> List[WebFileEntity]:
    """Fetch web content using Firecrawl and convert to FileEntity.

    This transformer:
    1. Takes a WebEntity with a URL
    2. Uses Firecrawl to crawl the URL and convert to markdown
    3. Saves the markdown content to a local temporary file
    4. Returns a list containing a single FileEntity with local_path set,
       ready for file chunker

    Args:
        web_entity: The WebEntity containing the URL to fetch

    Returns:
        List[WebFileEntity]: A list containing the single FileEntity with the web
        content as markdown and local_path set
    """
    # Get entity number for logging (default to "?" if not set)
    entity_number = getattr(web_entity, "entity_number", "?")

    logger.info(
        f"Starting web fetch for entity #{entity_number} ({web_entity.entity_id}) "
        f"URL: {web_entity.url}"
    )

    async def _scrape_with_firecrawl():
        """Internal function to handle the actual scraping with retry logic."""
        app = await get_firecrawl_client()

        logger.info(
            f"Scraping URL with Firecrawl for entity #{entity_number} ({web_entity.entity_id}): "
            f"{web_entity.url}"
        )
        scrape_result = await app.scrape_url(web_entity.url, formats=["markdown"])

        # Check if scraping was successful and has markdown content
        if (
            not scrape_result
            or not hasattr(scrape_result, "markdown")
            or not scrape_result.markdown
        ):
            logger.warning(
                f"No markdown content returned from Firecrawl for entity #{entity_number} "
                f"({web_entity.entity_id}) URL: {web_entity.url}"
            )
            raise ValueError(
                f"No content could be extracted from entity #{entity_number} "
                f"({web_entity.entity_id}) URL: {web_entity.url}"
            )

        return scrape_result

    try:
        # Use retry logic for the scraping operation with entity context
        entity_context = f"Entity #{entity_number} ({web_entity.entity_id})"
        scrape_result = await _retry_with_backoff(
            _scrape_with_firecrawl, entity_context=entity_context
        )

        # Get markdown content directly from the response
        markdown_content = scrape_result.markdown
        metadata = scrape_result.metadata  # Direct access

        # Extract useful metadata - handle both object attributes and dict access
        def safe_get_metadata(key, default=""):
            if hasattr(metadata, key):
                return getattr(metadata, key, default)
            elif isinstance(metadata, dict):
                return metadata.get(key, default)
            return default

        title = web_entity.title or safe_get_metadata("title", "Web Page")

        # Create a temporary file with the markdown content (similar to file_manager)
        base_temp_dir = "/tmp/airweave"
        # Make directory creation async to avoid blocking
        await asyncio.to_thread(os.makedirs, base_temp_dir, exist_ok=True)

        file_uuid = uuid4()
        safe_title = title.replace("/", "_").replace("\\", "_")
        safe_filename = f"{file_uuid}-{safe_title}.md"
        temp_file_path = os.path.join(base_temp_dir, safe_filename)

        # Write markdown content to file ASYNC
        async with aiofiles.open(temp_file_path, "w", encoding="utf-8") as f:
            await f.write(markdown_content)

        # Calculate file size and checksum in thread pool (CPU-bound operations)
        def _calculate_file_metrics(content: str):
            encoded_content = content.encode("utf-8")
            file_size = len(encoded_content)
            checksum = hashlib.sha256(encoded_content).hexdigest()
            return file_size, checksum

        file_size, checksum = await asyncio.to_thread(_calculate_file_metrics, markdown_content)

        # Create WebFileEntity with local_path set (similar to file_manager output)
        file_entity = WebFileEntity(
            entity_id=web_entity.entity_id,
            file_id=f"web_{web_entity.entity_id}",
            name=f"{title}.md",
            mime_type="text/markdown",
            size=file_size,
            download_url=web_entity.url,  # Original URL for reference
            url=web_entity.url,  # Set BaseEntity url field
            local_path=temp_file_path,  # Critical: set local_path for file chunker
            file_uuid=file_uuid,
            checksum=checksum,
            total_size=file_size,
            # Copy BaseEntity fields from web entity
            breadcrumbs=web_entity.breadcrumbs,
            parent_entity_id=web_entity.parent_entity_id,
            # Copy entity number if present
            entity_number=entity_number,
            # Copy sync metadata from web entity
            sync_id=web_entity.sync_id,
            sync_job_id=web_entity.sync_job_id,
            source_name=web_entity.source_name,
            sync_metadata=web_entity.sync_metadata,
            # WebFileEntity specific fields
            original_url=web_entity.url,
            crawl_metadata=metadata,
            web_title=safe_get_metadata("title"),
            web_description=safe_get_metadata("description"),
            # Add web-specific metadata to the base metadata field
            metadata={
                "scraped_title": safe_get_metadata("title"),
                "scraped_description": safe_get_metadata("description"),
                "language": safe_get_metadata("language"),
                "status_code": safe_get_metadata("statusCode"),
                "og_title": safe_get_metadata("ogTitle"),
                "og_description": safe_get_metadata("ogDescription"),
                "og_image": safe_get_metadata("ogImage"),
                "firecrawl_metadata": metadata,
                **(web_entity.metadata or {}),
            },
        )

        logger.info(
            f"Successfully created FileEntity for entity #{entity_number} ({web_entity.entity_id}) "
            f"URL: {web_entity.url}"
        )
        logger.info(f"Entity #{entity_number} content length: {len(markdown_content)} characters")
        logger.info(f"Entity #{entity_number} local file saved to: {temp_file_path}")
        logger.info(f"Entity #{entity_number} title: {title}")

        # Return a list containing the single entity
        return [file_entity]

    except Exception as e:
        logger.error(
            f"Error fetching web content for entity #{entity_number} ({web_entity.entity_id}) "
            f"URL {web_entity.url} after all retries: {str(e)}"
        )
        raise e
