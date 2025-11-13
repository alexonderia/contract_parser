"""Utilities for turning uploaded documents into prompt-ready lines."""
from __future__ import annotations

from .document_processing import blocks_to_prompt_lines, load_blocks

def document_to_lines(filename: str, payload: bytes) -> list[str]:
    """Return cleaned textual lines extracted from the document."""

    blocks = load_blocks(filename, payload)
    return blocks_to_prompt_lines(blocks)