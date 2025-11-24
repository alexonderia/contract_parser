from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from .common import LlmDebugInfo


class ChatHistoryMessage(BaseModel):
    role: Literal["user", "assistant", "system"] = Field(..., description="Роль автора сообщения")
    content: str = Field(..., description="Текст сообщения")


class ChatRequest(BaseModel):
    message: str = Field(..., description="Сообщение пользователя")
    history: list[ChatHistoryMessage] = Field(
        default_factory=list,
        description="Предыдущие сообщения диалога, чтобы сохранить контекст",
    )


class SimpleChatRequest(BaseModel):
    message: str = Field(..., description="Сообщение пользователя")
    system_prompt: str | None = Field(
        default=None,
        description="Необязательное системное сообщение, влияющее на стиль ответа",
    )


class ChatResponse(BaseModel):
    reply: str = Field(..., description="Ответ модели")
    raw: dict[str, object] = Field(..., description="Неформатированный ответ Ollama")
    debug: LlmDebugInfo | None = Field(
        default=None,
        description="Отладочная информация с промптом и ответом",
    )