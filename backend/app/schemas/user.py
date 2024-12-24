"""User schema module."""

from typing import Optional
from uuid import UUID

from app.core.shared_models import FlaggableFeature
from app.schemas.feature_flag import FeatureFlagInDBBase
from pydantic import BaseModel, EmailStr


class UserBase(BaseModel):
    """Base schema for User."""

    email: EmailStr
    full_name: Optional[str] = "Undefined"
    auth0_id: str

    class Config:
        """Pydantic config for UserBase."""

        from_orm = True
        from_attributes = True


class UserCreate(UserBase):
    """Schema for creating a User object."""

    pass


class UserUpdate(UserBase):
    """Schema for updating a User object."""

    permissions: Optional[list[str]] = None


class UserInDBBase(UserBase):
    """Base schema for User stored in DB."""

    id: UUID
    permissions: Optional[list[str]] = None
    has_flags: Optional[list[FeatureFlagInDBBase]] = []

    def has_feature(self, feature: FlaggableFeature) -> bool:
        """Checks if the user has a specific feature flag enabled.

        Args:
            feature (FlaggableFeature): The feature flag to check.

        Returns:
            bool: True if the feature is enabled for the user, False otherwise.
        """
        return any(
            flag.feature == feature and flag.flag.lower() == "true" for flag in self.has_flags
        )

    class Config:
        """Pydantic config for UserInDBBase."""

        from_attributes = True


class User(UserInDBBase):
    """Schema for User."""

    class Config:
        """Pydantic config for User."""

        from_attributes = True
        populate_by_name = True


class UserInDB(UserInDBBase):
    """Schema for User stored in DB."""

    hashed_password: Optional[str] = None
