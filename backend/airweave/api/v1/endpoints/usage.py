"""API endpoints for usage data."""

from fastapi import Depends, HTTPException, Query

from airweave import schemas
from airweave.api import deps
from airweave.api.router import TrailingSlashRouter
from airweave.core.exceptions import PaymentRequiredException, UsageLimitExceededException
from airweave.core.guard_rail_service import GuardRailService
from airweave.core.logging import ContextualLogger
from airweave.core.shared_models import ActionType
from airweave.schemas.auth import AuthContext

router = TrailingSlashRouter()


@router.get("/check-action", response_model=schemas.ActionCheckResponse)
async def check_action(
    action: str = Query(
        ...,
        description="The action type to check",
        examples=["queries", "syncs", "entities", "collections", "source_connections"],
    ),
    amount: int = Query(1, ge=1, description="Number of units to check (default 1)"),
    auth_context: AuthContext = Depends(deps.get_auth_context),
    guard_rail: GuardRailService = Depends(deps.get_guard_rail_service),
    logger: ContextualLogger = Depends(deps.get_logger),
) -> schemas.ActionCheckResponse:
    """Check if a specific action is allowed based on usage limits and billing status.

    Returns whether the action is allowed and why it might be blocked.
    Can check for multiple units at once by specifying the amount parameter.
    """
    logger.info(
        f"Checking if action '{action}' (amount={amount}) is allowed "
        f"for organization {auth_context.organization_id}"
    )

    # Validate action type
    try:
        action_type = ActionType(action)
    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid action type: {action}. "
            f"Must be one of: {', '.join([a.value for a in ActionType])}",
        ) from e

    try:
        # Check if the action is allowed
        is_allowed = await guard_rail.is_allowed(action_type, amount=amount)

        return schemas.ActionCheckResponse(
            allowed=is_allowed, action=action, reason=None, details=None
        )

    except PaymentRequiredException as e:
        # Action blocked due to billing status
        return schemas.ActionCheckResponse(
            allowed=False,
            action=action,
            reason="payment_required",
            details={"message": str(e), "payment_status": e.payment_status},
        )

    except UsageLimitExceededException as e:
        # Action blocked due to usage limit
        return schemas.ActionCheckResponse(
            allowed=False,
            action=action,
            reason="usage_limit_exceeded",
            details={"message": str(e), "current_usage": e.current_usage, "limit": e.limit},
        )

    except Exception as e:
        # Unexpected error
        logger.error(f"Unexpected error checking action {action}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error checking action: {str(e)}") from e
