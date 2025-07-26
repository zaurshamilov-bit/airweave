"""Stripe API client wrapper for billing operations."""

from typing import Dict, Optional

import stripe
from stripe.error import StripeError

from airweave.core.config import settings
from airweave.core.exceptions import ExternalServiceError
from airweave.core.logging import logger


class StripeClient:
    """Low-level Stripe API wrapper with error handling."""

    def __init__(self):
        """Initialize Stripe client with API key."""
        if not settings.STRIPE_ENABLED:
            raise ValueError("Stripe is not enabled in settings")

        stripe.api_key = settings.STRIPE_SECRET_KEY
        self.webhook_secret = settings.STRIPE_WEBHOOK_SECRET

        # Price IDs from configuration
        self.price_ids = {
            "developer": settings.STRIPE_DEVELOPER_PRICE_ID,
            "startup": settings.STRIPE_STARTUP_PRICE_ID,
        }

    async def create_customer(
        self, email: str, name: str, metadata: Optional[Dict[str, str]] = None
    ) -> stripe.Customer:
        """Create a Stripe customer.

        Args:
            email: Customer email
            name: Customer name (organization name)
            metadata: Additional metadata to attach

        Returns:
            Stripe Customer object

        Raises:
            ExternalServiceError: If Stripe API call fails
        """
        try:
            return stripe.Customer.create(email=email, name=name, metadata=metadata or {})
        except StripeError as e:
            logger.error(f"Failed to create Stripe customer: {e}")
            raise ExternalServiceError(
                service_name="Stripe",
                message=f"Failed to create billing account: {str(e)}",
            ) from e

    async def delete_customer(self, customer_id: str) -> None:
        """Delete a Stripe customer (for rollback scenarios).

        Args:
            customer_id: Stripe customer ID

        Raises:
            ExternalServiceError: If deletion fails
        """
        try:
            stripe.Customer.delete(customer_id)
        except StripeError as e:
            logger.error(f"Failed to delete Stripe customer {customer_id}: {e}")
            # Don't raise on cleanup failures

    async def create_checkout_session(
        self,
        customer_id: str,
        price_id: str,
        success_url: str,
        cancel_url: str,
        metadata: Optional[Dict[str, str]] = None,
        trial_end: Optional[int] = None,
        trial_period_days: Optional[int] = None,
    ) -> stripe.checkout.Session:
        """Create a checkout session for subscription.

        Args:
            customer_id: Stripe customer ID
            price_id: Stripe price ID for the plan
            success_url: URL to redirect on success
            cancel_url: URL to redirect on cancel
            metadata: Additional metadata
            trial_end: Unix timestamp for when trial should end (for existing trials)
            trial_period_days: Number of days for the trial period (for new trials)

        Returns:
            Stripe Checkout Session

        Raises:
            ExternalServiceError: If session creation fails
        """
        try:
            session_params = {
                "customer": customer_id,
                "payment_method_types": ["card"],
                "line_items": [
                    {
                        "price": price_id,
                        "quantity": 1,
                    }
                ],
                "mode": "subscription",
                "success_url": success_url,
                "cancel_url": cancel_url,
                "metadata": metadata or {},
                "allow_promotion_codes": True,
                "billing_address_collection": "required",
                "customer_update": {
                    "address": "auto",
                    "name": "auto",
                },
                "subscription_data": {
                    "metadata": metadata or {},
                },
            }

            # Add trial_end to subscription_data if provided
            if trial_end:
                session_params["subscription_data"]["trial_end"] = trial_end
            elif trial_period_days:
                session_params["subscription_data"]["trial_period_days"] = trial_period_days

            return stripe.checkout.Session.create(**session_params)
        except StripeError as e:
            logger.error(f"Failed to create checkout session: {e}")
            raise ExternalServiceError(
                service_name="Stripe",
                message=f"Failed to create checkout session: {str(e)}",
            ) from e

    async def create_portal_session(
        self, customer_id: str, return_url: str
    ) -> stripe.billing_portal.Session:
        """Create a customer portal session for subscription management.

        Args:
            customer_id: Stripe customer ID
            return_url: URL to return to after portal session

        Returns:
            Stripe Portal Session

        Raises:
            ExternalServiceError: If portal creation fails
        """
        try:
            return stripe.billing_portal.Session.create(
                customer=customer_id,
                return_url=return_url,
            )
        except StripeError as e:
            logger.error(f"Failed to create portal session: {e}")
            raise ExternalServiceError(
                service_name="Stripe",
                message=f"Failed to create billing portal: {str(e)}",
            ) from e

    async def get_subscription(self, subscription_id: str) -> stripe.Subscription:
        """Retrieve a subscription by ID.

        Args:
            subscription_id: Stripe subscription ID

        Returns:
            Stripe Subscription object

        Raises:
            ExternalServiceError: If retrieval fails
        """
        try:
            return stripe.Subscription.retrieve(subscription_id)
        except StripeError as e:
            logger.error(f"Failed to retrieve subscription {subscription_id}: {e}")
            raise ExternalServiceError(
                service_name="Stripe",
                message=f"Failed to retrieve subscription: {str(e)}",
            ) from e

    async def cancel_subscription(
        self, subscription_id: str, cancel_at_period_end: bool = True
    ) -> stripe.Subscription:
        """Cancel a subscription.

        Args:
            subscription_id: Stripe subscription ID
            cancel_at_period_end: If True, cancel at end of period

        Returns:
            Updated Stripe Subscription

        Raises:
            ExternalServiceError: If cancellation fails
        """
        try:
            if cancel_at_period_end:
                return stripe.Subscription.modify(subscription_id, cancel_at_period_end=True)
            else:
                return stripe.Subscription.delete(subscription_id)
        except StripeError as e:
            logger.error(f"Failed to cancel subscription {subscription_id}: {e}")
            raise ExternalServiceError(f"Failed to cancel subscription: {str(e)}") from e

    async def update_subscription(
        self,
        subscription_id: str,
        price_id: Optional[str] = None,
        proration_behavior: str = "create_prorations",
        cancel_at_period_end: Optional[bool] = None,
        trial_end: Optional[str] = None,
    ) -> stripe.Subscription:
        """Update a subscription with new plan or settings.

        Args:
            subscription_id: Stripe subscription ID
            price_id: New price ID for plan change
            proration_behavior: How to handle proration
            cancel_at_period_end: Update cancellation status
            trial_end: When to end the trial ("now" to end immediately)

        Returns:
            Updated Stripe Subscription

        Raises:
            ExternalServiceError: If update fails
        """
        try:
            update_params = {}

            # Update cancellation status if specified
            if cancel_at_period_end is not None:
                update_params["cancel_at_period_end"] = cancel_at_period_end

            # End trial if specified
            if trial_end is not None:
                update_params["trial_end"] = trial_end

            # Update plan if new price specified
            if price_id:
                # Get current subscription to find the item ID - expand items
                # Note: Trialing subscriptions may not have items until the trial ends
                subscription = stripe.Subscription.retrieve(subscription_id, expand=["items"])

                # Log what we got for debugging
                logger.info(
                    f"Subscription {subscription_id} status: {subscription.status}, "
                    f"cancel_at_period_end: {subscription.cancel_at_period_end}, "
                    f"items count: {len(getattr(subscription.items, 'data', []))}"
                )

                # Check if subscription has items
                if (
                    hasattr(subscription, "items")
                    and hasattr(subscription.items, "data")
                    and len(subscription.items.data) > 0
                ):
                    # Update the first item with new price
                    update_params["items"] = [
                        {
                            "id": subscription.items.data[0].id,
                            "price": price_id,
                        }
                    ]
                    update_params["proration_behavior"] = proration_behavior

                else:
                    # No items - add the price as a new item
                    logger.info(
                        f"No items found on subscription {subscription_id}, adding new item"
                    )
                    update_params["items"] = [
                        {
                            "price": price_id,
                        }
                    ]
                    update_params["proration_behavior"] = proration_behavior

            return stripe.Subscription.modify(subscription_id, **update_params)

        except StripeError as e:
            logger.error(f"Failed to update subscription {subscription_id}: {e}")
            raise ExternalServiceError(f"Failed to update subscription: {str(e)}") from e

    def construct_webhook_event(self, payload: bytes, sig_header: str) -> stripe.Event:
        """Verify and construct webhook event from Stripe.

        Args:
            payload: Raw request body
            sig_header: Stripe signature header

        Returns:
            Verified Stripe Event

        Raises:
            ValueError: If payload is invalid
            stripe.error.SignatureVerificationError: If signature is invalid
        """
        return stripe.Webhook.construct_event(payload, sig_header, self.webhook_secret)

    def get_price_id_for_plan(self, plan_name: str) -> Optional[str]:
        """Get Stripe price ID for a plan name.

        Args:
            plan_name: Plan name (developer, startup)

        Returns:
            Stripe price ID or None if not found
        """
        return self.price_ids.get(plan_name.lower())


# Singleton instance
stripe_client = StripeClient() if settings.STRIPE_ENABLED else None
