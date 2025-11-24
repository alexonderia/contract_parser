from .chat import router as chat_router
from .health import router as health_router
from .sections import router as sections_router
from .specification import router as specification_router

__all__ = [
    "chat_router",
    "health_router",
    "sections_router",
    "specification_router",
]