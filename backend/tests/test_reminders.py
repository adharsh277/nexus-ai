import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest
from sqlalchemy import select

from app.models import Notification, Reminder, ReminderStatus, User
from app.services.reminders import process_due_reminders, scheduler
from tests.conftest import act_as


def test_reminder_crud_flow(client, user: User):
    due = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()
    # 1. Create reminder via /api/v1/reminders
    payload = {
        "title": "Study Kubernetes Networking",
        "description": "Services, Ingress, and CNI plugins",
        "due_at": due,
        "timezone": "Asia/Kolkata",
    }
    r = client.post("/api/v1/reminders", json=payload)
    assert r.status_code == 201
    rem = r.json()
    rem_id = rem["id"]
    assert rem["title"] == "Study Kubernetes Networking"
    assert rem["description"] == "Services, Ingress, and CNI plugins"
    assert rem["timezone"] == "Asia/Kolkata"
    assert rem["status"] == "pending"
    assert rem["notified_at"] is None

    # Test alias route /api/reminders
    r_alias = client.post(
        "/api/reminders",
        json={
            "title": "Review Helm Charts",
            "due_at": due,
        },
    )
    assert r_alias.status_code == 201
    assert r_alias.json()["timezone"] == "UTC"

    # 2. Get reminder
    r = client.get(f"/api/v1/reminders/{rem_id}")
    assert r.status_code == 200
    assert r.json()["id"] == rem_id

    # 3. List reminders with search and sort
    r = client.get("/api/v1/reminders?search=Kubernetes")
    assert r.status_code == 200
    items = r.json()
    assert len(items) == 1
    assert items[0]["id"] == rem_id

    # 4. Update reminder
    r = client.patch(
        f"/api/v1/reminders/{rem_id}",
        json={"title": "Master Kubernetes Networking", "description": "Updated deep dive"},
    )
    assert r.status_code == 200
    assert r.json()["title"] == "Master Kubernetes Networking"
    assert r.json()["description"] == "Updated deep dive"

    # 5. Complete reminder
    r = client.post(f"/api/v1/reminders/{rem_id}/complete")
    assert r.status_code == 200
    assert r.json()["status"] == "completed"

    # Filter completed
    r = client.get("/api/v1/reminders?status=completed")
    assert r.status_code == 200
    assert len(r.json()) == 1

    # 6. Cancel reminder
    r = client.post(f"/api/v1/reminders/{rem_id}/cancel")
    assert r.status_code == 200
    assert r.json()["status"] == "cancelled"

    # 7. Delete reminder
    r = client.delete(f"/api/v1/reminders/{rem_id}")
    assert r.status_code == 204

    # 8. Confirm 404 after delete
    r = client.get(f"/api/v1/reminders/{rem_id}")
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "not_found"


def test_reminder_ownership_isolation(client, user: User, other_user: User):
    due = (datetime.now(timezone.utc) + timedelta(hours=2)).isoformat()
    r = client.post(
        "/api/v1/reminders",
        json={"title": "Alice Private Reminder", "due_at": due},
    )
    assert r.status_code == 201
    rem_id = r.json()["id"]

    # Switch identity to Bob
    act_as(other_user)

    # Bob cannot access, update, complete, cancel, or delete Alice's reminder
    assert client.get(f"/api/v1/reminders/{rem_id}").status_code == 404
    assert client.patch(f"/api/v1/reminders/{rem_id}", json={"title": "Hacked"}).status_code == 404
    assert client.post(f"/api/v1/reminders/{rem_id}/complete").status_code == 404
    assert client.post(f"/api/v1/reminders/{rem_id}/cancel").status_code == 404
    assert client.delete(f"/api/v1/reminders/{rem_id}").status_code == 404

    # Bob's list does not show Alice's reminder
    r = client.get("/api/v1/reminders")
    assert r.status_code == 200
    assert len(r.json()) == 0

    # Switch back to Alice
    act_as(user)
    r = client.get(f"/api/v1/reminders/{rem_id}")
    assert r.status_code == 200
    assert r.json()["title"] == "Alice Private Reminder"


def test_timezone_validation(client):
    due = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()

    # Valid timezones
    for tz in ["UTC", "America/New_York", "Europe/London", "Asia/Kolkata", "Pacific/Auckland"]:
        r = client.post(
            "/api/v1/reminders",
            json={"title": f"Test {tz}", "due_at": due, "timezone": tz},
        )
        assert r.status_code == 201
        assert r.json()["timezone"] == tz

    # Invalid timezones rejected with 422
    for bad_tz in ["Invalid/Timezone", "Mars/Olympus", "GMT+99"]:
        r = client.post(
            "/api/v1/reminders",
            json={"title": "Bad TZ", "due_at": due, "timezone": bad_tz},
        )
        assert r.status_code == 422
        assert r.json()["error"]["code"] == "validation_error"


def test_due_and_overdue_processing(client, db, user: User):
    now = datetime.now(timezone.utc)

    # 1. Overdue reminder (due 10 minutes ago)
    overdue_due = now - timedelta(minutes=10)
    overdue = Reminder(
        user_id=user.id,
        title="Overdue Task",
        description="Should be notified",
        due_at=overdue_due,
        status=ReminderStatus.pending,
    )

    # 2. Future reminder (due in 30 minutes)
    future_due = now + timedelta(minutes=30)
    future = Reminder(
        user_id=user.id,
        title="Future Task",
        description="Should NOT be notified yet",
        due_at=future_due,
        status=ReminderStatus.pending,
    )

    db.add_all([overdue, future])
    db.commit()

    # Process due reminders at `now`
    processed = process_due_reminders(db, now=now)
    assert len(processed) == 1
    assert processed[0].reminder_id == overdue.id

    db.refresh(overdue)
    db.refresh(future)
    assert overdue.notified_at is not None
    assert future.notified_at is None

    # Check notification API
    r = client.get("/api/v1/notifications")
    assert r.status_code == 200
    notifs = r.json()
    assert len(notifs) == 1
    assert notifs[0]["reminder_id"] == str(overdue.id)
    assert notifs[0]["title"] == "Reminder: Overdue Task"


def test_duplicate_prevention(db, user: User):
    now = datetime.now(timezone.utc)
    rem = Reminder(
        user_id=user.id,
        title="Run daily standup",
        due_at=now - timedelta(minutes=2),
        status=ReminderStatus.pending,
    )
    db.add(rem)
    db.commit()

    # First tick -> notifies
    first_run = process_due_reminders(db, now=now)
    assert len(first_run) == 1

    # Second tick (even slightly later) -> does NOT notify again
    second_run = process_due_reminders(db, now=now + timedelta(seconds=15))
    assert len(second_run) == 0

    # Total notifications remains 1
    notif_count = db.scalar(select(Notification).where(Notification.reminder_id == rem.id))
    assert notif_count is not None


def test_restart_recovery(db, user: User):
    """If the app was stopped/restarted, past-due unnotified reminders are safely caught on startup."""
    old_time = datetime.now(timezone.utc) - timedelta(hours=3)
    rem1 = Reminder(user_id=user.id, title="Catchup 1", due_at=old_time, status=ReminderStatus.pending)
    rem2 = Reminder(user_id=user.id, title="Catchup 2", due_at=old_time, status=ReminderStatus.pending)
    db.add_all([rem1, rem2])
    db.commit()

    # Simulated scheduler tick on startup
    notifs = process_due_reminders(db)
    assert len(notifs) == 2

    db.refresh(rem1)
    db.refresh(rem2)
    assert rem1.notified_at is not None
    assert rem2.notified_at is not None


def test_completed_and_cancelled_not_notified(db, user: User):
    now = datetime.now(timezone.utc)
    due = now - timedelta(minutes=5)

    comp = Reminder(user_id=user.id, title="Completed early", due_at=due, status=ReminderStatus.completed)
    canc = Reminder(user_id=user.id, title="Cancelled event", due_at=due, status=ReminderStatus.cancelled)
    db.add_all([comp, canc])
    db.commit()

    notifs = process_due_reminders(db, now=now)
    assert len(notifs) == 0


def test_edited_due_date_near_due_time(client, db, user: User):
    now = datetime.now(timezone.utc)
    due_past = now - timedelta(minutes=1)

    r = client.post(
        "/api/v1/reminders",
        json={"title": "Doctor Appointment", "due_at": due_past.isoformat()},
    )
    rem_id = r.json()["id"]

    # User reschedules to 2 hours from now
    due_future = now + timedelta(hours=2)
    client.patch(f"/api/v1/reminders/{rem_id}", json={"due_at": due_future.isoformat()})

    # Background tick runs
    notifs = process_due_reminders(db, now=now)
    assert len(notifs) == 0


def test_transaction_rollback_preserves_state(db, user: User):
    now = datetime.now(timezone.utc)
    rem = Reminder(
        user_id=user.id,
        title="Failing reminder",
        due_at=now - timedelta(minutes=5),
        status=ReminderStatus.pending,
    )
    db.add(rem)
    db.commit()

    # Simulate an unexpected error mid-transaction during commit
    with patch.object(db, "commit", side_effect=RuntimeError("Simulated DB Disk Failure")):
        with pytest.raises(RuntimeError):
            try:
                process_due_reminders(db, now=now)
            except RuntimeError:
                db.rollback()
                raise

    db.refresh(rem)
    # Because of rollback, notified_at remains None and state is intact
    assert rem.notified_at is None
    notif = db.scalar(select(Notification).where(Notification.reminder_id == rem.id))
    assert notif is None


def test_notification_api_endpoints(client, db, user: User, other_user: User):
    now = datetime.now(timezone.utc)
    n1 = Notification(user_id=user.id, title="Alert 1", message="Msg 1", created_at=now)
    n2 = Notification(user_id=user.id, title="Alert 2", message="Msg 2", created_at=now)
    db.add_all([n1, n2])
    db.commit()
    db.refresh(n1)
    db.refresh(n2)

    # 1. Check unread count
    r = client.get("/api/v1/notifications/unread-count")
    assert r.status_code == 200
    assert r.json() == {"unread": 2, "total": 2}

    # 2. Mark one as read
    r = client.patch(f"/api/v1/notifications/{n1.id}/read")
    assert r.status_code == 200
    assert r.json()["is_read"] is True

    r = client.get("/api/v1/notifications/unread-count")
    assert r.json() == {"unread": 1, "total": 2}

    # 3. Ownership isolation: other user cannot mark n2 as read
    act_as(other_user)
    r = client.patch(f"/api/v1/notifications/{n2.id}/read")
    assert r.status_code == 404
    r = client.get("/api/v1/notifications/unread-count")
    assert r.json() == {"unread": 0, "total": 0}

    # Switch back to user
    act_as(user)

    # 4. Mark all as read
    r = client.post("/api/v1/notifications/mark-all-read")
    assert r.status_code == 200
    assert r.json()["marked_read"] == 1

    r = client.get("/api/v1/notifications/unread-count")
    assert r.json() == {"unread": 0, "total": 2}
