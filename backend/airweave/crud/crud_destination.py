"""CRUD operations for destinations."""

from airweave.crud._base_public import CRUDPublic
from airweave.models.destination import Destination
from airweave.schemas.destination import DestinationCreate, DestinationUpdate


class CRUDDestination(CRUDPublic[Destination, DestinationCreate, DestinationUpdate]):
    """CRUD operations for destinations."""

    pass


destination = CRUDDestination(Destination)
