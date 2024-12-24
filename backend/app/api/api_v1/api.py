"""This file is used to define the API routes for the FastAPI application."""

from app.api.api_v1.endpoints import (
    api_keys,
    assistants,
    flow_requests,
    flow_results,
    flow_runs,
    flows,
    integration_credentials,
    integrations,
    task_definitions,
    trigger_definitions,
    trigger_operations,
    trigger_runs,
    users,
)
from fastapi import APIRouter

api_router = APIRouter()
api_router.include_router(api_keys.router, prefix="/api_keys", tags=["api_keys"])
api_router.include_router(assistants.router, prefix="/assistants", tags=["assistants"])
api_router.include_router(users.router, prefix="/users", tags=["users"])
api_router.include_router(flow_requests.router, prefix="/flow_requests", tags=["flow_requests"])
api_router.include_router(
    task_definitions.router, prefix="/task_definitions", tags=["task_definitions"]
)
api_router.include_router(flows.router, prefix="/flows", tags=["flows"])
api_router.include_router(flow_runs.router, prefix="/flow_runs", tags=["flow_runs"])
api_router.include_router(
    integration_credentials.router,
    prefix="/integration_credentials",
    tags=["integration_credentials"],
)
api_router.include_router(integrations.router, prefix="/integrations", tags=["integrations"])
api_router.include_router(
    trigger_definitions.router,
    prefix="/trigger_definitions",
    tags=["trigger_definitions"],
)
api_router.include_router(
    trigger_operations.router,
    prefix="/trigger_operations",
    tags=["trigger_operations"],
)
api_router.include_router(trigger_runs.router, prefix="/trigger_runs", tags=["trigger_runs"])
api_router.include_router(flow_results.router, prefix="/flow_results", tags=["flow_results"])
