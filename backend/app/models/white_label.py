"""White label model."""

from uuid import UUID

from sqlalchemy import UUID as UUIDType
from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.models._base import OrganizationBase, UserMixin


class WhiteLabel(OrganizationBase, UserMixin):
    """White label model."""

    __tablename__ = "white_label"

    name: Mapped[str] = mapped_column(String, nullable=False)
    source_id: Mapped[UUID] = mapped_column(UUIDType, nullable=False)
    redirect_url: Mapped[str] = mapped_column(String, nullable=False)
    client_id: Mapped[str] = mapped_column(String, nullable=False)
    client_secret: Mapped[str] = mapped_column(String, nullable=False)
