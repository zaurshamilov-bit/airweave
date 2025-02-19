"""Module for converting supported file types into entityable and vectorizable markdown text."""

import os
from pathlib import Path
from typing import Optional

from markitdown import MarkItDown

from app.core.logging import logger


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
        # ".zip", TODO: Needs more handling for edge cases
    }

    def __init__(self):
        """Initialize converter with optional configuration."""
        self.md_converter = MarkItDown()

    def convert_to_markdown(self, file_path: str) -> Optional[str]:
        """Converts a given file to markdown text using MarkItDown."""
        if not self._is_supported(file_path):
            return None

        if not os.path.exists(file_path):
            logger.warning(f"File not found: {file_path}")
            return None

        try:
            md_content = self.md_converter.convert(file_path).text_content
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


file_converter = FileConverter()
