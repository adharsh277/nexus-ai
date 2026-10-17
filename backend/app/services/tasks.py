import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Task, TaskStatus
from app.schemas.task import TaskCreate, TaskUpdate
from app.services import NotFoundError

SORTS = {
    "due_date": (Task.due_date.asc().nulls_last(), Task.created_at.desc()),
    "-due_date": (Task.due_date.desc().nulls_last(), Task.created_at.desc()),
    "created_at": (Task.created_at.desc(),),
}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def list_tasks(
    db: Session, user_id: uuid.UUID, status: TaskStatus | None = None, sort: str = "due_date"
) -> list[Task]:
    stmt = select(Task).where(Task.user_id == user_id)
    if status is not None:
        stmt = stmt.where(Task.status == status)
    return list(db.scalars(stmt.order_by(*SORTS[sort])))


def get_task(db: Session, user_id: uuid.UUID, task_id: uuid.UUID) -> Task:
    task = db.scalar(select(Task).where(Task.id == task_id, Task.user_id == user_id))
    if task is None:
        raise NotFoundError("Task")
    return task


def create_task(db: Session, user_id: uuid.UUID, data: TaskCreate) -> Task:
    task = Task(user_id=user_id, **data.model_dump())
    db.add(task)
    db.commit()
    db.refresh(task)
    return task


def _set_status(task: Task, status: TaskStatus) -> None:
    if status == task.status:
        return
    task.status = status
    task.completed_at = _now() if status == TaskStatus.completed else None


def update_task(db: Session, user_id: uuid.UUID, task_id: uuid.UUID, data: TaskUpdate) -> Task:
    task = get_task(db, user_id, task_id)
    changes = data.model_dump(exclude_unset=True)
    status = changes.pop("status", None)
    for field, value in changes.items():
        setattr(task, field, value)
    if status is not None:
        _set_status(task, status)
    db.commit()
    db.refresh(task)
    return task


def complete_task(db: Session, user_id: uuid.UUID, task_id: uuid.UUID) -> Task:
    task = get_task(db, user_id, task_id)
    _set_status(task, TaskStatus.completed)
    db.commit()
    db.refresh(task)
    return task


def delete_task(db: Session, user_id: uuid.UUID, task_id: uuid.UUID) -> None:
    task = get_task(db, user_id, task_id)
    db.delete(task)
    db.commit()


def dashboard(db: Session, user_id: uuid.UUID, tz_offset_minutes: int = 0) -> dict:
    """Counts plus due-today / upcoming lists.

    "Today" is the user's local calendar day, derived from `tz_offset_minutes`
    (minutes east of UTC, e.g. +330 for IST).
    """
    now = _now()
    local_tz = timezone(timedelta(minutes=tz_offset_minutes))
    start_of_day = now.astimezone(local_tz).replace(hour=0, minute=0, second=0, microsecond=0)
    end_of_day = start_of_day + timedelta(days=1)

    mine = Task.user_id == user_id
    pending = Task.status == TaskStatus.pending

    counts_by_status = dict(
        db.execute(select(Task.status, func.count()).where(mine).group_by(Task.status)).all()
    )
    overdue = db.scalar(
        select(func.count()).select_from(Task).where(mine, pending, Task.due_date < now)
    )
    due_today = db.scalars(
        select(Task)
        .where(mine, pending, Task.due_date >= start_of_day, Task.due_date < end_of_day)
        .order_by(Task.due_date)
    )
    upcoming = db.scalars(
        select(Task).where(mine, pending, Task.due_date >= now).order_by(Task.due_date).limit(5)
    )
    return {
        "counts": {
            "pending": counts_by_status.get(TaskStatus.pending, 0),
            "completed": counts_by_status.get(TaskStatus.completed, 0),
            "overdue": overdue or 0,
        },
        "due_today": list(due_today),
        "upcoming": list(upcoming),
    }
