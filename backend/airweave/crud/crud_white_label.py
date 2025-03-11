"""CRUD operations for white labels."""

from airweave.crud._base import CRUDBase
from airweave.models.white_label import WhiteLabel
from airweave.schemas.white_label import WhiteLabelCreate, WhiteLabelUpdate


class CRUDWhiteLabel(CRUDBase[WhiteLabel, WhiteLabelCreate, WhiteLabelUpdate]):
    """CRUD operations for white labels."""


white_label = CRUDWhiteLabel(WhiteLabel)
