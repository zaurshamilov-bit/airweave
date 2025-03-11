"""White label model."""

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from airweave.models._base import OrganizationBase, UserMixin


class WhiteLabel(OrganizationBase, UserMixin):
    """White label model."""

    __tablename__ = "white_label"

    name: Mapped[str] = mapped_column(String, nullable=False)
    source_short_name: Mapped[str] = mapped_column(
        String, ForeignKey("source.short_name"), nullable=False
    )
    redirect_url: Mapped[str] = mapped_column(String, nullable=False)
    client_id: Mapped[str] = mapped_column(String, nullable=False)
    client_secret: Mapped[str] = mapped_column(String, nullable=False)
