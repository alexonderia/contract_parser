from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class LlmDebugInfo(BaseModel):
    """Diagnostic information about an LLM interaction."""

    prompt: list[dict[str, str]] = Field(..., description="JSON-представление промпта")
    prompt_formatted: str = Field(..., description="Отформатированный промпт")
    response: dict[str, Any] = Field(..., description="Полный ответ модели")
    response_formatted: str = Field(..., description="Ответ модели с отступами")


class HealthResponse(BaseModel):
    status: str = Field(..., description="Текущее состояние API")
    model: str = Field(..., description="Модель Ollama, которую использует сервис")
    ollama: str = Field(..., description="Базовый URL Ollama, к которому идёт обращение")
    model_available: bool = Field(..., description="Присутствует ли модель среди загруженных в Ollama")


class ModelListResponse(BaseModel):
    current: str = Field(..., description="Активная модель Ollama для запросов")
    available: list[str] = Field(..., description="Перечень моделей, доступных в Ollama")


class ModelSelectRequest(BaseModel):
    model: str = Field(..., description="Название модели Ollama, выбранной пользователем")