import uuid
import zoneinfo
from datetime import datetime, timezone
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator

from app.models import ReminderStatus

Title = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
Description = Annotated[str, StringConstraints(max_length=5000)]


def _validate_iana_timezone(v: str | None) -> str:
    if v is None or not v.strip():
        return "UTC"
    cleaned = v.strip()
    try:
        zoneinfo.ZoneInfo(cleaned)
    except Exception as exc:
        raise ValueError(
            f"Invalid IANA timezone '{cleaned}'. Must be a recognized timezone like 'UTC', 'America/New_York', or 'Asia/Kolkata'."
        ) from exc
    return cleaned


def _ensure_utc_aware(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


class ReminderCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: Title
    description: Description | None = None
    due_at: datetime
    timezone: str = Field(default="UTC", description="IANA timezone name, e.g. 'UTC', 'Asia/Kolkata'")

    _validate_tz = field_validator("timezone", mode="before")(_validate_iana_timezone)
    _aware_due = field_validator("due_at")(_ensure_utc_aware)


class ReminderUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: Title | None = None
    description: Description | None = None
    due_at: datetime | None = None
    timezone: str | None = None
    status: ReminderStatus | None = None

    _validate_tz = field_validator("timezone", mode="before")(_validate_iana_timezone)
    _aware_due = field_validator("due_at")(_ensure_utc_aware)

    @field_validator("title", "due_at", "status", mode="before")
    @classmethod
    def _not_null(cls, value):
        if value is None:
            raise ValueError("may not be null")
        return value


class ReminderRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    title: str
    description: str | None
    due_at: datetime
    timezone: str
    status: ReminderStatus
    created_at: datetime
    updated_at: datetime
    notified_at: datetime | None


class NotificationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    reminder_id: uuid.UUID | None
    title: str
    message: str
    is_read: bool
    created_at: datetime


class NotificationCounts(BaseModel):
    unread: int
    total: int
