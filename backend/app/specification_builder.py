"""Helpers for converting parser results into API schemas."""
from __future__ import annotations

from .document_models import Block
from .document_parser import SpecificationResult, TableRegion
from .schemas import SpecificationAnchor, SpecificationResponse, SpecificationTable


def _block_preview(block: Block) -> str:
    if block.type == "table":
        rows = block.rows or []
        if rows:
            return " | ".join(rows[0])[:200]
        return "Таблица"
    return (block.text or "").strip()[:200]


def _make_anchor(index: int, block: Block, fallback: str | None = None) -> SpecificationAnchor:
    preview = _block_preview(block) or (fallback or "")
    return SpecificationAnchor(index=index, type=block.type, preview=preview)


def _make_table(region: TableRegion) -> SpecificationTable:
    rows = region.block.rows or []
    preview = " | ".join(rows[0])[:200] if rows else "Таблица"
    end_preview = " | ".join(rows[-1])[:200] if rows else preview
    return SpecificationTable(
        index=region.index,
        row_count=len(rows),
        column_count=max((len(row) for row in rows), default=0),
        preview=preview,
        start_anchor=_make_anchor(region.start_index, region.block, preview),
        end_anchor=_make_anchor(region.end_index, region.block, end_preview),
        rows=rows,
    )


def build_specification_response(result: SpecificationResult) -> SpecificationResponse:
    """Convert a :class:`SpecificationResult` to an API response schema."""

    start_anchor = _make_anchor(result.start_index, result.start_block)
    end_anchor = _make_anchor(result.end_index, result.end_block, start_anchor.preview)
    tables = [_make_table(region) for region in result.tables]

    return SpecificationResponse(
        heading=result.heading,
        start_anchor=start_anchor,
        end_anchor=end_anchor,
        tables=tables,
    )


__all__ = ["build_specification_response"]