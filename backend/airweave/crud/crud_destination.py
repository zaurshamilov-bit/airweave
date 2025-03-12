"""CRUD operations for destinations."""

from airweave.crud._base_system import CRUDBaseSystem
from airweave.models.destination import Destination
from airweave.schemas.destination import DestinationCreate, DestinationUpdate


class CRUDDestination(CRUDBaseSystem[Destination, DestinationCreate, DestinationUpdate]):
    """CRUD operations for destinations."""

    pass


destination = CRUDDestination(Destination)
