import uuid
from datetime import datetime, timezone

from sqlalchemy import String, Text, Integer, Float, DateTime, ForeignKey, JSON, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


def gen_id() -> str:
    return uuid.uuid4().hex


def utcnow() -> datetime:
    """Timezone-aware 'now' in UTC. Used instead of the deprecated/naive
    datetime.utcnow() so timestamps round-trip through the API with an
    explicit UTC offset (e.g. '...+00:00') instead of an ambiguous naive
    string that browsers misinterpret as local time."""
    return datetime.now(timezone.utc)


class AppSettings(Base):
    """A single row of app-wide configuration (LLM connection + RAG
    pipeline parameters). There are no user accounts, so this table only
    ever holds one row, looked up by the fixed LOCAL_WORKSPACE_ID."""

    __tablename__ = "app_settings"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=gen_id)
    workspace_id: Mapped[str] = mapped_column(String, unique=True)

    llm_base_url: Mapped[str] = mapped_column(String, default="https://api.gapgpt.app/v1")
    llm_model: Mapped[str] = mapped_column(String, default="gapgpt-qwen-3.6")
    llm_api_key: Mapped[str] = mapped_column(String, default="")
    embedding_model: Mapped[str] = mapped_column(String, default="text-embedding-3-small")

    # Optional separate vision-capable (VLLM) model used only for image
    # ingestion (see routers/knowledge.py). Left empty by default, meaning
    # "reuse the main text llm_* config above" — this keeps normal chat on
    # whatever cheap/fast text model is configured, and only pays for a
    # multimodal model when a document is actually an image.
    vision_llm_base_url: Mapped[str] = mapped_column(String, default="")
    vision_llm_model: Mapped[str] = mapped_column(String, default="")
    vision_llm_api_key: Mapped[str] = mapped_column(String, default="")

    chunk_size: Mapped[int] = mapped_column(Integer, default=800)
    chunk_overlap: Mapped[int] = mapped_column(Integer, default=150)
    hybrid_alpha: Mapped[float] = mapped_column(Float, default=0.6)
    mmr_lambda: Mapped[float] = mapped_column(Float, default=0.7)
    top_k: Mapped[int] = mapped_column(Integer, default=5)
    use_cross_encoder_rerank: Mapped[bool] = mapped_column(default=True)
    relevance_threshold: Mapped[float] = mapped_column(Float, default=0.08)

    # Upgraded LangChain-based RAG pipeline toggles
    use_semantic_chunking: Mapped[bool] = mapped_column(default=True)
    use_query_decomposition: Mapped[bool] = mapped_column(default=True)
    use_hyde: Mapped[bool] = mapped_column(default=True)

    # How the lexical (BM25) and dense (FAISS) candidate scores are combined
    # before MMR/rerank: "rrf" = Reciprocal Rank Fusion (rank-based, scale-
    # free — the standard approach for hybrid RAG), "weighted" = the older
    # linear blend controlled by hybrid_alpha above. rrf_k is RRF's smoothing
    # constant (higher = flatter weighting across ranks; 60 is the
    # conventional default from the original RRF paper).
    fusion_method: Mapped[str] = mapped_column(String, default="rrf")  # "rrf" | "weighted"
    rrf_k: Mapped[int] = mapped_column(Integer, default=60)


class ChatSession(Base):
    __tablename__ = "chat_sessions"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=gen_id)
    owner_id: Mapped[str] = mapped_column(String, index=True)

    title: Mapped[str] = mapped_column(String, default="گفتگوی جدید")
    # list of {id, role, content, sources?} — kept as a single JSON
    # blob since a chat page's full history is always read/written together.
    messages: Mapped[list] = mapped_column(JSON, default=list)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class MessageFeedback(Base):
    """Human 👍/👎 feedback on a specific assistant message, kept in its own
    table (rather than mutating the ChatSession.messages JSON blob) so it
    can't race with the background write in chat.py that persists the
    exchange right after streaming finishes. A message is identified by its
    (session_id, message_index) position — the index it has within that
    session's `messages` list, which only ever grows by appending."""

    __tablename__ = "message_feedback"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=gen_id)
    owner_id: Mapped[str] = mapped_column(String, index=True)
    session_id: Mapped[str] = mapped_column(String, ForeignKey("chat_sessions.id"), index=True)
    message_index: Mapped[int] = mapped_column(Integer)

    rating: Mapped[str] = mapped_column(String)  # "up" | "down"  (quick thumbs feedback)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Optional detailed human-evaluation scores (1-5), matching the 3
    # dimensions called for in the grading rubric: how useful, how correct,
    # and how complete the answer was. All nullable — a user can leave a
    # quick 👍/👎 without filling these in.
    usefulness: Mapped[int | None] = mapped_column(Integer, nullable=True)
    correctness: Mapped[int | None] = mapped_column(Integer, nullable=True)
    completeness: Mapped[int | None] = mapped_column(Integer, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    __table_args__ = (UniqueConstraint("session_id", "message_index", name="uq_feedback_session_message"),)


class KnowledgeChunk(Base):
    __tablename__ = "knowledge_chunks"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=gen_id)
    owner_id: Mapped[str] = mapped_column(String, index=True)

    content: Mapped[str] = mapped_column(Text)
    source_name: Mapped[str] = mapped_column(String)
    source_type: Mapped[str] = mapped_column(String)
    document_id: Mapped[str] = mapped_column(String, index=True)
    chunk_index: Mapped[int] = mapped_column(Integer, default=0)
    word_count: Mapped[int] = mapped_column(Integer, default=0)

    # Metadata extracted from the source file at ingestion time (see
    # parsers/extract.py). All optional — only populated when the format
    # actually carries this information (PDF/DOCX properties, HTML <meta>
    # tags, or a markdown/txt YAML frontmatter block).
    author: Mapped[str | None] = mapped_column(String, nullable=True)
    document_date: Mapped[str | None] = mapped_column(String, nullable=True)
    title: Mapped[str | None] = mapped_column(String, nullable=True)

    # embedding stored as JSON list of floats (fine for up to tens of thousands of chunks)
    embedding: Mapped[list | None] = mapped_column(JSON, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class EvaluationItem(Base):
    """A single test-set entry for RAG evaluation: a query, the chunk ids a
    human has judged relevant (ground truth for retrieval metrics), and an
    optional reference answer (currently unused by the metrics themselves,
    kept for future answer-similarity metrics / display)."""

    __tablename__ = "evaluation_items"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=gen_id)
    owner_id: Mapped[str] = mapped_column(String, index=True)

    query: Mapped[str] = mapped_column(Text)
    reference_answer: Mapped[str | None] = mapped_column(Text, nullable=True)
    relevant_chunk_ids: Mapped[list] = mapped_column(JSON, default=list)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class EvaluationRun(Base):
    """A saved evaluation pass over the current EvaluationItem set: the
    aggregated (mean) metrics plus a per-item breakdown, so past runs can be
    compared after tweaking retrieval/generation settings."""

    __tablename__ = "evaluation_runs"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=gen_id)
    owner_id: Mapped[str] = mapped_column(String, index=True)

    item_count: Mapped[int] = mapped_column(Integer, default=0)
    summary: Mapped[dict] = mapped_column(JSON, default=dict)
    details: Mapped[list] = mapped_column(JSON, default=list)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
