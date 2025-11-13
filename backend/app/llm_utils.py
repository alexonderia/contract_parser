"""Helper utilities for working with Ollama chat responses."""
from __future__ import annotations

from typing import Any


def extract_reply(data: dict[str, Any]) -> str:
    """Return the textual reply from an Ollama chat response."""
    message = data.get("message") if isinstance(data, dict) else None
    if isinstance(message, dict):
        content = message.get("content") or message.get("text")
        if isinstance(content, str):
            return content.strip()
        if isinstance(content, list):
            joined = "\n".join(str(part) for part in content)
            return joined.strip()
    fallback = data.get("response") or data.get("reply") if isinstance(data, dict) else ""
    return str(fallback or "").strip()