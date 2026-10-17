import uuid
from datetime import datetime, timezone
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator

from app.models import TaskStatus

Title = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
Description = Annotated[str, StringConstraints(max_length=5000)]


def _ensure_aware(value: datetime | None) -> datetime | None:
    """Naive datetimes are interpreted as UTC so everything stored is timezone-aware."""
    if value is not None and value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


class TaskCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: Title
    description: Description | None = None
    due_date: datetime | None = None

    _aware = field_validator("due_date")(_ensure_aware)


class TaskUpdate(BaseModel):
    """Partial update. Only fields that are sent are changed."""

    model_config = ConfigDict(extra="forbid")

    title: Title | None = None
    description: Description | None = None
    due_date: datetime | None = None
    status: TaskStatus | None = None

    _aware = field_validator("due_date")(_ensure_aware)

    @field_validator("title", "status", mode="before")
    @classmethod
    def _not_null(cls, value):
        if value is None:
            raise ValueError("may not be null")
        return value


class TaskRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    description: str | None
    status: TaskStatus
    due_date: datetime | None
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None


class DashboardCounts(BaseModel):
    pending: int
    completed: int
    overdue: int


class DashboardRead(BaseModel):
    counts: DashboardCounts
    due_today: list[TaskRead]
    upcoming: list[TaskRead] = Field(description="Next 5 pending tasks with a future due date")
