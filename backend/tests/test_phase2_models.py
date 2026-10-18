import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy import select

from app.models import (
    Document,
    DocumentChunk,
    DocumentStatus,
    Notification,
    Reminder,
    ReminderStatus,
    User,
)


def test_reminder_crud_and_relationships(db, user: User):
    due = datetime.now(timezone.utc)
    reminder = Reminder(
        user_id=user.id,
        title="Study Kubernetes",
        description="Chapter 4: Pods & Deployments",
        due_at=due,
        timezone="Asia/Kolkata",
    )
    db.add(reminder)
    db.commit()
    db.refresh(reminder)

    assert reminder.id is not None
    assert reminder.status == ReminderStatus.pending
    assert reminder.title == "Study Kubernetes"
    assert reminder.timezone == "Asia/Kolkata"
    assert reminder.notified_at is None
    assert reminder.created_at is not None

    # Update reminder
    reminder.status = ReminderStatus.completed
    reminder.notified_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(reminder)
    assert reminder.status == ReminderStatus.completed
    assert reminder.notified_at is not None


def test_notification_creation_and_cascade(db, user: User):
    reminder = Reminder(
        user_id=user.id,
        title="Review PR",
        due_at=datetime.now(timezone.utc),
    )
    db.add(reminder)
    db.commit()
    db.refresh(reminder)

    notification = Notification(
        user_id=user.id,
        reminder_id=reminder.id,
        title="Reminder Due",
        message="Review PR is now due!",
    )
    db.add(notification)
    db.commit()
    db.refresh(notification)

    assert notification.id is not None
    assert notification.is_read is False
    assert notification.reminder_id == reminder.id
    assert len(reminder.notifications) == 1

    # Cascade delete reminder -> notification deleted
    db.delete(reminder)
    db.commit()

    saved_notif = db.scalar(select(Notification).where(Notification.id == notification.id))
    assert saved_notif is None


def test_document_and_chunks_lifecycle(db, user: User):
    doc = Document(
        user_id=user.id,
        filename="abc-123.pdf",
        original_filename="Kubernetes_Notes.pdf",
        mime_type="application/pdf",
        file_size=1024,
        status=DocumentStatus.uploaded,
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)

    assert doc.id is not None
    assert doc.status == DocumentStatus.uploaded

    # Add chunk with 768-dim vector
    dummy_embedding = [0.05] * 768
    chunk = DocumentChunk(
        document_id=doc.id,
        user_id=user.id,
        chunk_index=0,
        page_number=1,
        content="Kubernetes pods represent the smallest deployable units.",
        embedding=dummy_embedding,
    )
    db.add(chunk)
    db.commit()
    db.refresh(chunk)

    assert chunk.id is not None
    assert chunk.chunk_index == 0
    assert chunk.page_number == 1
    assert chunk.document.id == doc.id
    if chunk.embedding is not None:
        assert len(chunk.embedding) == 768

    # Cascade delete document -> chunk deleted
    db.delete(doc)
    db.commit()

    saved_chunk = db.scalar(select(DocumentChunk).where(DocumentChunk.id == chunk.id))
    assert saved_chunk is None


def test_user_cascade_deletes_all_phase2_entities(db):
    u = User(email="cascade@nexus.ai", display_name="Cascade User")
    db.add(u)
    db.commit()
    db.refresh(u)

    rem = Reminder(user_id=u.id, title="Temp reminder", due_at=datetime.now(timezone.utc))
    doc = Document(
        user_id=u.id,
        filename="temp.txt",
        original_filename="temp.txt",
        mime_type="text/plain",
        file_size=10,
    )
    db.add_all([rem, doc])
    db.commit()

    rem_id = rem.id
    doc_id = doc.id

    db.delete(u)
    db.commit()

    assert db.scalar(select(Reminder).where(Reminder.id == rem_id)) is None
    assert db.scalar(select(Document).where(Document.id == doc_id)) is None
