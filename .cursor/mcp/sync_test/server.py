"""MCP server for testing Airweave source integrations.

This server provides endpoints for testing source integrations with Airweave:
1. Checking if a source connection is established
2. Running a sync for a specific source connection
"""

import asyncio
import logging
import time
import traceback
from typing import Any

import httpx
import uvicorn
from fastapi import FastAPI, HTTPException
from mcp.server.fastmcp import FastMCP

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("sync-test-mcp-server")

# Constants
BACKEND_URL = "http://localhost:8001"  # Backend service URL for local development
CONNECTION_CHECK_TIMEOUT = 300  # 5 minutes
CONNECTION_CHECK_INTERVAL = 5  # 5 seconds
MAX_RETRIES = 3

# Create MCP server
mcp = FastMCP("Sync Test MCP Server")


async def check_connection_status(short_name: str) -> dict[str, Any]:
    """Check if a source connection is established for the given short_name."""
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            response = await client.get(
                f"{BACKEND_URL}/api/v1/connections/by-short-name/{short_name}"
            )
            response.raise_for_status()
            return {"status": "success", "connection_found": True, "data": response.json()}
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                return {
                    "status": "pending",
                    "connection_found": False,
                    "message": f"No connection found for source: {short_name}",
                }
            return {
                "status": "error",
                "connection_found": False,
                "error": str(e),
                "status_code": e.response.status_code,
            }
        except Exception as e:
            return {"status": "error", "connection_found": False, "error": str(e)}


async def run_sync_for_source(short_name: str) -> dict[str, Any]:
    """Run a sync for the given source short_name."""
    async with httpx.AsyncClient(timeout=60.0) as client:
        try:
            for _ in range(MAX_RETRIES):
                try:
                    # Call the test-sync endpoint
                    response = await client.post(
                        f"{BACKEND_URL}/api/v1/cursor-dev/test-sync/{short_name}"
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
    "Check if a source connection is established. This will poll the backend until a connection is found or timeout is reached.",
)
async def check_connection(short_name: str) -> dict[str, Any]:
    """Check if a source connection is established.

    Args:
        short_name: The short name of the source to check

    Returns:
        A dictionary containing the connection status and details
    """
    logger.info(f"Checking connection for source: {short_name}")

    start_time = time.time()
    while time.time() - start_time < CONNECTION_CHECK_TIMEOUT:
        result = await check_connection_status(short_name)

        if result["status"] == "success" and result["connection_found"]:
            logger.info(f"Connection found for source: {short_name}")
            return result

        if result["status"] == "error":
            logger.error(f"Error checking connection: {result['error']}")
            if "status_code" in result and result["status_code"] != 404:
                # If it's a server error not a 404, return it
                return result

        logger.info(
            f"Connection not found for source: {short_name}, retrying in {CONNECTION_CHECK_INTERVAL} seconds"
        )
        await asyncio.sleep(CONNECTION_CHECK_INTERVAL)

    # Timeout reached
    logger.warning(f"Timeout reached waiting for connection: {short_name}")
    return {
        "status": "timeout",
        "connection_found": False,
        "message": f"Timeout waiting for connection: {short_name}",
    }


@mcp.tool(
    "Run Sync",
    "Run a sync for a source integration. This will first check if a connection exists, then run the sync.",
)
async def run_sync(short_name: str) -> dict[str, Any]:
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
            "error": f"No connection found for source: {short_name}",
            "message": "Please ensure a connection is established before running a sync",
        }

    # Run the sync
    result = await run_sync_for_source(short_name)
    logger.info(f"Sync result for {short_name}: {result['status']}")
    return result


def main() -> None:
    """Run the MCP server."""
    # Create a FastAPI app that mounts the MCP router
    app = FastAPI(title="Sync Test MCP Server")
    mcp.mount_to_app(app)

    # Start the server
    uvicorn.run(app, host="0.0.0.0", port=8100, log_level="info")


if __name__ == "__main__":
    main()
