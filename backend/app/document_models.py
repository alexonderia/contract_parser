"""Common document model definitions used across parsing utilities."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

BlockType = Literal["paragraph", "table"]


@dataclass(slots=True)
class Block:
    """Нормализованное представления блока документа

    Parameters
    ----------
    type:
        The kind of block encountered in the source document.
    text:
        Cleaned text value for paragraph blocks. Tables use an empty string.
    rows:
        Optional two-dimensional representation of table contents.
    """

    type: BlockType
    text: str
    rows: list[list[str]] | None = None


__all__ = ["Block", "BlockType"]