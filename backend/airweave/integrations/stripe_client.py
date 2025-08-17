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

    def _sanitize_for_stripe(self, text: str) -> str:
        """Sanitize text for Stripe API to prevent encoding issues.

        Removes or replaces non-ASCII characters that can cause issues
        with URL encoding in certain environments.
        """
        if not text:
            return text

        # First, try to encode as ASCII, replacing non-ASCII with '?'
        try:
            # This will replace any non-ASCII character with '?'
            return text.encode("ascii", "replace").decode("ascii")
        except Exception:
            # Fallback: remove all non-ASCII characters
            return "".join(char for char in text if ord(char) < 128)

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
            # Sanitize all inputs to be ASCII-safe
            clean_email = self._sanitize_for_stripe(email)
            clean_name = self._sanitize_for_stripe(name)

            # Clean metadata values
            clean_metadata = {}
            if metadata:
                for key, value in metadata.items():
                    clean_key = self._sanitize_for_stripe(str(key))
                    clean_value = self._sanitize_for_stripe(str(value))
                    clean_metadata[clean_key] = clean_value

            return await stripe.Customer.create_async(
                email=clean_email, name=clean_name, metadata=clean_metadata
            )
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
            await stripe.Customer.delete_async(customer_id)
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
            # Sanitize URLs to be ASCII-safe
            clean_success_url = self._sanitize_for_stripe(success_url)
            clean_cancel_url = self._sanitize_for_stripe(cancel_url)

            # Clean metadata values
            clean_metadata = {}
            if metadata:
                for key, value in metadata.items():
                    clean_key = self._sanitize_for_stripe(str(key))
                    clean_value = self._sanitize_for_stripe(str(value))
                    clean_metadata[clean_key] = clean_value

            session_params = {
                "customer": customer_id,
                "line_items": [
                    {
                        "price": price_id,
                        "quantity": 1,
                    }
                ],
                "mode": "subscription",
                "success_url": clean_success_url,
                "cancel_url": clean_cancel_url,
                "metadata": clean_metadata,
                "allow_promotion_codes": True,
                "billing_address_collection": "required",
                "customer_update": {
                    "address": "auto",
                    "name": "auto",
                },
                "subscription_data": {
                    "metadata": clean_metadata,
                },
            }

            # Add trial_end to subscription_data if provided
            if trial_end:
                session_params["subscription_data"]["trial_end"] = trial_end
            elif trial_period_days:
                session_params["subscription_data"]["trial_period_days"] = trial_period_days

            return await stripe.checkout.Session.create_async(**session_params)
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
            # Sanitize return URL to be ASCII-safe
            clean_return_url = self._sanitize_for_stripe(return_url)

            return await stripe.billing_portal.Session.create_async(
                customer=customer_id,
                return_url=clean_return_url,
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
            return await stripe.Subscription.retrieve_async(subscription_id)
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
                return await stripe.Subscription.modify_async(
                    subscription_id, cancel_at_period_end=True
                )
            else:
                return await stripe.Subscription.delete_async(subscription_id)
        except StripeError as e:
            logger.error(f"Failed to cancel subscription {subscription_id}: {e}")
            raise ExternalServiceError(
                service_name="Stripe",
                message=f"Failed to cancel subscription: {str(e)}",
            ) from e

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
            # Get current subscription to find the item ID
            subscription = await self.get_subscription(subscription_id)

            # Use dictionary-style access to avoid collision with `dict.items()`
            items_data = subscription.get("items", {}).get("data")
            subscription_item_id = items_data[0]["id"] if items_data else None

            update_params = {
                "proration_behavior": proration_behavior,
            }

            # If a new price ID is provided, this is a plan change
            if price_id:
                if not subscription_item_id:
                    raise ExternalServiceError(
                        service_name="Stripe",
                        message=f"Subscription {subscription_id} has no items to update.",
                    )
                update_params["items"] = [
                    {
                        "id": subscription_item_id,
                        "price": price_id,
                    }
                ]
            # If no price ID, but cancel or trial status is changing, this is a status update
            elif cancel_at_period_end is not None or trial_end is not None:
                pass  # No item changes needed, just status update
            else:
                raise ExternalServiceError(
                    service_name="Stripe",
                    message=(
                        f"No valid update parameters provided for subscription {subscription_id}"
                    ),
                )

            # Add cancel_at_period_end if specified
            if cancel_at_period_end is not None:
                update_params["cancel_at_period_end"] = cancel_at_period_end

            # Add trial_end if specified
            if trial_end is not None:
                update_params["trial_end"] = trial_end

            return await stripe.Subscription.modify_async(subscription_id, **update_params)

        except StripeError as e:
            logger.error(f"Failed to update subscription {subscription_id}: {e}")
            raise ExternalServiceError(
                service_name="Stripe",
                message=f"Failed to update subscription: {str(e)}",
            ) from e

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
