"""
Chat routes.

Note on prefix: these live under the same /api/v1 prefix as every other
route in this app (see main.py / core/config.py's api_v1_prefix), i.e.
/api/v1/chats, not the unprefixed /api/chats. This is a deliberate
consistency choice — every other endpoint in the app uses /api/v1, and
introducing a second, differently-prefixed API surface would be a real
inconsistency for no functional benefit. The frontend API client is
written against /api/v1/chats accordingly.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.dependencies import get_db
from app.models.schemas import (
    ChatDetail, ChatSummary, CreateChatRequest, PinChatRequest, RenameChatRequest, SendMessageRequest,
    SendMessageResponse,
)
from app.services import chat_service

router = APIRouter(prefix="/chats", tags=["chats"])


@router.post("", response_model=ChatSummary, status_code=201)
async def create_chat(request: CreateChatRequest, db: Session = Depends(get_db)):
    return chat_service.create_chat(db, title=request.title)


@router.get("", response_model=list[ChatSummary])
async def list_chats(db: Session = Depends(get_db)):
    return chat_service.list_chats(db)


@router.get("/{chat_id}", response_model=ChatDetail)
async def get_chat(chat_id: str, db: Session = Depends(get_db)):
    return chat_service.get_chat(db, chat_id)


@router.delete("/{chat_id}")
async def delete_chat(chat_id: str, db: Session = Depends(get_db)):
    chat_service.delete_chat(db, chat_id)
    return {"status": "deleted", "chat_id": chat_id}


@router.patch("/{chat_id}/pin", response_model=ChatSummary)
async def set_pin(chat_id: str, request: PinChatRequest, db: Session = Depends(get_db)):
    return chat_service.set_chat_pinned(db, chat_id, request.pinned)


@router.patch("/{chat_id}", response_model=ChatSummary)
async def rename_chat(chat_id: str, request: RenameChatRequest, db: Session = Depends(get_db)):
    return chat_service.rename_chat(db, chat_id, request.title)


@router.post("/{chat_id}/duplicate", response_model=ChatSummary, status_code=201)
async def duplicate_chat(chat_id: str, db: Session = Depends(get_db)):
    return chat_service.duplicate_chat(db, chat_id)


@router.post("/{chat_id}/messages", response_model=SendMessageResponse)
async def send_message(chat_id: str, request: SendMessageRequest, db: Session = Depends(get_db)):
    result = chat_service.send_message(
        db, chat_id, request.content, top_k=request.top_k, include_retrieval_debug=request.include_retrieval_debug
    )
    return SendMessageResponse(
        user_message=result.user_message, assistant_message=result.assistant_message, chat=result.chat
    )
