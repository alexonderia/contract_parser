from __future__ import annotations

"""Utilities for extracting specification sections from documents."""

from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import Iterable, Literal

from docx import Document
from docx.document import Document as _Document
from docx.oxml.table import CT_Tbl
from docx.oxml.text.paragraph import CT_P
from docx.table import Table
from docx.text.paragraph import Paragraph

import re

BlockType = Literal["paragraph", "table"]


@dataclass(slots=True)
class Block:
    """A normalized representation of a document block."""

    type: BlockType
    text: str
    rows: list[list[str]] | None = None


@dataclass(slots=True)
class TableRegion:
    """A contiguous table fragment inside the specification."""

    index: int
    start_index: int
    end_index: int
    block: Block


@dataclass(slots=True)
class SpecificationResult:
    """Information about the located specification block."""

    heading: str
    start_index: int
    end_index: int
    tables: list[TableRegion]
    start_block: Block
    end_block: Block


class UnsupportedDocumentError(RuntimeError):
    """Raised when a document cannot be parsed."""


def extract_specification(filename: str, content: bytes) -> SpecificationResult:
    """Extract anchors for the "Спецификация" block from the document.

    Parameters
    ----------
    filename:
        Name of the uploaded file, used to detect the format.
    content:
        Raw file payload as bytes.

    Returns
    -------
    SpecificationResult
        Information about the detected specification block.

    Raises
    ------
    UnsupportedDocumentError
        If the document type is not supported or cannot be parsed.
    ValueError
        If the document can be parsed but the specification block is missing.
    """

    suffix = Path(filename or "").suffix.lower()
    if suffix == ".docx":
        blocks = _parse_docx(content)
    elif suffix in {".txt", ".md"}:
        blocks = _parse_plain_text(content)
    else:
        raise UnsupportedDocumentError("Поддерживаются только файлы DOCX и TXT")

    result = _locate_specification(blocks)
    if result is None:
        raise ValueError("В документе не найден раздел 'Спецификация' с таблицами")

    return result


def _clean_text_noise(text: str) -> str:
    """Normalize placeholder symbols that often surround headings."""

    text = re.sub(r"[«»]", "", text)                 # убираем кавычки-ёлочки
    text = re.sub(r"[_]{2,}", " ", text)             # заменяем последовательности подчеркиваний
    text = re.sub(r"[-]{3,}", " ", text)             # убираем длинные тире
    text = re.sub(r"[.]{3,}", " ", text)             # убираем многоточия
    text = re.sub(r"\s{2,}", " ", text)              # схлопываем лишние пробелы
    return text.strip()


def _parse_plain_text(content: bytes) -> list[Block]:
    text = content.decode("utf-8", "ignore")
    lines = [line.strip() for line in text.splitlines()]
    blocks: list[Block] = []
    current_table: list[list[str]] = []

    def _flush_table() -> None:
        nonlocal current_table
        if current_table:
            blocks.append(Block(type="table", text="", rows=current_table))
            current_table = []

    for line in lines:
        clean_line = _clean_text_noise(line)
        if not clean_line:
            _flush_table()
            continue
        if "|" in line:
            columns = [col.strip() for col in line.split("|") if col.strip()]
            if columns:
                current_table.append(columns)
                continue
        _flush_table()
        blocks.append(Block(type="paragraph", text=clean_line))

    _flush_table()
    return blocks


def _parse_docx(content: bytes) -> list[Block]:
    document = Document(BytesIO(content))
    blocks: list[Block] = []
    for block in _iter_docx_blocks(document):
        if isinstance(block, Paragraph):
            raw_text = " ".join(part for part in block.text.split() if part)
            text = _clean_text_noise(raw_text)
            blocks.append(Block(type="paragraph", text=text))
        elif isinstance(block, Table):
            rows = _table_to_rows(block)
            if rows:
                blocks.append(Block(type="table", text="", rows=rows))
    return blocks


def _iter_docx_blocks(parent: _Document) -> Iterable[Paragraph | Table]:
    parent_element = parent.element.body
    for child in parent_element.iterchildren():
        if isinstance(child, CT_P):
            yield Paragraph(child, parent)
        elif isinstance(child, CT_Tbl):
            yield Table(child, parent)


def _table_to_rows(table: Table) -> list[list[str]]:
    rows: list[list[str]] = []
    for row in table.rows:
        cells: list[str] = []
        for cell in row.cells:
            fragments = [paragraph.text.strip() for paragraph in cell.paragraphs if paragraph.text.strip()]
            cell_text = " ".join(fragments)
            cells.append(cell_text)
        if any(cell for cell in cells):
            rows.append(cells)
    return rows


def _locate_specification(blocks: list[Block]) -> SpecificationResult | None:
    heading_index = _find_spec_heading(blocks)
    if heading_index is None:
        return None

    END_PATTERNS = ["общая сумма"]

    first_table_index: int | None = None
    last_table_index: int | None = None
    collected_tables: list[TableRegion] = []

    for idx in range(heading_index + 1, len(blocks)):
        block = blocks[idx]
        if block.type == "paragraph":
            paragraph_text = (block.text or "").casefold()
            if any(pattern in paragraph_text for pattern in END_PATTERNS):
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
    SPEC_PATTERNS = ["спецификац", "спецификация №", "приложение №", "приложение к договору"]
    candidates: list[int] = []

    for idx, block in enumerate(blocks):
        if block.type != "paragraph":
            continue
        text = (block.text or "").casefold()

        if len(text.split()) > 8 and "спецификац" in text:
            continue

        if any(pattern in text for pattern in SPEC_PATTERNS):
            for look_ahead in range(idx + 1, min(idx + 6, len(blocks))):
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