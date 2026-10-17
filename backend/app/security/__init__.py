"""Authentication boundary.

Phase 1 has no login: every request acts as the seeded default user.
Replace `get_current_user` with real auth (session/JWT) later; all endpoints
already depend on it and all queries filter by the returned user's id.
"""
from fastapi import Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_db
from app.models import User


def get_current_user(db: Session = Depends(get_db)) -> User:
    user = db.scalar(select(User).where(User.email == settings.default_user_email))
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Default user not found. Run `python -m app.seed`.",
        )
    return user
