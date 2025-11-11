from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class ChatHistoryMessage(BaseModel):
    role: Literal["user", "assistant", "system"] = Field(..., description="Роль автора сообщения")
    content: str = Field(..., description="Текст сообщения")


class ChatRequest(BaseModel):
    message: str = Field(..., description="Сообщение пользователя")
    history: list[ChatHistoryMessage] = Field(
        default_factory=list,
        description="Предыдущие сообщения диалога, чтобы сохранить контекст",
    )


class ChatResponse(BaseModel):
    reply: str = Field(..., description="Ответ модели")
    raw: dict[str, Any] = Field(..., description="Неформатированный ответ Ollama")


class HealthResponse(BaseModel):
    status: str = Field(..., description="Текущее состояние API")
    model: str = Field(..., description="Модель Ollama, которую использует сервис")
    ollama: str = Field(..., description="Базовый URL Ollama, к которому идёт обращение")
    model_available: bool = Field(..., description="Присутствует ли модель среди загруженных в Ollama")