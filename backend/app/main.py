from __future__ import annotations

import logging
from typing import Any

import httpx
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from .document_parser import UnsupportedDocumentError, extract_specification
from .ollama import client
from .sсhemas import (
    ChatRequest,
    ChatResponse,
    HealthResponse,
    SpecificationAnchor,
    SpecificationResponse,
    SpecificationTable,
)

logger = logging.getLogger("contract_parser.backend")
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")

app = FastAPI(title="FastAPI → Ollama Qwen2.5")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def _extract_reply(data: dict[str, Any]) -> str:
    message = data.get("message") or {}
    content = message.get("content") or message.get("text")
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        return "\n".join(str(part) for part in content)
    fallback = data.get("response") or data.get("reply") or ""
    return str(fallback).strip()

@app.post("/api/chat", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    messages = [
        {"role": item.role, "content": item.content}
        for item in request.history
        if item.content.strip()
    ]
    messages.append({"role": "user", "content": request.message})
    try:
        raw = await client.chat(messages)
    except httpx.HTTPStatusError as exc:  # pragma: no cover - defensive logging
        logger.error("Ollama returned HTTP %s: %s", exc.response.status_code, exc.response.text)
        raise HTTPException(status_code=502, detail="Ollama вернула ошибку") from exc
    except httpx.HTTPError as exc:  # pragma: no cover - defensive logging
        logger.error("Error talking to Ollama: %s", exc)
        raise HTTPException(status_code=502, detail="Не удалось подключиться к Ollama") from exc

    reply = _extract_reply(raw) or "(пустой ответ)"
    return ChatResponse(reply=reply, raw=raw)

@app.get("/api/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    model_available = False
    try:
        tags = await client.list_models()
        models = tags.get("models", []) if isinstance(tags, dict) else []
        for item in models:
            name = item.get("name") or item.get("model")
            if name == client.model:
                model_available = True
                break
    except httpx.HTTPError as exc:  # pragma: no cover - defensive logging
        logger.warning("Failed to query Ollama tags: %s", exc)

    return HealthResponse(
        status="ok",
        model=client.model,
        ollama=client.base_url,
        model_available=model_available,
    )


def _make_anchor(index: int, block_type: str, preview: str) -> SpecificationAnchor:
    return SpecificationAnchor(index=index, type=block_type, preview=preview)


def _make_table(index: int, rows: list[list[str]], start_index: int, end_index: int) -> SpecificationTable:
    preview = " | ".join(rows[0]) if rows else ""
    end_preview = " | ".join(rows[-1]) if rows else preview
    column_count = max((len(row) for row in rows), default=0)
    start_text = preview or "Таблица"
    end_text = end_preview or start_text
    return SpecificationTable(
        index=index,
        row_count=len(rows),
        column_count=column_count,
        preview=start_text[:200],
        start_anchor=_make_anchor(start_index, "table", start_text[:200]),
        end_anchor=_make_anchor(end_index, "table", end_text[:200]),
        rows=rows,
    )


@app.post("/api/specification", response_model=SpecificationResponse)
async def specification(file: UploadFile = File(...)) -> SpecificationResponse:
    payload = await file.read()
    try:
        result = extract_specification(file.filename or "", payload)
    except UnsupportedDocumentError as exc:
        raise HTTPException(status_code=415, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:  # pragma: no cover - defensive logging
        logger.exception("Failed to parse document '%s'", file.filename)
        raise HTTPException(status_code=400, detail="Не удалось обработать документ") from exc

    start_preview = result.start_block.text or "СПЕЦИФИКАЦИЯ" or "СПЕЦИФИКАЦИЯ №"
    if result.start_block.type == "table" and result.tables:
        first_rows = result.tables[0].block.rows or []
        if first_rows:
            start_preview = " | ".join(first_rows[0])

    end_preview = result.end_block.text
    if result.end_block.type == "table" and result.tables:
        last_rows = result.tables[-1].block.rows or []
        if last_rows:
            last_row = last_rows[-1] or last_rows[0]
            if last_row:
                end_preview = " | ".join(last_row)

    default_start = "Таблица" if result.start_block.type == "table" else ""
    start_text = (start_preview or default_start)[:200]
    default_end = "Таблица" if result.end_block.type == "table" else ""
    end_text = ((end_preview or start_preview) or default_end)[:200]
    start_anchor = _make_anchor(result.start_index, result.start_block.type, start_text)
    end_anchor = _make_anchor(result.end_index, result.end_block.type, end_text or start_text)

    tables = []
    for table_region in result.tables:
        rows = table_region.block.rows or []
        tables.append(
            _make_table(
                index=table_region.index,
                rows=rows,
                start_index=table_region.start_index,
                end_index=table_region.end_index,
            )
        )

    return SpecificationResponse(
        heading=result.heading,
        start_anchor=start_anchor,
        end_anchor=end_anchor,
        tables=tables,
    )