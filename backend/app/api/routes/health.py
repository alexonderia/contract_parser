"""Health check endpoints."""

from fastapi import APIRouter

router = APIRouter()


@router.get("/health", tags=["system"])
def healthcheck() -> dict[str, str]:
    """Simple readiness probe."""

    return {"status": "ok"}