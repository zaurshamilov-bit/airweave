"""Collection model."""

from typing import TYPE_CHECKING, List

from sqlalchemy import Enum as SQLAlchemyEnum
from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from airweave.models._base import OrganizationBase, UserMixin
from airweave.schemas.collection import CollectionStatus

if TYPE_CHECKING:
    from airweave.models.source_connection import SourceConnection


class Collection(OrganizationBase, UserMixin):
    """Collection model."""

    __tablename__ = "collection"

    name: Mapped[str] = mapped_column(String, nullable=False)
    readable_id: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    status: Mapped[CollectionStatus] = mapped_column(
        SQLAlchemyEnum(CollectionStatus), default=CollectionStatus.NEEDS_SOURCE, nullable=False
    )

    # Relationships
    if TYPE_CHECKING:
        source_connections: List["SourceConnection"]

    source_connections: Mapped[list["SourceConnection"]] = relationship(
        "SourceConnection",
        back_populates="collection",
        lazy="noload",
        cascade="all, delete-orphan",
        primaryjoin="SourceConnection.readable_collection_id == Collection.readable_id",
    )
