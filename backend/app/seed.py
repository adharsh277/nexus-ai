"""Idempotent seed: ensures the default local user exists. Run: python -m app.seed"""
import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.db import SessionLocal
from app.models import User

logger = logging.getLogger("nexus.seed")


def seed_default_user(db: Session) -> User:
    user = db.scalar(select(User).where(User.email == settings.default_user_email))
    if user is None:
        user = User(email=settings.default_user_email, display_name=settings.default_user_name)
        db.add(user)
        db.commit()
        db.refresh(user)
        logger.info("Created default user id=%s", user.id)
    else:
        logger.info("Default user already exists id=%s", user.id)
    return user


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
    with SessionLocal() as session:
        seed_default_user(session)
