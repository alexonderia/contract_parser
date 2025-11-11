"""Application configuration and settings management."""

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(env_file=".env", env_prefix="CONTRACT_PARSER_", extra="ignore")

    app_name: str = Field(default="Contract Parser API", description="Human readable application name.")
    environment: Literal["local", "development", "staging", "production"] = Field(
        default="local",
        description="Deployment environment name.",
    )
    ollama_base_url: str = Field(
        default="http://ollama:11434",
        description="Base URL for the Ollama service.",
    )
    specification_model: str = Field(
        default="llama3",
        description="Default model used to extract specification blocks.",
    )
    specification_prompt_template: str = Field(
        default=(
            "You are a contract analysis assistant. Extract only the specification (tables with product"
            " positions, quantities, prices) from the provided contract. Return a compact JSON with the"
            " following structure: {\"specification_sections\": [\"<cleaned block>\", ...],"
            " \"tables\": [[{\"columns\": [\"column name\", ...], \"rows\": [[\"cell\", ...], ...]}]],"
            " \"notes\": \"explain the reasoning shortly\"}. Avoid markdown tables or additional"
            " prose. If nothing resembles a specification return an empty list."
        ),
        description="Prompt template used when communicating with the LLM for specification extraction.",
    )
    chat_model: str = Field(
        default="llama3",
        description="Model used for the generic chat endpoint.",
    )


@lru_cache
def get_settings() -> Settings:
    """Return cached application settings."""

    return Settings()


settings = get_settings()