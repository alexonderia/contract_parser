from __future__ import annotations

import logging

from fastapi import HTTPException, UploadFile

logger = logging.getLogger("contract_parser.backend")


def log_debug_info(debug) -> None:
    """Log LLM prompt/response details when debugging is enabled."""

    if not debug:
        return
    logger.info("LLM prompt: %s", getattr(debug, "prompt_formatted", None))
    logger.info("LLM response: %s", getattr(debug, "response_formatted", None))


async def read_upload_payload(file: UploadFile) -> tuple[str, bytes]:
    """Return filename and raw bytes from an upload, ensuring it is not empty."""

    payload = await file.read()
    if not payload:
        raise HTTPException(status_code=422, detail="Загруженный файл пуст")
    return file.filename or "", payload