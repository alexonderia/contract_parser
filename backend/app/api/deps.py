"""Common dependency functions for API routes."""

from functools import lru_cache
from typing import Generator

from fastapi import Depends

from app.core.config import get_settings, settings
from app.services.ollama_client import OllamaClient
from app.services.specification_extractor import SpecificationExtractor


@lru_cache
def get_ollama_client() -> OllamaClient:
    return OllamaClient(base_url=settings.ollama_base_url)


def get_specification_extractor(
    client: OllamaClient = Depends(get_ollama_client),
) -> SpecificationExtractor:
    return SpecificationExtractor(
        client,
        model=settings.specification_model,
        prompt_template=settings.specification_prompt_template,
    )


def get_app_settings() -> Generator:
    yield get_settings()