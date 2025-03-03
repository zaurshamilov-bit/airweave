"""CRUD operations for transformers."""

from app.crud._base_system import CRUDBaseSystem
from app.models.transformer import Transformer
from app.schemas.transformer import TransformerCreate, TransformerUpdate


class CRUDTransformer(CRUDBaseSystem[Transformer, TransformerCreate, TransformerUpdate]):
    """CRUD operations for Transformer."""

    pass


transformer = CRUDTransformer(Transformer)
