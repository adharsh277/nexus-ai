from app.services.llm import MockProvider, override_llm_provider
from tests.conftest import act_as


def test_chat_flow(client):
    # 1. Create a conversation
    conv = client.post("/api/conversations", json={}).json()
    assert conv["title"] == "New conversation"

    # 2. Send message
    r = client.post(f"/api/conversations/{conv['id']}/messages", json={"content": "Hello Nexus"})
    assert r.status_code == 201
    body = r.json()
    assert body["user_message"]["role"] == "user"
    assert body["user_message"]["content"] == "Hello Nexus"
    assert body["assistant_message"]["role"] == "assistant"
    assert "Mock AI Echo: Hello Nexus" in body["assistant_message"]["content"]

    # 3. List messages in order
    msgs = client.get(f"/api/conversations/{conv['id']}/messages").json()
    assert len(msgs) == 2
    assert [m["role"] for m in msgs] == ["user", "assistant"]

    # 4. Check conversation was auto-titled
    convs = client.get("/api/conversations").json()
    assert convs[0]["title"] == "Hello Nexus"


def test_chat_validation_and_isolation(client, other_user):
    conv = client.post("/api/conversations").json()

    # Empty whitespace input is rejected with 422
    r = client.post(f"/api/conversations/{conv['id']}/messages", json={"content": "   "})
    assert r.status_code == 422

    # User isolation: other_user cannot see or write to this conversation
    act_as(other_user)
    assert client.get("/api/conversations").json() == []
    assert client.get(f"/api/conversations/{conv['id']}/messages").status_code == 404
    r = client.post(f"/api/conversations/{conv['id']}/messages", json={"content": "intruder"})
    assert r.status_code == 404


def test_delete_conversation(client, other_user):
    conv = client.post("/api/conversations", json={}).json()
    conv_id = conv["id"]

    # Delete existing conversation
    r = client.delete(f"/api/conversations/{conv_id}")
    assert r.status_code == 204

    # Verify 404 on subsequent get
    assert client.get(f"/api/conversations/{conv_id}/messages").status_code == 404

    # Other user cannot delete a non-owned conversation
    act_as(other_user)
    assert client.delete(f"/api/conversations/{conv_id}").status_code == 404



def test_chat_rate_limit_error_handling(client):
    """Verify rate limit errors from LLM return a graceful assistant message without crashing."""
    override_llm_provider(MockProvider(simulate_error="rate_limit"))

    conv = client.post("/api/conversations", json={}).json()
    r = client.post(f"/api/conversations/{conv['id']}/messages", json={"content": "High traffic test"})
    assert r.status_code == 201
    body = r.json()
    assert "too many requests" in body["assistant_message"]["content"].lower()

    # Verify messages are still persisted
    msgs = client.get(f"/api/conversations/{conv['id']}/messages").json()
    assert len(msgs) == 2


def test_chat_auth_error_handling(client):
    """Verify provider auth error (e.g. invalid key) returns friendly message."""
    override_llm_provider(MockProvider(simulate_error="auth"))

    conv = client.post("/api/conversations", json={}).json()
    r = client.post(f"/api/conversations/{conv['id']}/messages", json={"content": "Test auth failure"})
    assert r.status_code == 201
    body = r.json()
    assert "temporarily unavailable" in body["assistant_message"]["content"].lower()


def test_chat_timeout_error_handling(client):
    """Verify provider timeout error returns friendly message."""
    override_llm_provider(MockProvider(simulate_error="timeout"))

    conv = client.post("/api/conversations", json={}).json()
    r = client.post(f"/api/conversations/{conv['id']}/messages", json={"content": "Test timeout"})
    assert r.status_code == 201
    body = r.json()
    assert "longer than expected" in body["assistant_message"]["content"].lower()


def test_chat_unavailable_error_handling(client):
    """Verify service unavailable error returns friendly message."""
    override_llm_provider(MockProvider(simulate_error="unavailable"))

    conv = client.post("/api/conversations", json={}).json()
    r = client.post(f"/api/conversations/{conv['id']}/messages", json={"content": "Test unavailable"})
    assert r.status_code == 201
    body = r.json()
    assert "error communicating with the ai service" in body["assistant_message"]["content"].lower()
