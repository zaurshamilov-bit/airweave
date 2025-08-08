"""APIKey schema."""

from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator

from airweave.core.datetime_utils import utc_now_naive


class APIKeyBase(BaseModel):
    """Base schema for APIKey."""

    class Config:
        """Pydantic config for APIKeyBase."""

        from_attributes = True


class APIKeyCreate(BaseModel):
    """Schema for creating an APIKey object."""

    expiration_date: Optional[datetime] = Field(
        default=None,  # Let the backend handle the default
        description="Expiration date for the API key, defaults to 180 days from now",
    )

    @model_validator(mode="before")
    def set_expiration_utc(cls, values: dict) -> dict:
        """Ensure expiration_date is in UTC but as timezone-naive.

        Args:
        ----
            values (dict): The values to validate.

        Returns:
        -------
            dict: The validated values.

        """
        expiration_date = values.get("expiration_date")
        if expiration_date is None:
            return values  # Let the datetime validation handle this

        if isinstance(expiration_date, str):
            # Parse the string and convert to UTC naive
            try:
                parsed_date = datetime.fromisoformat(expiration_date)
                if parsed_date.tzinfo is not None:
                    # Convert to UTC and make naive
                    values["expiration_date"] = parsed_date.astimezone(timezone.utc).replace(
                        tzinfo=None
                    )
                else:
                    # Already naive, assume UTC
                    values["expiration_date"] = parsed_date
            except ValueError:
                return values  # Let the datetime validation handle this
        elif isinstance(expiration_date, datetime):
            if expiration_date.tzinfo is not None:
                # Convert to UTC and make naive
                values["expiration_date"] = expiration_date.astimezone(timezone.utc).replace(
                    tzinfo=None
                )
            else:
                # Already naive, assume UTC
                values["expiration_date"] = expiration_date

        return values

    @field_validator("expiration_date")
    def check_expiration_date(cls, v: Optional[datetime]) -> Optional[datetime]:
        """Validate the expiration date.

        Args:
        ----
            v (datetime): The expiration date.

        Raises:
        ------
            ValueError: If the expiration date is in the past or more than 1 year in the future.

        Returns:
        -------
            datetime: The expiration date.

        """
        if v is None:
            return None

        now = utc_now_naive()
        if v < now:
            raise ValueError("Expiration date cannot be in the past.")
        if v > now.replace(year=now.year + 1):
            raise ValueError("Expiration date cannot be more than 1 year in the future.")
        return v

    class Config:
        """Pydantic config for APIKeyCreate."""

        from_attributes = True


class APIKeyUpdate(BaseModel):
    """Schema for updating an APIKey object."""

    expiration_date: Optional[datetime] = None

    class Config:
        """Pydantic config for APIKeyUpdate."""

        from_attributes = True


class APIKeyInDBBase(APIKeyBase):
    """Base schema for APIKey stored in DB."""

    id: UUID
    organization: UUID
    created_at: datetime
    modified_at: datetime
    last_used_date: Optional[datetime] = None
    expiration_date: datetime
    created_by_email: Optional[EmailStr] = None
    modified_by_email: Optional[EmailStr] = None

    class Config:
        """Pydantic config for APIKeyInDBBase."""

        from_attributes = True


class APIKey(APIKeyInDBBase):
    """Schema for API keys returned to clients - includes decrypted key."""

    decrypted_key: str

    class Config:
        """Pydantic config for APIKey."""

        from_attributes = True
