import uuid
import asyncio
import base64
import mimetypes

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete

from app.database import get_db, LOCAL_WORKSPACE_ID
from app.models import KnowledgeChunk
from app.schemas import ChunkOut
from app.routers.settings_router import _get_or_create
from app.parsers.extract import (
    extract_text_and_metadata,
    extract_from_url,
    SUPPORTED_EXTENSIONS,
    IMAGE_EXTENSIONS,
)
from app.rag.chunking import chunk_text, semantic_chunk_text
from app.rag.llm_client import LLMClient
from app.rag.embeddings import OpenAICompatEmbeddings
from app.rag import vector_store, bm25_store
from app.config import settings as app_settings
from app.schemas import UrlIngestRequest

router = APIRouter(prefix="/knowledge", tags=["knowledge"])

IMAGE_DESCRIBE_PROMPT = (
    "این تصویر یک سند در پایگاه دانش است. ابتدا هر متنی که در تصویر دیده می‌شود را "
    "دقیقاً و کامل رونویسی کن (اگر متنی وجود ندارد این بخش را رد کن)، سپس محتوای "
    "بصری تصویر (نمودار، جدول، عکس، نمودار جریان و غیره) را به‌طور کامل و دقیق شرح "
    "بده — طوری که کسی بدون دیدن تصویر بتواند بر اساس توضیح تو به سوالات درباره‌اش "
    "پاسخ دهد. پاسخ را به فارسی و فقط شامل رونویسی/توضیح بده، بدون مقدمه اضافه."
)


@router.get("", response_model=list[ChunkOut])
async def list_chunks(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(KnowledgeChunk)
        .where(KnowledgeChunk.owner_id == LOCAL_WORKSPACE_ID)
        .order_by(KnowledgeChunk.created_at.desc())
    )
    return result.scalars().all()


async def _ingest_text(
    *,
    text: str,
    doc_metadata: dict,
    source_name: str,
    source_type: str,
    user_settings,
    llm: LLMClient,
    base_url: str,
    api_key: str,
    db: AsyncSession,
) -> list[KnowledgeChunk]:
    """Shared chunk → embed → store → (re)index pipeline, used by every
    ingestion source (file upload, image, URL/API). Keeping this in one
    place means BM25/FAISS/metadata handling can't drift between sources.
    """
    if not text.strip():
        raise HTTPException(400, "متنی از منبع استخراج نشد.")

    if getattr(user_settings, "use_semantic_chunking", False):
        embeddings_client = OpenAICompatEmbeddings(
            base_url=base_url, api_key=api_key, model=user_settings.embedding_model
        )
        # semantic_chunk_text is sync/blocking (httpx.Client + local
        # SemanticChunker); run it off the event loop.
        pieces = await asyncio.to_thread(
            semantic_chunk_text,
            text,
            user_settings.chunk_size,
            user_settings.chunk_overlap,
            embeddings_client,
        )
    else:
        pieces = chunk_text(text, user_settings.chunk_size, user_settings.chunk_overlap)

    if not pieces:
        raise HTTPException(400, "پس از پردازش، محتوایی برای ذخیره یافت نشد.")

    embedding_vectors: list[list[float] | None] = [None] * len(pieces)
    try:
        embedding_vectors = await llm.embed(pieces, user_settings.embedding_model)
    except Exception:
        # Embeddings are optional: retrieval falls back to pure lexical (BM25)
        # search if the configured provider doesn't support the /embeddings
        # endpoint (some OpenAI-compatible local servers only implement chat
        # completions).
        pass

    document_id = uuid.uuid4().hex
    records = []
    for i, piece in enumerate(pieces):
        chunk = KnowledgeChunk(
            owner_id=LOCAL_WORKSPACE_ID,
            content=piece,
            source_name=source_name,
            source_type=source_type,
            document_id=document_id,
            chunk_index=i,
            word_count=len(piece.split()),
            embedding=embedding_vectors[i] if i < len(embedding_vectors) else None,
            author=doc_metadata.get("author"),
            document_date=doc_metadata.get("document_date"),
            title=doc_metadata.get("title"),
        )
        db.add(chunk)
        records.append(chunk)

    await db.commit()
    for r in records:
        await db.refresh(r)

    # Update the persistent indexes (built once here, reused by every query
    # afterwards — see rag/vector_store.py and rag/bm25_store.py).
    try:
        embedded_items = [(r.id, r.embedding) for r in records if r.embedding]
        if embedded_items:
            vector_store.add_vectors(LOCAL_WORKSPACE_ID, embedded_items)

        all_chunks_result = await db.execute(
            select(KnowledgeChunk.id, KnowledgeChunk.content).where(
                KnowledgeChunk.owner_id == LOCAL_WORKSPACE_ID
            )
        )
        all_chunks = [{"id": row.id, "content": row.content} for row in all_chunks_result.all()]
        bm25_store.rebuild(LOCAL_WORKSPACE_ID, all_chunks)
    except Exception:
        # Index maintenance failing should never fail the ingestion itself —
        # retrieval will just fall back to a full scan until it's fixed.
        pass

    return records


@router.post("/upload", response_model=list[ChunkOut])
async def upload_document(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
):
    ext = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
    is_image = ext in IMAGE_EXTENSIONS
    if ext not in SUPPORTED_EXTENSIONS and not is_image:
        raise HTTPException(400, f"فرمت پشتیبانی نمی‌شود: .{ext}")

    raw = await file.read()
    max_bytes = app_settings.max_upload_mb * 1024 * 1024
    if len(raw) > max_bytes:
        raise HTTPException(400, f"حجم فایل بیشتر از حد مجاز ({app_settings.max_upload_mb}MB) است.")

    user_settings = await _get_or_create(db)

    base_url = user_settings.llm_base_url or app_settings.default_llm_base_url
    api_key = user_settings.llm_api_key or app_settings.default_llm_api_key

    llm = LLMClient(base_url=base_url, api_key=api_key, model=user_settings.llm_model)

    if is_image:
        # Multimodal ingestion: a vision-capable chat model transcribes any
        # text in the image and describes its visual content — that
        # description becomes the chunk's searchable "content", exactly
        # like extracted text from a PDF/DOCX would.
        #
        # Uses the separate vision_llm_* config if set (letting the main
        # chat model stay on whatever cheap/fast text-only model is
        # configured — vision-capable models are usually pricier and this
        # path only runs once per image, at upload time, not per chat
        # message) and falls back to the main llm_* config otherwise, so
        # nothing breaks for anyone who hasn't set a separate vision model.
        vision_base_url = user_settings.vision_llm_base_url or base_url
        vision_api_key = user_settings.vision_llm_api_key or api_key
        vision_model = user_settings.vision_llm_model or user_settings.llm_model
        vision_llm = LLMClient(base_url=vision_base_url, api_key=vision_api_key, model=vision_model)

        mime = mimetypes.guess_type(file.filename)[0] or f"image/{ext}"
        data_url = f"data:{mime};base64,{base64.b64encode(raw).decode()}"
        try:
            text = await vision_llm.describe_image(data_url, IMAGE_DESCRIBE_PROMPT)
        except Exception as e:
            raise HTTPException(
                400,
                "پردازش تصویر ناموفق بود — مطمئن شوید مدل انتخاب‌شده (در بخش «مدل تصویر» "
                "یا مدل چت اصلی در تنظیمات) از ورودی تصویری (vision) پشتیبانی می‌کند. "
                f"جزئیات: {e}",
            )
        doc_metadata = {"author": None, "document_date": None, "title": file.filename}
    else:
        text, doc_metadata = extract_text_and_metadata(file.filename, raw)

    return await _ingest_text(
        text=text,
        doc_metadata=doc_metadata,
        source_name=file.filename,
        source_type=ext,
        user_settings=user_settings,
        llm=llm,
        base_url=base_url,
        api_key=api_key,
        db=db,
    )


@router.post("/url", response_model=list[ChunkOut])
async def ingest_url(
    payload: UrlIngestRequest,
    db: AsyncSession = Depends(get_db),
):
    """Data-ingestion from the web: fetches a page or API endpoint and runs
    it through the same chunk/embed/index pipeline as an uploaded file —
    covers the "websites" and "APIs" ingestion sources from the
    architecture diagram, which file upload alone didn't."""
    user_settings = await _get_or_create(db)
    base_url = user_settings.llm_base_url or app_settings.default_llm_base_url
    api_key = user_settings.llm_api_key or app_settings.default_llm_api_key
    llm = LLMClient(base_url=base_url, api_key=api_key, model=user_settings.llm_model)

    try:
        text, doc_metadata, source_type = await extract_from_url(payload.url)
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        raise HTTPException(400, f"دریافت آدرس ناموفق بود: {e}")

    return await _ingest_text(
        text=text,
        doc_metadata=doc_metadata,
        source_name=payload.url,
        source_type=source_type,
        user_settings=user_settings,
        llm=llm,
        base_url=base_url,
        api_key=api_key,
        db=db,
    )


@router.delete("/document/{document_id}")
async def delete_document(
    document_id: str,
    db: AsyncSession = Depends(get_db),
):
    await db.execute(
        delete(KnowledgeChunk).where(
            KnowledgeChunk.owner_id == LOCAL_WORKSPACE_ID,
            KnowledgeChunk.document_id == document_id,
        )
    )
    await db.commit()

    try:
        remaining_result = await db.execute(
            select(KnowledgeChunk).where(KnowledgeChunk.owner_id == LOCAL_WORKSPACE_ID)
        )
        remaining = [
            {"id": c.id, "content": c.content, "embedding": c.embedding}
            for c in remaining_result.scalars().all()
        ]
        vector_store.rebuild(LOCAL_WORKSPACE_ID, remaining)
        bm25_store.rebuild(LOCAL_WORKSPACE_ID, remaining)
    except Exception:
        pass

    return {"message": "سند حذف شد."}


@router.delete("/all")
async def delete_all(db: AsyncSession = Depends(get_db)):
    await db.execute(delete(KnowledgeChunk).where(KnowledgeChunk.owner_id == LOCAL_WORKSPACE_ID))
    await db.commit()

    vector_store.clear(LOCAL_WORKSPACE_ID)
    bm25_store.clear(LOCAL_WORKSPACE_ID)

    return {"message": "تمام منابع حذف شدند."}
