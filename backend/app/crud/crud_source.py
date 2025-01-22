"""CRUD operations for the Source model."""

from app.crud._base_system import CRUDBaseSystem
from app.models.source import Source
from app.schemas.source import SourceCreate, SourceUpdate


class CRUDSource(CRUDBaseSystem[Source, SourceCreate, SourceUpdate]):
    """CRUD operations for the Source model."""

    pass


source = CRUDSource(Source)
