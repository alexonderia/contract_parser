from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api import (
    chat_router,
    health_router,
    models_router,
    sections_router,
    specification_router,
)
from .core import configure_logging, get_settings

logger = configure_logging()
settings = get_settings()

app = FastAPI(title="Contract specification parser")
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allow_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(chat_router)
app.include_router(specification_router)
app.include_router(sections_router)
app.include_router(models_router)
app.include_router(health_router)