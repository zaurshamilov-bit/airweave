"""Webhook handler for processing Stripe events."""

from uuid import UUID

import stripe
from sqlalchemy.ext.asyncio import AsyncSession

from airweave import crud
from airweave.core.billing_service import billing_service
from airweave.core.logging import ContextualLogger, logger


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
            "checkout.session.completed": self._handle_checkout_completed,
        }

    async def _get_organization_logger(self, event: stripe.Event) -> ContextualLogger:
        """Create a contextual logger with organization context from the event.

        Args:
            event: Stripe event object

        Returns:
            ContextualLogger with organization context if found, otherwise base logger
        """
        organization_id = None

        try:
            # Extract customer ID or subscription ID from the event
            event_object = event.data.object

            # Try to get organization ID from metadata first (if available)
            if hasattr(event_object, "metadata") and event_object.metadata:
                org_id_str = event_object.metadata.get("organization_id")
                if org_id_str:
                    organization_id = UUID(org_id_str)

            # If not in metadata, look up by customer or subscription
            if not organization_id:
                billing_model = None

                # For subscription events
                if hasattr(event_object, "id") and event.type.startswith("customer.subscription"):
                    billing_model = await crud.organization_billing.get_by_stripe_subscription(
                        self.db, stripe_subscription_id=event_object.id
                    )

                # For invoice/payment events
                elif hasattr(event_object, "customer"):
                    billing_model = await crud.organization_billing.get_by_stripe_customer(
                        self.db, stripe_customer_id=event_object.customer
                    )

                # For customer events with subscription
                elif hasattr(event_object, "subscription") and event_object.subscription:
                    billing_model = await crud.organization_billing.get_by_stripe_subscription(
                        self.db, stripe_subscription_id=event_object.subscription
                    )

                if billing_model:
                    organization_id = billing_model.organization_id

            # Create contextual logger with organization context
            if organization_id:
                return logger.with_context(
                    organization_id=str(organization_id),
                    auth_method="stripe_webhook",
                    event_type=event.type,
                    stripe_event_id=event.id,
                )

        except Exception as e:
            logger.error(f"Failed to get organization context for webhook: {e}")

        # Fallback to base logger with just event context
        return logger.with_context(
            auth_method="stripe_webhook", event_type=event.type, stripe_event_id=event.id
        )

    async def handle_event(self, event: stripe.Event) -> None:
        """Process a Stripe webhook event.

        Args:
            event: Stripe event object
        """
        # Get contextual logger for this event
        contextual_logger = await self._get_organization_logger(event)

        # Get handler for event type
        handler = self.event_handlers.get(event.type)

        if handler:
            try:
                contextual_logger.info(f"Processing webhook event: {event.type}")
                await handler(event, contextual_logger)

            except Exception as e:
                contextual_logger.error(f"Error handling {event.type}: {e}", exc_info=True)
                raise
        else:
            contextual_logger.info(f"Unhandled webhook event type: {event.type}")

    async def _handle_subscription_created(
        self, event: stripe.Event, contextual_logger: ContextualLogger
    ) -> None:
        """Handle new subscription creation.

        Args:
            event: Stripe event with subscription object
            contextual_logger: Logger with organization context
        """
        subscription = event.data.object
        contextual_logger.info(f"Handling subscription creation for subscription {subscription.id}")
        await billing_service.handle_subscription_created(
            self.db, subscription, contextual_logger=contextual_logger
        )

    async def _handle_subscription_updated(
        self, event: stripe.Event, contextual_logger: ContextualLogger
    ) -> None:
        """Handle subscription updates (plan changes, status changes).

        Args:
            event: Stripe event with subscription object
            contextual_logger: Logger with organization context
        """
        subscription = event.data.object

        # Check what changed
        previous_attributes = event.data.get("previous_attributes", {})

        # Log significant changes
        if "status" in previous_attributes:
            contextual_logger.info(
                f"Subscription {subscription.id} status changed: "
                f"{previous_attributes['status']} -> {subscription.status}"
            )

        if "items" in previous_attributes:
            contextual_logger.info(f"Subscription {subscription.id} plan changed")

        await billing_service.handle_subscription_updated(
            self.db, subscription, previous_attributes, contextual_logger=contextual_logger
        )

    async def _handle_subscription_deleted(
        self, event: stripe.Event, contextual_logger: ContextualLogger
    ) -> None:
        """Handle subscription cancellation/deletion.

        Args:
            event: Stripe event with subscription object
            contextual_logger: Logger with organization context
        """
        subscription = event.data.object
        contextual_logger.info(f"Handling subscription deletion for subscription {subscription.id}")
        await billing_service.handle_subscription_deleted(
            self.db, subscription, contextual_logger=contextual_logger
        )

    async def _handle_payment_succeeded(
        self, event: stripe.Event, contextual_logger: ContextualLogger
    ) -> None:
        """Handle successful payment.

        Args:
            event: Stripe event with invoice object
            contextual_logger: Logger with organization context
        """
        invoice = event.data.object
        contextual_logger.info(f"Payment succeeded for invoice {invoice.id}")
        await billing_service.handle_payment_succeeded(
            self.db, invoice, contextual_logger=contextual_logger
        )

    async def _handle_payment_failed(
        self, event: stripe.Event, contextual_logger: ContextualLogger
    ) -> None:
        """Handle failed payment.

        Args:
            event: Stripe event with invoice object
            contextual_logger: Logger with organization context
        """
        invoice = event.data.object

        # Log details about the failure
        contextual_logger.warning(
            f"Payment failed for invoice {invoice.id}: "
            f"Amount: {invoice.amount_due / 100:.2f} {invoice.currency.upper()}, "
            f"Attempt: {invoice.attempt_count}"
        )

        await billing_service.handle_payment_failed(
            self.db, invoice, contextual_logger=contextual_logger
        )

    async def _handle_trial_ending(
        self, event: stripe.Event, contextual_logger: ContextualLogger
    ) -> None:
        """Handle trial ending notification (sent 3 days before).

        Args:
            event: Stripe event with subscription object
            contextual_logger: Logger with organization context
        """
        subscription = event.data.object

        # Find organization using CRUD
        billing_model = await crud.organization_billing.get_by_stripe_subscription(
            self.db, stripe_subscription_id=subscription.id
        )

        if billing_model:
            # TODO: Send email notification to organization
            contextual_logger.info(
                f"Trial ending soon for organization {billing_model.organization_id}"
            )

    async def _handle_invoice_upcoming(
        self, event: stripe.Event, contextual_logger: ContextualLogger
    ) -> None:
        """Handle upcoming invoice (sent ~3 days before payment).

        Useful for notifying customers about upcoming charges.

        Args:
            event: Stripe event with invoice object
            contextual_logger: Logger with organization context
        """
        invoice = event.data.object

        # Find organization using CRUD
        billing_model = await crud.organization_billing.get_by_stripe_customer(
            self.db, stripe_customer_id=invoice.customer
        )

        if billing_model:
            contextual_logger.info(
                f"Upcoming invoice for organization {billing_model.organization_id}: "
                f"Amount: {invoice.amount_due / 100:.2f} {invoice.currency.upper()}"
            )

            # TODO: Send email notification if needed

    async def _handle_checkout_completed(
        self, event: stripe.Event, contextual_logger: ContextualLogger
    ) -> None:
        """Handle checkout session completed event.

        This is particularly important for trial upgrades to ensure
        the old subscription is properly handled.

        Args:
            event: Stripe event with checkout session object
            contextual_logger: Logger with organization context
        """
        session = event.data.object

        # Log checkout completion
        contextual_logger.info(
            f"Checkout session completed: {session.id}, "
            f"Customer: {session.customer}, "
            f"Subscription: {session.subscription}"
        )

        # The subscription.created webhook will handle the actual upgrade
        # This event just helps us track the checkout completion
