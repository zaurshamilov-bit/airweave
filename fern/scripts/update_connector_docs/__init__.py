"""Connector documentation generator package."""

from .parsers.entity_parser import parse_entity_file
from .parsers.source_parser import parse_source_file
from .parsers.auth_parser import parse_auth_config
from .generators.mdx_generator import generate_mdx_content
from .utils.file_utils import (
    get_connectors_from_icons,
    copy_svg_icon,
    update_docs_yml,
    update_or_create_mdx,
)
from .constants import DOCS_CONNECTORS_DIR

__all__ = [
    "parse_entity_file",
    "parse_source_file",
    "parse_auth_config",
    "generate_mdx_content",
    "get_connectors_from_icons",
    "copy_svg_icon",
    "update_docs_yml",
    "update_or_create_mdx",
    "DOCS_CONNECTORS_DIR",
]
