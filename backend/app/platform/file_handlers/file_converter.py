"""Module for converting supported file types into entityable and vectorizable markdown text."""

import os
from pathlib import Path
from typing import Optional

from app.core.config import settings
from app.core.logging import logger

from .async_markitdown import AsyncMarkItDown

openai_client = None

if settings.OPENAI_API_KEY:
    from openai import AsyncOpenAI

    openai_client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)


class FileConverter:
    """Handles conversion of various file types to markdown format."""

    SUPPORTED_EXTENSIONS = {
        ".pdf",
        ".doc",
        ".docx",
        ".ppt",
        ".pptx",
        ".xls",
        ".xlsx",
        ".html",
        ".htm",
        ".txt",
        ".csv",
        ".json",
        ".xml",
        ".png",
        ".jpg",
        ".jpeg",
    }

    def __init__(self, llm_client: Optional[AsyncOpenAI] = None):
        """Initialize converter with optional configuration."""
        self.llm_client = llm_client
        self.md_converter = AsyncMarkItDown(
            llm_client=self.llm_client,
            llm_model="gpt-4o-mini",
        )

    async def convert_to_markdown(self, file_path: str) -> Optional[str]:
        """Converts a given file to markdown text using MarkItDown."""
        if not self._is_supported(file_path):
            return None

        if not os.path.exists(file_path):
            logger.warning(f"File not found: {file_path}")
            return None

        try:
            # Run the synchronous convert method in a thread pool
            result = await self.md_converter.convert(file_path)
            md_content = result.text_content
            if md_content.startswith("[ERROR]"):
                logger.error(f"Error converting file to markdown: {md_content}")
                return None
            return md_content
        except Exception as e:
            logger.error(f"Error converting file to markdown: {e}")
            return None

    def _is_supported(self, file_path: str) -> bool:
        """Check if the file extension is supported."""
        ext = Path(file_path).suffix.lower()
        if ext not in self.SUPPORTED_EXTENSIONS:
            logger.warning(f"Unsupported file extension: {ext} for file: {file_path}")
            return False
        return True

    # Future extension points:
    # def convert_zip(self, zip_path: str) -> List[str]:
    # def batch_convert(self, file_paths: List[str]) -> Dict[str, Optional[str]]:
    # def convert_with_options(self, file_path: str, options: Dict) -> Optional[str]:
    # support image and audio conversion with user-provided llm_client (e.g., openai.OpenAI) and
    #   llm_model (e.g., gpt-4o)


file_converter = FileConverter(llm_client=openai_client)
