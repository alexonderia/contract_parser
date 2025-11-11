from __future__ import annotations

import logging
from typing import Any

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from .ollama import client
from .sсhemas import ChatRequest, ChatResponse, HealthResponse

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