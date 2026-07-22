"""Persistent per-user vector index (FAISS), stored on disk under
/app/data/faiss/. Replaces the old approach of loading every chunk's
embedding from SQLite and brute-force scanning it on every single chat
request: the index is built once when documents are ingested (or edited)
and simply loaded + searched on every query after that.

Each user gets their own IndexIDMap2(IndexFlatIP) index — inner product
over L2-normalized vectors is equivalent to cosine similarity, and
IndexIDMap2 lets us address vectors by our own chunk ids and remove them
individually (needed when a document is deleted).

Design notes:
- FAISS ids must be int64, but our chunk ids are uuid4 hex strings, so we
  keep a small JSON sidecar mapping int id <-> chunk_id per user.
- If a user re-embeds with a different embedding model (different vector
  dimensionality), we can't mix dimensions in one FAISS index; in that
  case we transparently drop and rebuild that user's index from scratch
  rather than crashing.
"""
import os
import json
import hashlib

import numpy as np

try:
    import faiss
except Exception:  # pragma: no cover - optional dependency
    faiss = None

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data", "faiss")

_cache: dict[str, dict] = {}  # owner_id -> {"index": faiss.Index, "dim": int, "id_to_chunk": {int: str}}


def _paths(owner_id: str):
    os.makedirs(DATA_DIR, exist_ok=True)
    return (
        os.path.join(DATA_DIR, f"{owner_id}.index"),
        os.path.join(DATA_DIR, f"{owner_id}.meta.json"),
    )


def _chunk_id_to_faiss_id(chunk_id: str) -> int:
    # Stable 60-bit id derived from the chunk's uuid — collisions are
    # astronomically unlikely for a single user's knowledge base.
    return int(hashlib.sha1(chunk_id.encode()).hexdigest()[:15], 16)


def _new_index(dim: int):
    return faiss.IndexIDMap2(faiss.IndexFlatIP(dim))


def _load(owner_id: str, dim: int | None = None) -> dict | None:
    """Returns the cached/loaded store dict for this user, or None if FAISS
    isn't available. If `dim` is given and differs from what's on disk, the
    stored index is dropped and a fresh one for `dim` is created."""
    if faiss is None:
        return None

    if owner_id in _cache:
        entry = _cache[owner_id]
        if dim is not None and entry["dim"] != dim:
            entry = {"index": _new_index(dim), "dim": dim, "id_to_chunk": {}}
            _cache[owner_id] = entry
        return entry

    index_path, meta_path = _paths(owner_id)
    if os.path.exists(index_path) and os.path.exists(meta_path):
        try:
            index = faiss.read_index(index_path)
            with open(meta_path, "r", encoding="utf-8") as f:
                meta = json.load(f)
            id_to_chunk = {int(k): v for k, v in meta["id_to_chunk"].items()}
            entry = {"index": index, "dim": meta["dim"], "id_to_chunk": id_to_chunk}
            if dim is not None and entry["dim"] != dim:
                entry = {"index": _new_index(dim), "dim": dim, "id_to_chunk": {}}
            _cache[owner_id] = entry
            return entry
        except Exception:
            pass  # fall through to a fresh index below

    if dim is None:
        return None
    entry = {"index": _new_index(dim), "dim": dim, "id_to_chunk": {}}
    _cache[owner_id] = entry
    return entry


def _save(owner_id: str, entry: dict):
    index_path, meta_path = _paths(owner_id)
    faiss.write_index(entry["index"], index_path)
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump({"dim": entry["dim"], "id_to_chunk": entry["id_to_chunk"]}, f)


def add_vectors(owner_id: str, items: list[tuple[str, list[float]]]):
    """items: list of (chunk_id, embedding). Skips anything whose
    dimensionality doesn't match the user's existing index (see module
    docstring) instead of crashing — those chunks simply won't be
    dense-searchable until the index is rebuilt for the new dimension."""
    if faiss is None or not items:
        return

    dim = len(items[0][1])
    entry = _load(owner_id, dim=dim)
    if entry is None:
        return

    ids, vecs = [], []
    for chunk_id, embedding in items:
        if len(embedding) != entry["dim"]:
            continue
        fid = _chunk_id_to_faiss_id(chunk_id)
        ids.append(fid)
        vecs.append(embedding)
        entry["id_to_chunk"][fid] = chunk_id

    if not ids:
        return

    mat = np.array(vecs, dtype="float32")
    faiss.normalize_L2(mat)
    id_arr = np.array(ids, dtype="int64")
    # Replace-on-conflict: remove any pre-existing vectors for these ids
    # first (e.g. re-uploading/re-embedding the same chunk).
    entry["index"].remove_ids(id_arr)
    entry["index"].add_with_ids(mat, id_arr)
    _save(owner_id, entry)


def rebuild(owner_id: str, chunks: list[dict]):
    """Full rebuild from a fresh set of {id, embedding} dicts — used after
    a document delete, or to lazily backfill a user who has DB chunks but
    no index yet (pre-upgrade data)."""
    if faiss is None:
        return

    embedded = [c for c in chunks if c.get("embedding")]
    index_path, meta_path = _paths(owner_id)
    _cache.pop(owner_id, None)

    if not embedded:
        for p in (index_path, meta_path):
            if os.path.exists(p):
                os.remove(p)
        return

    dim = len(embedded[0]["embedding"])
    entry = {"index": _new_index(dim), "dim": dim, "id_to_chunk": {}}
    _cache[owner_id] = entry
    add_vectors(owner_id, [(c["id"], c["embedding"]) for c in embedded if len(c["embedding"]) == dim])


def clear(owner_id: str):
    _cache.pop(owner_id, None)
    index_path, meta_path = _paths(owner_id)
    for p in (index_path, meta_path):
        if os.path.exists(p):
            os.remove(p)


def search(owner_id: str, query_vector: list[float], top_k: int) -> list[tuple[str, float]]:
    """Returns [(chunk_id, cosine_score), ...] sorted descending."""
    if faiss is None:
        return []
    entry = _load(owner_id, dim=len(query_vector))
    if entry is None or entry["index"].ntotal == 0:
        return []

    q = np.array([query_vector], dtype="float32")
    faiss.normalize_L2(q)
    k = min(top_k, entry["index"].ntotal)
    scores, ids = entry["index"].search(q, k)

    results = []
    for score, fid in zip(scores[0], ids[0]):
        if fid == -1:
            continue
        chunk_id = entry["id_to_chunk"].get(int(fid))
        if chunk_id:
            results.append((chunk_id, float(score)))
    return results


def has_index(owner_id: str) -> bool:
    entry = _cache.get(owner_id)
    if entry is not None:
        return entry["index"].ntotal > 0
    index_path, meta_path = _paths(owner_id)
    return os.path.exists(index_path) and os.path.exists(meta_path)
