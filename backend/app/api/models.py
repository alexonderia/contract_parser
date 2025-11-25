from __future__ import annotations

import httpx
from fastapi import APIRouter, HTTPException

from ..llm import client
from ..schemas import ModelListResponse, ModelSelectRequest

router = APIRouter(prefix="/api/models", tags=["models"])


def _extract_model_names(payload: dict[str, object]) -> list[str]:
    models: list[str] = []
    items = payload.get("models") if isinstance(payload, dict) else None

    if isinstance(items, list):
        for item in items:
            if not isinstance(item, dict):
                continue
            name = item.get("name") or item.get("model")
            if isinstance(name, str) and name.strip():
                models.append(name.strip())

    return models


async def _load_available_models() -> list[str]:
    try:
        tags = await client.list_models()
    except httpx.HTTPError as exc:  # pragma: no cover - network/remote errors
        raise HTTPException(
            status_code=502,
            detail="Не удалось получить список моделей Ollama",
        ) from exc

    models = _extract_model_names(tags)
    return models or [client.model]


@router.get("", response_model=ModelListResponse)
async def list_models() -> ModelListResponse:
    models = await _load_available_models()
    return ModelListResponse(current=client.model, available=models)


@router.post("/select", response_model=ModelListResponse)
async def select_model(request: ModelSelectRequest) -> ModelListResponse:
    models = await _load_available_models()

    if request.model not in models:
        raise HTTPException(status_code=404, detail="Модель не найдена среди загруженных")

    client.model = request.model
    return ModelListResponse(current=client.model, available=models)