from datetime import datetime
from pydantic import BaseModel, Field


# ── Settings ──────────────────────────────────────────
class SettingsOut(BaseModel):
    llm_base_url: str
    llm_model: str
    llm_api_key: str
    embedding_model: str
    vision_llm_base_url: str
    vision_llm_model: str
    vision_llm_api_key: str
    chunk_size: int
    chunk_overlap: int
    hybrid_alpha: float
    mmr_lambda: float
    top_k: int
    use_cross_encoder_rerank: bool
    relevance_threshold: float
    use_semantic_chunking: bool
    use_query_decomposition: bool
    use_hyde: bool
    fusion_method: str
    rrf_k: int

    class Config:
        from_attributes = True


class SettingsUpdate(BaseModel):
    llm_base_url: str | None = None
    llm_model: str | None = None
    llm_api_key: str | None = None
    embedding_model: str | None = None
    vision_llm_base_url: str | None = None
    vision_llm_model: str | None = None
    vision_llm_api_key: str | None = None
    chunk_size: int | None = None
    chunk_overlap: int | None = None
    hybrid_alpha: float | None = None
    mmr_lambda: float | None = None
    top_k: int | None = None
    use_cross_encoder_rerank: bool | None = None
    relevance_threshold: float | None = None
    use_semantic_chunking: bool | None = None
    use_query_decomposition: bool | None = None
    use_hyde: bool | None = None
    fusion_method: str | None = Field(default=None, pattern="^(rrf|weighted)$")
    rrf_k: int | None = None


# ── Knowledge ─────────────────────────────────────────
class UrlIngestRequest(BaseModel):
    url: str = Field(min_length=1)


class ChunkOut(BaseModel):
    id: str
    content: str
    source_name: str
    source_type: str
    document_id: str
    chunk_index: int
    word_count: int
    author: str | None = None
    document_date: str | None = None
    title: str | None = None

    class Config:
        from_attributes = True


# ── Chat ──────────────────────────────────────────────
class ChatMessage(BaseModel):
    role: str  # system | user | assistant
    content: str


class ChatRequest(BaseModel):
    messages: list[ChatMessage]
    session_id: str | None = None


class Citation(BaseModel):
    chunk_id: str
    source_name: str
    document_id: str
    content: str
    score: float
    author: str | None = None
    document_date: str | None = None


# ── Chat sessions (history) ────────────────────────────
class ChatSessionOut(BaseModel):
    id: str
    title: str
    messages: list[dict]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ChatSessionSummary(BaseModel):
    id: str
    title: str
    updated_at: datetime

    class Config:
        from_attributes = True


class ChatSessionCreate(BaseModel):
    title: str | None = None


class ChatSessionUpdate(BaseModel):
    title: str | None = None
    messages: list[dict] | None = None


# ── Message feedback ────────────────────────────────────
class FeedbackCreate(BaseModel):
    rating: str = Field(pattern="^(up|down)$")
    comment: str | None = None
    # Detailed human-evaluation scores (1-5), all optional — the rubric asks
    # for usefulness, correctness (accuracy) and completeness separately,
    # in addition to the quick thumbs up/down above.
    usefulness: int | None = Field(default=None, ge=1, le=5)
    correctness: int | None = Field(default=None, ge=1, le=5)
    completeness: int | None = Field(default=None, ge=1, le=5)


class FeedbackOut(BaseModel):
    id: str
    session_id: str
    message_index: int
    rating: str
    comment: str | None
    usefulness: int | None = None
    correctness: int | None = None
    completeness: int | None = None
    created_at: datetime

    class Config:
        from_attributes = True


# ── Evaluation ────────────────────────────────────────
class EvaluationItemCreate(BaseModel):
    query: str
    reference_answer: str | None = None
    relevant_chunk_ids: list[str] = Field(default_factory=list)


class EvaluationItemOut(BaseModel):
    id: str
    query: str
    reference_answer: str | None
    relevant_chunk_ids: list[str]
    created_at: datetime

    class Config:
        from_attributes = True


class EvaluationItemsImport(BaseModel):
    items: list[EvaluationItemCreate]


class EvaluationRunRequest(BaseModel):
    # k values to compute Precision@k / Recall@k / NDCG@k at
    k_values: list[int] = Field(default_factory=lambda: [1, 3, 5, 10])
    # LLM-as-judge generation metrics (Faithfulness, Answer Relevance) are
    # slower (one extra chat completion per item, plus two judge calls), so
    # they can be switched off to run a quick retrieval-only pass.
    evaluate_generation: bool = True


class EvaluationRunSummary(BaseModel):
    id: str
    item_count: int
    summary: dict
    created_at: datetime

    class Config:
        from_attributes = True


class EvaluationRunOut(EvaluationRunSummary):
    details: list[dict]

    class Config:
        from_attributes = True
