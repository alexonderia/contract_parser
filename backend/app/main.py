from __future__ import annotations

import logging

import httpx
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from .document_parser import UnsupportedDocumentError, extract_specification
from .llm_utils import build_debug_info, extract_reply
from .neural_specification import detect_specification
from .ollama import client
from .schemas import (
    ChatRequest,
    ChatResponse,
    HealthResponse,
    LlmDebugInfo,
    SimpleChatRequest,
    SpecificationExtractionResponse,
)
from .specification_builder import build_specification_response

logger = logging.getLogger("contract_parser.backend")
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")

app = FastAPI(title="Contract specification parser")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def _perform_debug_logging(debug: LlmDebugInfo | None) -> None:
    if not debug:
        return
    logger.info("LLM prompt: %s", debug.prompt_formatted)
    logger.info("LLM response: %s", debug.response_formatted)


async def _perform_chat(messages: list[dict[str, str]]) -> ChatResponse:
    try:
        raw = await client.chat(messages)
    except httpx.HTTPStatusError as exc:  # pragma: no cover - defensive logging
        logger.error("Ollama returned HTTP %s: %s", exc.response.status_code, exc.response.text)
        raise HTTPException(status_code=502, detail="Ollama вернула ошибку") from exc
    except httpx.HTTPError as exc:  # pragma: no cover - defensive logging
        logger.error("Error talking to Ollama: %s", exc)
        raise HTTPException(status_code=502, detail="Не удалось подключиться к Ollama") from exc

    debug = build_debug_info(messages, raw)
    _perform_debug_logging(debug)

    reply = extract_reply(raw) or "(пустой ответ)"
    return ChatResponse(reply=reply, raw=raw, debug=debug)

@app.post("/api/chat", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    messages = [
        {"role": item.role, "content": item.content}
        for item in request.history
        if item.content.strip()
    ]
    messages.append({"role": "user", "content": request.message})

    return await _perform_chat(messages)


@app.post("/api/chat/simple", response_model=ChatResponse)
async def simple_chat(request: SimpleChatRequest) -> ChatResponse:
    messages: list[dict[str, str]] = []
    if request.system_prompt and request.system_prompt.strip():
        messages.append({"role": "system", "content": request.system_prompt.strip()})
    messages.append({"role": "user", "content": request.message})

    return await _perform_chat(messages)


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


async def _extract_ai_specification(file: UploadFile) -> SpecificationExtractionResponse:
    payload = await file.read()
    try:
        specification, debug = await detect_specification(file.filename or "", payload)
    except httpx.HTTPStatusError as exc:  # pragma: no cover - defensive logging
        logger.error("Ollama returned HTTP %s: %s", exc.response.status_code, exc.response.text)
        raise HTTPException(status_code=502, detail="Ollama вернула ошибку") from exc
    except httpx.HTTPError as exc:  # pragma: no cover - defensive logging
        logger.error("Error talking to Ollama: %s", exc)
        raise HTTPException(status_code=502, detail="Не удалось подключиться к Ollama") from exc
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:  # pragma: no cover - defensive logging
        logger.exception("Failed to process document '%s' via neural service", file.filename)
        raise HTTPException(status_code=400, detail="Не удалось обработать документ") from exc
    _perform_debug_logging(debug)
    return SpecificationExtractionResponse(specification=specification, debug=debug)


async def _extract_internal_specification(file: UploadFile) -> SpecificationExtractionResponse:
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
    specification = build_specification_response(result)
    return SpecificationExtractionResponse(specification=specification, debug=None)


@app.post("/api/specification/ai", response_model=SpecificationExtractionResponse)
async def specification_ai(file: UploadFile = File(...)) -> SpecificationExtractionResponse:
    return await _extract_ai_specification(file)


@app.post("/api/specification/internal", response_model=SpecificationExtractionResponse)
async def specification_internal(file: UploadFile = File(...)) -> SpecificationExtractionResponse:
    return await _extract_internal_specification(file)


__all__ = ["app"]