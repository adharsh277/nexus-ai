import uuid
from typing import Literal

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import TaskStatus, User
from app.schemas.task import DashboardRead, TaskCreate, TaskRead, TaskUpdate
from app.security import get_current_user
from app.services import tasks as task_service

router = APIRouter(tags=["tasks"])


@router.get("/tasks", response_model=list[TaskRead])
def list_tasks(
    status_: TaskStatus | None = Query(None, alias="status"),
    sort: Literal["due_date", "-due_date", "created_at"] = "due_date",
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return task_service.list_tasks(db, user.id, status_, sort)


@router.post("/tasks", response_model=TaskRead, status_code=status.HTTP_201_CREATED)
def create_task(
    data: TaskCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)
):
    return task_service.create_task(db, user.id, data)


@router.get("/tasks/{task_id}", response_model=TaskRead)
def get_task(
    task_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)
):
    return task_service.get_task(db, user.id, task_id)


@router.patch("/tasks/{task_id}", response_model=TaskRead)
def update_task(
    task_id: uuid.UUID,
    data: TaskUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return task_service.update_task(db, user.id, task_id, data)


@router.post("/tasks/{task_id}/complete", response_model=TaskRead)
def complete_task(
    task_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)
):
    return task_service.complete_task(db, user.id, task_id)


@router.delete("/tasks/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_task(
    task_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)
):
    task_service.delete_task(db, user.id, task_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/dashboard", response_model=DashboardRead)
def dashboard(
    tz_offset_minutes: int = Query(0, ge=-14 * 60, le=14 * 60),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return task_service.dashboard(db, user.id, tz_offset_minutes)
