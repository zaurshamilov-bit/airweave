"""Models for transformers."""

from sqlalchemy import JSON, Column, String

from app.models._base import OrganizationBase, UserMixin


class Transformer(OrganizationBase, UserMixin):
    """Definition of a transformer that can transform entities."""

    __tablename__ = "transformer"

    name = Column(String, nullable=False)
    description = Column(String)
    # List of entity definition IDs this transformer can input
    input_entity_definition_ids = Column(JSON, nullable=False)
    # List of entity definition IDs this transformer can output
    output_entity_definition_ids = Column(JSON, nullable=False)
    config_schema = Column(JSON, nullable=False)  # JSON Schema for configuration
