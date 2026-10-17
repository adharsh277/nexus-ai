from datetime import datetime, timedelta, timezone

from tests.conftest import act_as


def iso(dt: datetime) -> str:
    return dt.isoformat()


def test_health_ok(client):
    r = client.get("/api/health")
    data = r.json()
    assert data["status"] == "ok"
    assert data["database"] == "ok"
    assert "llm" in data


def test_task_crud(client):
    due = datetime.now(timezone.utc) + timedelta(days=2)
    r = client.post("/api/tasks", json={"title": "  Buy milk  ", "due_date": iso(due)})
    assert r.status_code == 201
    task = r.json()
    assert task["title"] == "Buy milk"
    assert task["status"] == "pending"
    assert task["completed_at"] is None

    r = client.get(f"/api/tasks/{task['id']}")
    assert r.status_code == 200

    r = client.patch(f"/api/tasks/{task['id']}", json={"description": "2 litres"})
    assert r.status_code == 200
    assert r.json()["description"] == "2 litres"
    assert r.json()["title"] == "Buy milk"

    assert len(client.get("/api/tasks").json()) == 1

    r = client.delete(f"/api/tasks/{task['id']}")
    assert r.status_code == 204
    r = client.get(f"/api/tasks/{task['id']}")
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "not_found"


def test_complete_flow_and_filter(client):
    a = client.post("/api/tasks", json={"title": "A"}).json()
    client.post("/api/tasks", json={"title": "B"})

    r = client.post(f"/api/tasks/{a['id']}/complete")
    assert r.status_code == 200
    assert r.json()["status"] == "completed"
    assert r.json()["completed_at"] is not None

    pending = client.get("/api/tasks", params={"status": "pending"}).json()
    completed = client.get("/api/tasks", params={"status": "completed"}).json()
    assert [t["title"] for t in pending] == ["B"]
    assert [t["title"] for t in completed] == ["A"]

    # Reopen via PATCH clears completed_at
    r = client.patch(f"/api/tasks/{a['id']}", json={"status": "pending"})
    assert r.json()["completed_at"] is None


def test_sort_by_due_date(client):
    now = datetime.now(timezone.utc)
    client.post("/api/tasks", json={"title": "later", "due_date": iso(now + timedelta(days=3))})
    client.post("/api/tasks", json={"title": "none"})
    client.post("/api/tasks", json={"title": "soon", "due_date": iso(now + timedelta(days=1))})
    titles = [t["title"] for t in client.get("/api/tasks").json()]
    assert titles == ["soon", "later", "none"]


def test_validation_errors(client):
    for payload in (
        {"title": ""},
        {"title": "   "},
        {"title": "x" * 201},
        {"title": "ok", "due_date": "not-a-date"},
        {"title": "ok", "due_date": "2026-13-45"},
        {"title": "ok", "unknown": 1},
        {},
    ):
        r = client.post("/api/tasks", json=payload)
        assert r.status_code == 422, payload
        body = r.json()["error"]
        assert body["code"] == "validation_error"
        assert body["details"]

    t = client.post("/api/tasks", json={"title": "ok"}).json()
    assert client.patch(f"/api/tasks/{t['id']}", json={"status": "done"}).status_code == 422
    assert client.patch(f"/api/tasks/{t['id']}", json={"title": None}).status_code == 422
    assert client.get("/api/tasks", params={"status": "bogus"}).status_code == 422
    assert client.get("/api/tasks/not-a-uuid").status_code == 422


def test_ownership_isolation(client, user, other_user):
    task = client.post("/api/tasks", json={"title": "Alice's secret"}).json()

    act_as(other_user)
    assert client.get("/api/tasks").json() == []
    assert client.get(f"/api/tasks/{task['id']}").status_code == 404
    assert client.patch(f"/api/tasks/{task['id']}", json={"title": "hacked"}).status_code == 404
    assert client.post(f"/api/tasks/{task['id']}/complete").status_code == 404
    assert client.delete(f"/api/tasks/{task['id']}").status_code == 404
    assert client.get("/api/dashboard").json()["counts"]["pending"] == 0

    act_as(user)
    r = client.get(f"/api/tasks/{task['id']}")
    assert r.status_code == 200
    assert r.json()["title"] == "Alice's secret"
    assert r.json()["status"] == "pending"


def test_dashboard_counts(client):
    now = datetime.now(timezone.utc)
    client.post("/api/tasks", json={"title": "overdue", "due_date": iso(now - timedelta(days=1))})
    client.post("/api/tasks", json={"title": "today", "due_date": iso(now + timedelta(minutes=1))})
    for i in range(6):
        client.post("/api/tasks", json={"title": f"up{i}", "due_date": iso(now + timedelta(days=2 + i))})
    client.post("/api/tasks", json={"title": "no date"})
    done = client.post("/api/tasks", json={"title": "done"}).json()
    client.post(f"/api/tasks/{done['id']}/complete")

    # Choose an offset that makes the local time ~noon, so "now + 1 min" is safely "today".
    offset = (12 - now.hour) * 60 - now.minute

    r = client.get("/api/dashboard", params={"tz_offset_minutes": offset})
    assert r.status_code == 200
    data = r.json()
    assert data["counts"] == {"pending": 9, "completed": 1, "overdue": 1}
    assert "today" in [t["title"] for t in data["due_today"]]
    assert [t["title"] for t in data["upcoming"]] == ["today", "up0", "up1", "up2", "up3"]
