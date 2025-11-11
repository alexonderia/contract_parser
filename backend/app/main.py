"""Application entrypoint."""
from __future__ import annotations
import logging
from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.routes import chat, health, specification
from app.api.deps import get_ollama_client
from app.core.config import settings
from app.services.ollama_client import OllamaError


logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
logger = logging.getLogger(__name__)


def create_app() -> FastAPI:
    app = FastAPI(title=settings.app_name)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    api_router = APIRouter(prefix="/api")
    api_router.include_router(health.router)
    api_router.include_router(chat.router)
    api_router.include_router(specification.router)
    app.include_router(api_router)

    @app.on_event("startup")
    def startup_event() -> None:
        client = get_ollama_client()
        try:
            client.ensure_model(settings.specification_model)
        except OllamaError as exc:
            logger.warning("Unable to ensure specification model '%s': %s", settings.specification_model, exc)

    return app


app = create_app()