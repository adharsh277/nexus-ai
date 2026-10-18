"""HTTP route handlers. Keep these thin; logic lives in app.services."""
from app.api import chat, health, notifications, reminders, tasks

__all__ = ["chat", "health", "notifications", "reminders", "tasks"]
