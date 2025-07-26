"""Webhook handler for processing Stripe events."""

import stripe
from sqlalchemy.ext.asyncio import AsyncSession

from airweave import crud
from airweave.core.billing_service import billing_service
from airweave.core.logging import logger


class StripeWebhookHandler:
    """Handle Stripe webhook events with idempotency and error recovery."""

    def __init__(self, db: AsyncSession):
        """Initialize webhook handler with database session.

        Args:
            db: Database session for processing events
        """
        self.db = db

        # Map event types to handler methods
        self.event_handlers = {
            "customer.subscription.created": self._handle_subscription_created,
            "customer.subscription.updated": self._handle_subscription_updated,
            "customer.subscription.deleted": self._handle_subscription_deleted,
            "invoice.payment_succeeded": self._handle_payment_succeeded,
            "invoice.payment_failed": self._handle_payment_failed,
            "customer.subscription.trial_will_end": self._handle_trial_ending,
            "invoice.upcoming": self._handle_invoice_upcoming,
        }

    async def handle_event(self, event: stripe.Event) -> None:
        """Process a Stripe webhook event.

        Args:
            event: Stripe event object
        """
        # Get handler for event type
        handler = self.event_handlers.get(event.type)

        if handler:
            try:
                logger.info(f"Processing webhook event: {event.type} ({event.id})")
                await handler(event)

            except Exception as e:
                logger.error(f"Error handling {event.type}: {e}", exc_info=True)
                raise
        else:
            logger.info(f"Unhandled webhook event type: {event.type}")

    async def _handle_subscription_created(self, event: stripe.Event) -> None:
        """Handle new subscription creation.

        Args:
            event: Stripe event with subscription object
        """
        subscription = event.data.object
        await billing_service.handle_subscription_created(self.db, subscription)

    async def _handle_subscription_updated(self, event: stripe.Event) -> None:
        """Handle subscription updates (plan changes, status changes).

        Args:
            event: Stripe event with subscription object
        """
        subscription = event.data.object

        # Check what changed
        previous_attributes = event.data.get("previous_attributes", {})

        # Log significant changes
        if "status" in previous_attributes:
            logger.info(
                f"Subscription {subscription.id} status changed: "
                f"{previous_attributes['status']} -> {subscription.status}"
            )

        if "items" in previous_attributes:
            logger.info(f"Subscription {subscription.id} plan changed")

        await billing_service.handle_subscription_updated(
            self.db, subscription, previous_attributes
        )

    async def _handle_subscription_deleted(self, event: stripe.Event) -> None:
        """Handle subscription cancellation/deletion.

        Args:
            event: Stripe event with subscription object
        """
        subscription = event.data.object
        await billing_service.handle_subscription_deleted(self.db, subscription)

    async def _handle_payment_succeeded(self, event: stripe.Event) -> None:
        """Handle successful payment."""
        invoice = event.data.object
        await billing_service.handle_payment_succeeded(self.db, invoice)

    async def _handle_payment_failed(self, event: stripe.Event) -> None:
        """Handle failed payment.

        Args:
            event: Stripe event with invoice object
        """
        invoice = event.data.object

        # Log details about the failure
        logger.warning(
            f"Payment failed for invoice {invoice.id}: "
            f"Amount: {invoice.amount_due / 100:.2f} {invoice.currency.upper()}, "
            f"Attempt: {invoice.attempt_count}"
        )

        await billing_service.handle_payment_failed(self.db, invoice)

    async def _handle_trial_ending(self, event: stripe.Event) -> None:
        """Handle trial ending notification (sent 3 days before).

        Args:
            event: Stripe event with subscription object
        """
        subscription = event.data.object

        # Find organization using CRUD
        billing_model = await crud.organization_billing.get_by_stripe_subscription(
            self.db, stripe_subscription_id=subscription.id
        )

        if billing_model:
            # TODO: Send email notification to organization
            logger.info(f"Trial ending soon for organization {billing_model.organization_id}")

    async def _handle_invoice_upcoming(self, event: stripe.Event) -> None:
        """Handle upcoming invoice (sent ~3 days before payment).

        Useful for notifying customers about upcoming charges.

        Args:
            event: Stripe event with invoice object
        """
        invoice = event.data.object

        # Find organization using CRUD
        billing_model = await crud.organization_billing.get_by_stripe_customer(
            self.db, stripe_customer_id=invoice.customer
        )

        if billing_model:
            logger.info(
                f"Upcoming invoice for organization {billing_model.organization_id}: "
                f"Amount: {invoice.amount_due / 100:.2f} {invoice.currency.upper()}"
            )

            # TODO: Send email notification if needed
