from __future__ import annotations

import base64
import hashlib
import httpx
from fastapi import APIRouter, File, Form, HTTPException, Path, UploadFile

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
from ..services.section_splitter import (
    export_sections_bundle,
    export_sections_with_specification,
    import_sections_with_specification,
    build_sections_instruction,
    split_into_sections,
    SectionChunk,
    _resolve_export_dir,
)
from ..services.section_reviews import evaluate_section_file
from ..services.specification_internal import build_specification_response
from ..services.report_registry import (
    fetch_cached_report_html,
    record_report_generation,
)
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


@router.post("/sections/full:{key}", response_model=FullProcessingResponse)
async def process_full_document(
    key: str = Path(...),
    file: UploadFile = File(...),    
) -> FullProcessingResponse:
    """Generate a complete instruction review report based on the uploaded document."""

    normalized_key = (key or "lawyer").strip().lower()
    if normalized_key not in {"lawyer", "economist", "accountant"}:
        raise HTTPException(status_code=422, detail="Некорректный тип обработки")

    filename, payload = await read_upload_payload(file)
    file_hash = hashlib.sha256(payload).hexdigest()
    blocks = load_blocks(file.filename or "", payload)
    docx_text = blocks_to_html(blocks)
    sections_filename = f"{file_hash}.json"
    
    cached_export = import_sections_with_specification(filename_hash=file_hash)
    if cached_export is not None:
        cached_sections, cached_specification, cached_payload_text = cached_export
        combined_sections_text = build_sections_instruction(
            [
                SectionChunk(
                    number=item.number,
                    title=item.title,
                    content=item.content,
                )
                for item in cached_sections
            ],
            cached_payload_text,
        )
        spec_result = SpecificationExtractionResponse(
            specification=cached_specification,
            debug=None,
            exported_json_name=f"{file_hash}.json",
            exported_json_base64=base64.b64encode(
                cached_payload_text.encode("utf-8")
            ).decode("ascii"),
            sections=cached_sections,
            combined_sections_name=None,
            combined_sections_base64=None,
            combined_sections_text=combined_sections_text,
        )
        specification_text = cached_payload_text
    else:
        spec_result = _extract_internal_specification_from_payload(filename, payload)

        specification_text = None
        if spec_result.exported_json_base64:
            try:
                specification_text = base64.b64decode(spec_result.exported_json_base64).decode(
                    "utf-8"
                )
            except UnicodeDecodeError:  # pragma: no cover - fallback for unexpected encodings
                specification_text = base64.b64decode(spec_result.exported_json_base64).decode(
                    "utf-8", errors="replace"
                )

        if not spec_result.combined_sections_text:
            raise HTTPException(
                status_code=422,
                detail="Не удалось сформировать файл с разделами и инструкциями",
            )
        exported_sections = export_sections_with_specification(
            sections=spec_result.sections,
            specification=spec_result.specification,
            source_filename=filename,
            filename_hash=file_hash,
        )
        if exported_sections:
            sections_filename = exported_sections.name

    cached_report = fetch_cached_report_html(file_hash=file_hash)
    if cached_report:
        html_report, entry = cached_report
        return FullProcessingResponse(
            overall_score=entry.overall_score,
            inaccuracy=entry.inaccuracy,
            red_flags=entry.red_flags,
            html=html_report,
            specification_text=specification_text,
            docx_text=docx_text,
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
            role_key=normalized_key,
        )
    except httpx.HTTPStatusError as exc:  # pragma: no cover - defensive logging
        raise HTTPException(status_code=502, detail="Ollama вернула ошибку") from exc
    except httpx.HTTPError as exc:  # pragma: no cover - defensive logging
        raise HTTPException(status_code=502, detail="Не удалось подключиться к Ollama") from exc

    log_debug_info(debug)

    report_path = _resolve_export_dir(None) / f"{file_hash}.html"
    try:
        report_path.write_text(html_report, encoding="utf-8")
    except OSError:
        report_path = None

    if report_path:
        record_report_generation(
            file_hash=file_hash,
            sections_filename=sections_filename,
            source_filename=filename,
            report_filename=report_path.name,
            overall_score=overall_score,
            inaccuracy=inaccuracy,
            red_flags=red_flags,
        )

    return FullProcessingResponse(
        overall_score=overall_score,
        inaccuracy=inaccuracy,
        red_flags=red_flags,
        html=html_report,
        specification_text=specification_text,
        docx_text=docx_text,
    )