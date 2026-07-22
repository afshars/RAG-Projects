"""RAG evaluation metrics.

Retrieval metrics (Precision@k, Recall@k, MRR, NDCG@k) are computed purely
from a ranked list of retrieved chunk ids against a human-labeled set of
relevant chunk ids — no LLM calls, deterministic, cheap.

Generation metrics (Faithfulness, Answer Relevance) have no ground truth to
compare against mechanically, so — following the same "LLM as a judge"
approach already used for reranking in retrieval.py (`rerank_with_llm`) —
they ask the configured chat model to score the answer and parse a single
0-10 integer out of the reply, defaulting to a neutral score if parsing or
the call itself fails rather than raising.

  Faithfulness      — are the answer's claims actually supported by the
                       retrieved context, or is the model making things up
                       (hallucinating) beyond what the sources say?
  Answer Relevance   — does the answer actually address the user's
                       question, independent of whether it's grounded?

Both are returned as floats in [0, 1].
"""
import re
import math

from app.rag.llm_client import LLMClient


# ── Retrieval metrics ────────────────────────────────────────────────────
def _dcg(gains: list[float]) -> float:
    return sum(g / math.log2(i + 2) for i, g in enumerate(gains))


def _ndcg_at_k(hits: list[int], num_relevant: int, k: int) -> float:
    dcg = _dcg(hits)
    ideal = [1] * min(num_relevant, k) + [0] * max(0, k - min(num_relevant, k))
    idcg = _dcg(ideal)
    return dcg / idcg if idcg > 0 else 0.0


def _reciprocal_rank(retrieved_ids: list[str], relevant_ids: set[str]) -> float:
    for i, rid in enumerate(retrieved_ids):
        if rid in relevant_ids:
            return 1.0 / (i + 1)
    return 0.0


def retrieval_metrics(
    retrieved_ids: list[str], relevant_ids: set[str], k_values: list[int]
) -> dict:
    """Precision@k, Recall@k and NDCG@k (binary relevance) for each k in
    `k_values`, plus a single MRR over the whole ranked list. Assumes
    `relevant_ids` is non-empty — callers should skip items with no
    ground-truth labels rather than calling this with an empty set."""
    metrics: dict[str, float] = {}
    for k in k_values:
        top_k = retrieved_ids[:k]
        hits = [1 if rid in relevant_ids else 0 for rid in top_k]
        num_hits = sum(hits)
        metrics[f"precision@{k}"] = num_hits / k if k > 0 else 0.0
        metrics[f"recall@{k}"] = num_hits / len(relevant_ids) if relevant_ids else 0.0
        metrics[f"ndcg@{k}"] = _ndcg_at_k(hits, len(relevant_ids), k)
    metrics["mrr"] = _reciprocal_rank(retrieved_ids, relevant_ids)
    return metrics


# ── Generation metrics (LLM-as-judge) ────────────────────────────────────
async def _llm_score(system_prompt: str, user_content: str, llm: LLMClient) -> float | None:
    try:
        raw = await llm.chat_completion(
            [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},
            ],
            temperature=0,
        )
        digits = re.sub(r"[^0-9.]", "", raw.strip())
        score = float(digits) if digits else None
        if score is None:
            return None
        return max(0.0, min(10.0, score)) / 10.0
    except Exception:
        return None


FAITHFULNESS_SYSTEM_PROMPT = (
    "You are a strict fact-checking judge for a RAG (retrieval-augmented "
    "generation) system. Given a set of context passages and an answer, "
    "rate how well the answer's claims are supported by ONLY the given "
    "context, on a scale of 0 to 10 (0 = answer is entirely unsupported "
    "or contradicts the context / fabricates facts not present in it, "
    "10 = every claim in the answer is directly supported by the context; "
    "an answer that honestly says the context doesn't contain the answer "
    "also scores 10, since it makes no unsupported claims). "
    "Reply with ONLY a single integer number, nothing else."
)

ANSWER_RELEVANCE_SYSTEM_PROMPT = (
    "You are a judge scoring how relevant an answer is to a user's "
    "question, on a scale of 0 to 10 (0 = answer is off-topic or doesn't "
    "address the question at all, 10 = answer directly and completely "
    "addresses what was asked). Score relevance to the question only — do "
    "NOT judge factual correctness or completeness of sourcing here. "
    "Reply with ONLY a single integer number, nothing else."
)

CONTEXT_PRECISION_SYSTEM_PROMPT = (
    "You are a judge scoring retrieval quality for a RAG system. Given a "
    "user's question and a numbered list of retrieved context passages, "
    "rate what fraction of the passages are actually relevant/useful for "
    "answering the question, on a scale of 0 to 10 (0 = none of the "
    "passages are relevant, 10 = every passage is relevant — no noise "
    "made it into the retrieved context). Judge relevance to the question "
    "only, not whether the passages fully answer it. "
    "Reply with ONLY a single integer number, nothing else."
)


async def evaluate_faithfulness(
    query: str, answer: str, context_chunks: list[str], llm: LLMClient
) -> float | None:
    if not answer.strip():
        return None
    context = "\n\n".join(f"[{i+1}] {c}" for i, c in enumerate(context_chunks)) or "(هیچ منبعی بازیابی نشد)"
    content = f"Context passages:\n{context[:6000]}\n\nQuestion: {query}\n\nAnswer: {answer[:2000]}"
    return await _llm_score(FAITHFULNESS_SYSTEM_PROMPT, content, llm)


async def evaluate_answer_relevance(query: str, answer: str, llm: LLMClient) -> float | None:
    if not answer.strip():
        return None
    content = f"Question: {query}\n\nAnswer: {answer[:2000]}"
    return await _llm_score(ANSWER_RELEVANCE_SYSTEM_PROMPT, content, llm)


async def evaluate_context_precision(
    query: str, context_chunks: list[str], llm: LLMClient
) -> float | None:
    """How much of the *retrieved* context was actually relevant noise-free
    signal — independent of whether an answer was generated at all, and
    independent of ground-truth chunk labels (unlike Precision@k, which
    needs a human-labeled relevant set; this works on any query)."""
    if not context_chunks:
        return None
    context = "\n\n".join(f"[{i+1}] {c}" for i, c in enumerate(context_chunks))
    content = f"Question: {query}\n\nRetrieved passages:\n{context[:6000]}"
    return await _llm_score(CONTEXT_PRECISION_SYSTEM_PROMPT, content, llm)


async def evaluate_generation(
    query: str, answer: str, context_chunks: list[str], llm: LLMClient
) -> dict:
    return {
        "faithfulness": await evaluate_faithfulness(query, answer, context_chunks, llm),
        "answer_relevance": await evaluate_answer_relevance(query, answer, llm),
        "context_precision": await evaluate_context_precision(query, context_chunks, llm),
    }
