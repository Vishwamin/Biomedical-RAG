"""
Chat persistence service: CRUD for chats and messages, plus the
send-message flow that runs a question through the shared RAG pipeline
and persists both the user and assistant messages with full retrieval/
citation/claim/confidence data attached.

Opening an existing chat NEVER reruns retrieval or generation — it only
reads back what's already in `messages`. Persisting the full response
shape (not just answer text) at message-creation time is what makes that
possible.
"""

import json
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.core.exceptions import BioRAGException
from app.models.database import ChatRecord, MessageRecord
from app.models.schemas import (
    ChatDetail, ChatSummary, ClaimSchema, ConfidenceBreakdownSchema, GenerationCitation, MessageSchema,
    QueryResponse, RetrievalDebugResponse,
)
from app.services.chat_titles import generate_chat_title
from app.services.rag_pipeline import execute_rag_query


class ChatNotFoundError(BioRAGException):
    status_code = 404
    error_code = "chat_not_found"


def _new_chat_id() -> str:
    return f"chat_{uuid.uuid4().hex[:12]}"


def _new_message_id() -> str:
    return f"msg_{uuid.uuid4().hex[:12]}"


def _chat_to_summary(record: ChatRecord) -> ChatSummary:
    return ChatSummary(
        id=record.id, title=record.title, pinned=record.pinned,
        created_at=record.created_at, updated_at=record.updated_at,
    )


def _message_to_schema(record: MessageRecord) -> MessageSchema:
    return MessageSchema(
        id=record.id, chat_id=record.chat_id, role=record.role, content=record.content,
        confidence=record.confidence, confidence_label=record.confidence_label,
        confidence_breakdown=(
            ConfidenceBreakdownSchema(**json.loads(record.confidence_breakdown_json))
            if record.confidence_breakdown_json else None
        ),
        insufficient_evidence=record.insufficient_evidence,
        citations=(
            [GenerationCitation(**c) for c in json.loads(record.citations_json)] if record.citations_json else []
        ),
        claims=([ClaimSchema(**c) for c in json.loads(record.claims_json)] if record.claims_json else []),
        sources=(json.loads(record.sources_json) if record.sources_json else []),
        retrieval_debug=(
            RetrievalDebugResponse(**json.loads(record.retrieval_json)) if record.retrieval_json else None
        ),
        processing_latency_ms=(json.loads(record.latency_json) if record.latency_json else None),
        created_at=record.created_at,
    )


def create_chat(db: Session, title: str | None = None) -> ChatSummary:
    record = ChatRecord(id=_new_chat_id(), title=title or "New Chat", pinned=False)
    db.add(record)
    db.commit()
    db.refresh(record)
    return _chat_to_summary(record)


def list_chats(db: Session) -> list[ChatSummary]:
    # Pinned first, then newest-updated first within each group.
    records = db.query(ChatRecord).order_by(ChatRecord.pinned.desc(), ChatRecord.updated_at.desc()).all()
    return [_chat_to_summary(r) for r in records]


def get_chat(db: Session, chat_id: str) -> ChatDetail:
    record = db.query(ChatRecord).filter_by(id=chat_id).first()
    if not record:
        raise ChatNotFoundError(f"Chat '{chat_id}' not found.", details={"chat_id": chat_id})
    messages = db.query(MessageRecord).filter_by(chat_id=chat_id).order_by(MessageRecord.created_at.asc()).all()
    return ChatDetail(
        id=record.id, title=record.title, pinned=record.pinned, created_at=record.created_at,
        updated_at=record.updated_at, messages=[_message_to_schema(m) for m in messages],
    )


def delete_chat(db: Session, chat_id: str) -> None:
    record = db.query(ChatRecord).filter_by(id=chat_id).first()
    if not record:
        raise ChatNotFoundError(f"Chat '{chat_id}' not found.", details={"chat_id": chat_id})
    db.query(MessageRecord).filter_by(chat_id=chat_id).delete()
    db.delete(record)
    db.commit()


def set_chat_pinned(db: Session, chat_id: str, pinned: bool) -> ChatSummary:
    record = db.query(ChatRecord).filter_by(id=chat_id).first()
    if not record:
        raise ChatNotFoundError(f"Chat '{chat_id}' not found.", details={"chat_id": chat_id})
    record.pinned = pinned
    record.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(record)
    return _chat_to_summary(record)


def rename_chat(db: Session, chat_id: str, title: str) -> ChatSummary:
    record = db.query(ChatRecord).filter_by(id=chat_id).first()
    if not record:
        raise ChatNotFoundError(f"Chat '{chat_id}' not found.", details={"chat_id": chat_id})
    title = title.strip()
    record.title = title if title else record.title
    record.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(record)
    return _chat_to_summary(record)


def duplicate_chat(db: Session, chat_id: str) -> ChatSummary:
    original = db.query(ChatRecord).filter_by(id=chat_id).first()
    if not original:
        raise ChatNotFoundError(f"Chat '{chat_id}' not found.", details={"chat_id": chat_id})

    new_chat = ChatRecord(id=_new_chat_id(), title=f"{original.title} (copy)", pinned=False)
    db.add(new_chat)
    db.flush()  # populate new_chat.id relationships before copying messages

    original_messages = db.query(MessageRecord).filter_by(chat_id=chat_id).order_by(MessageRecord.created_at.asc()).all()
    for m in original_messages:
        db.add(
            MessageRecord(
                id=_new_message_id(), chat_id=new_chat.id, role=m.role, content=m.content,
                confidence=m.confidence, confidence_label=m.confidence_label,
                insufficient_evidence=m.insufficient_evidence, retrieval_json=m.retrieval_json,
                citations_json=m.citations_json, claims_json=m.claims_json, sources_json=m.sources_json,
                confidence_breakdown_json=m.confidence_breakdown_json, latency_json=m.latency_json,
            )
        )
    db.commit()
    db.refresh(new_chat)
    return _chat_to_summary(new_chat)


@dataclass
class SendMessageResult:
    user_message: MessageSchema
    assistant_message: MessageSchema
    chat: ChatSummary


def send_message(
    db: Session, chat_id: str, content: str, top_k: int | None = None, include_retrieval_debug: bool = True,
) -> SendMessageResult:
    chat_record = db.query(ChatRecord).filter_by(id=chat_id).first()
    if not chat_record:
        raise ChatNotFoundError(f"Chat '{chat_id}' not found.", details={"chat_id": chat_id})

    is_first_message = db.query(MessageRecord).filter_by(chat_id=chat_id).count() == 0

    user_record = MessageRecord(id=_new_message_id(), chat_id=chat_id, role="user", content=content)
    db.add(user_record)

    query_response: QueryResponse = execute_rag_query(
        content, db, top_k=top_k, include_retrieval_debug=include_retrieval_debug
    )

    assistant_record = MessageRecord(
        id=_new_message_id(), chat_id=chat_id, role="assistant", content=query_response.answer,
        confidence=query_response.confidence, confidence_label=query_response.confidence_label,
        insufficient_evidence=query_response.insufficient_evidence,
        retrieval_json=(
            query_response.retrieval_debug.model_dump_json() if query_response.retrieval_debug else None
        ),
        citations_json=json.dumps([c.model_dump(mode="json") for c in query_response.citations]),
        claims_json=json.dumps([c.model_dump(mode="json") for c in query_response.claims]),
        sources_json=json.dumps(query_response.sources),
        confidence_breakdown_json=(
            query_response.confidence_breakdown.model_dump_json() if query_response.confidence_breakdown else None
        ),
        latency_json=json.dumps(query_response.processing_latency_ms),
    )
    db.add(assistant_record)

    if is_first_message and chat_record.title == "New Chat":
        chat_record.title = generate_chat_title(content)
    chat_record.updated_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(user_record)
    db.refresh(assistant_record)
    db.refresh(chat_record)

    return SendMessageResult(
        user_message=_message_to_schema(user_record),
        assistant_message=_message_to_schema(assistant_record),
        chat=_chat_to_summary(chat_record),
    )
