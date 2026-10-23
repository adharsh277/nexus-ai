"""HTTP route handlers. Keep these thin; logic lives in app.services."""
from app.api import chat, documents, health, notifications, reminders, tasks

__all__ = ["chat", "documents", "health", "notifications", "reminders", "tasks"]

