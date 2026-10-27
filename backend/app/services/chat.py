import logging
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.models import Conversation, Message, MessageRole
from app.services import NotFoundError
from app.services.llm import (
    LLMAuthError,
    LLMError,
    LLMMessage,
    LLMRateLimitError,
    LLMTimeoutError,
    LLMUnavailableError,
    get_llm_provider,
)

logger = logging.getLogger("nexus.services.chat")

SYSTEM_PROMPT = (
    "You are Nexus, an intelligent, helpful, and concise personal AI assistant. "
    "Provide clear, direct, and well-structured responses. Use markdown formatting when appropriate."
)


def list_conversations(db: Session, user_id: uuid.UUID) -> list[Conversation]:
    stmt = (
        select(Conversation)
        .where(Conversation.user_id == user_id)
        .order_by(Conversation.created_at.desc())
    )
    return list(db.scalars(stmt))


def create_conversation(db: Session, user_id: uuid.UUID, title: str | None = None) -> Conversation:
    conversation = Conversation(user_id=user_id, title=title or "New conversation")
    db.add(conversation)
    db.commit()
    db.refresh(conversation)
    return conversation


def get_conversation(db: Session, user_id: uuid.UUID, conversation_id: uuid.UUID) -> Conversation:
    conversation = db.scalar(
        select(Conversation).where(
            Conversation.id == conversation_id, Conversation.user_id == user_id
        )
    )
    if conversation is None:
        raise NotFoundError("Conversation")
    return conversation


def list_messages(db: Session, user_id: uuid.UUID, conversation_id: uuid.UUID) -> list[Message]:
    get_conversation(db, user_id, conversation_id)
    stmt = (
        select(Message)
        .where(Message.conversation_id == conversation_id, Message.user_id == user_id)
        .order_by(Message.created_at, Message.id)
    )
    return list(db.scalars(stmt))


def get_bounded_history(
    db: Session, user_id: uuid.UUID, conversation_id: uuid.UUID, limit: int
) -> list[Message]:
    """Retrieve the latest `limit` messages in chronological order for bounded prompt context."""
    subq = (
        select(Message)
        .where(Message.conversation_id == conversation_id, Message.user_id == user_id)
        .order_by(Message.created_at.desc(), Message.id.desc())
        .limit(limit)
        .subquery()
    )
    stmt = select(Message).from_statement(
        select(subq).order_by(subq.c.created_at.asc(), subq.c.id.asc())
    )
    return list(db.scalars(stmt))


from app.agent.orchestrator import default_orchestrator


def generate_reply(
    history_messages: list[Message],
    user_content: str,
    db: Session | None = None,
    user_id: uuid.UUID | None = None,
    conversation_id: uuid.UUID | None = None,
) -> str:
    """Generate an AI response using the agent orchestrator (with tools) or direct LLM fallback."""
    if db is not None and user_id is not None:
        return default_orchestrator.run(
            db=db,
            user_id=user_id,
            history_messages=history_messages,
            user_content=user_content,
            conversation_id=conversation_id,
        )

    llm_messages: list[LLMMessage] = []
    for m in history_messages:
        role = "user" if m.role == MessageRole.user else "assistant"
        llm_messages.append(LLMMessage(role=role, content=m.content))

    llm_messages.append(LLMMessage(role="user", content=user_content))

    provider = get_llm_provider()
    try:
        response = provider.generate_reply(llm_messages, system_prompt=SYSTEM_PROMPT)
        return response.content

    except LLMRateLimitError as exc:
        logger.warning("LLM rate limit encountered: %s", exc)
        return "I am currently receiving too many requests. Please wait a moment and try again."

    except LLMAuthError as exc:
        logger.error("LLM auth error: %s", exc)
        return "The AI assistant is temporarily unavailable due to a service configuration issue."

    except LLMTimeoutError as exc:
        logger.warning("LLM timeout: %s", exc)
        return "Thinking took a bit longer than expected. Please retry your message."

    except (LLMUnavailableError, LLMError) as exc:
        logger.warning("LLM error: %s", exc)
        return "I encountered an error communicating with the AI service. Please try again in a moment."

    except Exception as exc:
        logger.exception("Unexpected error while generating AI reply: %s", type(exc).__name__)
        return "An unexpected error occurred while processing your request. Please try again."


def send_message(
    db: Session, user_id: uuid.UUID, conversation_id: uuid.UUID, content: str
) -> tuple[Message, Message]:
    conversation = get_conversation(db, user_id, conversation_id)
    now = datetime.now(timezone.utc)

    # Fetch bounded history before adding the new message
    history = get_bounded_history(
        db, user_id, conversation_id, limit=settings.llm_max_history_messages
    )

    # 1. Persist User Message
    user_msg = Message(
        conversation_id=conversation.id,
        user_id=user_id,
        role=MessageRole.user,
        content=content,
        created_at=now,
    )
    db.add(user_msg)

    # Name untitled conversations after their first message
    if conversation.title == "New conversation":
        conversation.title = content[:60].strip()

    # 2. Generate Reply via Orchestrator with Tools
    reply_content = generate_reply(
        history,
        content,
        db=db,
        user_id=user_id,
        conversation_id=conversation_id,
    )

    # 3. Persist Assistant Message
    assistant_msg = Message(
        conversation_id=conversation.id,
        user_id=user_id,
        role=MessageRole.assistant,
        content=reply_content,
        created_at=now + timedelta(milliseconds=1),
    )
    db.add(assistant_msg)
    db.commit()
    db.refresh(user_msg)
    db.refresh(assistant_msg)

    return user_msg, assistant_msg

