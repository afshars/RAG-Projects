"""Retrieval pipeline (LangChain-flavored hybrid RAG):

  query
    │
    ├─ query decomposition ── LLM breaks compound questions into subqueries  ┐
    ├─ HyDE ─────────────── LLM drafts a hypothetical answer for dense search┘ (run concurrently)
    │
    ├─ BM25 (persistent, rank_bm25) ─────────┐
    └─ dense (persistent FAISS index, max    ├─► RRF / weighted fusion ─► cross-encoder rerank* ─► MMR ─► top_k
              over query variants + HyDE) ───┘
                                                 *rerank runs on a wide candidate pool, not the
                                                  post-MMR top_k, so it can actually promote a
                                                  match the coarse fusion score ranked lower.

Score fusion defaults to Reciprocal Rank Fusion (rrf_fuse below), combining
the two candidate lists purely by rank rather than assuming BM25 scores and
cosine similarities live on comparable scales. The older weighted linear
blend (hybrid_alpha) is kept as a selectable alternative (settings.fusion_method).

Both the BM25 and FAISS indexes are built once at ingestion time (see
knowledge.py) and simply searched here — no more loading every chunk from
SQLite and rescoring the whole knowledge base on every chat request.

Every stage still degrades gracefully: if an LLM call, an optional
dependency, or a not-yet-built index isn't available, the pipeline falls
back to the next-simplest working strategy (including, as a last resort,
scanning the user's chunks directly) rather than failing the request.
"""
import re
import math
import asyncio
import numpy as np
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import KnowledgeChunk
from app.rag.llm_client import LLMClient
from app.rag.query_transform import decompose_query, generate_hyde
from app.rag.tokenizer import tokenize
from app.rag import vector_store, bm25_store


# ── Fallback-only lexical scoring (plain TF-IDF), used solely when a
#    user has no persistent BM25/FAISS index yet (e.g. right after
#    upgrading, before the first re-ingestion backfills it) ────────────
def _build_tfidf(chunks_content: list[str]):
    tokenized = [tokenize(c) for c in chunks_content]
    n = len(tokenized)
    df: dict[str, int] = {}
    for tokens in tokenized:
        for term in set(tokens):
            df[term] = df.get(term, 0) + 1
    idf = {term: math.log((n + 1) / (d + 1)) + 1 for term, d in df.items()}

    vectors = []
    for tokens in tokenized:
        tf: dict[str, int] = {}
        for t in tokens:
            tf[t] = tf.get(t, 0) + 1
        vec = {t: cnt * idf.get(t, 0) for t, cnt in tf.items()}
        vectors.append(vec)
    return {"vectors": vectors, "idf": idf}


def _sparse_cosine(a: dict, b: dict) -> float:
    dot = sum(v * b[t] for t, v in a.items() if t in b)
    mag_a = math.sqrt(sum(v * v for v in a.values()))
    mag_b = math.sqrt(sum(v * v for v in b.values()))
    denom = mag_a * mag_b
    return dot / denom if denom > 0 else 0.0


def _tfidf_scores(chunks_content: list[str], query: str) -> np.ndarray:
    tfidf = _build_tfidf(chunks_content)
    q_tf: dict[str, int] = {}
    for t in tokenize(query):
        q_tf[t] = q_tf.get(t, 0) + 1
    q_vec = {t: cnt * tfidf["idf"].get(t, 0) for t, cnt in q_tf.items()}
    return np.array([_sparse_cosine(q_vec, v) for v in tfidf["vectors"]], dtype=float)


def _dense_cosine_matrix(query_vec: np.ndarray, matrix: np.ndarray) -> np.ndarray:
    if matrix.size == 0:
        return np.array([])
    q_norm = query_vec / (np.linalg.norm(query_vec) + 1e-9)
    m_norm = matrix / (np.linalg.norm(matrix, axis=1, keepdims=True) + 1e-9)
    return m_norm @ q_norm


def _normalize(scores: np.ndarray) -> np.ndarray:
    if scores.size == 0:
        return scores
    lo, hi = scores.min(), scores.max()
    return (scores - lo) / (hi - lo) if hi > lo else np.zeros_like(scores)


# ── Reciprocal Rank Fusion ───────────────────────────────────────────────
def rrf_fuse(lex_map: dict[str, float], dense_map: dict[str, float], k: int = 60) -> dict[str, float]:
    """Combines the lexical (BM25) and dense (FAISS) candidate lists purely
    by *rank* rather than by raw score: score(doc) = sum over each ranked
    list it appears in of 1 / (k + rank_in_that_list). This is the standard
    Reciprocal Rank Fusion formula — unlike a weighted sum of the two raw
    scores, it needs no assumption about the two scales being comparable
    (BM25 scores and cosine similarities live on completely different
    ranges), which is why RRF is the usual default for hybrid search. `k`
    (60 by convention, from the original RRF paper) controls how much the
    fusion favors top ranks vs. spreading credit further down the list.
    """
    fused: dict[str, float] = {}
    for score_map in (lex_map, dense_map):
        if not score_map:
            continue
        ranked_ids = sorted(score_map.keys(), key=lambda cid: score_map[cid], reverse=True)
        for rank, cid in enumerate(ranked_ids, start=1):
            fused[cid] = fused.get(cid, 0.0) + 1.0 / (k + rank)
    return fused


# ── MMR (diversity-aware selection) ─────────────────────────────────────
def apply_mmr(scored: list[dict], dense_matrix: np.ndarray, lam: float, top_k: int) -> list[dict]:
    if len(scored) <= top_k:
        return scored
    candidates = scored[: min(len(scored), top_k * 3)]
    idxs = [c["index"] for c in candidates]
    sub = dense_matrix[idxs] if dense_matrix.size else None

    def sim(i: int, j: int) -> float:
        if sub is None:
            return 0.0
        a, b = sub[i], sub[j]
        denom = np.linalg.norm(a) * np.linalg.norm(b)
        return float(a @ b / denom) if denom > 0 else 0.0

    selected = [0]
    remaining = list(range(1, len(candidates)))

    while len(selected) < top_k and remaining:
        best_idx, best_mmr = -1, -math.inf
        for i in remaining:
            relevance = candidates[i]["score"]
            max_sim = max((sim(i, s) for s in selected), default=0.0)
            mmr = lam * relevance - (1 - lam) * max_sim
            if mmr > best_mmr:
                best_mmr, best_idx = mmr, i
        selected.append(best_idx)
        remaining.remove(best_idx)

    return [candidates[i] for i in selected]


# ── Reranking: real cross-encoder (sentence-transformers) with an
#    LLM-based fallback if the library/model isn't available ───────────
_cross_encoder_cache: dict = {}


def _get_cross_encoder(model_name: str = "cross-encoder/mmarco-mMiniLMv2-L12-H384-v1"):
    if model_name in _cross_encoder_cache:
        return _cross_encoder_cache[model_name]
    try:
        from sentence_transformers import CrossEncoder
        model = CrossEncoder(model_name)
    except Exception:
        model = None
    _cross_encoder_cache[model_name] = model
    return model


async def rerank_with_llm(query: str, ranked: list[dict], llm: LLMClient) -> list[dict]:
    async def score_one(r: dict) -> dict:
        try:
            raw = await llm.chat_completion(
                [
                    {
                        "role": "system",
                        "content": (
                            "You are a relevance scoring system. Rate how relevant the "
                            "passage is to the query on a scale of 0 to 10. Reply with "
                            "ONLY a single integer number, nothing else."
                        ),
                    },
                    {
                        "role": "user",
                        "content": f"Query: {query}\n\nPassage: {r['content'][:600]}",
                    },
                ],
                temperature=0,
            )
            digits = re.sub(r"[^0-9.]", "", raw.strip())
            score = float(digits) if digits else 0.0
        except Exception:
            score = r["score"] * 10
        return {**r, "rerank_score": score}

    # These are independent scoring calls (no shared state between them), so
    # firing them concurrently turns N sequential LLM round trips into one —
    # sequential scoring was the single biggest latency source in this
    # fallback path (only used when the local cross-encoder isn't available).
    reranked = await asyncio.gather(*(score_one(r) for r in ranked))
    return sorted(reranked, key=lambda r: r["rerank_score"], reverse=True)


async def rerank(query: str, ranked: list[dict], llm: LLMClient) -> list[dict]:
    """Cross-encoder rerank via sentence-transformers (jointly encodes the
    query+passage pair, which is much more precise than comparing two
    independent embeddings). Falls back to an LLM-scored rerank if the
    model can't be loaded (e.g. offline / dependency missing).

    Model load (first call — may hit the network to download weights) and
    .predict() (CPU-bound) are both synchronous/blocking calls, so they're
    pushed onto a worker thread via asyncio.to_thread — otherwise they'd
    freeze the single asyncio event loop for the whole app (including this
    same request's SSE stream) for as long as they take.
    """
    model = await asyncio.to_thread(_get_cross_encoder)
    if model is None:
        return await rerank_with_llm(query, ranked, llm)

    try:
        pairs = [(query, r["content"][:1000]) for r in ranked]
        raw_scores = await asyncio.to_thread(model.predict, pairs)
        # ms-marco cross-encoders output unbounded logits; squash to 0-1 with
        # a sigmoid so the score is comparable to the LLM fallback's 0-10
        # scale (divided by 10 below) and to the relevance-threshold checks
        # elsewhere in the pipeline.
        normalized = 1 / (1 + np.exp(-np.array(raw_scores, dtype=float)))
        reranked = [
            {**r, "rerank_score": float(s) * 10}
            for r, s in zip(ranked, normalized)
        ]
        return sorted(reranked, key=lambda r: r["rerank_score"], reverse=True)
    except Exception:
        return await rerank_with_llm(query, ranked, llm)


def _row_to_dict(c: KnowledgeChunk) -> dict:
    return {
        "id": c.id,
        "content": c.content,
        "source_name": c.source_name,
        "document_id": c.document_id,
        "embedding": c.embedding,
        "author": c.author,
        "document_date": c.document_date,
        "title": c.title,
    }


async def _fetch_all_chunks(db: AsyncSession, owner_id: str) -> list[dict]:
    result = await db.execute(select(KnowledgeChunk).where(KnowledgeChunk.owner_id == owner_id))
    return [_row_to_dict(c) for c in result.scalars().all()]


async def _fetch_chunks_by_id(db: AsyncSession, owner_id: str, ids: list[str]) -> list[dict]:
    if not ids:
        return []
    result = await db.execute(
        select(KnowledgeChunk).where(
            KnowledgeChunk.owner_id == owner_id, KnowledgeChunk.id.in_(ids)
        )
    )
    return [_row_to_dict(c) for c in result.scalars().all()]


async def _fallback_full_scan(
    query: str,
    dense_query_variants: list[str],
    owner_id: str,
    db: AsyncSession,
    settings,
    llm: LLMClient,
) -> tuple[list[dict], np.ndarray, dict[str, float], dict[str, float]] | None:
    """Old brute-force behavior, used only when this user has no persistent
    index yet. Also kicks off building that index in the background so the
    *next* query takes the fast path."""
    chunks = await _fetch_all_chunks(db, owner_id)
    if not chunks:
        return None

    have_embeddings = all(c.get("embedding") for c in chunks)
    if have_embeddings:
        dims = {len(c["embedding"]) for c in chunks}
        have_embeddings = len(dims) == 1
    contents = [c["content"] for c in chunks]

    lex = _tfidf_scores(contents, query)
    lex_map = {c["id"]: float(lex[i]) for i, c in enumerate(chunks)}

    dense_matrix = np.array([c["embedding"] for c in chunks]) if have_embeddings else np.array([])
    dense_map: dict[str, float] = {}
    if have_embeddings:
        try:
            embeddings = await llm.embed(dense_query_variants, settings.embedding_model)
            all_scores = [
                _normalize(_dense_cosine_matrix(np.array(e), dense_matrix)) for e in embeddings
            ]
            agg = np.max(np.stack(all_scores), axis=0)
            dense_map = {c["id"]: float(agg[i]) for i, c in enumerate(chunks)}
        except Exception:
            pass

    # Lazily backfill the persistent indexes so subsequent queries are fast.
    try:
        bm25_store.rebuild(owner_id, [{"id": c["id"], "content": c["content"]} for c in chunks])
        vector_store.rebuild(owner_id, chunks)
    except Exception:
        pass

    return chunks, dense_matrix, lex_map, dense_map


async def retrieve(
    query: str,
    owner_id: str,
    db: AsyncSession,
    settings,
    llm: LLMClient,
) -> dict:
    # ── Query strengthening ──────────────────────────────────────────
    # Decomposition and HyDE are independent LLM calls — HyDE only needs
    # the original query, not decomposition's output — so run them
    # concurrently instead of one after another. Both are enabled by
    # default, so this alone removes a full sequential LLM round trip from
    # every query's latency before retrieval even starts.
    query_variants = [query]
    hyde_doc = None
    decompose_on = getattr(settings, "use_query_decomposition", False)
    hyde_on = getattr(settings, "use_hyde", False)

    if decompose_on or hyde_on:
        coros = {}
        if decompose_on:
            coros["decompose"] = decompose_query(query, llm)
        if hyde_on:
            coros["hyde"] = generate_hyde(query, llm)

        results = await asyncio.gather(*coros.values(), return_exceptions=True)
        result_map = dict(zip(coros.keys(), results))

        if "decompose" in result_map:
            r = result_map["decompose"]
            query_variants = r if isinstance(r, list) and r else [query]
        if "hyde" in result_map:
            r = result_map["hyde"]
            hyde_doc = r if isinstance(r, str) else None

    dense_query_variants = list(query_variants)
    if hyde_doc:
        dense_query_variants.append(hyde_doc)

    candidate_k = max(settings.top_k * 6, 30)
    use_persistent = vector_store.has_index(owner_id) or bm25_store.has_index(owner_id)

    if not use_persistent:
        fallback = await _fallback_full_scan(
            query, dense_query_variants, owner_id, db, settings, llm
        )
        if fallback is None:
            return {"results": [], "found": False}
        chunks, dense_matrix, lex_map, dense_map = fallback
    else:
        # ── Persistent lexical (BM25) candidates ───────────────────────
        bm25_hits = bm25_store.search(owner_id, query, candidate_k)
        lex_scores_raw = np.array([s for _, s in bm25_hits], dtype=float)
        lex_scores_norm = _normalize(lex_scores_raw)
        lex_map = {cid: float(s) for (cid, _), s in zip(bm25_hits, lex_scores_norm)}

        # ── Persistent dense (FAISS) candidates, aggregated across all
        #    query variants (+ HyDE) via max score per chunk ────────────
        dense_map: dict[str, float] = {}
        if dense_query_variants:
            try:
                embeddings = await llm.embed(dense_query_variants, settings.embedding_model)
                for emb in embeddings:
                    for cid, score in vector_store.search(owner_id, emb, candidate_k):
                        if score > dense_map.get(cid, -1e9):
                            dense_map[cid] = score
            except Exception:
                pass

        candidate_ids = list({*lex_map.keys(), *dense_map.keys()})
        if not candidate_ids:
            return {"results": [], "found": False}

        chunks = await _fetch_chunks_by_id(db, owner_id, candidate_ids)
        if not chunks:
            return {"results": [], "found": False}

        embeddings_present = [c.get("embedding") for c in chunks]
        uniform_dims = len({len(e) for e in embeddings_present if e}) <= 1
        if embeddings_present and all(embeddings_present) and uniform_dims:
            dense_matrix = np.array(embeddings_present)
        else:
            # Mixed/missing embeddings (e.g. some chunks predate the current
            # embedding model) — numpy can't build a matrix from ragged
            # rows, so skip dense diversity scoring for this candidate set
            # rather than crashing; lexical + rerank still apply.
            dense_matrix = np.array([])

    fusion_method = getattr(settings, "fusion_method", "rrf")
    scored = []
    if fusion_method == "rrf":
        fused = rrf_fuse(lex_map, dense_map, getattr(settings, "rrf_k", 60))
        # RRF scores have no fixed scale (they depend on how many candidates
        # were fused), so normalize to [0, 1] against the best score in
        # *this* query's candidate set — keeps relevance_threshold and the
        # confidence-score display meaningful regardless of fusion method.
        max_fused = max(fused.values()) if fused else 0.0
        for i, c in enumerate(chunks):
            lexical = lex_map.get(c["id"], 0.0)
            semantic = dense_map.get(c["id"], 0.0)
            raw = fused.get(c["id"], 0.0)
            score = (raw / max_fused) if max_fused > 0 else 0.0
            scored.append({**c, "index": i, "score": score, "lexical": lexical, "semantic": semantic})
    else:
        for i, c in enumerate(chunks):
            lexical = lex_map.get(c["id"], 0.0)
            semantic = dense_map.get(c["id"], lexical if not dense_map else 0.0)
            score = settings.hybrid_alpha * semantic + (1 - settings.hybrid_alpha) * lexical
            scored.append({**c, "index": i, "score": score, "lexical": lexical, "semantic": semantic})

    scored.sort(key=lambda s: s["score"], reverse=True)
    relevant = [s for s in scored if s["score"] > (settings.relevance_threshold or 0.05)]

    if not relevant:
        return {"results": [], "found": False}

    if getattr(settings, "use_cross_encoder_rerank", False):
        # Rerank a WIDE candidate pool (not just the post-MMR top_k) with the
        # precise cross-encoder, *then* narrow to top_k with MMR — doing it
        # the other way around (as before) let MMR throw away everything
        # outside the coarse first-stage top_k before the more accurate
        # reranker ever got a chance to look at it, which defeats the entire
        # point of reranking: a genuinely better match ranked at position
        # top_k+1 by the fused BM25/dense score could never be recovered.
        rerank_pool = relevant[: min(len(relevant), max(settings.top_k * 4, 20))]
        reranked = await rerank(query, rerank_pool, llm)
        if reranked and reranked[0].get("rerank_score", 10) < 2:
            return {"results": [], "found": False}
        # Swap in the cross-encoder score as the relevance signal MMR uses
        # for its diversity trade-off — it's a strictly more accurate
        # measure of relevance than the coarse fused score it replaces.
        for r in reranked:
            r["score"] = r.get("rerank_score", r["score"] * 10) / 10.0
        ranked = apply_mmr(reranked, dense_matrix, settings.mmr_lambda, settings.top_k)
        ranked = ranked[: settings.top_k]
    else:
        ranked = apply_mmr(relevant, dense_matrix, settings.mmr_lambda, settings.top_k)
        ranked = ranked[: settings.top_k]

    return {"results": ranked, "found": True}
