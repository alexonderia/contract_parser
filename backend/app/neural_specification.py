"""Neural-network powered specification detection service."""
from __future__ import annotations


import base64
import json
import logging
import re
from io import BytesIO
from pathlib import Path
from typing import Any, Iterable, Union

from docx import Document
from docx.document import Document as _Document
from docx.oxml.table import CT_Tbl
from docx.oxml.text.paragraph import CT_P
from docx.table import Table
from docx.text.paragraph import Paragraph

from .document_text import document_to_lines
from .llm_utils import extract_reply
from .ollama import client
from .schemas import SpecificationAnchor, SpecificationResponse, SpecificationTable  # ← проверьте, что файл назван латинским 'schemas.py'

logger = logging.getLogger("contract_parser.backend.neural_spec")

_SYSTEM_PROMPT = """Вы анализируете контракты и находите разделы со спецификациями."""

_USER_PROMPT_TEMPLATE = """
    Ты анализируешь документ и должен найти раздел "СПЕЦИФИКАЦИЯ".
Этот раздел обычно начинается строкой, где встречается слово "СПЕЦИФИКАЦИЯ",
и включает в себя одну или несколько таблиц ("TABLE:") и сопровождающий текст.

Документ передаётся в виде пронумерованных строк. Строки, начинающиеся с "TABLE:", 
соответствуют строкам таблицы.

Если найден раздел со спецификацией, верни JSON строго следующего вида:

{
  "found": true,
  "heading": "строка с заголовком",
  "start": {"line": <номер строки>, "preview": "короткое описание начала"},
  "end": {"line": <номер строки>, "preview": "короткое описание конца"},
  "tables": [
    {
      "index": <номер таблицы>,
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
{document}
    """


def _enumerate_document(lines: list[str]) -> str:
    """Преобразует список строк/блоков в ровно те строки, которые мы показываем LLM."""
    rows: list[str] = []
    for index, line in enumerate(lines):
        if not isinstance(line, str):
            # объект вашего Block: paragraph/table
            if hasattr(line, "type") and getattr(line, "type") == "table":
                table_rows = []
                for r in (getattr(line, "rows", None) or []):
                    joined = " | ".join(cell.strip() for cell in r if cell and str(cell).strip())
                    if joined:
                        table_rows.append(joined)
                line = "TABLE: " + (" / ".join(table_rows) if table_rows else "(пустая таблица)")
            elif hasattr(line, "text"):
                line = str(getattr(line, "text") or "").strip()
            else:
                line = str(line)

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
) -> SpecificationAnchor:
    line_index = _coerce_index(payload.get("line"))
    preview = str(payload.get("preview") or "").strip()
    if 0 <= line_index < len(fallback_lines) and not preview:
        preview = fallback_lines[line_index][:200]
    return SpecificationAnchor(index=line_index, type="table", preview=preview[:200])



async def detect_specification(filename: str, payload: bytes) -> SpecificationResponse:
    lines = document_to_lines(filename, payload)
    enumerated = _enumerate_document(lines)

    messages = [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {"role": "user",  "content": _USER_PROMPT_TEMPLATE.format(document=enumerated)},
    ]

    raw = await client.chat(messages)
    reply = extract_reply(raw).strip()

    # срезаем ```json ... ```
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

    # нормализуем структуру
    if "start" in data and "start_anchor" not in data:
        data["start_anchor"] = {**data["start"]}
    if "end" in data and "end_anchor" not in data:
        data["end_anchor"] = {**data["end"]}

    start_anchor = _anchor_from_payload(data.get("start_anchor") or {})
    end_anchor = _anchor_from_payload(data.get("end_anchor") or {})

    tables: list[SpecificationTable] = []
    for t in data.get("tables") or []:
        try:
            start_t = _anchor_from_payload(t.get("start") or {})
            end_t = _anchor_from_payload(t.get("end") or {})
            tables.append(
                SpecificationTable(
                    index=_coerce_index(t.get("index")),
                    row_count=int(t.get("row_count") or 0),
                    column_count=int(t.get("column_count") or 0),
                    preview=str(t.get("preview") or "")[:200],
                    start_anchor=start_t,
                    end_anchor=end_t,
                    rows=t.get("rows") or [],
                )
            )
        except Exception:
            continue

    return SpecificationResponse(
        heading=data.get("heading") or "СПЕЦИФИКАЦИЯ",
        start_anchor=start_anchor,
        end_anchor=end_anchor,
        tables=tables,
    )