"""Web fetcher transformer using Firecrawl."""

import hashlib
import os
from typing import List
from uuid import uuid4

from firecrawl import AsyncFirecrawlApp

from airweave.core.config import settings
from airweave.core.logging import logger
from airweave.platform.decorators import transformer
from airweave.platform.entities._base import WebEntity
from airweave.platform.entities.web import WebFileEntity


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
    logger.info(f"Starting web fetch for URL: {web_entity.url}")

    # Get Firecrawl API key from settings
    firecrawl_api_key = getattr(settings, "FIRECRAWL_API_KEY", None)
    if not firecrawl_api_key:
        logger.error("FIRECRAWL_API_KEY not found in settings")
        raise ValueError("FIRECRAWL_API_KEY must be configured to use web fetcher")

    try:
        # Initialize Firecrawl app
        app = AsyncFirecrawlApp(api_key=firecrawl_api_key)

        # Scrape the URL and get markdown using scrape_url instead of crawl_url
        logger.info(f"Scraping URL with Firecrawl: {web_entity.url}")
        scrape_result = await app.scrape_url(web_entity.url, formats=["markdown"])

        # Check if scraping was successful and has markdown content
        if (
            not scrape_result
            or not hasattr(scrape_result, "markdown")
            or not scrape_result.markdown
        ):
            logger.warning(f"No markdown content returned from Firecrawl for URL: {web_entity.url}")
            raise ValueError(f"No content could be extracted from URL: {web_entity.url}")

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
        os.makedirs(base_temp_dir, exist_ok=True)

        file_uuid = uuid4()
        safe_title = title.replace("/", "_").replace("\\", "_")
        safe_filename = f"{file_uuid}-{safe_title}.md"
        temp_file_path = os.path.join(base_temp_dir, safe_filename)

        # Write markdown content to file
        with open(temp_file_path, "w", encoding="utf-8") as f:
            f.write(markdown_content)

        # Calculate file size and checksum
        file_size = len(markdown_content.encode("utf-8"))
        checksum = hashlib.sha256(markdown_content.encode("utf-8")).hexdigest()

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

        logger.info(f"Successfully created FileEntity for URL: {web_entity.url}")
        logger.info(f"Content length: {len(markdown_content)} characters")
        logger.info(f"Local file saved to: {temp_file_path}")
        logger.info(f"Title: {title}")

        # Return a list containing the single entity
        return [file_entity]

    except Exception as e:
        logger.error(f"Error fetching web content for URL {web_entity.url}: {str(e)}")
        raise e
