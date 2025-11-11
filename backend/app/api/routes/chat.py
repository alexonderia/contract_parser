"""Chat endpoints for interacting with the LLM."""

from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import get_ollama_client
from app.core.config import settings
from app.schemas.chat import ChatRequest, ChatResponse
from app.services.ollama_client import OllamaClient, OllamaError

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("", response_model=ChatResponse)
def chat(
    payload: ChatRequest,
    client: OllamaClient = Depends(get_ollama_client),
) -> ChatResponse:
    """Relay chat messages to the configured Ollama model."""

    history = payload.history or []
    messages = [message.model_dump() for message in history]
    messages.append({"role": "user", "content": payload.message})
    try:
        response = client.chat(model=settings.chat_model, messages=messages, stream=False)
    except OllamaError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return ChatResponse(reply=response.response.strip(), model=response.model)