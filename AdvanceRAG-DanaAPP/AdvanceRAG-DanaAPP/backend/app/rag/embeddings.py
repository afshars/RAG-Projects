"""A synchronous LangChain-compatible Embeddings implementation around the
same OpenAI-compatible /embeddings endpoint that LLMClient talks to
asynchronously. LangChain's SemanticChunker (and most of its retriever
utilities) expect a sync `Embeddings` object, so this is a thin, dependency-
light adapter rather than a second embeddings backend.
"""
import httpx

try:
    from langchain_core.embeddings import Embeddings
except Exception:  # langchain not installed — degrade gracefully
    Embeddings = object


class OpenAICompatEmbeddings(Embeddings):
    def __init__(self, base_url: str, api_key: str, model: str, timeout: float = 60.0):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.timeout = timeout

    def _headers(self) -> dict:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    def _embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        with httpx.Client(timeout=self.timeout) as client:
            resp = client.post(
                f"{self.base_url}/embeddings",
                headers=self._headers(),
                json={"model": self.model, "input": texts},
            )
            resp.raise_for_status()
            data = resp.json()
            items = sorted(data["data"], key=lambda d: d["index"])
            return [item["embedding"] for item in items]

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return self._embed(list(texts))

    def embed_query(self, text: str) -> list[float]:
        result = self._embed([text])
        return result[0] if result else []
