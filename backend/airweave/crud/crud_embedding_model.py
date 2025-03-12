"""CRUD operations for embedding models."""

from airweave.crud._base_system import CRUDBaseSystem
from airweave.models.embedding_model import EmbeddingModel
from airweave.schemas.embedding_model import EmbeddingModelCreate, EmbeddingModelUpdate


class CRUDEmbeddingModel(
    CRUDBaseSystem[EmbeddingModel, EmbeddingModelCreate, EmbeddingModelUpdate]
):
    """CRUD operations for embedding models."""

    pass


embedding_model = CRUDEmbeddingModel(EmbeddingModel)
