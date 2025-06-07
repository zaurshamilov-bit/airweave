"""CRUD operations for the Source model."""

from airweave.crud._base_public import CRUDPublic
from airweave.models.source import Source
from airweave.schemas.source import SourceCreate, SourceUpdate


class CRUDSource(CRUDPublic[Source, SourceCreate, SourceUpdate]):
    """CRUD operations for the Source model."""

    pass


source = CRUDSource(Source)
