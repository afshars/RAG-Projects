from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete

from app.database import get_db, LOCAL_WORKSPACE_ID
from app.models import ChatSession, MessageFeedback
from app.schemas import (
    ChatSessionOut, ChatSessionSummary, ChatSessionCreate, ChatSessionUpdate,
    FeedbackCreate, FeedbackOut,
)

router = APIRouter(prefix="/chat/sessions", tags=["chat-sessions"])


@router.get("", response_model=list[ChatSessionSummary])
async def list_sessions(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(ChatSession)
        .where(ChatSession.owner_id == LOCAL_WORKSPACE_ID)
        .order_by(ChatSession.updated_at.desc())
    )
    return result.scalars().all()


@router.post("", response_model=ChatSessionOut)
async def create_session(
    payload: ChatSessionCreate,
    db: AsyncSession = Depends(get_db),
):
    session = ChatSession(
        owner_id=LOCAL_WORKSPACE_ID,
        title=(payload.title or "گفتگوی جدید"),
        messages=[],
    )
    db.add(session)
    await db.commit()
    await db.refresh(session)
    return session


@router.get("/{session_id}", response_model=ChatSessionOut)
async def get_session(
    session_id: str,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(ChatSession).where(
            ChatSession.id == session_id, ChatSession.owner_id == LOCAL_WORKSPACE_ID
        )
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(404, "گفتگو یافت نشد.")
    return session


@router.patch("/{session_id}", response_model=ChatSessionOut)
async def update_session(
    session_id: str,
    payload: ChatSessionUpdate,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(ChatSession).where(
            ChatSession.id == session_id, ChatSession.owner_id == LOCAL_WORKSPACE_ID
        )
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(404, "گفتگو یافت نشد.")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(session, field, value)
    await db.commit()
    await db.refresh(session)
    return session


@router.delete("/{session_id}")
async def delete_session(
    session_id: str,
    db: AsyncSession = Depends(get_db),
):
    await db.execute(
        delete(ChatSession).where(
            ChatSession.id == session_id, ChatSession.owner_id == LOCAL_WORKSPACE_ID
        )
    )
    await db.commit()
    return {"message": "گفتگو حذف شد."}


# ── Human feedback on individual messages ───────────────────────────────
async def _get_owned_session(db: AsyncSession, owner_id: str, session_id: str) -> ChatSession:
    result = await db.execute(
        select(ChatSession).where(ChatSession.id == session_id, ChatSession.owner_id == owner_id)
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(404, "گفتگو یافت نشد.")
    return session


@router.get("/{session_id}/feedback", response_model=list[FeedbackOut])
async def list_feedback(
    session_id: str,
    db: AsyncSession = Depends(get_db),
):
    await _get_owned_session(db, LOCAL_WORKSPACE_ID, session_id)
    result = await db.execute(
        select(MessageFeedback).where(
            MessageFeedback.owner_id == LOCAL_WORKSPACE_ID, MessageFeedback.session_id == session_id
        )
    )
    return result.scalars().all()


@router.put("/{session_id}/messages/{message_index}/feedback", response_model=FeedbackOut)
async def set_feedback(
    session_id: str,
    message_index: int,
    payload: FeedbackCreate,
    db: AsyncSession = Depends(get_db),
):
    session = await _get_owned_session(db, LOCAL_WORKSPACE_ID, session_id)
    if message_index < 0 or message_index >= len(session.messages or []):
        raise HTTPException(400, "پیام مورد نظر در این گفتگو یافت نشد.")

    result = await db.execute(
        select(MessageFeedback).where(
            MessageFeedback.owner_id == LOCAL_WORKSPACE_ID,
            MessageFeedback.session_id == session_id,
            MessageFeedback.message_index == message_index,
        )
    )
    feedback = result.scalar_one_or_none()
    if feedback:
        # Quick thumbs (up/down) and the detailed 1-5 scores can be
        # submitted in separate calls (see FeedbackButtons.jsx) — only
        # overwrite a detailed field when this call actually provided one,
        # so opening the detailed panel later doesn't erase the earlier
        # quick rating, and vice versa.
        feedback.rating = payload.rating
        if payload.comment is not None:
            feedback.comment = payload.comment
        if payload.usefulness is not None:
            feedback.usefulness = payload.usefulness
        if payload.correctness is not None:
            feedback.correctness = payload.correctness
        if payload.completeness is not None:
            feedback.completeness = payload.completeness
    else:
        feedback = MessageFeedback(
            owner_id=LOCAL_WORKSPACE_ID,
            session_id=session_id,
            message_index=message_index,
            rating=payload.rating,
            comment=payload.comment,
            usefulness=payload.usefulness,
            correctness=payload.correctness,
            completeness=payload.completeness,
        )
        db.add(feedback)

    await db.commit()
    await db.refresh(feedback)
    return feedback


@router.delete("/{session_id}/messages/{message_index}/feedback")
async def clear_feedback(
    session_id: str,
    message_index: int,
    db: AsyncSession = Depends(get_db),
):
    await _get_owned_session(db, LOCAL_WORKSPACE_ID, session_id)
    await db.execute(
        delete(MessageFeedback).where(
            MessageFeedback.owner_id == LOCAL_WORKSPACE_ID,
            MessageFeedback.session_id == session_id,
            MessageFeedback.message_index == message_index,
        )
    )
    await db.commit()
    return {"message": "بازخورد حذف شد."}
