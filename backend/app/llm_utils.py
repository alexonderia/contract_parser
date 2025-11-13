"""Helper utilities for working with Ollama chat responses."""
from __future__ import annotations

import json
from typing import Any

from .schemas import LlmDebugInfo


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


def build_debug_info(messages: list[dict[str, str]], raw: dict[str, Any]) -> LlmDebugInfo:
    """Return a :class:`LlmDebugInfo` instance for logging and responses."""

    prompt_pretty = json.dumps(messages, ensure_ascii=False, indent=2)
    response_pretty = json.dumps(raw, ensure_ascii=False, indent=2)
    return LlmDebugInfo(
        prompt=messages,
        prompt_formatted=prompt_pretty,
        response=raw,
        response_formatted=response_pretty,
    )