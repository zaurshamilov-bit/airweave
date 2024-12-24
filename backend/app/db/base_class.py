"""Base classes for SQLAlchemy models."""

from uuid import UUID

from sqlalchemy.orm import DeclarativeBase, declared_attr


class Base(DeclarativeBase):
    """Base class for all models in the database.

    Attributes
    ----------
        id: UUID: The id of the model.
        __name__: str: The name of the model.

    """

    id: UUID
    __name__: str

    @declared_attr
    def __tablename__(cls) -> str:
        """Generate the table name for the model.

        Returns
        -------
            str: The table name for the model.

        """
        return cls.__name__.lower()
