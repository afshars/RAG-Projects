"""Persistent per-user BM25 index, pickled to disk under /app/data/bm25/.

rank_bm25's BM25Okapi has no true incremental-update API (its IDF stats
are a function of the whole corpus), so "adding" a chunk here still means
recomputing the index — but only once, at ingestion time (upload/delete),
and the result is cached in memory + persisted to disk. Queries then just
reuse it, instead of the old behavior of re-tokenizing and rebuilding the
whole corpus on *every single chat request*.
"""
import os
import pickle

from app.rag.tokenizer import tokenize

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data", "bm25")

_cache: dict[str, dict] = {}  # owner_id -> {"bm25": BM25Okapi, "chunk_ids": [str, ...]}


def _path(owner_id: str) -> str:
    os.makedirs(DATA_DIR, exist_ok=True)
    return os.path.join(DATA_DIR, f"{owner_id}.pkl")


def rebuild(owner_id: str, chunks: list[dict]):
    """chunks: list of {id, content}. Rebuilds and persists the index from
    this exact set — call after any upload/delete so it stays in sync with
    the DB."""
    try:
        from rank_bm25 import BM25Okapi
    except Exception:
        return

    path = _path(owner_id)
    if not chunks:
        _cache.pop(owner_id, None)
        if os.path.exists(path):
            os.remove(path)
        return

    tokenized = [tokenize(c["content"]) for c in chunks]
    bm25 = BM25Okapi(tokenized) if any(tokenized) else None
    chunk_ids = [c["id"] for c in chunks]
    entry = {"bm25": bm25, "chunk_ids": chunk_ids}
    _cache[owner_id] = entry

    try:
        with open(path, "wb") as f:
            pickle.dump(entry, f)
    except Exception:
        pass  # in-memory cache still works even if disk persistence fails


def clear(owner_id: str):
    _cache.pop(owner_id, None)
    path = _path(owner_id)
    if os.path.exists(path):
        os.remove(path)


def _load(owner_id: str) -> dict | None:
    if owner_id in _cache:
        return _cache[owner_id]
    path = _path(owner_id)
    if os.path.exists(path):
        try:
            with open(path, "rb") as f:
                entry = pickle.load(f)
            _cache[owner_id] = entry
            return entry
        except Exception:
            return None
    return None


def search(owner_id: str, query: str, top_k: int) -> list[tuple[str, float]]:
    """Returns [(chunk_id, raw_bm25_score), ...] sorted descending, capped
    to top_k. Scores are NOT normalized here (retrieval.py does that once
    it merges with dense scores)."""
    entry = _load(owner_id)
    if not entry or entry["bm25"] is None:
        return []

    scores = entry["bm25"].get_scores(tokenize(query))
    ranked = sorted(
        zip(entry["chunk_ids"], scores), key=lambda pair: pair[1], reverse=True
    )
    return [(cid, float(s)) for cid, s in ranked[:top_k]]


def has_index(owner_id: str) -> bool:
    return _load(owner_id) is not None
