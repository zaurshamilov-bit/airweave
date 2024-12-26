"""CRUD operations for embedding models."""

from app.crud._base_system import CRUDBaseSystem
from app.models.embedding_model import EmbeddingModel
from app.schemas.embedding_model import EmbeddingModelCreate, EmbeddingModelUpdate


class CRUDEmbeddingModel(CRUDBaseSystem[EmbeddingModel, EmbeddingModelCreate, EmbeddingModelUpdate]):
    """CRUD operations for embedding models."""
    pass


embedding_model = CRUDEmbeddingModel(EmbeddingModel)
