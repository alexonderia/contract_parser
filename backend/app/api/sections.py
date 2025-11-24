from __future__ import annotations

import httpx
from fastapi import APIRouter, File, HTTPException, UploadFile

from .deps import log_debug_info
from ..schemas import SectionReviewResponse
from ..services.section_reviews import evaluate_section_file

router = APIRouter(prefix="/api/sections", tags=["sections"])


@router.post("/review", response_model=SectionReviewResponse)
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
        raise HTTPException(status_code=502, detail="Ollama вернула ошибку") from exc
    except httpx.HTTPError as exc:  # pragma: no cover - defensive logging
        raise HTTPException(status_code=502, detail="Не удалось подключиться к Ollama") from exc

    log_debug_info(debug)

    return SectionReviewResponse(
        reviews=reviews,
        overall_score=overall_score,
        inaccuracy=inaccuracy,
        red_flags=red_flags,
        html=html_report,
        debug=debug,
    )