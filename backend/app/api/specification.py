from __future__ import annotations

import base64
import httpx
from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from .deps import log_debug_info, read_upload_payload
from ..core import UnsupportedDocumentError
from ..document.reader import blocks_to_html, load_blocks
from ..document.spec_extractor import extract_specification_from_blocks
from ..schemas import (
    DocumentSection,
    FullProcessingResponse,
    SpecificationExtractionResponse,
)
from ..services.specification_ai import detect_specification
from ..services.section_splitter import export_sections_bundle, split_into_sections
from ..services.section_reviews import evaluate_section_file
from ..services.specification_internal import build_specification_response
from ..services.full_processing import export_specification_to_json

router = APIRouter(prefix="/api", tags=["specification"])


def _extract_internal_specification_from_payload(
    filename: str,
    payload: bytes,
) -> SpecificationExtractionResponse:
    """Extract specification from the given payload without calling the neural service."""

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
    filename, payload = await read_upload_payload(file)
    try:
        specification, debug = await detect_specification(
            filename,
            payload,
            prompt=prompt,
        )
    except httpx.HTTPStatusError:  # pragma: no cover - defensive logging
        return _extract_internal_specification_from_payload(filename, payload)
    except httpx.HTTPError:  # pragma: no cover - defensive logging
        return _extract_internal_specification_from_payload(filename, payload)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:  # pragma: no cover - defensive logging
        raise HTTPException(status_code=400, detail="Не удалось обработать документ") from exc
    log_debug_info(debug)
    export_payload = export_specification_to_json(
        specification,
        source_filename=filename,
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


@router.post("/specification/ai", response_model=SpecificationExtractionResponse)
async def specification_ai(
    file: UploadFile = File(...),
    prompt: str | None = Form(default=None),
) -> SpecificationExtractionResponse:
    """Handle specification extraction via neural service with safe fallback."""

    return await _extract_ai_specification(file, prompt)


@router.post("/specification/internal", response_model=SpecificationExtractionResponse)
async def specification_internal(file: UploadFile = File(...)) -> SpecificationExtractionResponse:
    """Extract specification using the local parser without calling external services."""

    filename, payload = await read_upload_payload(file)
    return _extract_internal_specification_from_payload(filename, payload)


@router.post("/sections/full", response_model=FullProcessingResponse)
async def process_full_document(file: UploadFile = File(...)) -> FullProcessingResponse:
    """Generate a complete instruction review report based on the uploaded document."""

    filename, payload = await read_upload_payload(file)
    blocks = load_blocks(file.filename or "", payload)
    docx_text = blocks_to_html(blocks)
    spec_result = _extract_internal_specification_from_payload(filename, payload)

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
            _reviews,
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
        raise HTTPException(status_code=502, detail="Ollama вернула ошибку") from exc
    except httpx.HTTPError as exc:  # pragma: no cover - defensive logging
        raise HTTPException(status_code=502, detail="Не удалось подключиться к Ollama") from exc

    log_debug_info(debug)

    return FullProcessingResponse(
        overall_score=overall_score,
        inaccuracy=inaccuracy,
        red_flags=red_flags,
        html=html_report,
        specification_text=specification_text,
        docx_text=docx_text,
    )