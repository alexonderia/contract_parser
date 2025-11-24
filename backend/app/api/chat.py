from __future__ import annotations

import httpx
from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile

from .deps import log_debug_info
from ..llm import build_debug_info, client, extract_reply
from ..schemas import ChatRequest, ChatResponse

router = APIRouter(prefix="/api/chat", tags=["chat"])


async def _perform_chat(messages: list[dict[str, str]]) -> ChatResponse:
    """Send chat messages to Ollama and normalize the response format."""

    try:
        raw = await client.chat(messages)
    except httpx.HTTPStatusError as exc:  # pragma: no cover - defensive logging
        raise HTTPException(status_code=502, detail="Ollama вернула ошибку") from exc
    except httpx.HTTPError as exc:  # pragma: no cover - defensive logging
        raise HTTPException(status_code=502, detail="Не удалось подключиться к Ollama") from exc

    debug = build_debug_info(messages, raw)
    log_debug_info(debug)

    reply = extract_reply(raw) or "(пустой ответ)"
    return ChatResponse(reply=reply, raw=raw, debug=debug)


@router.post("", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    messages = [
        {"role": item.role, "content": item.content}
        for item in request.history
        if item.content.strip()
    ]
    messages.append({"role": "user", "content": request.message})

    return await _perform_chat(messages)


@router.post("/simple", response_model=ChatResponse)
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

    if not message_form or not message_form.strip():
        raise HTTPException(status_code=422, detail="Сообщение не должно быть пустым")

    message = message_form.strip()
    system_prompt = system_prompt_form.strip() if system_prompt_form else None

    messages: list[dict[str, str]] = []

    if system_prompt:
        messages.append({
            "role": "system",
            "content": system_prompt
        })

    if file is not None:
        try:
            content_bytes = await file.read()
            text_content = ""

            try:
                text_content = content_bytes.decode("utf-8", errors="ignore")
            except Exception:
                text_content = ""

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

    messages.append({"role": "user", "content": message})

    return await _perform_chat(messages)