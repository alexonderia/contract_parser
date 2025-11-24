from __future__ import annotations

import os
from functools import lru_cache
from typing import Any


class Settings:
    """Application configuration loaded from environment variables."""

    def __init__(self) -> None:
        self.ollama_base_url: str = os.getenv("OLLAMA_BASE_URL", "http://ollama:11434").rstrip("/")
        self.ollama_model: str = os.getenv("OLLAMA_MODEL", "qwen2.5:1.5b")
        self.ollama_timeout: float = float(os.getenv("OLLAMA_TIMEOUT", "600"))
        self.cors_allow_origins: list[str] = [origin.strip() for origin in os.getenv("CORS_ALLOW_ORIGINS", "*").split(",") if origin.strip()] or ["*"]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


def settings_dict() -> dict[str, Any]:
    cfg = get_settings()
    return {
        "ollama_base_url": cfg.ollama_base_url,
        "ollama_model": cfg.ollama_model,
        "ollama_timeout": cfg.ollama_timeout,
        "cors_allow_origins": cfg.cors_allow_origins,
    }