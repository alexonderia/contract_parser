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
from .document_processing import blocks_to_html, load_blocks
from .llm_utils import build_debug_info, extract_reply
from .neural_specification import detect_specification
from .ollama import client
from .schemas import (
    ChatRequest,
    ChatResponse,
    HealthResponse,
    LlmDebugInfo,
    DocumentSection,
    FullProcessingResponse,
    SectionReviewResponse,
    SimpleChatRequest,
    SpecificationExtractionResponse,
)
from .specification_builder import build_specification_response
from .specification_exporter import export_specification_to_json
from .section_processing import export_sections_bundle, split_into_sections
from .section_reviews import evaluate_section_file

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
    """
    Обработчик простого чата.
    Поддерживает:
      - только текстовое сообщение
      - текст + прикреплённый файл (txt/md/docx)
    """

    # 1. Проверяем, что сообщение есть
    if not message_form or not message_form.strip():
        raise HTTPException(status_code=422, detail="Сообщение не должно быть пустым")

    message = message_form.strip()
    system_prompt = system_prompt_form.strip() if system_prompt_form else None

    # 2. Формируем итоговый массив сообщений
    messages: list[dict[str, str]] = []

    # Системный промпт, если был указан
    if system_prompt:
        messages.append({
            "role": "system",
            "content": system_prompt
        })

    # 3. Если файл был прикреплён — читаем содержимое
    if file is not None:
        try:
            content_bytes = await file.read()
            text_content = ""

            # Попытка прочитать как UTF-8
            try:
                text_content = content_bytes.decode("utf-8", errors="ignore")
            except Exception:
                text_content = ""

            # Если docx — парсим через python-docx
            if file.filename.lower().endswith(".docx"):
                try:
                    from docx import Document
                    import io
                    doc = Document(io.BytesIO(content_bytes))
                    text_content = "\n".join(p.text for p in doc.paragraphs)
                except Exception:
                    pass

            if text_content.strip():
                messages.append({
                    "role": "user",
                    "content": (
                        f"Содержимое прикреплённого документа «{file.filename}»:\n\n"
                        f"{text_content}"
                    )
                })

        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Ошибка чтения файла: {e}")

    # 4. Основное сообщение пользователя
    messages.append({"role": "user", "content": message})

    # 5. Вызываем модель
    return await _perform_chat(messages)

@app.post("/api/sections/review", response_model=SectionReviewResponse)
async def review_sections(file: UploadFile = File(...)) -> SectionReviewResponse:
    content_bytes = await file.read()
    try:
        content = content_bytes.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise HTTPException(status_code=400, detail="Файл должен быть в кодировке UTF-8") from exc

    content = content.strip()
    if not content:
        raise HTTPException(status_code=422, detail="Файл с инструкциями пуст")

    try:
        reviews, overall_score, inaccuracy, red_flags, html_report, debug = await evaluate_section_file(
            content
        )
    except httpx.HTTPStatusError as exc:  # pragma: no cover - defensive logging
        logger.error(
            "Ollama returned HTTP %s while reviewing sections: %s",
            exc.response.status_code,
            exc.response.text,
        )
        raise HTTPException(status_code=502, detail="Ollama вернула ошибку") from exc
    except httpx.HTTPError as exc:  # pragma: no cover - defensive logging
        logger.error("Error talking to Ollama during section review: %s", exc)
        raise HTTPException(status_code=502, detail="Не удалось подключиться к Ollama") from exc

    _perform_debug_logging(debug)

    return SectionReviewResponse(
        reviews=reviews,
        overall_score=overall_score,
        inaccuracy=inaccuracy,
        red_flags=red_flags,
        html=html_report,
        debug=debug,
    )

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

@app.post("/api/sections/full", response_model=FullProcessingResponse)
async def process_full_document(file: UploadFile = File(...)) -> FullProcessingResponse:
    payload = await file.read()
    blocks = load_blocks(file.filename or "", payload)
    docx_text = blocks_to_html(blocks)
    spec_result = _extract_internal_specification_from_payload(file.filename or "", payload)

    specification_text = None
    if spec_result.exported_json_base64:
        try:
            specification_text = base64.b64decode(spec_result.exported_json_base64).decode("utf-8")
        except UnicodeDecodeError:  # pragma: no cover - fallback for unexpected encodings
            specification_text = base64.b64decode(spec_result.exported_json_base64).decode(
                "utf-8", errors="replace"
            )

    if not spec_result.combined_sections_text:
        raise HTTPException(
            status_code=422,
            detail="Не удалось сформировать файл с разделами и инструкциями",
        )

    try:
        (
            reviews,
            overall_score,
            inaccuracy,
            red_flags,
            html_report,
            debug,
        ) = await evaluate_section_file(
            spec_result.combined_sections_text,
            docx_text,
        )
    except httpx.HTTPStatusError as exc:  # pragma: no cover - defensive logging
        logger.error(
            "Ollama returned HTTP %s while building full report: %s",
            exc.response.status_code,
            exc.response.text,
        )
        raise HTTPException(status_code=502, detail="Ollama вернула ошибку") from exc
    except httpx.HTTPError as exc:  # pragma: no cover - defensive logging
        logger.error("Error talking to Ollama during full processing: %s", exc)
        raise HTTPException(status_code=502, detail="Не удалось подключиться к Ollama") from exc

    _perform_debug_logging(debug)

    return FullProcessingResponse(
        docx_text=docx_text,
        specification_text=specification_text,
        overall_score=overall_score,
        inaccuracy=inaccuracy,
        red_flags=red_flags,
        html=html_report,
    )

__all__ = ["app"]