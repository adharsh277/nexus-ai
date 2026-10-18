import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import User
from app.schemas.reminder import NotificationCounts, NotificationRead
from app.security import get_current_user
from app.services import reminders as reminder_service

router = APIRouter(tags=["notifications"])


@router.get("/notifications", response_model=list[NotificationRead])
def list_notifications(
    unread_only: bool = Query(False),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Retrieve in-app notifications for the authenticated user."""
    return reminder_service.list_notifications(
        db, user.id, unread_only=unread_only, limit=limit
    )


@router.get("/notifications/unread-count", response_model=NotificationCounts)
def get_unread_count(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Get the current count of unread and total notifications."""
    return reminder_service.get_notification_counts(db, user.id)


@router.patch("/notifications/{notification_id}/read", response_model=NotificationRead)
def mark_notification_read(
    notification_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Mark a specific notification as read."""
    return reminder_service.mark_notification_read(db, user.id, notification_id)


@router.post("/notifications/mark-all-read")
def mark_all_read(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Mark all unread notifications as read for the authenticated user."""
    count = reminder_service.mark_all_notifications_read(db, user.id)
    return {"marked_read": count}
