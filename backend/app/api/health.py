from __future__ import annotations

import httpx
from fastapi import APIRouter

from ..core import get_settings
from ..llm import client
from ..schemas import HealthResponse

router = APIRouter(prefix="/api", tags=["health"])


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    """Return basic availability information including Ollama model status."""

    cfg = get_settings()
    model_available = False
    try:
        tags = await client.list_models()
        models = tags.get("models", []) if isinstance(tags, dict) else []
        for item in models:
            name = item.get("name") or item.get("model")
            if name == cfg.ollama_model:
                model_available = True
                break
    except httpx.HTTPError:  # pragma: no cover - defensive logging
        pass

    return HealthResponse(
        status="ok",
        model=cfg.ollama_model,
        ollama=cfg.ollama_base_url,
        model_available=model_available,
    )