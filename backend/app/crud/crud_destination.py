"""CRUD operations for destinations."""

from app.crud._base_system import CRUDBaseSystem
from app.models.destination import Destination
from app.schemas.destination import DestinationCreate, DestinationUpdate


class CRUDDestination(CRUDBaseSystem[Destination, DestinationCreate, DestinationUpdate]):
    """CRUD operations for destinations."""

    pass


destination = CRUDDestination(Destination)
