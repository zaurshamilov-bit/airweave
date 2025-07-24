"""Billing service for managing subscriptions and payments."""

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from airweave.core.exceptions import InvalidStateError, NotFoundException
from airweave.core.logging import logger
from airweave.db.unit_of_work import UnitOfWork
from airweave.integrations.stripe_client import stripe_client
from airweave.models import BillingEvent, Organization, OrganizationBilling
from airweave.schemas.organization_billing import BillingPlan, BillingStatus, SubscriptionInfo


class BillingService:
    """Service for managing organization billing and subscriptions."""

    # Plan limits configuration
    PLAN_LIMITS = {
        BillingPlan.TRIAL: {
            "source_connections": 3,
            "entities_per_month": 10000,
            "sync_frequency_minutes": 1440,  # Daily
            "team_members": 2,
        },
        BillingPlan.DEVELOPER: {
            "source_connections": 10,
            "entities_per_month": 100000,
            "sync_frequency_minutes": 60,  # Hourly
            "team_members": 5,
        },
        BillingPlan.STARTUP: {
            "source_connections": 50,
            "entities_per_month": 1000000,
            "sync_frequency_minutes": 15,
            "team_members": 20,
        },
        BillingPlan.ENTERPRISE: {
            "source_connections": -1,  # Unlimited
            "entities_per_month": -1,
            "sync_frequency_minutes": 5,
            "team_members": -1,
        },
    }

    async def create_billing_record_with_transaction(
        self,
        db: AsyncSession,
        organization: Organization,
        stripe_customer_id: str,
        billing_email: str,
        uow: UnitOfWork,
    ) -> OrganizationBilling:
        """Create initial billing record within a transaction.

        Args:
            db: Database session
            organization: Organization to create billing for
            stripe_customer_id: Stripe customer ID
            billing_email: Billing contact email
            uow: Unit of work for transaction management

        Returns:
            Created OrganizationBilling record
        """
        # Check if billing already exists
        existing = await self.get_billing_for_organization(db, organization.id)
        if existing:
            raise InvalidStateError("Billing record already exists for organization")

        billing = OrganizationBilling(
            organization_id=organization.id,
            stripe_customer_id=stripe_customer_id,
            billing_plan=BillingPlan.TRIAL,
            billing_status=BillingStatus.ACTIVE,
            trial_ends_at=datetime.now(timezone.utc) + timedelta(days=14),
            billing_email=billing_email,
        )

        db.add(billing)
        # Don't commit here - let the UoW handle it
        await db.flush()

        # Log the event
        await self._log_billing_event(
            db,
            organization.id,
            "billing_record_created",
            {"plan": BillingPlan.TRIAL, "trial_days": 14},
        )

        return billing

    async def get_billing_for_organization(
        self, db: AsyncSession, organization_id: UUID
    ) -> Optional[OrganizationBilling]:
        """Get billing record for an organization.

        Args:
            db: Database session
            organization_id: Organization ID

        Returns:
            OrganizationBilling or None if not found
        """
        query = select(OrganizationBilling).where(
            OrganizationBilling.organization_id == organization_id
        )
        result = await db.execute(query)
        return result.scalar_one_or_none()

    async def get_billing_by_stripe_customer(
        self, db: AsyncSession, stripe_customer_id: str
    ) -> Optional[OrganizationBilling]:
        """Get billing record by Stripe customer ID.

        Args:
            db: Database session
            stripe_customer_id: Stripe customer ID

        Returns:
            OrganizationBilling or None if not found
        """
        query = select(OrganizationBilling).where(
            OrganizationBilling.stripe_customer_id == stripe_customer_id
        )
        result = await db.execute(query)
        return result.scalar_one_or_none()

    async def start_subscription_checkout(
        self, db: AsyncSession, organization_id: UUID, plan: str, success_url: str, cancel_url: str
    ) -> str:
        """Start subscription checkout flow.

        Args:
            db: Database session
            organization_id: Organization ID
            plan: Plan name (developer, startup)
            success_url: URL to redirect on success
            cancel_url: URL to redirect on cancel

        Returns:
            Checkout session URL

        Raises:
            NotFoundException: If billing record not found
            InvalidStateError: If invalid plan or state
        """
        # Get billing record
        billing = await self.get_billing_for_organization(db, organization_id)
        if not billing:
            raise NotFoundException("No billing record found for organization")

        # Get price ID for plan
        price_id = stripe_client.get_price_id_for_plan(plan)
        if not price_id:
            raise InvalidStateError(f"Invalid plan: {plan}")

        # Check if already has active subscription
        if billing.stripe_subscription_id and billing.billing_status == BillingStatus.ACTIVE:
            # Check if this is an upgrade/downgrade
            current_plan = billing.billing_plan
            if current_plan != BillingPlan.TRIAL and current_plan != plan:
                # This is a plan change, use update_subscription instead
                logger.info(
                    f"Redirecting to subscription update for plan change from {current_plan} "
                    f"to {plan}"
                )
                return await self.update_subscription_plan(db, organization_id, plan)
            elif current_plan == plan:
                raise InvalidStateError(f"Organization already has an active {plan} subscription")

        # Create checkout session
        session = await stripe_client.create_checkout_session(
            customer_id=billing.stripe_customer_id,
            price_id=price_id,
            success_url=success_url,
            cancel_url=cancel_url,
            metadata={
                "organization_id": str(organization_id),
                "plan": plan,
            },
        )

        # Log the event
        await self._log_billing_event(
            db,
            organization_id,
            "checkout_session_created",
            {"plan": plan, "session_id": session.id},
        )

        await db.commit()

        return session.url

    async def update_subscription_plan(
        self, db: AsyncSession, organization_id: UUID, new_plan: str
    ) -> str:
        """Update subscription to a different plan (upgrade/downgrade).

        For upgrades: Changes take effect immediately with proration
        For downgrades: Changes take effect at the end of the current billing period

        Args:
            db: Database session
            organization_id: Organization ID
            new_plan: Target plan name

        Returns:
            Success message or checkout URL if payment update needed

        Raises:
            NotFoundException: If billing record not found
            InvalidStateError: If subscription update not allowed
        """
        billing = await self.get_billing_for_organization(db, organization_id)
        if not billing or not billing.stripe_subscription_id:
            raise NotFoundException("No active subscription found")

        # Get current and new price IDs
        new_price_id = stripe_client.get_price_id_for_plan(new_plan)
        if not new_price_id:
            raise InvalidStateError(f"Invalid plan: {new_plan}")

        current_plan = billing.billing_plan

        # Determine if this is an upgrade or downgrade
        plan_hierarchy = {
            BillingPlan.TRIAL: 0,
            BillingPlan.DEVELOPER: 1,
            BillingPlan.STARTUP: 2,
            BillingPlan.ENTERPRISE: 3,
        }

        is_upgrade = plan_hierarchy.get(new_plan, 0) > plan_hierarchy.get(current_plan, 0)

        try:
            # Update the subscription in Stripe
            _ = await stripe_client.update_subscription(
                subscription_id=billing.stripe_subscription_id,
                price_id=new_price_id,
                proration_behavior="create_prorations" if is_upgrade else "none",
                cancel_at_period_end=False,  # Clear any pending cancellation
            )

            # Update local billing record
            if is_upgrade:
                # Immediate change for upgrades
                billing.billing_plan = BillingPlan(new_plan)
                billing.cancel_at_period_end = False
            else:
                # Schedule change for downgrades
                billing.cancel_at_period_end = True
                # Note: The actual plan change will happen via webhook when period ends

            # Log the event
            await self._log_billing_event(
                db,
                organization_id,
                "subscription_plan_changed",
                {
                    "old_plan": current_plan,
                    "new_plan": new_plan,
                    "change_type": "upgrade" if is_upgrade else "downgrade",
                    "effective": "immediate" if is_upgrade else "next_period",
                },
            )

            await db.commit()

            if is_upgrade:
                return f"Successfully upgraded to {new_plan} plan"
            else:
                return (
                    f"Subscription will be downgraded to {new_plan} at the end "
                    f"of the current billing period"
                )

        except Exception as e:
            logger.error(f"Failed to update subscription: {e}")
            raise InvalidStateError(f"Failed to update subscription: {str(e)}") from e

    async def cancel_subscription(
        self, db: AsyncSession, organization_id: UUID, immediate: bool = False
    ) -> str:
        """Cancel a subscription.

        Args:
            db: Database session
            organization_id: Organization ID
            immediate: If True, cancel immediately. If False, cancel at period end

        Returns:
            Success message

        Raises:
            NotFoundException: If no active subscription
        """
        billing = await self.get_billing_for_organization(db, organization_id)
        if not billing or not billing.stripe_subscription_id:
            raise NotFoundException("No active subscription found")

        try:
            # Cancel in Stripe
            _ = await stripe_client.cancel_subscription(
                subscription_id=billing.stripe_subscription_id, cancel_at_period_end=not immediate
            )

            # Update local record
            if immediate:
                billing.billing_status = BillingStatus.CANCELED
                billing.billing_plan = BillingPlan.TRIAL
                billing.stripe_subscription_id = None
            else:
                billing.cancel_at_period_end = True

            # Log the event
            await self._log_billing_event(
                db,
                organization_id,
                "subscription_cancel_requested",
                {
                    "immediate": immediate,
                    "effective_date": "immediate" if immediate else str(billing.current_period_end),
                },
            )

            await db.commit()

            if immediate:
                return "Subscription canceled immediately"
            else:
                return (
                    f"Subscription will be canceled at the end of the current billing period "
                    f"({billing.current_period_end.strftime('%B %d, %Y')})"
                )

        except Exception as e:
            logger.error(f"Failed to cancel subscription: {e}")
            raise InvalidStateError(f"Failed to cancel subscription: {str(e)}") from e

    async def reactivate_subscription(self, db: AsyncSession, organization_id: UUID) -> str:
        """Reactivate a subscription that's set to cancel at period end.

        Args:
            db: Database session
            organization_id: Organization ID

        Returns:
            Success message

        Raises:
            NotFoundException: If no subscription found
            InvalidStateError: If subscription not set to cancel
        """
        billing = await self.get_billing_for_organization(db, organization_id)
        if not billing or not billing.stripe_subscription_id:
            raise NotFoundException("No active subscription found")

        if not billing.cancel_at_period_end:
            raise InvalidStateError("Subscription is not set to cancel")

        try:
            # Reactivate in Stripe
            _ = await stripe_client.update_subscription(
                subscription_id=billing.stripe_subscription_id, cancel_at_period_end=False
            )

            # Update local record
            billing.cancel_at_period_end = False

            # Log the event
            await self._log_billing_event(
                db,
                organization_id,
                "subscription_reactivated",
                {"subscription_id": billing.stripe_subscription_id},
            )

            await db.commit()

            return "Subscription reactivated successfully"

        except Exception as e:
            logger.error(f"Failed to reactivate subscription: {e}")
            raise InvalidStateError(f"Failed to reactivate subscription: {str(e)}") from e

    async def delete_billing_record(self, db: AsyncSession, organization_id: UUID) -> None:
        """Delete billing record when organization is deleted.

        This should only be called as part of organization deletion.
        Cancels any active subscription immediately.

        Args:
            db: Database session
            organization_id: Organization ID
        """
        billing = await self.get_billing_for_organization(db, organization_id)
        if not billing:
            return

        # Cancel subscription if active
        if billing.stripe_subscription_id:
            try:
                await stripe_client.cancel_subscription(
                    subscription_id=billing.stripe_subscription_id,
                    cancel_at_period_end=False,  # Immediate cancellation
                )
            except Exception as e:
                logger.error(f"Failed to cancel subscription during org deletion: {e}")
                # Continue with deletion even if Stripe cancellation fails

        # Delete the billing record
        await db.delete(billing)

        # Don't log the event here since the organization is being deleted
        # and would cause a foreign key constraint violation
        logger.info(f"Deleted billing record for organization {organization_id}")

    async def create_customer_portal_session(
        self, db: AsyncSession, organization_id: UUID, return_url: str
    ) -> str:
        """Create customer portal session for billing management.

        Args:
            db: Database session
            organization_id: Organization ID
            return_url: URL to return to

        Returns:
            Portal session URL

        Raises:
            NotFoundException: If billing record not found
        """
        billing = await self.get_billing_for_organization(db, organization_id)
        if not billing:
            raise NotFoundException("No billing record found for organization")

        session = await stripe_client.create_portal_session(
            customer_id=billing.stripe_customer_id, return_url=return_url
        )

        return session.url

    async def handle_subscription_created(
        self,
        db: AsyncSession,
        subscription: Any,  # stripe.Subscription
    ) -> None:
        """Handle subscription created webhook event.

        Args:
            db: Database session
            subscription: Stripe subscription object
        """
        # Get organization ID from metadata
        org_id = subscription.metadata.get("organization_id")
        if not org_id:
            logger.error(f"No organization_id in subscription {subscription.id} metadata")
            return

        # Get billing record
        billing = await self.get_billing_for_organization(db, UUID(org_id))
        if not billing:
            logger.error(f"No billing record for organization {org_id}")
            return

        # Determine plan from metadata or price
        plan = subscription.metadata.get("plan", "developer")

        # Update billing record
        billing.stripe_subscription_id = subscription.id
        billing.billing_plan = BillingPlan(plan)
        billing.billing_status = BillingStatus.ACTIVE
        billing.current_period_start = datetime.fromtimestamp(
            subscription.current_period_start, tz=timezone.utc
        )
        billing.current_period_end = datetime.fromtimestamp(
            subscription.current_period_end, tz=timezone.utc
        )
        billing.trial_ends_at = None  # Clear trial

        # Log the event
        await self._log_billing_event(
            db,
            UUID(org_id),
            "subscription_created",
            {
                "subscription_id": subscription.id,
                "plan": plan,
                "status": subscription.status,
            },
        )

        await db.commit()
        logger.info(f"Subscription created for org {org_id}: {plan}")

    async def handle_subscription_updated(
        self,
        db: AsyncSession,
        subscription: Any,  # stripe.Subscription
    ) -> None:
        """Handle subscription updated webhook event.

        Args:
            db: Database session
            subscription: Stripe subscription object
        """
        # Find billing by subscription ID
        query = select(OrganizationBilling).where(
            OrganizationBilling.stripe_subscription_id == subscription.id
        )
        result = await db.execute(query)
        billing = result.scalar_one_or_none()

        if not billing:
            logger.error(f"No billing record for subscription {subscription.id}")
            return

        # Update status
        old_status = billing.billing_status
        billing.billing_status = BillingStatus(subscription.status)
        billing.cancel_at_period_end = subscription.cancel_at_period_end

        # Update period dates
        billing.current_period_start = datetime.fromtimestamp(
            subscription.current_period_start, tz=timezone.utc
        )
        billing.current_period_end = datetime.fromtimestamp(
            subscription.current_period_end, tz=timezone.utc
        )

        # Check if plan changed (for downgrades that take effect at period end)
        if subscription.items and subscription.items.data:
            # Get the plan from the subscription item
            new_plan = None
            for price_id, plan_name in stripe_client.price_ids.items():
                if subscription.items.data[0].price.id == price_id:
                    new_plan = plan_name
                    break

            if new_plan and new_plan != billing.billing_plan:
                old_plan = billing.billing_plan
                billing.billing_plan = BillingPlan(new_plan)

                await self._log_billing_event(
                    db,
                    billing.organization_id,
                    "subscription_plan_changed_effective",
                    {
                        "old_plan": old_plan,
                        "new_plan": new_plan,
                        "subscription_id": subscription.id,
                    },
                )

        # Log significant changes
        if old_status != billing.billing_status:
            await self._log_billing_event(
                db,
                billing.organization_id,
                "subscription_status_changed",
                {
                    "old_status": old_status,
                    "new_status": billing.billing_status,
                    "subscription_id": subscription.id,
                },
            )

        await db.commit()
        logger.info(f"Subscription updated for org {billing.organization_id}")

    async def handle_subscription_deleted(
        self,
        db: AsyncSession,
        subscription: Any,  # stripe.Subscription
    ) -> None:
        """Handle subscription deleted/canceled webhook event.

        Args:
            db: Database session
            subscription: Stripe subscription object
        """
        # Find billing by subscription ID
        query = select(OrganizationBilling).where(
            OrganizationBilling.stripe_subscription_id == subscription.id
        )
        result = await db.execute(query)
        billing = result.scalar_one_or_none()

        if not billing:
            logger.error(f"No billing record for subscription {subscription.id}")
            return

        # Update to canceled status
        billing.billing_status = BillingStatus.CANCELED
        billing.billing_plan = BillingPlan.TRIAL  # Revert to trial/free tier
        billing.stripe_subscription_id = None
        billing.cancel_at_period_end = False

        # Log the event
        await self._log_billing_event(
            db,
            billing.organization_id,
            "subscription_canceled",
            {"subscription_id": subscription.id},
        )

        await db.commit()
        logger.info(f"Subscription canceled for org {billing.organization_id}")

    async def handle_payment_succeeded(
        self,
        db: AsyncSession,
        invoice: Any,  # stripe.Invoice
    ) -> None:
        """Handle successful payment webhook event.

        Args:
            db: Database session
            invoice: Stripe invoice object
        """
        if not invoice.subscription:
            return  # One-time payment, ignore

        # Find billing by customer ID
        billing = await self.get_billing_by_stripe_customer(db, invoice.customer)
        if not billing:
            logger.error(f"No billing record for customer {invoice.customer}")
            return

        # Update payment info
        billing.last_payment_status = "succeeded"
        billing.last_payment_at = datetime.now(timezone.utc)

        # If was past_due, update to active
        if billing.billing_status == BillingStatus.PAST_DUE:
            billing.billing_status = BillingStatus.ACTIVE

        # Log the event
        await self._log_billing_event(
            db,
            billing.organization_id,
            "payment_succeeded",
            {
                "invoice_id": invoice.id,
                "amount": invoice.amount_paid,
                "currency": invoice.currency,
            },
        )

        await db.commit()
        logger.info(f"Payment succeeded for org {billing.organization_id}")

    async def handle_payment_failed(self, db: AsyncSession, invoice: Any) -> None:  # stripe.Invoice
        """Handle failed payment webhook event.

        Args:
            db: Database session
            invoice: Stripe invoice object
        """
        if not invoice.subscription:
            return  # One-time payment, ignore

        # Find billing by customer ID
        billing = await self.get_billing_by_stripe_customer(db, invoice.customer)
        if not billing:
            logger.error(f"No billing record for customer {invoice.customer}")
            return

        # Update payment info
        billing.last_payment_status = "failed"
        billing.billing_status = BillingStatus.PAST_DUE

        # Log the event
        await self._log_billing_event(
            db,
            billing.organization_id,
            "payment_failed",
            {
                "invoice_id": invoice.id,
                "amount": invoice.amount_due,
                "currency": invoice.currency,
                "attempt_count": invoice.attempt_count,
            },
        )

        await db.commit()
        logger.warning(f"Payment failed for org {billing.organization_id}")

    async def get_subscription_info(
        self, db: AsyncSession, organization_id: UUID
    ) -> SubscriptionInfo:
        """Get comprehensive subscription information for an organization.

        Args:
            db: Database session
            organization_id: Organization ID

        Returns:
            SubscriptionInfo with plan, status, limits
        """
        billing = await self.get_billing_for_organization(db, organization_id)

        if not billing:
            # Return free/OSS tier info
            return SubscriptionInfo(
                plan=BillingPlan.TRIAL,
                status=BillingStatus.ACTIVE,
                limits=self.PLAN_LIMITS.get(BillingPlan.TRIAL, {}),
                is_oss=True,
            )

        return SubscriptionInfo(
            plan=billing.billing_plan,
            status=billing.billing_status,
            trial_ends_at=billing.trial_ends_at,
            current_period_end=billing.current_period_end,
            cancel_at_period_end=billing.cancel_at_period_end,
            limits=self.PLAN_LIMITS.get(billing.billing_plan, {}),
            is_oss=False,
            has_active_subscription=bool(billing.stripe_subscription_id),
        )

    async def _log_billing_event(
        self,
        db: AsyncSession,
        organization_id: UUID,
        event_type: str,
        event_data: Dict[str, Any],
        stripe_event_id: Optional[str] = None,
    ) -> None:
        """Log a billing event for audit trail.

        Args:
            db: Database session
            organization_id: Organization ID
            event_type: Type of event
            event_data: Event data to store
            stripe_event_id: Optional Stripe event ID for deduplication
        """
        event = BillingEvent(
            organization_id=organization_id,
            event_type=event_type,
            event_data=event_data,
            stripe_event_id=stripe_event_id,
        )
        db.add(event)
        # Don't commit here - let caller handle transaction


# Singleton instance
billing_service = BillingService()
