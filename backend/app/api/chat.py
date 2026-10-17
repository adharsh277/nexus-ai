import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import User
from app.schemas.chat import (
    ChatExchange,
    ConversationCreate,
    ConversationRead,
    MessageCreate,
    MessageRead,
)
from app.security import get_current_user
from app.services import chat as chat_service

router = APIRouter(tags=["chat"])


@router.get("/conversations", response_model=list[ConversationRead])
def list_conversations(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return chat_service.list_conversations(db, user.id)


@router.post("/conversations", response_model=ConversationRead, status_code=status.HTTP_201_CREATED)
def create_conversation(
    data: ConversationCreate | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return chat_service.create_conversation(db, user.id, data.title if data else None)


@router.get("/conversations/{conversation_id}/messages", response_model=list[MessageRead])
def list_messages(
    conversation_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return chat_service.list_messages(db, user.id, conversation_id)


@router.post(
    "/conversations/{conversation_id}/messages",
    response_model=ChatExchange,
    status_code=status.HTTP_201_CREATED,
)
def send_message(
    conversation_id: uuid.UUID,
    data: MessageCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    user_msg, assistant_msg = chat_service.send_message(db, user.id, conversation_id, data.content)
    return {"user_message": user_msg, "assistant_message": assistant_msg}
