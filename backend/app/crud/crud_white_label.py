"""CRUD operations for white labels."""

from app.crud._base import CRUDBase
from app.models.white_label import WhiteLabel
from app.schemas.white_label import WhiteLabelCreate, WhiteLabelUpdate


class CRUDWhiteLabel(CRUDBase[WhiteLabel, WhiteLabelCreate, WhiteLabelUpdate]):
    """CRUD operations for white labels."""

white_label = CRUDWhiteLabel(WhiteLabel)
