"""CRUD operations for transformers."""

from app.models.transformer import Transformer
from app.schemas.transformer import TransformerCreate, TransformerUpdate

from ._base_organization import CRUDBaseOrganization


class CRUDTransformer(CRUDBaseOrganization[Transformer, TransformerCreate, TransformerUpdate]):
    """CRUD operations for Transformer."""

    pass


transformer = CRUDTransformer(Transformer)
