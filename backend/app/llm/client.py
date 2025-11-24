from __future__ import annotations

from typing import Any, Iterable

import httpx

from ..core import get_settings

class OllamaClient:
    """Минимальный клиент для обращения к Ollama."""

    def __init__(
        self,
        base_url: str | None = None,
        model: str | None = None,
        timeout: float | None = None,
    ) -> None:
        cfg = get_settings()
        self.base_url = (base_url or cfg.ollama_base_url).rstrip("/")
        self.model = model or cfg.ollama_model
        self.timeout = timeout or cfg.ollama_timeout

    async def chat(self, messages: Iterable[dict[str, str]]) -> dict[str, Any]:
        payload = {
            "model": self.model,
            "messages": list(messages),
            "stream": False,
            "options": {
                "temperature": 0 # дефолт
            }
        }
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(f"{self.base_url}/api/chat", json=payload)
            response.raise_for_status()
            return response.json()
        
    async def list_models(self) -> dict[str, Any]:
        """Return the response from the `/api/tags` endpoint."""

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.get(f"{self.base_url}/api/tags")
            response.raise_for_status()
            return response.json()


client = OllamaClient()