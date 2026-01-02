"""
Routes module - API endpoints.
"""

from app.routes.extract import router as extract_router
from app.routes.accounts import router as accounts_router

__all__ = [
    "extract_router",
    "accounts_router",
]
