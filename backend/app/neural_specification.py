"""Neural-network powered specification detection service."""
from __future__ import annotations

import json
import logging
import re
from collections import defaultdict
from typing import Any
from string import Template

from .document_models import Block
from .document_processing import (
    blocks_to_prompt_lines_with_mapping,
    load_blocks,
)
from .llm_utils import build_debug_info, extract_reply
from .ollama import client
from .schemas import LlmDebugInfo, SpecificationAnchor, SpecificationResponse, SpecificationTable
from .specification_utils import is_specification_table, table_has_goods

logger = logging.getLogger("contract_parser.backend.neural_spec")

_SYSTEM_PROMPT = """Вы анализируете контракты и находите разделы со спецификациями."""

_USER_PROMPT_TEMPLATE = Template("""
Ты анализируешь документ и должен найти раздел "СПЕЦИФИКАЦИЯ".
Этот раздел обычно начинается строкой, где встречается слово "СПЕЦИФИКАЦИЯ",
и включает в себя одну или несколько таблиц ("TABLE:") и сопровождающий текст.
Заканчивается раздел строкой, где встречается фраза "Общая цена" или "Общая сумма".
Документ передаётся в виде пронумерованных строк.
Найди диапазон строк, где начинается и заканчивается спецификация.
Строки таблиц начинаются с "TABLE:".

Если найден раздел со спецификацией, верни JSON строго следующего вида:

{
  "found": true,
  "heading": "строка с заголовком",
  "start": {"line": <номер строки>, "preview": "короткое описание начала"},
  "end": {"line": <номер строки>, "preview": "короткое описание конца"},
  "tables": [
    {
      "index": <номер таблицы от 0>,
      "row_count": <число строк>,
      "column_count": <число столбцов>,
      "preview": "первые слова таблицы",
      "start": {"line": <номер первой строки TABLE>, "preview": "начало таблицы"},
      "end": {"line": <номер последней строки TABLE>, "preview": "конец таблицы"},
      "rows": []
    }
  ]
}

Если раздел не найден, верни:
{
  "found": false,
  "reason": "объяснение"
}

Не добавляй текстовых комментариев, только JSON.

Документ:
$document
""")


def _enumerate_document(lines: list[str]) -> str:
    """Convert list of document lines to a numbered representation."""
    rows: list[str] = []
    for index, line in enumerate(lines):
        clean_line = str(line).replace("\n", " ").strip()
        if clean_line:
            rows.append(f"{index:04d}: {clean_line}")
    return "\n".join(rows) if rows else "(пустой документ)"


def _coerce_index(value: Any) -> int:
    try:
        index = int(value)
    except (TypeError, ValueError):
        return -1
    return index if index >= 0 else -1


def _anchor_from_payload(
    payload: dict[str, Any],
    fallback_lines: list[str],
    *,
    default_type: str = "paragraph",
) -> SpecificationAnchor:
    line_index = _coerce_index(payload.get("line"))
    preview = str(payload.get("preview") or "").strip()
    if 0 <= line_index < len(fallback_lines) and not preview:
        preview = fallback_lines[line_index][:200]
    block_type = str(payload.get("type") or default_type)
    if block_type not in {"paragraph", "table"}:
        block_type = default_type
    return SpecificationAnchor(index=line_index, type=block_type, preview=preview[:200])

def _find_tables_in_section(
    blocks: list[Block],
    mapping: list[tuple[int, int]],
    start_index: int,
    end_index: int,
) -> list[SpecificationTable]:
    """Return tables present within the detected specification boundaries."""

    if not mapping:
        return []

    total_lines = len(mapping)
    if start_index < 0:
        start_index = 0
    if end_index < 0 or end_index >= total_lines:
        end_index = total_lines - 1
    if end_index < start_index:
        end_index = total_lines - 1

    block_line_positions: dict[int, list[int]] = defaultdict(list)
    for line_index, (block_index, _) in enumerate(mapping):
        block_line_positions[block_index].append(line_index)

    seen_blocks: set[int] = set()
    detected: list[SpecificationTable] = []

    for line_index in range(start_index, min(end_index, total_lines - 1) + 1):
        block_index, _ = mapping[line_index]
        if block_index in seen_blocks:
            continue

        block = blocks[block_index]
        if block.type != "table":
            continue

        rows = block.rows or []
        if not rows:
            continue

        if not is_specification_table(block):
            continue

        line_positions = block_line_positions.get(block_index) or []
        if not line_positions:
            continue

        preview = " | ".join(rows[0])[:200]
        end_preview = " | ".join(rows[-1])[:200]

        start_anchor = SpecificationAnchor(
            index=line_positions[0],
            type="table",
            preview=preview or "Таблица",
        )
        end_anchor = SpecificationAnchor(
            index=line_positions[-1],
            type="table",
            preview=end_preview or preview or "Таблица",
        )

        detected.append(
            SpecificationTable(
                index=block_index,
                row_count=len(rows),
                column_count=max((len(row) for row in rows), default=0),
                preview=preview or "Таблица",
                start_anchor=start_anchor,
                end_anchor=end_anchor,
                rows=rows,
            )
        )
        seen_blocks.add(block_index)

    return detected

async def detect_specification(filename: str, payload: bytes) -> tuple[SpecificationResponse, LlmDebugInfo]:
    blocks = load_blocks(filename, payload)
    lines, mapping = blocks_to_prompt_lines_with_mapping(blocks)
    enumerated = _enumerate_document(lines)

    messages = [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {"role": "user", "content": _USER_PROMPT_TEMPLATE.substitute(document=enumerated)},
    ]

    raw = await client.chat(messages)
    debug = build_debug_info(messages, raw)

    reply = extract_reply(raw).strip()

    reply = re.sub(r"^```(?:json)?\s*", "", reply, flags=re.I)
    reply = re.sub(r"\s*```$", "", reply)

    try:
        data = json.loads(reply)
    except json.JSONDecodeError as exc:
        logger.error("LLM JSON parse error: %s", reply)
        raise ValueError(f"Нейросеть вернула неожиданный ответ: {reply}") from exc

    if not data.get("found"):
        reason = str(data.get("reason") or "Раздел 'Спецификация' не найден")
        raise ValueError(reason)

    if "start" in data and "start_anchor" not in data:
        data["start_anchor"] = {**data["start"]}
    if "end" in data and "end_anchor" not in data:
        data["end_anchor"] = {**data["end"]}

    start_anchor = _anchor_from_payload(data.get("start_anchor") or {}, lines)
    end_anchor = _anchor_from_payload(data.get("end_anchor") or {}, lines)

    tables: list[SpecificationTable] = []
    for table_payload in data.get("tables") or []:
        try:
            start_t = _anchor_from_payload(
                table_payload.get("start") or {},
                lines,
                default_type="table",
            )
            end_t = _anchor_from_payload(
                table_payload.get("end") or {},
                lines,
                default_type="table",
            )
            tables.append(
                SpecificationTable(
                    index=_coerce_index(table_payload.get("index")),
                    row_count=int(table_payload.get("row_count") or 0),
                    column_count=int(table_payload.get("column_count") or 0),
                    preview=str(table_payload.get("preview") or "")[:200],
                    start_anchor=start_t,
                    end_anchor=end_t,
                    rows=table_payload.get("rows") or [],
                )
            )
        except Exception:  # pragma: no cover - robust parsing
            continue

    tables = [table for table in tables if table.rows and table_has_goods(table.rows)]

    specification = SpecificationResponse(
        heading=data.get("heading") or "СПЕЦИФИКАЦИЯ",
        start_anchor=start_anchor,
        end_anchor=end_anchor,
        tables=tables,
    )

    detected_tables = _find_tables_in_section(blocks, mapping, start_anchor.index, end_anchor.index)
    if detected_tables:
        specification = specification.copy(update={"tables": detected_tables})

    logger.info("LLM specification prompt: %s", debug.prompt_formatted)
    logger.info("LLM specification response: %s", debug.response_formatted)

    return specification, debug


__all__ = ["detect_specification"]