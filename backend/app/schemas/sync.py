"""Sync schemas."""

import re
from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, EmailStr, field_validator


class SyncBase(BaseModel):
    """Base schema for Sync."""

    name: str
    schedule: str  # Human-readable schedule description
    source_integration_credential_id: UUID
    destination_integration_credential_id: Optional[UUID] = None
    embedding_model_integration_credential_id: Optional[UUID] = None
    cron_schedule: str  # Actual cron expression
    white_label_id: Optional[UUID] = None
    white_label_user_identifier: Optional[str] = None

    @field_validator("cron_schedule")
    def validate_cron_schedule(cls, v: str) -> str:
        """Validate cron schedule format.

        Format: * * * * *
        minute (0-59)
        hour (0-23)
        day of month (1-31)
        month (1-12 or JAN-DEC)
        day of week (0-6 or SUN-SAT)

        * * * * *
        │ │ │ │ │
        │ │ │ │ └─ Day of week (0-6 or SUN-SAT)
        │ │ │ └─── Month (1-12 or JAN-DEC)
        │ │ └───── Day of month (1-31)
        │ └─────── Hour (0-23)
        └───────── Minute (0-59)
        """
        cron_pattern = r"^(\*|[0-9]{1,2}|[0-9]{1,2}-[0-9]{1,2}|[0-9]{1,2}/[0-9]{1,2}|[0-9]{1,2},[0-9]{1,2}|\*\/[0-9]{1,2}) (\*|[0-9]{1,2}|[0-9]{1,2}-[0-9]{1,2}|[0-9]{1,2}/[0-9]{1,2}|[0-9]{1,2},[0-9]{1,2}|\*\/[0-9]{1,2}) (\*|[0-9]{1,2}|[0-9]{1,2}-[0-9]{1,2}|[0-9]{1,2}/[0-9]{1,2}|[0-9]{1,2},[0-9]{1,2}|\*\/[0-9]{1,2}) (\*|[0-9]{1,2}|JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC|[0-9]{1,2}-[0-9]{1,2}|[0-9]{1,2}/[0-9]{1,2}|[0-9]{1,2},[0-9]{1,2}|\*\/[0-9]{1,2}) (\*|[0-6]|SUN|MON|TUE|WED|THU|FRI|SAT|[0-6]-[0-6]|[0-6]/[0-6]|[0-6],[0-6]|\*\/[0-6])$"
        if not re.match(cron_pattern, v):
            raise ValueError("Invalid cron schedule format")
        return v

    class Config:
        """Pydantic config."""

        from_attributes = True


class SyncCreate(SyncBase):
    """Schema for creating a Sync object."""

    pass


class SyncUpdate(BaseModel):
    """Schema for updating a Sync object."""

    name: Optional[str] = None
    schedule: Optional[str] = None
    source_integration_credential_id: Optional[UUID] = None
    destination_integration_credential_id: Optional[UUID] = None
    embedding_model_integration_credential_id: Optional[UUID] = None
    cron_schedule: Optional[str] = None
    white_label_id: Optional[UUID] = None
    white_label_user_identifier: Optional[str] = None


class SyncInDBBase(SyncBase):
    """Base schema for Sync stored in DB."""

    id: UUID
    organization_id: UUID
    created_at: datetime
    modified_at: datetime
    created_by_email: EmailStr
    modified_by_email: EmailStr

    class Config:
        """Pydantic config."""

        from_attributes = True


class Sync(SyncInDBBase):
    """Schema for Sync."""

    pass
