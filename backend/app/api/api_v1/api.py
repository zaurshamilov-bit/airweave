"""API routes for the FastAPI application."""

from fastapi import APIRouter

from app.api.api_v1.endpoints import api_keys, users

api_router = APIRouter()
api_router.include_router(api_keys.router, prefix="/api_keys", tags=["api_keys"])
api_router.include_router(users.router, prefix="/users", tags=["users"])
