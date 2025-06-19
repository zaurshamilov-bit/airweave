"""CRUD operations for transformers."""

from airweave.crud._base_public import CRUDPublic
from airweave.models.transformer import Transformer
from airweave.schemas.transformer import TransformerCreate, TransformerUpdate


class CRUDTransformer(CRUDPublic[Transformer, TransformerCreate, TransformerUpdate]):
    """CRUD operations for Transformer."""

    pass


transformer = CRUDTransformer(Transformer)
