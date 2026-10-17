import logging

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db import get_db

router = APIRouter(tags=["health"])
logger = logging.getLogger("nexus.health")


@router.get("/health")
def health(db: Session = Depends(get_db)):
    try:
        db.execute(text("SELECT 1"))
    except Exception as exc:  # noqa: BLE001 - report any DB failure as unhealthy
        logger.warning("DB health check failed: %s", type(exc).__name__)
        return JSONResponse(status_code=503, content={"status": "error", "database": "error"})
    from app.config import settings
    return {
        "status": "ok",
        "database": "ok",
        "llm": {
            "provider": settings.llm_provider,
            "model": settings.gemini_model if settings.llm_provider == "gemini" else "mock",
        },
    }
