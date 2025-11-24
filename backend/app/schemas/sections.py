from __future__ import annotations

from pydantic import BaseModel, Field

from .common import LlmDebugInfo


class DocumentSection(BaseModel):
    number: int | None = Field(
        default=None, description="Номер раздела (None для шапки документа)"
    )
    title: str = Field(..., description="Заголовок или текст раздела")
    content: str = Field(..., description="Полное содержимое раздела")
    filename: str | None = Field(
        default=None, description="Имя txt-файла с сохраненным разделом"
    )


class SectionReview(BaseModel):
    title: str = Field(..., description="Название раздела")
    resume: str = Field(..., description="Краткое резюме раздела")
    risks: str = Field(..., description="Перечень рисков по разделу")
    score: str = Field(..., description="Оценка соответствия раздела")


class SectionReviewResponse(BaseModel):
    reviews: list[SectionReview] = Field(..., description="Разбор каждого раздела")
    overall_score: float | None = Field(
        default=None, description="Средняя оценка по всем разделам"
    )
    inaccuracy: str | None = Field(
        default=None, description="Ключевые неточности по документу"
    )
    red_flags: str | None = Field(
        default=None, description="Серьезные ошибки по документу"
    )
    html: str = Field(..., description="HTML-страница со сводкой по разделам")
    debug: LlmDebugInfo | None = Field(
        default=None, description="Отладочная информация с промптом и ответом"
    )


class FullProcessingResponse(BaseModel):
    docx_text: str | None = Field(
        default=None, description="Полный текст документа в формате HTML"
    )
    specification_text: str | None = Field(
        default=None, description="Полный текст спецификации в формате JSON"
    )
    overall_score: float | None = Field(
        default=None, description="Средняя оценка по всем разделам"
    )
    inaccuracy: str | None = Field(
        default=None, description="Ключевые неточности по документу"
    )
    red_flags: str | None = Field(
        default=None, description="Серьезные ошибки по документу"
    )
    html: str = Field(..., description="HTML-страница со сводкой по разделам")
    