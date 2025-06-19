"""CRUD operations for white labels."""

from airweave.crud._base_organization import CRUDBaseOrganization
from airweave.models.white_label import WhiteLabel
from airweave.schemas.white_label import WhiteLabelCreate, WhiteLabelUpdate


class CRUDWhiteLabel(CRUDBaseOrganization[WhiteLabel, WhiteLabelCreate, WhiteLabelUpdate]):
    """CRUD operations for white labels."""


white_label = CRUDWhiteLabel(WhiteLabel)
