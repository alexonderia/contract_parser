"""Utilities for extracting specification sections from documents."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from .document_models import Block
from .document_processing import load_blocks
from .specification_utils import is_specification_table

BlockType = Literal["paragraph", "table"]


@dataclass(slots=True)
class TableRegion:
    """Данные о фрагменте прилегающей таблицы в спецификации"""

    index: int
    start_index: int
    end_index: int
    block: Block


@dataclass(slots=True)
class SpecificationResult:
    """Информация о локальном блоке спецификации"""

    heading: str
    start_index: int
    end_index: int
    tables: list[TableRegion]
    start_block: Block
    end_block: Block


class UnsupportedDocumentError(RuntimeError):
    """Raised when a document cannot be parsed."""


def extract_specification(filename: str, content: bytes) -> SpecificationResult:
    """Определенные якори для блока "Спецификация". """

    suffix = Path(filename or "").suffix.lower()
    if suffix not in {".docx", ".txt", ".md"}:
        raise UnsupportedDocumentError("Поддерживаются только файлы DOCX и TXT")

    blocks = load_blocks(filename, content)
    result = _locate_specification(blocks)
    if result is None:
        raise ValueError("В документе не найден раздел 'Спецификация' с таблицами")
    return result

def _locate_specification(blocks: list[Block]) -> SpecificationResult | None:
    heading_index = _find_spec_heading(blocks)
    if heading_index is None:
        return None

    end_patterns = ["общая цена", "общая сумма"]
    
    first_table_index: int | None = None
    last_table_index: int | None = None
    collected_tables: list[TableRegion] = []

    for idx in range(heading_index + 1, len(blocks)):
        block = blocks[idx]
        if block.type == "paragraph":
            paragraph_text = (block.text or "").casefold()
            if any(pattern in paragraph_text for pattern in end_patterns):
                break
            if not block.text:
                continue
            if last_table_index is not None and _looks_like_heading(block.text):
                break


        if block.type == "table":
            flat_text = " ".join(" ".join(row) for row in (block.rows or [])).lower()
            keywords = ["наименован", "ед.", "кол", "цена", "сумм"]
            if any(keyword in flat_text for keyword in keywords):
                last_table_index = idx
                if first_table_index is None:
                    first_table_index = idx
                collected_tables.append(
                    TableRegion(
                        index=idx,
                        start_index=idx,
                        end_index=idx,
                        block=block,
                    )
                )
                continue
            if first_table_index is not None:
                break

    if first_table_index is None or last_table_index is None:
        return None

    heading_text = blocks[heading_index].text or "Спецификация" or "Спецификация №"
    start_block = blocks[heading_index]
    end_block = blocks[last_table_index]

    return SpecificationResult(
        heading=heading_text,
        start_index=heading_index,
        end_index=last_table_index,
        tables=collected_tables,
        start_block=start_block,
        end_block=end_block,
    )


def _find_spec_heading(blocks: list[Block]) -> int | None:
    spec_patterns = [
        "пецификац",
        "пецификация №",
        "приложение №",
        "к договору",
        # "приложение №1",
        # "Номенклатура",
        # "характеристика",
        # "количество",
        # "цена",
    ]
    candidates: list[int] = []

    for idx, block in enumerate(blocks):
        if block.type != "paragraph":
            continue
        text = (block.text or "").casefold()

        if len(text.split()) > 8 and "спецификац" in text:
            continue

        if any(pattern in text for pattern in spec_patterns):
            for look_ahead in range(idx + 1, min(idx + 25, len(blocks))):
                if blocks[look_ahead].type == "table":
                    candidates.append(idx)
                    break
            
    if not candidates:
        return None
    return candidates[-1]


def _looks_like_heading(text: str) -> bool:
    normalized = text.strip()
    if not normalized:
        return False

    if len(normalized) <= 80 and normalized == normalized.upper():
        return True

    if normalized.endswith(":") and len(normalized) <= 120:
        return True

    if normalized.startswith("Приложение"):
        return True

    return False


__all__ = [
    "SpecificationResult",
    "TableRegion",
    "UnsupportedDocumentError",
    "extract_specification",
]