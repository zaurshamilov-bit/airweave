"""CRUD operations for embedding models."""

from airweave.crud._base_public import CRUDPublic
from airweave.models.embedding_model import EmbeddingModel
from airweave.schemas.embedding_model import EmbeddingModelCreate, EmbeddingModelUpdate


class CRUDEmbeddingModel(CRUDPublic[EmbeddingModel, EmbeddingModelCreate, EmbeddingModelUpdate]):
    """CRUD operations for embedding models."""

    pass


embedding_model = CRUDEmbeddingModel(EmbeddingModel)
