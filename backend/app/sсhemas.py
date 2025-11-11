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


class SpecificationAnchor(BaseModel):
    index: int = Field(..., description="Позиция блока в документе, начиная с 0")
    type: Literal["paragraph", "table"] = Field(..., description="Тип блока")
    preview: str = Field(..., description="Короткий фрагмент текста для ориентирования")


class SpecificationTable(BaseModel):
    index: int = Field(..., description="Позиция таблицы в документе")
    row_count: int = Field(..., description="Количество строк таблицы")
    column_count: int = Field(..., description="Количество столбцов таблицы")
    preview: str = Field(..., description="Первый ряд таблицы или ключевые ячейки")
    start_anchor: SpecificationAnchor = Field(..., description="Якорь начала таблицы")
    end_anchor: SpecificationAnchor = Field(..., description="Якорь конца таблицы")
    rows: list[list[str]] = Field(..., description="Содержимое таблицы построчно")


class SpecificationResponse(BaseModel):
    heading: str = Field(..., description="Заголовок раздела 'Спецификация'")
    start_anchor: SpecificationAnchor = Field(..., description="Начальная точка раздела")
    end_anchor: SpecificationAnchor = Field(..., description="Конечная точка раздела")
    tables: list[SpecificationTable] = Field(..., description="Обнаруженные таблицы раздела")