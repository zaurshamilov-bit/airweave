"""SharePoint-specific Pydantic schemas used for LLM structured generation."""

from typing import List
from pydantic import BaseModel, Field


class SharePointFileSpec(BaseModel):
    """Metadata for file generation."""

    filename: str = Field(
        description="Name of the file with .txt or .md extension (e.g., 'Project Plan.txt' or 'Project Plan.md')"
    )
    token: str = Field(description="Unique verification token to embed in the content")
    file_type: str = Field(
        default="text/plain",
        description="MIME type: must be 'text/plain' or 'text/markdown' only",
    )


class SharePointFileContent(BaseModel):
    """Content structure for a generated file."""

    title: str = Field(description="Document title/heading")
    content: str = Field(
        description="Main document content with verification token embedded"
    )
    sections: List[str] = Field(
        default_factory=list, description="List of section contents for the document"
    )
    summary: str = Field(default="", description="Brief summary of the document")


class SharePointFile(BaseModel):
    """Complete file structure for generation."""

    spec: SharePointFileSpec
    content: SharePointFileContent


class SharePointFolderSpec(BaseModel):
    """Metadata for folder generation."""

    name: str = Field(description="Name of the folder")
    description: str = Field(default="", description="Folder description")
