"""API routes for the FastAPI application."""

from fastapi import APIRouter

from app.api.api_v1.endpoints import (
    api_keys,
    connections,
    destinations,
    embedding_models,
    sources,
    users,
)

api_router = APIRouter()
api_router.include_router(api_keys.router, prefix="/api_keys", tags=["api_keys"])
api_router.include_router(users.router, prefix="/users", tags=["users"])
api_router.include_router(sources.router, prefix="/sources", tags=["sources"])
api_router.include_router(destinations.router, prefix="/destinations", tags=["destinations"])
api_router.include_router(
    embedding_models.router, prefix="/embedding_models", tags=["embedding_models"]
)
api_router.include_router(connections.router, prefix="/connections", tags=["connections"])
