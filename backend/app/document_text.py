"""Utilities for turning uploaded documents into plain text lines."""
from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import Iterable, Literal
import re

from docx import Document
from docx.document import Document as _Document
from docx.oxml.table import CT_Tbl
from docx.oxml.text.paragraph import CT_P
from docx.table import Table
from docx.text.paragraph import Paragraph

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


def _clean_text_noise(text: str) -> str:
    """Normalize placeholder symbols that often surround headings."""

    text = re.sub(r"[«»]", "", text)                 # убираем кавычки-ёлочки
    text = re.sub(r"[_]{2,}", " ", text)             # заменяем последовательности подчеркиваний
    text = re.sub(r"[-]{3,}", " ", text)             # убираем длинные тире
    text = re.sub(r"[.]{3,}", " ", text)             # убираем многоточия
    text = re.sub(r"\s{2,}", " ", text)              # схлопываем лишние пробелы
    return text.strip()



def _iter_docx_blocks(document: _Document) -> Iterable[Paragraph | Table]:
    body = document.element.body
    for element in body.iterchildren():
        if isinstance(element, CT_P):
            yield Paragraph(element, document)
        elif isinstance(element, CT_Tbl):
            yield Table(element, document)

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


def _docx_to_lines(payload: bytes) -> list[Block]:
    document = Document(BytesIO(payload))
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


def _plain_text_to_lines(payload: bytes) -> list[str]:
    text = payload.decode("utf-8", "ignore")
    lines = [_clean_text_noise(line) for line in text.splitlines()]
    return [line for line in lines if line]


def document_to_lines(filename: str, payload: bytes) -> list[str]:
    """Return a list of cleaned lines extracted from the document."""
    suffix = Path(filename or "").suffix.lower()
    if suffix == ".docx":
        return _docx_to_lines(payload)
    return _plain_text_to_lines(payload)