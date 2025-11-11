"""Pydantic schemas for chat endpoints."""

from __future__ import annotations

from typing import List, Literal, Optional

from pydantic import BaseModel, Field


class ChatMessage(BaseModel):
    role: Literal["user", "assistant", "system"]
    content: str = Field(min_length=1)


class ChatRequest(BaseModel):
    message: str = Field(..., description="Message from the user")
    history: Optional[List[ChatMessage]] = Field(
        default=None,
        description="Optional conversation history to provide context to the model.",
    )


class ChatResponse(BaseModel):
    reply: str
    model: str