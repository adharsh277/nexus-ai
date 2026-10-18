import asyncio
import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.config import settings
from app.db import SessionLocal
from app.models import Notification, Reminder, ReminderStatus
from app.schemas.reminder import ReminderCreate, ReminderUpdate
from app.services import NotFoundError

logger = logging.getLogger("nexus.services.reminders")

REMINDER_SORTS = {
    "due_at": (Reminder.due_at.asc(), Reminder.created_at.desc()),
    "-due_at": (Reminder.due_at.desc(), Reminder.created_at.desc()),
    "created_at": (Reminder.created_at.desc(),),
}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def list_reminders(
    db: Session,
    user_id: uuid.UUID,
    status: ReminderStatus | None = None,
    search: str | None = None,
    sort: str = "due_at",
) -> list[Reminder]:
    stmt = select(Reminder).where(Reminder.user_id == user_id)
    if status is not None:
        stmt = stmt.where(Reminder.status == status)
    if search and search.strip():
        term = f"%{search.strip()}%"
        stmt = stmt.where(
            or_(Reminder.title.ilike(term), Reminder.description.ilike(term))
        )
    order = REMINDER_SORTS.get(sort, REMINDER_SORTS["due_at"])
    return list(db.scalars(stmt.order_by(*order)))


def get_reminder(db: Session, user_id: uuid.UUID, reminder_id: uuid.UUID) -> Reminder:
    reminder = db.scalar(
        select(Reminder).where(Reminder.id == reminder_id, Reminder.user_id == user_id)
    )
    if reminder is None:
        raise NotFoundError("Reminder")
    return reminder


def create_reminder(db: Session, user_id: uuid.UUID, data: ReminderCreate) -> Reminder:
    reminder = Reminder(
        user_id=user_id,
        title=data.title,
        description=data.description,
        due_at=data.due_at,
        timezone=data.timezone,
        status=ReminderStatus.pending,
    )
    db.add(reminder)
    db.commit()
    db.refresh(reminder)
    return reminder


def update_reminder(
    db: Session, user_id: uuid.UUID, reminder_id: uuid.UUID, data: ReminderUpdate
) -> Reminder:
    reminder = get_reminder(db, user_id, reminder_id)
    changes = data.model_dump(exclude_unset=True)

    for field, value in changes.items():
        setattr(reminder, field, value)

    # If due_at was changed to a future time, allow it to be re-notified if previously notified
    if "due_at" in changes and reminder.due_at > _now():
        reminder.notified_at = None

    db.commit()
    db.refresh(reminder)
    return reminder


def complete_reminder(db: Session, user_id: uuid.UUID, reminder_id: uuid.UUID) -> Reminder:
    reminder = get_reminder(db, user_id, reminder_id)
    reminder.status = ReminderStatus.completed
    db.commit()
    db.refresh(reminder)
    return reminder


def cancel_reminder(db: Session, user_id: uuid.UUID, reminder_id: uuid.UUID) -> Reminder:
    reminder = get_reminder(db, user_id, reminder_id)
    reminder.status = ReminderStatus.cancelled
    db.commit()
    db.refresh(reminder)
    return reminder


def delete_reminder(db: Session, user_id: uuid.UUID, reminder_id: uuid.UUID) -> None:
    reminder = get_reminder(db, user_id, reminder_id)
    db.delete(reminder)
    db.commit()


# ---- Notifications ----

def list_notifications(
    db: Session, user_id: uuid.UUID, unread_only: bool = False, limit: int = 50
) -> list[Notification]:
    stmt = select(Notification).where(Notification.user_id == user_id)
    if unread_only:
        stmt = stmt.where(Notification.is_read.is_(False))
    stmt = stmt.order_by(Notification.created_at.desc()).limit(limit)
    return list(db.scalars(stmt))


def get_notification_counts(db: Session, user_id: uuid.UUID) -> dict[str, int]:
    unread = db.scalar(
        select(func.count())
        .select_from(Notification)
        .where(Notification.user_id == user_id, Notification.is_read.is_(False))
    ) or 0
    total = db.scalar(
        select(func.count()).select_from(Notification).where(Notification.user_id == user_id)
    ) or 0
    return {"unread": unread, "total": total}


def mark_notification_read(
    db: Session, user_id: uuid.UUID, notification_id: uuid.UUID
) -> Notification:
    notif = db.scalar(
        select(Notification).where(
            Notification.id == notification_id, Notification.user_id == user_id
        )
    )
    if notif is None:
        raise NotFoundError("Notification")
    notif.is_read = True
    db.commit()
    db.refresh(notif)
    return notif


def mark_all_notifications_read(db: Session, user_id: uuid.UUID) -> int:
    notifications = list(
        db.scalars(
            select(Notification).where(
                Notification.user_id == user_id, Notification.is_read.is_(False)
            )
        )
    )
    for n in notifications:
        n.is_read = True
    db.commit()
    return len(notifications)


# ---- Background Processor & Scheduler ----

def process_due_reminders(db: Session, now: datetime | None = None) -> list[Notification]:
    """Find all pending reminders that are due and not yet notified, transactionally mark notified_at,
    and persist in-app notifications.

    Concurrency control:
    - On PostgreSQL: Uses `SELECT ... FOR UPDATE SKIP LOCKED`. Multiple concurrent workers or
      container replicas safely distribute pending due reminders without duplicates or deadlocks.
    - On SQLite: Operates under database write transaction locking.

    Restart recovery:
    - Any reminder that became overdue while the service was stopped is captured on the next tick
      because `due_at <= :now AND notified_at IS NULL AND status = 'pending'`.
    """
    current_time = now or _now()

    stmt = (
        select(Reminder)
        .where(
            Reminder.status == ReminderStatus.pending,
            Reminder.due_at <= current_time,
            Reminder.notified_at.is_(None),
        )
        .order_by(Reminder.due_at.asc())
    )

    if db.bind is not None and db.bind.dialect.name == "postgresql":
        stmt = stmt.with_for_update(skip_locked=True)

    due_reminders = list(db.scalars(stmt))
    if not due_reminders:
        return []

    notifications: list[Notification] = []
    for rem in due_reminders:
        rem.notified_at = current_time
        notif = Notification(
            user_id=rem.user_id,
            reminder_id=rem.id,
            title=f"Reminder: {rem.title}",
            message=rem.description or f"Your reminder '{rem.title}' is due now.",
            created_at=current_time,
        )
        db.add(notif)
        notifications.append(notif)

    db.commit()
    logger.info("Processed %d due reminders at %s", len(notifications), current_time.isoformat())
    return notifications


class ReminderScheduler:
    """Asynchronous background scheduler for checking due reminders at a configurable interval."""

    def __init__(self, poll_interval: float | None = None):
        self.poll_interval = (
            poll_interval
            if poll_interval is not None
            else settings.reminder_poll_interval_seconds
        )
        self._running = False
        self._task: asyncio.Task | None = None

    async def start(self) -> None:
        if self._running:
            return
        self._running = True
        logger.info(
            "Starting ReminderScheduler with interval=%.1fs", self.poll_interval
        )
        self._task = asyncio.create_task(self._loop())

    async def stop(self) -> None:
        if not self._running:
            return
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        logger.info("ReminderScheduler stopped")

    async def _loop(self) -> None:
        while self._running:
            try:
                await asyncio.to_thread(self.tick)
            except Exception as exc:
                logger.exception("Error during reminder scheduler tick: %s", exc)

            try:
                await asyncio.sleep(self.poll_interval)
            except asyncio.CancelledError:
                break

    def tick(self, now: datetime | None = None) -> int:
        with SessionLocal() as db:
            notifs = process_due_reminders(db, now=now)
            return len(notifs)


scheduler = ReminderScheduler()
