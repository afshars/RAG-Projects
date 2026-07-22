import json

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db, AsyncSessionLocal, LOCAL_WORKSPACE_ID
from app.models import ChatSession
from app.schemas import ChatRequest
from app.routers.settings_router import _get_or_create
from app.rag.llm_client import LLMClient
from app.rag.retrieval import retrieve
from app.config import settings as app_settings

router = APIRouter(prefix="/chat", tags=["chat"])

SYSTEM_PROMPT_TEMPLATE = """شما دستیار هوشمند پرسش و پاسخ هستید. فقط بر اساس منابع زیر پاسخ بده. \
اگر پاسخ در منابع موجود نیست، صادقانه بگو که اطلاعات کافی در پایگاه دانش وجود ندارد.

منابع:
{context}
"""

NO_CONTEXT_SYSTEM_PROMPT = (
    "اطلاعات مرتبطی در پایگاه دانش پیدا نشد. صادقانه به کاربر بگو که پاسخ این سوال در منابع موجود نیست."
)


def build_llm_message(m) -> dict:
    return {"role": m.role, "content": m.content}


def build_context(results: list[dict]) -> str:
    parts = []
    for i, r in enumerate(results, 1):
        meta_bits = []
        if r.get("author"):
            meta_bits.append(f"نویسنده: {r['author']}")
        if r.get("document_date"):
            meta_bits.append(f"تاریخ: {r['document_date']}")
        meta = f" ({', '.join(meta_bits)})" if meta_bits else ""
        parts.append(f"[{i}] منبع: {r['source_name']}{meta}\n{r['content']}")
    return "\n\n".join(parts)


def compute_confidence(retrieval: dict) -> dict:
    """A single overall confidence score for the answer, derived from how
    strongly (and how consistently) the retrieved chunks matched the
    question — not a judgment of factual correctness, just "how solid was
    the evidence this answer is grounded in".

    Uses cross-encoder rerank scores when available (0-10 scale, most
    precise signal we have), otherwise the hybrid retrieval score (0-1).
    Averaging across the returned chunks means one great match alongside
    several weak ones still yields a middling score — the same principle
    used for the relevance_threshold cutoff elsewhere in the pipeline.
    """
    results = retrieval.get("results") or []
    if not retrieval.get("found") or not results:
        return {"score": 0.0, "label": "بدون منبع"}

    if "rerank_score" in results[0]:
        scores = [max(0.0, min(10.0, r.get("rerank_score", 0.0))) / 10.0 for r in results]
    else:
        scores = [max(0.0, min(1.0, r.get("score", 0.0))) for r in results]

    avg = sum(scores) / len(scores)
    if avg >= 0.6:
        label = "بالا"
    elif avg >= 0.35:
        label = "متوسط"
    else:
        label = "پایین"
    return {"score": round(avg, 3), "label": label}


async def _persist_exchange(
    owner_id: str,
    session_id: str,
    user_messages: list[dict],
    assistant_text: str,
    citations: list[dict],
    confidence: dict,
):
    """Runs after the streaming response has finished, using its own DB
    session (the request-scoped one from Depends(get_db) is already closed
    by the time this coroutine gets here)."""
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(ChatSession).where(
                ChatSession.id == session_id, ChatSession.owner_id == owner_id
            )
        )
        session = result.scalar_one_or_none()
        if not session:
            return

        messages = list(session.messages or [])
        # user_messages is the full running transcript sent by the client;
        # keep whichever is longer/newer so we never drop prior turns.
        if len(user_messages) > len(messages):
            messages = user_messages
        messages.append(
            {
                "role": "assistant",
                "content": assistant_text,
                "sources": citations,
                "confidence": confidence,
            }
        )
        session.messages = messages

        if session.title == "گفتگوی جدید":
            first_user = next((m for m in messages if m.get("role") == "user"), None)
            if first_user and first_user.get("content"):
                title = first_user["content"].strip().replace("\n", " ")
                session.title = (title[:40] + "…") if len(title) > 40 else title

        await db.commit()


@router.post("")
async def chat(
    payload: ChatRequest,
    db: AsyncSession = Depends(get_db),
):
    user_settings = await _get_or_create(db)

    llm = LLMClient(
        base_url=user_settings.llm_base_url or app_settings.default_llm_base_url,
        api_key=user_settings.llm_api_key or app_settings.default_llm_api_key,
        model=user_settings.llm_model,
    )

    query = next((m.content for m in reversed(payload.messages) if m.role == "user"), "")
    retrieval = await retrieve(query, LOCAL_WORKSPACE_ID, db, user_settings, llm)

    citations = [
        {
            "chunk_id": r["id"],
            "source_name": r["source_name"],
            "document_id": r["document_id"],
            "content": r["content"],
            "score": r["score"],
            "author": r.get("author"),
            "document_date": r.get("document_date"),
        }
        for r in retrieval["results"]
    ]

    if retrieval["found"]:
        context = build_context(retrieval["results"])
        system_msg = {"role": "system", "content": SYSTEM_PROMPT_TEMPLATE.format(context=context)}
    else:
        system_msg = {"role": "system", "content": NO_CONTEXT_SYSTEM_PROMPT}

    confidence = compute_confidence(retrieval)

    llm_messages = [system_msg] + [
        build_llm_message(m) for m in payload.messages if m.role != "system"
    ]

    session_id = payload.session_id
    user_messages_for_history = [
        {"role": m.role, "content": m.content} for m in payload.messages if m.role != "system"
    ]

    async def event_stream():
        # First event: citations + confidence, so the UI can render them
        # alongside the streamed answer (mirrors the frontend's
        # CitationsExpander).
        yield f"data: {json.dumps({'type': 'citations', 'citations': citations, 'confidence': confidence}, ensure_ascii=False)}\n\n"
        full_answer = []
        try:
            async for token in llm.stream_chat_completion(llm_messages):
                full_answer.append(token)
                yield f"data: {json.dumps({'type': 'token', 'content': token}, ensure_ascii=False)}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)}, ensure_ascii=False)}\n\n"
        yield "data: [DONE]\n\n"

        if session_id:
            try:
                await _persist_exchange(
                    LOCAL_WORKSPACE_ID,
                    session_id,
                    user_messages_for_history,
                    "".join(full_answer),
                    citations,
                    confidence,
                )
            except Exception:
                # History persistence failing should never break the chat
                # response itself.
                pass

    return StreamingResponse(event_stream(), media_type="text/event-stream")
