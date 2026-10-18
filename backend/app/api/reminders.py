import uuid
from typing import Literal

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import ReminderStatus, User
from app.schemas.reminder import ReminderCreate, ReminderRead, ReminderUpdate
from app.security import get_current_user
from app.services import reminders as reminder_service

router = APIRouter(tags=["reminders"])


@router.get("/reminders", response_model=list[ReminderRead])
def list_reminders(
    status_: ReminderStatus | None = Query(None, alias="status"),
    search: str | None = Query(None),
    sort: Literal["due_at", "-due_at", "created_at"] = "due_at",
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """List all reminders for the authenticated user with optional status and text search filtering."""
    return reminder_service.list_reminders(db, user.id, status=status_, search=search, sort=sort)


@router.post("/reminders", response_model=ReminderRead, status_code=status.HTTP_201_CREATED)
def create_reminder(
    data: ReminderCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Create a new reminder scheduled for a specific timezone-aware due_at time."""
    return reminder_service.create_reminder(db, user.id, data)


@router.get("/reminders/{reminder_id}", response_model=ReminderRead)
def get_reminder(
    reminder_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Retrieve details of a single reminder owned by the authenticated user."""
    return reminder_service.get_reminder(db, user.id, reminder_id)


@router.patch("/reminders/{reminder_id}", response_model=ReminderRead)
def update_reminder(
    reminder_id: uuid.UUID,
    data: ReminderUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Update title, description, due_at, timezone, or status of an existing reminder."""
    return reminder_service.update_reminder(db, user.id, reminder_id, data)


@router.post("/reminders/{reminder_id}/complete", response_model=ReminderRead)
def complete_reminder(
    reminder_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Mark a reminder as completed."""
    return reminder_service.complete_reminder(db, user.id, reminder_id)


@router.post("/reminders/{reminder_id}/cancel", response_model=ReminderRead)
def cancel_reminder(
    reminder_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Cancel a scheduled reminder."""
    return reminder_service.cancel_reminder(db, user.id, reminder_id)


@router.delete("/reminders/{reminder_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_reminder(
    reminder_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Permanently delete a reminder and its notifications."""
    reminder_service.delete_reminder(db, user.id, reminder_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
