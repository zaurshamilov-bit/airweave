"""Base config class."""

from typing import Optional

from pydantic import BaseModel


class BaseConfig(BaseModel):
    """Base config class."""

    pass


class ConfigField(BaseModel):
    """Config field model."""

    name: str
    value: str
    options: Optional[list[str]] = None
    description: Optional[str] = None


class Fields(BaseModel):
    """Fields model."""

    fields: list[ConfigField]

    @classmethod
    def from_config_class(cls, config_class: type[BaseConfig]) -> "Fields":
        """Create fields from config class."""
        fields = []
        for field_name, field_info in config_class.model_fields.items():
            fields.append(
                ConfigField(
                    name=field_name,
                    value="",
                    description=field_info.description or "",
                    options=[]  # If you need options, they can be added via field metadata
                )
            )
        return Fields(fields=fields)
