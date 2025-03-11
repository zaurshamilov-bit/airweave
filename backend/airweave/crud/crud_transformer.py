"""CRUD operations for transformers."""

from airweave.crud._base_system import CRUDBaseSystem
from airweave.models.transformer import Transformer
from airweave.schemas.transformer import TransformerCreate, TransformerUpdate


class CRUDTransformer(CRUDBaseSystem[Transformer, TransformerCreate, TransformerUpdate]):
    """CRUD operations for Transformer."""

    pass


transformer = CRUDTransformer(Transformer)
