"""Thin wrapper around any OpenAI-compatible API (OpenAI, vLLM, LM Studio,
Groq, Together, etc.) — chosen via base_url + api_key, exactly like the
frontend's settings.llm did.
"""
import json
import httpx
from typing import AsyncIterator


class LLMClient:
    def __init__(self, base_url: str, api_key: str, model: str):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model

    def _headers(self) -> dict:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    async def chat_completion(self, messages: list[dict], temperature: float = 0.3) -> str:
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                f"{self.base_url}/chat/completions",
                headers=self._headers(),
                json={"model": self.model, "messages": messages, "temperature": temperature},
            )
            resp.raise_for_status()
            data = resp.json()
            return data["choices"][0]["message"]["content"] or ""

    async def stream_chat_completion(
        self, messages: list[dict], temperature: float = 0.3
    ) -> AsyncIterator[str]:
        async with httpx.AsyncClient(timeout=None) as client:
            async with client.stream(
                "POST",
                f"{self.base_url}/chat/completions",
                headers=self._headers(),
                json={
                    "model": self.model,
                    "messages": messages,
                    "temperature": temperature,
                    "stream": True,
                },
            ) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    line = line.strip()
                    if not line or not line.startswith("data:"):
                        continue
                    data = line[5:].strip()
                    if data == "[DONE]":
                        return
                    try:
                        chunk = json.loads(data)
                        token = chunk["choices"][0]["delta"].get("content")
                        if token:
                            yield token
                    except (json.JSONDecodeError, KeyError, IndexError):
                        continue

    async def describe_image(self, image_data_url: str, prompt: str) -> str:
        """Sends an image to a vision-capable chat model and returns its
        text description/transcription — used to make image documents
        searchable in the knowledge base (see routers/knowledge.py)."""
        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": image_data_url}},
                ],
            }
        ]
        return await self.chat_completion(messages, temperature=0.2)

    async def embed(self, texts: list[str], embedding_model: str) -> list[list[float]]:
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                f"{self.base_url}/embeddings",
                headers=self._headers(),
                json={"model": embedding_model, "input": texts},
            )
            resp.raise_for_status()
            data = resp.json()
            # sort by index to guarantee order matches input
            items = sorted(data["data"], key=lambda d: d["index"])
            return [item["embedding"] for item in items]
