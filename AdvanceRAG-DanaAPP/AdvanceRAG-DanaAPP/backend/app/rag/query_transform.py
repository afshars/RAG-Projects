"""Query-strengthening techniques run before retrieval:

- Query decomposition: breaks a compound/multi-part question into 2-4
  focused sub-questions, so retrieval isn't dominated by whichever part of
  the question has the most common words.
- HyDE (Hypothetical Document Embeddings): asks the LLM to *sketch a plausible
  answer* to the question (even though it may not know the real answer), then
  embeds that hypothetical answer instead of (or alongside) the raw query.
  Answers and source passages tend to be phrased more like each other than a
  short question is like a passage, so this usually improves dense-retrieval
  recall.

Both degrade to a no-op (returning just the original query) if the LLM call
fails for any reason — retrieval always has a safe fallback.
"""
import json
import re

from app.rag.llm_client import LLMClient


async def decompose_query(query: str, llm: LLMClient, max_subqueries: int = 4) -> list[str]:
    prompt = (
        "متن زیر یک سوال کاربر است. اگر سوال شامل چند بخش یا چند مفهوم مجزا "
        "است، آن را به ۲ تا {n} زیرسوال مستقل و دقیق‌تر بشکن که هرکدام برای "
        "جستجو در یک پایگاه دانش مناسب باشند. اگر سوال از قبل ساده و تک‌بخشی "
        "است، فقط همان یک سوال را برگردان.\n\n"
        "فقط یک آرایه JSON از رشته‌ها برگردان، بدون هیچ توضیح اضافه. مثال: "
        '["زیرسوال اول", "زیرسوال دوم"]\n\n'
        f"سوال: {query}"
    ).format(n=max_subqueries)

    try:
        raw = await llm.chat_completion(
            [
                {"role": "system", "content": "You output only valid JSON arrays of strings, nothing else."},
                {"role": "user", "content": prompt},
            ],
            temperature=0,
        )
        match = re.search(r"\[.*\]", raw, re.DOTALL)
        payload = match.group(0) if match else raw
        subqueries = json.loads(payload)
        cleaned = [q.strip() for q in subqueries if isinstance(q, str) and q.strip()]
        if not cleaned:
            return [query]
        # Always keep the original query in the mix — decomposition helps,
        # but shouldn't ever fully replace the user's actual question.
        if query not in cleaned:
            cleaned.insert(0, query)
        return cleaned[: max_subqueries + 1]
    except Exception:
        return [query]


async def generate_hyde(query: str, llm: LLMClient) -> str | None:
    prompt = (
        "برای سوال زیر، یک پاسخ فرضی کوتاه (۳ تا ۵ جمله) به همان زبان سوال "
        "بنویس؛ حتی اگر مطمئن نیستی، بهترین حدس محتمل را به سبک یک پاراگراف "
        "مرجع/دانشنامه‌ای بنویس. فقط متن پاسخ فرضی را برگردان، بدون مقدمه.\n\n"
        f"سوال: {query}"
    )
    try:
        hypothetical = await llm.chat_completion(
            [
                {"role": "system", "content": "You write short, plausible hypothetical answers used only to improve search retrieval."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.3,
        )
        hypothetical = (hypothetical or "").strip()
        return hypothetical or None
    except Exception:
        return None
