"""Tests for Nexus AI agent tools.

Validates:
- All 7 tools registered and operational.
- Server-side context injection (never accepts user_id from arguments).
- Strict Pydantic argument validation (extra='forbid', length, boundaries).
- User ownership isolation across all operations.
- Confirmation boundary for destructive deletion.
- Grounded document Q&A with citations.
- Insufficient evidence handling when documents do not contain answers.
- Untrusted document content safety.
"""
import uuid
from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from app.agent.tools import (
    AskDocumentsInput,
    CompleteReminderInput,
    CreateReminderInput,
    DeleteReminderInput,
    ListRemindersInput,
    SearchDocumentsInput,
    UpdateReminderInput,
    handle_ask_documents,
    handle_complete_reminder,
    handle_create_reminder,
    handle_delete_reminder,
    handle_list_reminders,
    handle_search_documents,
    handle_update_reminder,
)
from app.models import Document, DocumentChunk, DocumentStatus, Reminder, ReminderStatus
from app.services.llm import ToolContext, tool_registry


def test_tool_registry_registration():
    """Verify that all 7 Phase 2 tools are properly registered with schemas and handlers."""
    expected_tools = {
        "create_reminder",
        "list_reminders",
        "update_reminder",
        "complete_reminder",
        "delete_reminder",
        "search_documents",
        "ask_documents",
    }
    registered = {t.name for t in tool_registry.list_tools()}
    assert expected_tools.issubset(registered)

    for tool_name in expected_tools:
        tool = tool_registry.get(tool_name)
        assert tool is not None
        assert tool.description
        assert tool.input_model is not None
        assert tool.handler is not None


def test_server_side_user_id_enforcement_and_extra_fields_forbidden(db, user, other_user):
    """Ensure user_id is injected strictly from server context and model arguments cannot inject or override it."""
    context = ToolContext(user_id=user.id, db=db)

    # 1. Pydantic validation rejects extra fields like user_id
    with pytest.raises(ValidationError) as exc:
        CreateReminderInput(
            title="Sneaky reminder",
            due_at="2026-10-28T10:00:00Z",
            user_id=str(other_user.id),  # Malicious argument
        )
    assert "extra_forbidden" in str(exc.value)

    # 2. ToolRegistry.execute safely handles extra fields and returns error instead of crashing
    res = tool_registry.execute(
        "create_reminder",
        context,
        {
            "title": "Sneaky reminder",
            "due_at": "2026-10-28T10:00:00Z",
            "user_id": str(other_user.id),
        },
    )
    assert "error" in res
    assert "Invalid arguments" in res["error"]


def test_create_reminder_tool(db, user):
    """Verify successful reminder creation via tool handler and tool registry execution."""
    context = ToolContext(user_id=user.id, db=db)

    args = CreateReminderInput(
        title="Team Sync",
        due_at="2026-10-28T14:30:00Z",
        description="Weekly engineering standup",
        timezone="UTC",
    )
    result = handle_create_reminder(context, args)
    assert result["status"] == "success"
    assert result["reminder"]["title"] == "Team Sync"
    assert result["reminder"]["status"] == "pending"

    # Verify persisted in database under user.id
    reminder_id = uuid.UUID(result["reminder"]["id"])
    db_reminder = db.get(Reminder, reminder_id)
    assert db_reminder is not None
    assert db_reminder.user_id == user.id
    assert db_reminder.title == "Team Sync"


def test_list_reminders_tool_and_user_isolation(db, user, other_user):
    """Verify list_reminders filters and strict user isolation."""
    # Create reminders for user
    r1 = Reminder(
        user_id=user.id,
        title="User Reminder 1",
        due_at=datetime(2026, 10, 28, 10, 0, tzinfo=timezone.utc),
        status=ReminderStatus.pending,
    )
    r2 = Reminder(
        user_id=user.id,
        title="User Reminder 2",
        due_at=datetime(2026, 10, 29, 10, 0, tzinfo=timezone.utc),
        status=ReminderStatus.completed,
    )
    # Create reminder for other_user
    r_other = Reminder(
        user_id=other_user.id,
        title="Bob Private Reminder",
        due_at=datetime(2026, 10, 28, 12, 0, tzinfo=timezone.utc),
        status=ReminderStatus.pending,
    )
    db.add_all([r1, r2, r_other])
    db.commit()

    context = ToolContext(user_id=user.id, db=db)

    # 1. List all for user (Bob's reminder must NOT be included)
    res = handle_list_reminders(context, ListRemindersInput())
    assert res["status"] == "success"
    assert res["count"] == 2
    titles = [r["title"] for r in res["reminders"]]
    assert "User Reminder 1" in titles
    assert "User Reminder 2" in titles
    assert "Bob Private Reminder" not in titles

    # 2. Filter by status
    res_pending = handle_list_reminders(
        context, ListRemindersInput(status=ReminderStatus.pending)
    )
    assert res_pending["count"] == 1
    assert res_pending["reminders"][0]["title"] == "User Reminder 1"

    # 3. Filter by search query
    res_search = handle_list_reminders(context, ListRemindersInput(search="Reminder 2"))
    assert res_search["count"] == 1
    assert res_search["reminders"][0]["title"] == "User Reminder 2"


def test_update_and_complete_reminder_tools(db, user, other_user):
    """Verify updating and completing reminders, plus cross-user protection."""
    r_user = Reminder(
        user_id=user.id,
        title="Initial Title",
        due_at=datetime(2026, 10, 28, 10, 0, tzinfo=timezone.utc),
        status=ReminderStatus.pending,
    )
    r_bob = Reminder(
        user_id=other_user.id,
        title="Bob's Reminder",
        due_at=datetime(2026, 10, 28, 10, 0, tzinfo=timezone.utc),
        status=ReminderStatus.pending,
    )
    db.add_all([r_user, r_bob])
    db.commit()

    context = ToolContext(user_id=user.id, db=db)

    # 1. Successful update
    res_up = handle_update_reminder(
        context,
        UpdateReminderInput(reminder_id=str(r_user.id), title="Updated Title"),
    )
    assert res_up["status"] == "success"
    assert res_up["reminder"]["title"] == "Updated Title"

    # 2. Cross-user isolation: cannot update Bob's reminder
    res_cross = handle_update_reminder(
        context,
        UpdateReminderInput(reminder_id=str(r_bob.id), title="Hacked"),
    )
    assert "error" in res_cross
    assert "not found" in res_cross["error"].lower()

    # 3. Complete user's reminder
    res_comp = handle_complete_reminder(
        context, CompleteReminderInput(reminder_id=str(r_user.id))
    )
    assert res_comp["status"] == "success"
    db.refresh(r_user)
    assert r_user.status == ReminderStatus.completed

    # 4. Cross-user isolation on complete
    res_comp_bob = handle_complete_reminder(
        context, CompleteReminderInput(reminder_id=str(r_bob.id))
    )
    assert "error" in res_comp_bob
    assert "not found" in res_comp_bob["error"].lower()


def test_delete_reminder_confirmation_boundary(db, user, other_user):
    """Verify destructive delete_reminder requires explicit confirm=True."""
    reminder = Reminder(
        user_id=user.id,
        title="Delete Me",
        due_at=datetime(2026, 10, 28, 10, 0, tzinfo=timezone.utc),
        status=ReminderStatus.pending,
    )
    db.add(reminder)
    db.commit()

    context = ToolContext(user_id=user.id, db=db)

    # 1. Unconfirmed call must NOT delete the reminder
    res_unconfirmed = handle_delete_reminder(
        context, DeleteReminderInput(reminder_id=str(reminder.id), confirm=False)
    )
    assert res_unconfirmed["status"] == "confirmation_required"
    assert "confirm" in res_unconfirmed["message"].lower()

    # Verify still in DB
    assert db.get(Reminder, reminder.id) is not None

    # 2. Confirmed call deletes the reminder
    res_confirmed = handle_delete_reminder(
        context, DeleteReminderInput(reminder_id=str(reminder.id), confirm=True)
    )
    assert res_confirmed["status"] == "success"
    assert res_confirmed["action"] == "delete_reminder"

    # Verify deleted from DB
    assert db.get(Reminder, reminder.id) is None


def test_search_documents_tool_and_untrusted_wrapping(db, user, other_user):
    """Verify search_documents returns untrusted content delimiters and isolates users."""
    doc_user = Document(
        user_id=user.id,
        filename="notes.pdf",
        original_filename="engineering_notes.pdf",
        mime_type="application/pdf",
        file_size=1024,
        status=DocumentStatus.processed,
    )
    doc_bob = Document(
        user_id=other_user.id,
        filename="secret.pdf",
        original_filename="bob_secret.pdf",
        mime_type="application/pdf",
        file_size=1024,
        status=DocumentStatus.processed,
    )
    db.add_all([doc_user, doc_bob])
    db.commit()

    from app.services.embeddings import get_embedding_provider
    provider = get_embedding_provider()
    user_emb = provider.embed_text("graviton pulses")
    bob_emb = provider.embed_text("financial records")

    chunk_user = DocumentChunk(
        document_id=doc_user.id,
        user_id=user.id,
        chunk_index=0,
        page_number=2,
        content="Antigravity uses high frequency graviton pulses.",
        embedding=user_emb,
    )
    chunk_bob = DocumentChunk(
        document_id=doc_bob.id,
        user_id=other_user.id,
        chunk_index=0,
        page_number=1,
        content="Bob's private financial records.",
        embedding=bob_emb,
    )
    db.add_all([chunk_user, chunk_bob])
    db.commit()

    context = ToolContext(user_id=user.id, db=db)

    res = handle_search_documents(
        context, SearchDocumentsInput(query="graviton pulses", top_k=5)
    )
    assert res["status"] == "success"
    assert res["count"] == 1
    result_item = res["results"][0]
    assert result_item["document_name"] == "engineering_notes.pdf"
    assert result_item["page_number"] == 2
    # Verify wrapped in untrusted data tag
    assert "<untrusted_document_content" in result_item["content"]
    assert "Antigravity uses high frequency graviton pulses." in result_item["content"]

    # Bob's private document is never returned to user
    contents = [r["content"] for r in res["results"]]
    assert not any("Bob" in c for c in contents)


def test_ask_documents_grounded_answer_with_citations(db, user):
    """Verify ask_documents returns grounded answer with exact document and page citations."""
    doc = Document(
        user_id=user.id,
        filename="handbook.pdf",
        original_filename="Employee_Handbook_2026.pdf",
        mime_type="application/pdf",
        file_size=2048,
        status=DocumentStatus.processed,
    )
    db.add(doc)
    db.commit()

    from app.services.embeddings import get_embedding_provider
    provider = get_embedding_provider()
    embedding = provider.embed_text("How many days of paid leave do employees get?")

    chunk = DocumentChunk(
        document_id=doc.id,
        user_id=user.id,
        chunk_index=1,
        page_number=14,
        content="Employees are granted 25 days of annual paid leave.",
        embedding=embedding,
    )
    db.add(chunk)
    db.commit()

    context = ToolContext(user_id=user.id, db=db)
    res = handle_ask_documents(
        context, AskDocumentsInput(question="How many days of paid leave do employees get?")
    )
    assert res["evidence_found"] is True
    assert len(res["citations"]) > 0
    assert "[Document: Employee_Handbook_2026.pdf, Page: 14]" in res["citations"][0]
    assert "25 days of annual paid leave" in res["answer"]
    assert "[Document: Employee_Handbook_2026.pdf, Page: 14]" in res["answer"]


def test_ask_documents_insufficient_evidence(db, user):
    """Verify ask_documents returns explicit insufficient evidence notice when no chunks match."""
    context = ToolContext(user_id=user.id, db=db)

    # Empty document store
    res = handle_ask_documents(
        context, AskDocumentsInput(question="What is the nuclear launch code?")
    )
    assert res["evidence_found"] is False
    assert res["citations"] == []
    assert "could not find any relevant information" in res["answer"].lower()
