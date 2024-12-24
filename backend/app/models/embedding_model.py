"""Embedding model model."""

from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models._base import Base


class EmbeddingModel(Base):
    """Embedding model model."""

    __tablename__ = "embedding_model"

    name: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    provider: Mapped[str] = mapped_column(String, nullable=False)
    model_name: Mapped[str] = mapped_column(String, nullable=False)
    model_version: Mapped[str] = mapped_column(String, nullable=False)
