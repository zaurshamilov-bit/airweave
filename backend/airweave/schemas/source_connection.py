"""Source connection schemas."""

import re
from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, EmailStr, field_validator

from airweave.core.shared_models import SourceConnectionStatus
from airweave.platform.configs._base import ConfigValues


class SourceConnectionBase(BaseModel):
    """Base schema for source connection."""

    name: str
    description: Optional[str] = None
    config_fields: Optional[ConfigValues] = None  # stored in core table
    short_name: str  # Short name of the source

    class Config:
        """Pydantic config for SourceConnectionBase."""

        from_attributes = True


class SourceConnectionCreate(SourceConnectionBase):
    """Schema for creating a source connection.

    Contains all fields that are required to create a source connection.
    - Sync specific fields are included here.
    """

    collection: Optional[str] = None
    cron_schedule: Optional[str] = None
    auth_fields: Optional[ConfigValues] = None  # part of create, stored in integration_credential
    sync_immediately: bool = True

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
        if v is None:
            return None
        cron_pattern = r"^(\*|[0-9]{1,2}|[0-9]{1,2}-[0-9]{1,2}|[0-9]{1,2}/[0-9]{1,2}|[0-9]{1,2},[0-9]{1,2}|\*\/[0-9]{1,2}) (\*|[0-9]{1,2}|[0-9]{1,2}-[0-9]{1,2}|[0-9]{1,2}/[0-9]{1,2}|[0-9]{1,2},[0-9]{1,2}|\*\/[0-9]{1,2}) (\*|[0-9]{1,2}|[0-9]{1,2}-[0-9]{1,2}|[0-9]{1,2}/[0-9]{1,2}|[0-9]{1,2},[0-9]{1,2}|\*\/[0-9]{1,2}) (\*|[0-9]{1,2}|JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC|[0-9]{1,2}-[0-9]{1,2}|[0-9]{1,2}/[0-9]{1,2}|[0-9]{1,2},[0-9]{1,2}|\*\/[0-9]{1,2}) (\*|[0-6]|SUN|MON|TUE|WED|THU|FRI|SAT|[0-6]-[0-6]|[0-6]/[0-6]|[0-6],[0-6]|\*\/[0-6])$"  # noqa: E501
        if not re.match(cron_pattern, v):
            raise ValueError("Invalid cron schedule format")
        return v


class SourceConnectionUpdate(SourceConnectionBase):
    """Schema for updating a source connection."""

    name: Optional[str] = None
    description: Optional[str] = None
    auth_fields: Optional[ConfigValues] = None
    config_fields: Optional[ConfigValues] = None
    cron_schedule: Optional[str] = None
    short_name: Optional[str] = None
    sync_id: Optional[UUID] = None
    integration_credential_id: Optional[UUID] = None


class SourceConnectionInDBBase(SourceConnectionBase):
    """Core schema for source connection stored in DB."""

    id: UUID
    dag_id: Optional[UUID] = None
    sync_id: Optional[UUID] = None
    organization_id: UUID
    status: SourceConnectionStatus
    created_at: datetime
    modified_at: datetime
    integration_credential_id: Optional[UUID] = None
    collection: Optional[str] = None
    created_by_email: EmailStr
    modified_by_email: EmailStr

    class Config:
        """Pydantic config for SourceConnectionInDBBase."""

        from_attributes = True


class SourceConnection(SourceConnectionInDBBase):
    """Schema for source connection."""

    # str if encrypted, ConfigValues if not
    # comes from integration_credential
    auth_fields: Optional[ConfigValues | str] = None
