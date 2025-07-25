"""Billing service for managing subscriptions and payments."""

from datetime import datetime, timezone
from typing import Any, Optional
from uuid import UUID

import stripe
from sqlalchemy.ext.asyncio import AsyncSession

from airweave import crud, schemas
from airweave.core.config import settings
from airweave.core.exceptions import InvalidStateError, NotFoundException
from airweave.core.logging import logger
from airweave.db.unit_of_work import UnitOfWork
from airweave.integrations.stripe_client import stripe_client
from airweave.models import Organization
from airweave.schemas.auth import AuthContext
from airweave.schemas.organization_billing import (
    BillingPlan,
    BillingStatus,
    OrganizationBillingCreate,
    OrganizationBillingUpdate,
    SubscriptionInfo,
)


class BillingService:
    """Service for managing organization billing and subscriptions."""

    # Plan limits configuration
    PLAN_LIMITS = {
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
        auth_context: AuthContext,
        uow: UnitOfWork,
    ) -> schemas.OrganizationBilling:
        """Create initial billing record within a transaction.

        Args:
            db: Database session
            organization: Organization to create billing for
            stripe_customer_id: Stripe customer ID
            billing_email: Billing contact email
            auth_context: Authentication context
            uow: Unit of work for transaction management

        Returns:
            Created OrganizationBilling record
        """
        # Check if billing already exists
        existing = await crud.organization_billing.get_by_organization(
            db, organization_id=organization.id
        )
        if existing:
            raise InvalidStateError("Billing record already exists for organization")

        # Get plan from organization metadata if available
        selected_plan = BillingPlan.DEVELOPER  # Default
        if hasattr(organization, "org_metadata") and organization.org_metadata:
            onboarding_data = organization.org_metadata.get("onboarding", {})
            plan_from_metadata = onboarding_data.get("subscriptionPlan", "developer")
            # Convert to BillingPlan enum
            if plan_from_metadata in ["developer", "startup", "enterprise"]:
                selected_plan = BillingPlan(plan_from_metadata)

        billing_create = OrganizationBillingCreate(
            stripe_customer_id=stripe_customer_id,
            billing_plan=selected_plan,
            billing_status=BillingStatus.TRIALING,  # New orgs start in trialing state
            billing_email=billing_email,
            # No grace period for new organizations - they need to complete setup
        )

        billing = await crud.organization_billing.create(
            db,
            obj_in=billing_create,
            auth_context=auth_context,
            uow=uow,
        )

        # Get local billing record
        await db.flush()

        return schemas.OrganizationBilling.model_validate(billing, from_attributes=True)

    async def get_billing_for_organization(
        self, db: AsyncSession, organization_id: UUID
    ) -> Optional[schemas.OrganizationBilling]:
        """Get billing record for an organization.

        Args:
            db: Database session
            organization_id: Organization ID

        Returns:
            OrganizationBilling or None if not found
        """
        billing = await crud.organization_billing.get_by_organization(
            db, organization_id=organization_id
        )
        return schemas.OrganizationBilling.model_validate(billing) if billing else None

    async def get_billing_by_stripe_customer(
        self, db: AsyncSession, stripe_customer_id: str
    ) -> Optional[schemas.OrganizationBilling]:
        """Get billing record by Stripe customer ID.

        Args:
            db: Database session
            stripe_customer_id: Stripe customer ID

        Returns:
            OrganizationBilling or None if not found
        """
        billing = await crud.organization_billing.get_by_stripe_customer(
            db, stripe_customer_id=stripe_customer_id
        )
        return schemas.OrganizationBilling.model_validate(billing) if billing else None

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
        billing_model = await crud.organization_billing.get_by_organization(
            db, organization_id=organization_id
        )
        if not billing_model:
            raise NotFoundException("No billing record found for organization")

        # Get price ID for plan
        price_id = stripe_client.get_price_id_for_plan(plan)
        if not price_id:
            raise InvalidStateError(f"Invalid plan: {plan}")

        # Check if already has a subscription (active or scheduled to cancel)
        if billing_model.stripe_subscription_id:
            # If there's an existing subscription, always update/overwrite it
            current_plan = billing_model.billing_plan
            if current_plan != plan:
                # This is a plan change, use update_subscription instead
                logger.info(
                    f"Redirecting to subscription update for plan change from {current_plan} "
                    f"to {plan} (existing subscription: {billing_model.stripe_subscription_id})"
                )
                return await self.update_subscription_plan(db, organization_id, plan)
            else:
                # Same plan - check if it's canceled and needs reactivation
                if billing_model.cancel_at_period_end:
                    logger.info(f"Reactivating canceled {plan} subscription")
                    return await self.update_subscription_plan(db, organization_id, plan)
                else:
                    raise InvalidStateError(
                        f"Organization already has an active {plan} subscription"
                    )

        # Determine if we should include a trial
        # Only give trial for developer plan and only if no previous subscription
        use_trial_period_days = None
        if plan == "developer" and not billing_model.stripe_subscription_id:
            use_trial_period_days = 14  # Stripe manages the 14-day trial

        # Create checkout session
        session = await stripe_client.create_checkout_session(
            customer_id=billing_model.stripe_customer_id,
            price_id=price_id,
            success_url=success_url,
            cancel_url=cancel_url,
            metadata={
                "organization_id": str(organization_id),
                "plan": plan,
            },
            trial_period_days=use_trial_period_days,
        )

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
        billing_model = await crud.organization_billing.get_by_organization(
            db, organization_id=organization_id
        )
        if not billing_model or not billing_model.stripe_subscription_id:
            raise NotFoundException("No active subscription found")

        # Don't allow plan changes if subscription is set to cancel
        if billing_model.cancel_at_period_end:
            raise InvalidStateError(
                "Cannot change plans while subscription is set to cancel. "
                "Please reactivate your subscription first."
            )

        # Get current and new price IDs
        new_price_id = stripe_client.get_price_id_for_plan(new_plan)
        if not new_price_id:
            raise InvalidStateError(f"Invalid plan: {new_plan}")

        current_plan = billing_model.billing_plan

        # Determine if this is an upgrade or downgrade
        plan_hierarchy = {
            BillingPlan.DEVELOPER: 1,
            BillingPlan.STARTUP: 2,
            BillingPlan.ENTERPRISE: 3,
        }

        is_upgrade = plan_hierarchy.get(new_plan, 0) > plan_hierarchy.get(current_plan, 0)

        # Special handling for upgrading from Developer trial to Startup
        # This should immediately end trial and start billing
        is_trial_to_startup = (
            new_plan == "startup"
            and current_plan == BillingPlan.DEVELOPER
            and billing_model.trial_ends_at
            and billing_model.trial_ends_at > datetime.now(timezone.utc)
        )

        try:
            # Check if this is a trialing subscription or a downgrade
            subscription = await stripe_client.get_subscription(
                billing_model.stripe_subscription_id
            )

            # For trialing subscriptions with no items OR downgrades, cancel and create new
            if (
                subscription.status == "trialing"
                and len(getattr(subscription.items, "data", [])) == 0
            ) or not is_upgrade:
                # Cancel the current subscription
                state = "trial upgrade" if subscription.status == "trialing" else "downgrade"
                logger.info(
                    f"Canceling subscription {billing_model.stripe_subscription_id} to "
                    f"create new one for {state}"
                )
                await stripe_client.cancel_subscription(
                    subscription_id=billing_model.stripe_subscription_id,
                    cancel_at_period_end=False,  # Cancel immediately
                )

                # Create a new checkout session for the new plan
                price_id = stripe_client.get_price_id_for_plan(new_plan)
                session = await stripe_client.create_checkout_session(
                    customer_id=billing_model.stripe_customer_id,
                    price_id=price_id,
                    success_url=f"{settings.app_url}/organization/settings?tab=billing&success=true",
                    cancel_url=f"{settings.app_url}/organization/settings?tab=billing",
                    metadata={
                        "organization_id": str(organization_id),
                        "plan": new_plan,
                    },
                    trial_period_days=None,  # No trial for the new subscription
                )

                return f"Please complete checkout at: {session.url}"

            # For non-trial subscriptions, proceed with normal update
            # If subscription is set to cancel, reactivate it first
            if billing_model.cancel_at_period_end:
                logger.info(
                    f"Reactivate canceled subscription before plan change for org {organization_id}"
                )
                await stripe_client.update_subscription(
                    subscription_id=billing_model.stripe_subscription_id,
                    cancel_at_period_end=False,
                )

            # Update the subscription in Stripe
            _ = await stripe_client.update_subscription(
                subscription_id=billing_model.stripe_subscription_id,
                price_id=new_price_id,
                proration_behavior="create_prorations" if is_upgrade else "none",
                cancel_at_period_end=False,  # Ensure cancellation is cleared
                trial_end=(
                    "now" if is_trial_to_startup else None
                ),  # End trial immediately for Startup
            )

            # Create system auth context for update
            system_auth = AuthContext(
                organization_id=organization_id,
                user=None,
                auth_method="system",
                auth_metadata={"source": "billing_service"},
            )

            # Update local billing record using CRUD
            update_data = OrganizationBillingUpdate(
                cancel_at_period_end=False,  # Always clear cancellation when updating plan
            )
            if is_upgrade:
                # Immediate change for upgrades
                update_data.billing_plan = BillingPlan(new_plan)

                # Clear trial end date if upgrading to Startup from trial
                if is_trial_to_startup:
                    update_data.trial_ends_at = None
            else:
                # For downgrades, schedule the plan change for end of period
                # but still clear the cancellation flag since we're changing plans
                update_data.cancel_at_period_end = False

            await crud.organization_billing.update(
                db,
                db_obj=billing_model,
                obj_in=update_data,
                auth_context=system_auth,
            )

            if is_upgrade:
                return f"Successfully upgraded to {new_plan} plan"
            else:
                return (
                    f"Subscription will be downgraded to {new_plan} at the end "
                    f"of the current billing period"
                )

        except Exception as e:
            logger.error(
                f"Failed to update subscription plan from {current_plan} to {new_plan}: {e}"
            )
            raise InvalidStateError(f"Failed to update subscription plan: {str(e)}") from e

    async def cancel_subscription(self, db: AsyncSession, auth_context: AuthContext) -> str:
        """Cancel a subscription.

        Args:
            db: Database session
            auth_context: Authentication context

        Returns:
            Success message

        Raises:
            NotFoundException: If no active subscription
        """
        billing_model = await crud.organization_billing.get_by_organization(
            db, organization_id=auth_context.organization_id
        )
        if not billing_model or not billing_model.stripe_subscription_id:
            raise NotFoundException("No active subscription found")

        try:
            # Cancel in Stripe - schedule cancellation at period end
            _ = await stripe_client.cancel_subscription(
                subscription_id=billing_model.stripe_subscription_id,
                cancel_at_period_end=True,
            )

            # Create system auth context for update
            system_auth = AuthContext(
                organization_id=auth_context.organization_id,
                user=None,
                auth_method="system",
                auth_metadata={"source": "billing_service"},
            )

            update_data = OrganizationBillingUpdate(
                cancel_at_period_end=True,
            )

            await crud.organization_billing.update(
                db,
                db_obj=billing_model,
                obj_in=update_data,
                auth_context=system_auth,
            )

            return "Subscription will be canceled at the end of the current billing period"

        except Exception as e:
            logger.error(f"Failed to cancel subscription: {e}")
            raise InvalidStateError(f"Failed to cancel subscription: {str(e)}") from e

    async def reactivate_subscription(self, db: AsyncSession, auth_context: AuthContext) -> str:
        """Reactivate a subscription that's set to cancel at period end.

        Args:
            db: Database session
            auth_context: Authentication context

        Returns:
            Success message

        Raises:
            NotFoundException: If no subscription found
            InvalidStateError: If subscription not set to cancel
        """
        billing_model = await crud.organization_billing.get_by_organization(
            db, organization_id=auth_context.organization_id
        )
        if not billing_model or not billing_model.stripe_subscription_id:
            raise NotFoundException("No active subscription found")

        if not billing_model.cancel_at_period_end:
            raise InvalidStateError("Subscription is not set to cancel")

        try:
            # Reactivate in Stripe
            _ = await stripe_client.update_subscription(
                subscription_id=billing_model.stripe_subscription_id, cancel_at_period_end=False
            )

            # Update local record using CRUD
            update_data = OrganizationBillingUpdate(cancel_at_period_end=False)
            await crud.organization_billing.update(
                db,
                db_obj=billing_model,
                obj_in=update_data,
                auth_context=auth_context,
            )

            return "Subscription reactivated successfully"

        except Exception as e:
            logger.error(f"Failed to reactivate subscription: {e}")
            raise InvalidStateError(f"Failed to reactivate subscription: {str(e)}") from e

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
        billing_model = await crud.organization_billing.get_by_organization(
            db, organization_id=organization_id
        )
        if not billing_model:
            raise NotFoundException("No billing record found for organization")

        session = await stripe_client.create_portal_session(
            customer_id=billing_model.stripe_customer_id, return_url=return_url
        )

        return session.url

    async def handle_subscription_created(
        self,
        db: AsyncSession,
        subscription: stripe.Subscription,
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

        # Get billing record using CRUD
        billing_model = await crud.organization_billing.get_by_organization(
            db, organization_id=UUID(org_id)
        )
        if not billing_model:
            logger.error(f"No billing record for organization {org_id}")
            return

        # Determine plan from metadata or price
        plan = subscription.metadata.get("plan", "developer")

        # Check if subscription has trial
        has_trial = subscription.trial_end is not None
        trial_ends_at = None
        if has_trial:
            trial_ends_at = datetime.fromtimestamp(subscription.trial_end, tz=timezone.utc)

        # Create system auth context for update
        system_auth = AuthContext(
            organization_id=UUID(org_id),
            user=None,
            auth_method="system",
            auth_metadata={"source": "stripe_webhook"},
        )

        # Update billing record using CRUD
        update_data = OrganizationBillingUpdate(
            stripe_subscription_id=subscription.id,
            billing_plan=BillingPlan(plan),
            billing_status=BillingStatus.ACTIVE,
            current_period_start=datetime.fromtimestamp(
                subscription.current_period_start, tz=timezone.utc
            ),
            current_period_end=datetime.fromtimestamp(
                subscription.current_period_end, tz=timezone.utc
            ),
            trial_ends_at=trial_ends_at,
            grace_period_ends_at=None,  # Clear grace period
            payment_method_added=True,
        )

        # Store payment method ID if available
        if hasattr(subscription, "default_payment_method"):
            update_data.payment_method_id = subscription.default_payment_method

        await crud.organization_billing.update(
            db,
            db_obj=billing_model,
            obj_in=update_data,
            auth_context=system_auth,
        )

        logger.info(f"Subscription created for org {org_id}: {plan} (trial: {has_trial})")

    async def handle_subscription_updated(
        self,
        db: AsyncSession,
        subscription: stripe.Subscription,
    ) -> None:
        """Handle subscription updated webhook event.

        Args:
            db: Database session
            subscription: Stripe subscription object
        """
        # Find billing by subscription ID using CRUD
        billing_model = await crud.organization_billing.get_by_stripe_subscription(
            db, stripe_subscription_id=subscription.id
        )

        if not billing_model:
            logger.error(f"No billing record for subscription {subscription.id}")
            return

        # Store organization_id before any DB operations to avoid lazy loading issues
        org_id = billing_model.organization_id

        # Create system auth context for update
        system_auth = AuthContext(
            organization_id=org_id,
            user=None,
            auth_method="system",
            auth_metadata={"source": "stripe_webhook"},
        )

        # Prepare update data
        update_data = OrganizationBillingUpdate(
            billing_status=BillingStatus(subscription.status),
            cancel_at_period_end=subscription.cancel_at_period_end,
            current_period_start=datetime.fromtimestamp(
                subscription.current_period_start, tz=timezone.utc
            ),
            current_period_end=datetime.fromtimestamp(
                subscription.current_period_end, tz=timezone.utc
            ),
        )

        # Handle trial end updates
        if hasattr(subscription, "trial_end"):
            if subscription.trial_end is None:
                # Trial has been removed/ended
                update_data.trial_ends_at = None
            else:
                # Trial end date updated
                update_data.trial_ends_at = datetime.fromtimestamp(
                    subscription.trial_end, tz=timezone.utc
                )

        # Check if plan changed (for downgrades that take effect at period end)
        if hasattr(subscription, "items") and subscription.items:
            # Get the plan from the subscription item
            new_plan = None
            items_data = subscription.items.data if hasattr(subscription.items, "data") else []
            if items_data and len(items_data) > 0:
                for price_id, plan_name in stripe_client.price_ids.items():
                    if items_data[0].price.id == price_id:
                        new_plan = plan_name
                        break

            if new_plan and new_plan != billing_model.billing_plan:
                update_data.billing_plan = BillingPlan(new_plan)

        await crud.organization_billing.update(
            db,
            db_obj=billing_model,
            obj_in=update_data,
            auth_context=system_auth,
        )

        logger.info(f"Subscription updated for org {org_id}")

    async def handle_subscription_deleted(
        self,
        db: AsyncSession,
        subscription: Any,  # stripe.Subscription
    ) -> None:
        """Handle subscription deleted/canceled webhook event.

        This event is sent both when:
        1. A subscription is scheduled to cancel (cancel_at_period_end=true)
        2. A subscription is actually deleted/ended

        We need to check the subscription status to determine which case it is.

        Args:
            db: Database session
            subscription: Stripe subscription object
        """
        # Find billing by subscription ID using CRUD
        billing_model = await crud.organization_billing.get_by_stripe_subscription(
            db, stripe_subscription_id=subscription.id
        )

        if not billing_model:
            logger.error(f"No billing record for subscription {subscription.id}")
            return

        # Store organization_id before any DB operations to avoid lazy loading issues
        org_id = billing_model.organization_id

        # Create system auth context for update
        system_auth = AuthContext(
            organization_id=org_id,
            user=None,
            auth_method="system",
            auth_metadata={"source": "stripe_webhook"},
        )

        # Check if this is a scheduled cancellation or actual deletion
        # When cancel_at_period_end is set to true, Stripe sends this event but
        # the subscription remains active until period end
        if hasattr(subscription, "cancel_at_period_end") and subscription.cancel_at_period_end:
            # Subscription is scheduled to cancel but still active
            # Just update the cancel_at_period_end flag, keep the subscription ID
            update_data = OrganizationBillingUpdate(
                cancel_at_period_end=True,
                # Keep current status - subscription is still active
            )
            logger.info(f"Subscription scheduled to cancel at period end for org {org_id}")
        else:
            # Subscription is actually deleted/ended
            update_data = OrganizationBillingUpdate(
                billing_status=BillingStatus.CANCELED,
                stripe_subscription_id=None,
                cancel_at_period_end=False,
            )
            logger.info(f"Subscription fully canceled for org {org_id}")

        await crud.organization_billing.update(
            db,
            db_obj=billing_model,
            obj_in=update_data,
            auth_context=system_auth,
        )

    async def handle_payment_succeeded(
        self,
        db: AsyncSession,
        invoice: stripe.Invoice,
    ) -> None:
        """Handle successful payment webhook event.

        Args:
            db: Database session
            invoice: Stripe invoice object
        """
        if not invoice.subscription:
            return  # One-time payment, ignore

        # Find billing by customer ID using CRUD
        billing_model = await crud.organization_billing.get_by_stripe_customer(
            db, stripe_customer_id=invoice.customer
        )
        if not billing_model:
            logger.error(f"No billing record for customer {invoice.customer}")
            return

        # Store organization_id before any DB operations to avoid lazy loading issues
        org_id = billing_model.organization_id

        # Create system auth context for update
        system_auth = AuthContext(
            organization_id=org_id,
            user=None,
            auth_method="system",
            auth_metadata={"source": "stripe_webhook"},
        )

        # Update payment info using CRUD
        update_data = OrganizationBillingUpdate(
            last_payment_status="succeeded",
            last_payment_at=datetime.now(timezone.utc),
        )

        # If was past_due, update to active
        if billing_model.billing_status == BillingStatus.PAST_DUE:
            update_data.billing_status = BillingStatus.ACTIVE

        await crud.organization_billing.update(
            db,
            db_obj=billing_model,
            obj_in=update_data,
            auth_context=system_auth,
        )

        logger.info(f"Payment succeeded for org {org_id}")

    async def handle_payment_failed(self, db: AsyncSession, invoice: stripe.Invoice) -> None:
        """Handle failed payment webhook event.

        Args:
            db: Database session
            invoice: Stripe invoice object
        """
        if not invoice.subscription:
            return  # One-time payment, ignore

        # Find billing by customer ID using CRUD
        billing_model = await crud.organization_billing.get_by_stripe_customer(
            db, stripe_customer_id=invoice.customer
        )
        if not billing_model:
            logger.error(f"No billing record for customer {invoice.customer}")
            return

        # Store organization_id before any DB operations to avoid lazy loading issues
        org_id = billing_model.organization_id

        # Create system auth context for update
        system_auth = AuthContext(
            organization_id=org_id,
            user=None,
            auth_method="system",
            auth_metadata={"source": "stripe_webhook"},
        )

        # Update payment info using CRUD
        update_data = OrganizationBillingUpdate(
            last_payment_status="failed",
            billing_status=BillingStatus.PAST_DUE,
        )

        await crud.organization_billing.update(
            db,
            db_obj=billing_model,
            obj_in=update_data,
            auth_context=system_auth,
        )

        logger.warning(f"Payment failed for org {org_id}")

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
        billing_model = await crud.organization_billing.get_by_organization(
            db, organization_id=organization_id
        )

        if not billing_model:
            # Return free/OSS tier info - using developer limits
            return SubscriptionInfo(
                plan=BillingPlan.DEVELOPER,
                status=BillingStatus.ACTIVE,
                limits=self.PLAN_LIMITS.get(BillingPlan.DEVELOPER, {}),
                is_oss=True,
                has_active_subscription=False,
                in_trial=False,
                in_grace_period=False,
                payment_method_added=False,
                requires_payment_method=False,
            )

        # Check if in trial (Stripe-managed trial)
        in_trial = (
            billing_model.trial_ends_at is not None
            and billing_model.trial_ends_at > datetime.now(timezone.utc)
            and billing_model.stripe_subscription_id is not None
        )

        # Check if in grace period (only for existing subscriptions with payment failures)
        in_grace_period = (
            billing_model.grace_period_ends_at is not None
            and billing_model.grace_period_ends_at > datetime.now(timezone.utc)
            and not billing_model.payment_method_added
            and billing_model.stripe_subscription_id
            is not None  # Grace period only applies to existing subscriptions
        )

        # Check if grace period expired
        grace_period_expired = (
            billing_model.grace_period_ends_at is not None
            and billing_model.grace_period_ends_at <= datetime.now(timezone.utc)
            and not billing_model.payment_method_added
            and billing_model.stripe_subscription_id
            is not None  # Grace period only applies to existing subscriptions
        )

        # For new organizations without subscriptions, they always need to complete setup
        needs_initial_setup = (
            not billing_model.stripe_subscription_id
            and billing_model.billing_status == BillingStatus.TRIALING
        )

        # Determine if payment method is required now
        requires_payment_method = needs_initial_setup or in_grace_period or grace_period_expired

        # Update status if grace period expired
        if grace_period_expired and billing_model.billing_status != BillingStatus.TRIAL_EXPIRED:
            # Create system auth context for update
            system_auth = AuthContext(
                organization_id=organization_id,
                user=None,
                auth_method="system",
                auth_metadata={"source": "billing_service"},
            )

            update_data = OrganizationBillingUpdate(
                billing_status=BillingStatus.TRIAL_EXPIRED,
            )

            await crud.organization_billing.update(
                db,
                db_obj=billing_model,
                obj_in=update_data,
                auth_context=system_auth,
            )

        return SubscriptionInfo(
            plan=billing_model.billing_plan,
            status=billing_model.billing_status,
            trial_ends_at=billing_model.trial_ends_at,
            grace_period_ends_at=billing_model.grace_period_ends_at,
            current_period_end=billing_model.current_period_end,
            cancel_at_period_end=billing_model.cancel_at_period_end,
            limits=self.PLAN_LIMITS.get(billing_model.billing_plan, {}),
            is_oss=False,
            has_active_subscription=bool(billing_model.stripe_subscription_id),
            in_trial=in_trial,
            in_grace_period=in_grace_period,
            payment_method_added=billing_model.payment_method_added,
            requires_payment_method=requires_payment_method,
        )

    async def handle_trial_expired(self, db: AsyncSession, organization_id: UUID) -> None:
        """Handle trial expiration for an organization.

        This should be called when a trial period ends without an active subscription.
        Updates the billing status to indicate the trial has expired.

        Args:
            db: Database session
            organization_id: Organization ID
        """
        billing_model = await crud.organization_billing.get_by_organization(
            db, organization_id=organization_id
        )
        if not billing_model:
            logger.error(f"No billing record for organization {organization_id}")
            return

        # Only process if actually in trial without subscription
        if (
            billing_model.trial_ends_at
            and billing_model.trial_ends_at <= datetime.now(timezone.utc)
            and not billing_model.stripe_subscription_id
        ):
            # Create system auth context for update
            system_auth = AuthContext(
                organization_id=organization_id,
                user=None,
                auth_method="system",
                auth_metadata={"source": "billing_service"},
            )

            update_data = OrganizationBillingUpdate(
                billing_status=BillingStatus.TRIAL_EXPIRED,
                trial_ends_at=None,  # Clear trial end date
            )

            await crud.organization_billing.update(
                db,
                db_obj=billing_model,
                obj_in=update_data,
                auth_context=system_auth,
            )

            logger.info(f"Trial expired for organization {organization_id}")


# Singleton instance
billing_service = BillingService()
