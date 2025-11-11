"""Schemas for specification extraction endpoints."""

from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field


class ExtractSpecificationRequest(BaseModel):
    text: str = Field(..., description="Raw contract text to analyse")
    prefer_model: bool = Field(
        default=True,
        description="If true, the LLM will be used before falling back to heuristics.",
    )


class SpecificationExtractionResponse(BaseModel):
    specification_text: str = Field(default="", description="Extracted specification block")
    table_rows: List[List[str]] = Field(
        default_factory=list,
        description="Table rows parsed from the specification block (if any).",
    )
    used_fallback: bool = Field(
        default=False,
        description="Indicates whether the heuristic fallback was used.",
    )
    raw_model_output: Optional[str] = Field(
        default=None,
        description="Raw response returned by the language model, useful for debugging.",
    )
    reasoning: Optional[str] = Field(
        default=None,
        description="Additional notes or reasoning provided by the model.",
    )


class SpecificationFileResponse(SpecificationExtractionResponse):
    filename: str = Field(..., description="Original uploaded file name")