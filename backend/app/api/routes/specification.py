"""Endpoints that expose the specification extraction service."""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from app.api.deps import get_specification_extractor
from app.schemas.specification import (
    ExtractSpecificationRequest,
    SpecificationExtractionResponse,
    SpecificationFileResponse,
)
from app.services.specification_extractor import SpecificationExtractor

router = APIRouter(prefix="/specification", tags=["specification"])


@router.post("/extract", response_model=SpecificationExtractionResponse)
def extract_specification(
    payload: ExtractSpecificationRequest,
    extractor: SpecificationExtractor = Depends(get_specification_extractor),
) -> SpecificationExtractionResponse:
    try:
        result = extractor.extract_specification(payload.text, prefer_model=payload.prefer_model)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return SpecificationExtractionResponse(**result.__dict__)


@router.post("/extract-file", response_model=SpecificationFileResponse)
async def extract_specification_from_file(
    file: UploadFile = File(...),
    extractor: SpecificationExtractor = Depends(get_specification_extractor),
) -> SpecificationFileResponse:
    contents = await file.read()
    try:
        text = contents.decode("utf-8")
    except UnicodeDecodeError:
        text = contents.decode("cp1251", errors="ignore")
    if not text.strip():
        raise HTTPException(status_code=400, detail="Uploaded file is empty or unreadable")
    try:
        result = extractor.extract_specification(text)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    response = SpecificationFileResponse(filename=file.filename or "contract.txt", **result.__dict__)
    return response