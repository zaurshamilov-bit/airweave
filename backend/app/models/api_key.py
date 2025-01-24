"""Api key model."""

from datetime import datetime

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models._base import OrganizationBase, UserMixin


class APIKey(OrganizationBase, UserMixin):
    """SQLAlchemy model for the APIKey table."""

    __tablename__ = "api_key"

    key: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    key_prefix: Mapped[str] = mapped_column(String(8), nullable=False)
    expiration_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
