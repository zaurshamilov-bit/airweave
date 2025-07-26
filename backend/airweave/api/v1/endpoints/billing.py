"""Billing API endpoints for subscription management."""

from typing import Optional

from fastapi import Depends, Header, HTTPException, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from airweave import schemas
from airweave.api import deps
from airweave.api.router import TrailingSlashRouter
from airweave.core.billing_service import billing_service
from airweave.core.config import settings
from airweave.core.logging import ContextualLogger, logger
from airweave.core.stripe_webhook_handler import StripeWebhookHandler
from airweave.integrations.stripe_client import stripe_client
from airweave.schemas.auth import AuthContext

router = TrailingSlashRouter()


@router.post("/checkout-session", response_model=schemas.CheckoutSessionResponse)
async def create_checkout_session(
    request: schemas.CheckoutSessionRequest,
    db: AsyncSession = Depends(deps.get_db),
    auth_context: AuthContext = Depends(deps.get_auth_context),
    contextual_logger: ContextualLogger = Depends(deps.get_logger),
) -> schemas.CheckoutSessionResponse:
    """Create a Stripe checkout session for subscription.

    This endpoint initiates the Stripe checkout flow for subscribing to a plan.

    Args:
        request: Checkout session request with plan and URLs
        db: Database session
        auth_context: Authentication context
        contextual_logger: Contextual logger

    Returns:
        Checkout session URL to redirect user to

    Raises:
        HTTPException: If billing is disabled or request is invalid
    """
    if not settings.STRIPE_ENABLED:
        raise HTTPException(status_code=400, detail="Billing is not enabled for this instance")

    try:
        # Create checkout session
        checkout_url = await billing_service.start_subscription_checkout(
            db=db,
            organization_id=auth_context.organization_id,
            plan=request.plan,
            success_url=request.success_url,
            cancel_url=request.cancel_url,
            contextual_logger=contextual_logger,
        )

        return schemas.CheckoutSessionResponse(checkout_url=checkout_url)

    except Exception as e:
        contextual_logger.error(f"Failed to create checkout session: {e}")
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.post("/portal-session", response_model=schemas.CustomerPortalResponse)
async def create_portal_session(
    request: schemas.CustomerPortalRequest,
    db: AsyncSession = Depends(deps.get_db),
    auth_context: AuthContext = Depends(deps.get_auth_context),
    contextual_logger: ContextualLogger = Depends(deps.get_logger),
) -> schemas.CustomerPortalResponse:
    """Create a Stripe customer portal session.

    The customer portal allows users to:
    - Update payment methods
    - Download invoices
    - Cancel subscription
    - Update billing address

    Args:
        request: Portal session request with return URL
        db: Database session
        auth_context: Authentication context
        contextual_logger: Contextual logger
    Returns:
        Portal session URL to redirect user to

    Raises:
        HTTPException: If billing is disabled or no billing record exists
    """
    if not settings.STRIPE_ENABLED:
        raise HTTPException(status_code=400, detail="Billing is not enabled for this instance")

    try:
        portal_url = await billing_service.create_customer_portal_session(
            db=db,
            organization_id=auth_context.organization_id,
            return_url=request.return_url,
            contextual_logger=contextual_logger,
        )

        return schemas.CustomerPortalResponse(portal_url=portal_url)

    except Exception as e:
        contextual_logger.error(f"Failed to create portal session: {e}")
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.get("/subscription", response_model=schemas.SubscriptionInfo)
async def get_subscription(
    db: AsyncSession = Depends(deps.get_db),
    auth_context: AuthContext = Depends(deps.get_auth_context),
    contextual_logger: ContextualLogger = Depends(deps.get_logger),
) -> schemas.SubscriptionInfo:
    """Get current subscription information.

    Returns comprehensive subscription details including:
    - Current plan and status
    - Trial information
    - Usage limits
    - Billing period

    Args:
        db: Database session
        auth_context: Authentication context

        contextual_logger: Contextual logger
    Returns:
        Subscription information
    """
    subscription_info = await billing_service.get_subscription_info(
        db, auth_context.organization_id
    )

    return subscription_info


@router.post("/cancel", response_model=schemas.MessageResponse)
async def cancel_subscription(
    request: schemas.CancelSubscriptionRequest,
    db: AsyncSession = Depends(deps.get_db),
    auth_context: AuthContext = Depends(deps.get_auth_context),
    contextual_logger: ContextualLogger = Depends(deps.get_logger),
) -> schemas.MessageResponse:
    """Cancel the current subscription.

    The subscription will be canceled at the end of the current billing period,
    allowing continued access until then. For immediate cancellation, delete
    the organization instead.

    Args:
        request: Cancellation request (empty body)
        db: Database session
        auth_context: Authentication context

        contextual_logger: Contextual logger
    Returns:
        Success message

    Raises:
        HTTPException: If no active subscription or cancellation fails
    """
    if not settings.STRIPE_ENABLED:
        raise HTTPException(status_code=400, detail="Billing is not enabled for this instance")

    try:
        message = await billing_service.cancel_subscription(
            db, auth_context, contextual_logger=contextual_logger
        )

        return schemas.MessageResponse(message=message)

    except Exception as e:
        contextual_logger.error(f"Failed to cancel subscription: {e}")
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.post("/reactivate", response_model=schemas.MessageResponse)
async def reactivate_subscription(
    db: AsyncSession = Depends(deps.get_db),
    auth_context: AuthContext = Depends(deps.get_auth_context),
    contextual_logger: ContextualLogger = Depends(deps.get_logger),
) -> schemas.MessageResponse:
    """Reactivate a subscription that's set to cancel.

    This endpoint can only be used if the subscription is set to cancel
    at the end of the current period.

    Args:
        db: Database session
        auth_context: Authentication context

        contextual_logger: Contextual logger
    Returns:
        Success message

    Raises:
        HTTPException: If subscription is not set to cancel
    """
    if not settings.STRIPE_ENABLED:
        raise HTTPException(status_code=400, detail="Billing is not enabled for this instance")

    try:
        message = await billing_service.reactivate_subscription(
            db=db,
            auth_context=auth_context,
            contextual_logger=contextual_logger,
        )

        return schemas.MessageResponse(message=message)

    except Exception as e:
        contextual_logger.error(f"Failed to reactivate subscription: {e}")
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.post("/cancel-plan-change", response_model=schemas.MessageResponse)
async def cancel_pending_plan_change(
    db: AsyncSession = Depends(deps.get_db),
    auth_context: AuthContext = Depends(deps.get_auth_context),
    contextual_logger: ContextualLogger = Depends(deps.get_logger),
) -> schemas.MessageResponse:
    """Cancel a scheduled plan change (downgrade).

    Args:
        db: Database session
        auth_context: Authentication context

        contextual_logger: Contextual logger
    Returns:
        Success message
    """
    if not settings.STRIPE_ENABLED:
        raise HTTPException(status_code=400, detail="Billing is not enabled")

    try:
        message = await billing_service.cancel_pending_plan_change(
            db, auth_context.organization_id, contextual_logger=contextual_logger
        )
        return schemas.MessageResponse(message=message)
    except Exception as e:
        contextual_logger.error(f"Failed to cancel plan change: {e}")
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.post("/update-plan", response_model=schemas.MessageResponse)
async def update_subscription_plan(
    request: schemas.UpdatePlanRequest,
    db: AsyncSession = Depends(deps.get_db),
    auth_context: AuthContext = Depends(deps.get_auth_context),
    contextual_logger: ContextualLogger = Depends(deps.get_logger),
) -> schemas.MessageResponse:
    """Update subscription to a different plan.

    Upgrades take effect immediately with proration.
    Downgrades take effect at the end of the current billing period.

    Args:
        request: Plan update request
        db: Database session
        auth_context: Authentication context

        contextual_logger: Contextual logger
    Returns:
        Success message or redirect URL

    Raises:
        HTTPException: If update fails
    """
    if not settings.STRIPE_ENABLED:
        raise HTTPException(status_code=400, detail="Billing is not enabled for this instance")

    try:
        message = await billing_service.update_subscription_plan(
            db=db,
            organization_id=auth_context.organization_id,
            new_plan=request.plan,
            contextual_logger=contextual_logger,
        )

        return schemas.MessageResponse(message=message)

    except Exception as e:
        contextual_logger.error(f"Failed to update subscription plan: {e}")
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.post("/webhook", include_in_schema=False)
async def stripe_webhook(
    request: Request,
    stripe_signature: Optional[str] = Header(None),
    db: AsyncSession = Depends(deps.get_db),
) -> Response:
    """Handle Stripe webhook events.

    This endpoint receives and processes Stripe webhook events for:
    - Subscription lifecycle (created, updated, deleted)
    - Payment events (succeeded, failed)
    - Customer events

    Security:
    - Verifies webhook signature
    - Idempotent processing
    - Comprehensive error handling

    Args:
        request: Raw HTTP request
        stripe_signature: Stripe signature header
        db: Database session

    Returns:
        200 OK on success, 400 on error
    """
    # Create a contextual logger for webhook processing
    webhook_logger = logger.with_context(auth_method="stripe_webhook", endpoint="billing_webhook")

    if not settings.STRIPE_ENABLED:
        return Response(status_code=200)

    # Get raw body
    try:
        payload = await request.body()
    except Exception as e:
        webhook_logger.error(f"Failed to get request body: {e}")
        return Response(status_code=400)

    # Verify signature
    if not stripe_signature:
        webhook_logger.error("Missing Stripe signature header")
        return Response(status_code=400)

    try:
        event = stripe_client.construct_webhook_event(payload, stripe_signature)
    except ValueError as e:
        webhook_logger.error(f"Invalid webhook payload: {e}")
        return Response(status_code=400)
    except Exception as e:  # stripe.error.SignatureVerificationError
        webhook_logger.error(f"Invalid webhook signature: {e}")
        return Response(status_code=400)

    # Process event
    try:
        webhook_handler = StripeWebhookHandler(db)
        await webhook_handler.handle_event(event)

        return Response(status_code=200)

    except Exception as e:
        webhook_logger.error(f"Failed to process webhook event {event.type}: {e}")
        return Response(status_code=500)
