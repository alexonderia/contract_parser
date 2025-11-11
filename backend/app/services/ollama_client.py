"""Client wrapper around the Ollama REST API."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional

import requests

logger = logging.getLogger(__name__)


class OllamaError(RuntimeError):
    """Raised when the Ollama API returns an unexpected response."""


@dataclass
class OllamaResponse:
    """Structured response from the Ollama API."""

    model: str
    response: str
    raw: Dict[str, Any]


class OllamaClient:
    """Synchronous HTTP client for Ollama interactions."""

    def __init__(self, base_url: str = "http://localhost:11434") -> None:
        self.base_url = base_url.rstrip("/")

    # ---------------------------------------------------------------------
    # Helper HTTP methods
    # ---------------------------------------------------------------------
    def _get(self, path: str) -> Dict[str, Any]:
        url = f"{self.base_url}{path}"
        try:
            response = requests.get(url, timeout=10)
        except requests.RequestException as exc:  # pragma: no cover - network errors are rare
            raise OllamaError(f"Failed to connect to Ollama at {url}: {exc}") from exc
        if response.status_code != 200:
            raise OllamaError(f"Ollama GET {url} failed with status {response.status_code}: {response.text}")
        return response.json()

    def _post(self, path: str, payload: Dict[str, Any]) -> Dict[str, Any] | List[Dict[str, Any]]:
        url = f"{self.base_url}{path}"
        try:
            response = requests.post(url, json=payload, timeout=60)
        except requests.RequestException as exc:  # pragma: no cover
            raise OllamaError(f"Failed to connect to Ollama at {url}: {exc}") from exc
        if response.status_code != 200:
            raise OllamaError(
                f"Ollama POST {url} failed with status {response.status_code}: {response.text}"
            )
        content_type = response.headers.get("Content-Type", "application/json")
        if "json" not in content_type:
            raise OllamaError(f"Unexpected content type from Ollama: {content_type}")
        return response.json()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def check_connection(self) -> Dict[str, Any]:
        """Return the list of available models as a health indicator."""

        return self._get("/api/tags")

    def list_models(self) -> Iterable[str]:
        """Return the names of locally available models."""

        tags = self._get("/api/tags")
        for item in tags.get("models", []):
            name = item.get("name")
            if name:
                yield name

    def ensure_model(self, model: str) -> None:
        """Ensure that a model is available locally."""

        if model in set(self.list_models()):
            logger.info("Model '%s' already available in Ollama instance", model)
            return
        logger.info("Pulling model '%s' from Ollama registry", model)
        payload = {"name": model}
        try:
            data = self._post("/api/pull", payload)
        except OllamaError as exc:
            logger.error("Failed to pull model '%s': %s", model, exc)
            raise
        logger.debug("Model pull response: %s", data)

    def generate(
        self,
        model: str,
        prompt: str,
        *,
        options: Optional[Dict[str, Any]] = None,
        stream: bool = False,
    ) -> OllamaResponse:
        """Generate text from a prompt using Ollama."""

        payload: Dict[str, Any] = {
            "model": model,
            "prompt": prompt,
            "stream": stream,
        }
        if options:
            payload["options"] = options

        data = self._post("/api/generate", payload)
        text = self._extract_response_text(data)
        return OllamaResponse(model=model, response=text, raw={"request": payload, "response": data})

    def chat(
        self,
        model: str,
        messages: List[Dict[str, str]],
        *,
        stream: bool = False,
        options: Optional[Dict[str, Any]] = None,
    ) -> OllamaResponse:
        """Chat with a model using the conversation-style API."""

        payload: Dict[str, Any] = {
            "model": model,
            "messages": messages,
            "stream": stream,
        }
        if options:
            payload["options"] = options

        data = self._post("/api/chat", payload)
        text = self._extract_response_text(data)
        return OllamaResponse(model=model, response=text, raw={"request": payload, "response": data})

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _extract_response_text(data: Dict[str, Any] | List[Dict[str, Any]]) -> str:
        """Extract plain text from Ollama responses."""

        if isinstance(data, dict):
            response = data.get("response")
            if response is None:
                return json.dumps(data, ensure_ascii=False)
            return str(response)
        if isinstance(data, list):
            combined = "".join(str(chunk.get("response", "")) for chunk in data)
            if combined:
                return combined
            return json.dumps(data, ensure_ascii=False)
        return json.dumps(data, ensure_ascii=False)