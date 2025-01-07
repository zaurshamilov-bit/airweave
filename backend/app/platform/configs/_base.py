"""Base config class."""

from typing import Optional

from pydantic import BaseModel


class BaseConfig(BaseModel):
    """Base config class."""

    pass


class ConfigField(BaseModel):
    """Config field model."""

    name: str
    title: str
    description: Optional[str] = None
    type: str


_type_map = {str: "string", int: "number", float: "number", bool: "boolean"}


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
                    title=field_info.title,
                    description=field_info.description,
                    type=_type_map[field_info.annotation],
                )
            )
        return Fields(fields=fields)
