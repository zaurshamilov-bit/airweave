"""Webhook handler for processing Stripe events."""

import stripe
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from airweave.core.billing_service import billing_service
from airweave.core.logging import logger
from airweave.models import BillingEvent, OrganizationBilling


class WebhookHandler:
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

        Implements idempotency by checking if event was already processed.

        Args:
            event: Stripe event object
        """
        # Check if we've already processed this event
        if await self._is_event_processed(event.id):
            logger.info(f"Event {event.id} already processed, skipping")
            return

        # Get handler for event type
        handler = self.event_handlers.get(event.type)

        if handler:
            try:
                logger.info(f"Processing webhook event: {event.type} ({event.id})")
                await handler(event)

                # Event is logged within each handler via billing_service

            except Exception as e:
                logger.error(f"Error handling {event.type}: {e}", exc_info=True)
                raise
        else:
            logger.info(f"Unhandled webhook event type: {event.type}")

    async def _is_event_processed(self, stripe_event_id: str) -> bool:
        """Check if event has already been processed.

        Args:
            stripe_event_id: Stripe event ID

        Returns:
            True if already processed
        """
        query = select(BillingEvent).where(BillingEvent.stripe_event_id == stripe_event_id)
        result = await self.db.execute(query)
        return result.scalar_one_or_none() is not None

    async def _mark_event_processed(self, event: stripe.Event) -> None:
        """Mark event as processed in database.

        Args:
            event: Stripe event object
        """
        # The event is marked as processed by the individual handlers
        # when they call billing_service._log_billing_event with the stripe_event_id
        # This method is kept for interface consistency but doesn't need to do anything
        pass

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

        await billing_service.handle_subscription_updated(self.db, subscription)

        # Log the Stripe event ID
        query = select(OrganizationBilling).where(
            OrganizationBilling.stripe_subscription_id == subscription.id
        )
        result = await self.db.execute(query)
        billing = result.scalar_one_or_none()

        if billing:
            await billing_service._log_billing_event(
                self.db,
                billing.organization_id,
                event.type,
                {"subscription_id": subscription.id, "previous_attributes": previous_attributes},
                stripe_event_id=event.id,
            )

    async def _handle_subscription_deleted(self, event: stripe.Event) -> None:
        """Handle subscription cancellation/deletion.

        Args:
            event: Stripe event with subscription object
        """
        subscription = event.data.object

        # Get billing record before handling
        query = select(OrganizationBilling).where(
            OrganizationBilling.stripe_subscription_id == subscription.id
        )
        result = await self.db.execute(query)
        billing = result.scalar_one_or_none()

        await billing_service.handle_subscription_deleted(self.db, subscription)

        # Log the Stripe event ID
        if billing:
            await billing_service._log_billing_event(
                self.db,
                billing.organization_id,
                event.type,
                {"subscription_id": subscription.id},
                stripe_event_id=event.id,
            )

    async def _handle_payment_succeeded(self, event: stripe.Event) -> None:
        """Handle successful payment.

        Args:
            event: Stripe event with invoice object
        """
        invoice = event.data.object

        # Get billing record before handling
        billing = await billing_service.get_billing_by_stripe_customer(self.db, invoice.customer)

        await billing_service.handle_payment_succeeded(self.db, invoice)

        # Log the Stripe event ID
        if billing:
            await billing_service._log_billing_event(
                self.db,
                billing.organization_id,
                event.type,
                {
                    "invoice_id": invoice.id,
                    "amount": invoice.amount_paid,
                },
                stripe_event_id=event.id,
            )

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

        # Get billing record before handling
        billing = await billing_service.get_billing_by_stripe_customer(self.db, invoice.customer)

        await billing_service.handle_payment_failed(self.db, invoice)

        # Log the Stripe event ID
        if billing:
            await billing_service._log_billing_event(
                self.db,
                billing.organization_id,
                event.type,
                {
                    "invoice_id": invoice.id,
                    "amount": invoice.amount_due,
                    "attempt_count": invoice.attempt_count,
                },
                stripe_event_id=event.id,
            )

    async def _handle_trial_ending(self, event: stripe.Event) -> None:
        """Handle trial ending notification (sent 3 days before).

        Args:
            event: Stripe event with subscription object
        """
        subscription = event.data.object

        # Find organization
        query = select(OrganizationBilling).where(
            OrganizationBilling.stripe_subscription_id == subscription.id
        )
        result = await self.db.execute(query)
        billing = result.scalar_one_or_none()

        if billing:
            # TODO: Send email notification to organization
            logger.info(f"Trial ending soon for organization {billing.organization_id}")

            # Log the event
            await billing_service._log_billing_event(
                self.db,
                billing.organization_id,
                "trial_ending_notification",
                {
                    "subscription_id": subscription.id,
                    "trial_end": subscription.trial_end,
                },
                stripe_event_id=event.id,
            )

            await self.db.commit()

    async def _handle_invoice_upcoming(self, event: stripe.Event) -> None:
        """Handle upcoming invoice (sent ~3 days before payment).

        Useful for notifying customers about upcoming charges.

        Args:
            event: Stripe event with invoice object
        """
        invoice = event.data.object

        # Find organization
        billing = await billing_service.get_billing_by_stripe_customer(self.db, invoice.customer)

        if billing:
            logger.info(
                f"Upcoming invoice for organization {billing.organization_id}: "
                f"Amount: {invoice.amount_due / 100:.2f} {invoice.currency.upper()}"
            )

            # TODO: Send email notification if needed

            # Log the event
            await billing_service._log_billing_event(
                self.db,
                billing.organization_id,
                "invoice_upcoming",
                {
                    "invoice_id": invoice.id,
                    "amount": invoice.amount_due,
                    "currency": invoice.currency,
                    "period_end": invoice.period_end,
                },
                stripe_event_id=event.id,
            )

            await self.db.commit()
