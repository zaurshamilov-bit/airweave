"""Configuration classes for platform components."""

from pydantic import Field

from airweave.platform.configs._base import BaseConfig


class SourceConfig(BaseConfig):
    """Source config schema."""

    pass


class GithubConfig(SourceConfig):
    """Github configuration schema."""

    exclude_path: str = Field(
        title="Exclude Path",
        description="Path's in the Github Repository, you want to exclude from Airweave's scope",
    )
