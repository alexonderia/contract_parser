from __future__ import annotations

import base64
import logging

import httpx
from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from .document_parser import (
    UnsupportedDocumentError,
    extract_specification_from_blocks,
)
from .document_processing import load_blocks
from .llm_utils import build_debug_info, extract_reply
from .neural_specification import detect_specification
from .ollama import client
from .schemas import (
    ChatRequest,
    ChatResponse,
    HealthResponse,
    LlmDebugInfo,
    DocumentSection,
    SimpleChatRequest,
    SpecificationExtractionResponse,
)
from .specification_builder import build_specification_response
from .specification_exporter import export_specification_to_json
from .section_processing import export_sections_bundle, split_into_sections

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
async def simple_chat(
    request: Request,
    message_form: str | None = Form(default=None),
    system_prompt_form: str | None = Form(default=None),
    file: UploadFile | None = File(default=None),
) -> ChatResponse:
    message: str | None = None
    system_prompt: str | None = None
    content_type = request.headers.get("content-type", "").lower()

    expects_json = content_type.startswith("application/json") and not any(
        item is not None for item in (message_form, system_prompt_form, file)
    )

    if expects_json:
        try:
            payload = await request.json()
        except ValueError as exc:  # pragma: no cover - defensive guardrail
            raise HTTPException(status_code=400, detail="Некорректный JSON-запрос") from exc
        data = SimpleChatRequest(**payload)
        message = data.message
        system_prompt = data.system_prompt
    else:
        message = message_form
        system_prompt = system_prompt_form

    if not message or not message.strip():
        raise HTTPException(status_code=422, detail="Сообщение не должно быть пустым")
    messages: list[dict[str, str]] = []
    if system_prompt and system_prompt.strip():
        messages.append({"role": "system", "content": system_prompt.strip()})
    messages.append({"role": "user", "content": message})

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


def _extract_internal_specification_from_payload(
    filename: str,
    payload: bytes,
) -> SpecificationExtractionResponse:
    try:
        suffix = filename.lower()
        if not suffix.endswith((".docx", ".txt", ".md")):
            raise UnsupportedDocumentError("Поддерживаются только файлы DOCX и TXT")
        blocks = load_blocks(filename, payload)
        result = extract_specification_from_blocks(blocks)
    except UnsupportedDocumentError as exc:
        raise HTTPException(status_code=415, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:  # pragma: no cover - defensive logging
        logger.exception("Failed to parse document '%s'", filename)
        raise HTTPException(status_code=400, detail="Не удалось обработать документ") from exc
    specification = build_specification_response(result)
    sections = split_into_sections(blocks)

    export_payload = export_specification_to_json(
        specification,
        source_filename=filename,
    )
    exported_name = None
    exported_base64 = None
    specification_text = None
    if export_payload:
        path, data = export_payload
        exported_name = path.name
        exported_base64 = base64.b64encode(data).decode("ascii")
        try:
            specification_text = data.decode("utf-8")
        except UnicodeDecodeError:  # pragma: no cover - fallback for unexpected encodings
            specification_text = data.decode("utf-8", errors="replace")

    combined_sections = export_sections_bundle(
        sections,
        source_filename=filename,
        specification_text=specification_text,
    )

    combined_name = None
    combined_base64 = None
    combined_text = None
    if combined_sections:
        combined_path, combined_text = combined_sections
        combined_name = combined_path.name
        combined_base64 = base64.b64encode(combined_text.encode("utf-8")).decode("ascii")
    return SpecificationExtractionResponse(
        specification=specification,
        debug=None,
        exported_json_name=exported_name,
        exported_json_base64=exported_base64,
        combined_sections_name=combined_name,
        combined_sections_base64=combined_base64,
        combined_sections_text=combined_text,
        sections=[
            DocumentSection(
                number=section.number,
                title=section.title,
                content=section.content,
                filename=None,
            )
            for section in sections
        ],
    )

async def _extract_ai_specification(
    file: UploadFile,
    prompt: str | None = None,
) -> SpecificationExtractionResponse:
    payload = await file.read()
    try:
        specification, debug = await detect_specification(
            file.filename or "",
            payload,
            prompt=prompt,
        )
    except httpx.HTTPStatusError as exc:  # pragma: no cover - defensive logging
        logger.warning(
            "Neural specification service returned HTTP %s, falling back to internal logic",
            exc.response.status_code,
        )
        return _extract_internal_specification_from_payload(file.filename or "", payload)
    except httpx.HTTPError as exc:  # pragma: no cover - defensive logging
        logger.warning("Error talking to neural specification service, falling back: %s", exc)
        return _extract_internal_specification_from_payload(file.filename or "", payload)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:  # pragma: no cover - defensive logging
        logger.exception("Failed to process document '%s' via neural service", file.filename)
        raise HTTPException(status_code=400, detail="Не удалось обработать документ") from exc
    _perform_debug_logging(debug)
    export_payload = export_specification_to_json(
        specification,
        source_filename=file.filename,
    )
    exported_name = None
    exported_base64 = None
    if export_payload:
        path, data = export_payload
        exported_name = path.name
        exported_base64 = base64.b64encode(data).decode("ascii")

    return SpecificationExtractionResponse(
        specification=specification,
        debug=debug,
        exported_json_name=exported_name,
        exported_json_base64=exported_base64,
    )



async def _extract_internal_specification(file: UploadFile) -> SpecificationExtractionResponse:
    payload = await file.read()
    try:
        suffix = (file.filename or "").lower()
        if not suffix.endswith((".docx", ".txt", ".md")):
            raise UnsupportedDocumentError("Поддерживаются только файлы DOCX и TXT")

        blocks = load_blocks(file.filename or "", payload)
        result = extract_specification_from_blocks(blocks)
    except UnsupportedDocumentError as exc:
        raise HTTPException(status_code=415, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:  # pragma: no cover - defensive logging
        logger.exception("Failed to parse document '%s'", file.filename)
        raise HTTPException(status_code=400, detail="Не удалось обработать документ") from exc
    specification = build_specification_response(result)
    sections = split_into_sections(blocks)
    
    export_payload = export_specification_to_json(
        specification,
        source_filename=file.filename,
    )
    exported_name = None
    exported_base64 = None
    specification_text = None
    if export_payload:
        path, data = export_payload
        exported_name = path.name
        exported_base64 = base64.b64encode(data).decode("ascii")
        try:
            specification_text = data.decode("utf-8")
        except UnicodeDecodeError:  # pragma: no cover - fallback for unexpected encodings
            specification_text = data.decode("utf-8", errors="replace")

    combined_sections = export_sections_bundle(
        sections,
        source_filename=file.filename,
        specification_text=specification_text,
    )

    combined_name = None
    combined_base64 = None
    combined_text = None
    if combined_sections:
        combined_path, combined_text = combined_sections
        combined_name = combined_path.name
        combined_base64 = base64.b64encode(combined_text.encode("utf-8")).decode("ascii")
    return SpecificationExtractionResponse(
        specification=specification,
        debug=None,
        exported_json_name=exported_name,
        exported_json_base64=exported_base64,
        combined_sections_name=combined_name,
        combined_sections_base64=combined_base64,
        combined_sections_text=combined_text,
        sections=[
            DocumentSection(
                number=section.number,
                title=section.title,
                content=section.content,
                filename=None,
            )
            for section in sections
        ],
    )


@app.post("/api/specification/ai", response_model=SpecificationExtractionResponse)
async def specification_ai(
    file: UploadFile = File(...),
    prompt: str | None = Form(default=None),
) -> SpecificationExtractionResponse:
    return await _extract_ai_specification(file, prompt)

@app.post("/api/specification/internal", response_model=SpecificationExtractionResponse)
async def specification_internal(file: UploadFile = File(...)) -> SpecificationExtractionResponse:
    return await _extract_internal_specification(file)


__all__ = ["app"]