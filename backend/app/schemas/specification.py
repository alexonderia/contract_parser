from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from .common import LlmDebugInfo
from .sections import DocumentSection


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


class SpecificationExtractionResponse(BaseModel):
    specification: SpecificationResponse = Field(..., description="Результаты извлечения")
    debug: LlmDebugInfo | None = Field(
        default=None,
        description="Диагностика, если документ обрабатывался через ИИ",
    )
    exported_json_name: str | None = Field(
        default=None,
        description="Имя JSON-файла с нормализованными позициями спецификации",
    )
    exported_json_base64: str | None = Field(
        default=None,
        description="Содержимое JSON-файла в кодировке base64",
    )
    sections: list[DocumentSection] = Field(
        default_factory=list,
        description="Найденные разделы контракта (для отображения в интерфейсе)",
    )
    combined_sections_name: str | None = Field(
        default=None,
        description="Имя объединенного txt-файла с шапкой и разделами",
    )
    combined_sections_base64: str | None = Field(
        default=None,
        description="Содержимое объединенного txt-файла в base64",
    )
    combined_sections_text: str | None = Field(
        default=None,
        description="Текстовое содержимое объединенного файла",
    )


class CroppedSpecResponse(BaseModel):
    specification: SpecificationResponse = Field(...)
    cropped_file_base64: str = Field(..., description="DOCX файла, base64 без префикса data:")
    cropped_file_name: str = Field(..., description="Имя файла для сохранения на клиенте")