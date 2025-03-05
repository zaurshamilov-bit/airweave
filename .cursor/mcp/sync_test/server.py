"""MCP server for testing Airweave source integrations.

This server provides endpoints for testing source integrations with Airweave:
1. Checking if a source connection is established
2. Running a sync for a specific source connection
"""

import asyncio
import logging
import traceback
from typing import Any, Dict

import httpx
from fastapi import HTTPException
from mcp.server.fastmcp import FastMCP

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("sync-test-mcp-server")

# Constants
DEFAULT_BACKEND_URL = "http://localhost:8001"  # Backend service URL for local development
MAX_RETRIES = 3

# Create MCP server
mcp = FastMCP(
    name="Sync Test MCP Server",
    instructions="This server provides tools for testing Airweave source integrations.",
)


async def check_connection_status(short_name: str) -> Dict[str, Any]:
    """Check if a source connection is established for the given short_name."""
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            response = await client.get(
                f"{DEFAULT_BACKEND_URL}/connections/by-short-name/{short_name}"
            )
            response.raise_for_status()
            return {
                "status": "success",
                "connection_found": True,
                "message": f"Connection found for source {short_name}!",
            }
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                return {
                    "status": "error",
                    "connection_found": False,
                    "message": f"No connection detected for source {short_name}",
                }
            return {
                "status": "error",
                "connection_found": False,
                "error": str(e),
                "status_code": e.response.status_code,
                "message": f"No connection detected for source {short_name}",
            }
        except Exception as e:
            return {
                "status": "error",
                "connection_found": False,
                "error": str(e),
                "message": f"No connection detected for source {short_name}",
            }


async def run_sync_for_source(short_name: str) -> Dict[str, Any]:
    """Run a sync for the given source short_name."""
    async with httpx.AsyncClient(timeout=60.0) as client:
        try:
            for _ in range(MAX_RETRIES):
                try:
                    # Call the test-sync endpoint
                    response = await client.post(
                        f"{DEFAULT_BACKEND_URL}/cursor-dev/test-sync/{short_name}"
                    )
                    response.raise_for_status()
                    return {"status": "success", "data": response.json()}
                except httpx.HTTPStatusError as e:
                    if e.response.status_code == 404:
                        raise HTTPException(
                            status_code=404, detail=f"Source {short_name} not found"
                        )
                    # If we get a 500, extract the stacktrace and return it
                    if e.response.status_code == 500:
                        error_data = e.response.json()
                        return {
                            "status": "error",
                            "error": error_data.get("detail", str(e)),
                            "stacktrace": error_data.get("stacktrace"),
                            "status_code": e.response.status_code,
                        }
                    # For other errors, retry
                    await asyncio.sleep(2)
                except Exception:
                    # For connection errors, retry
                    await asyncio.sleep(2)

            # If we've exhausted retries
            return {
                "status": "error",
                "error": "Max retries exceeded when trying to run sync",
            }
        except Exception as e:
            return {"status": "error", "error": str(e), "stacktrace": traceback.format_exc()}


@mcp.tool(
    "Check Connection",
    "Check if a source connection is established.",
)
async def check_connection(short_name: str) -> Dict[str, Any]:
    """Check if a source connection is established.

    Args:
        short_name: The short name of the source to check

    Returns:
        A dictionary containing the connection status and message
    """
    logger.info(f"Checking connection for source: {short_name}")

    result = await check_connection_status(short_name)

    # Just return the result directly, which now includes the appropriate message
    return result


@mcp.tool(
    "Run Sync",
    "Run a sync for a source integration. This will first check if a connection exists, then run the sync.",
)
async def run_sync(short_name: str) -> Dict[str, Any]:
    """Run a sync for a source integration.

    Args:
        short_name: The short name of the source to sync

    Returns:
        A dictionary containing the sync status and results
    """
    logger.info(f"Running sync for source: {short_name}")

    # First check if connection exists
    connection_result = await check_connection_status(short_name)
    if connection_result["status"] != "success" or not connection_result["connection_found"]:
        return {
            "status": "error",
            "error": connection_result.get(
                "message", f"No connection found for source: {short_name}"
            ),
            "message": "Please ensure a connection is established before running a sync",
        }

    # Run the sync
    result = await run_sync_for_source(short_name)
    logger.info(f"Sync result for {short_name}: {result['status']}")
    return result
