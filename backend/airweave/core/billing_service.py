"""Billing service for managing subscriptions and payments."""

from datetime import datetime, timedelta, timezone
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
from airweave.schemas.billing_period import (
    BillingPeriodCreate,
    BillingPeriodStatus,
    BillingTransition,
)
from airweave.schemas.organization_billing import (
    BillingPlan,
    BillingStatus,
    OrganizationBillingCreate,
    OrganizationBillingUpdate,
    SubscriptionInfo,
)
from airweave.schemas.usage import UsageCreate


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
        return (
            schemas.OrganizationBilling.model_validate(billing, from_attributes=True)
            if billing
            else None
        )

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
        return (
            schemas.OrganizationBilling.model_validate(billing, from_attributes=True)
            if billing
            else None
        )

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

    def _validate_plan_change(self, billing_model: Any, new_plan: str) -> str:
        """Validate that a plan change is allowed.

        Args:
            billing_model: Organization billing model
            new_plan: Target plan name

        Returns:
            Price ID for the new plan

        Raises:
            NotFoundException: If no active subscription
            InvalidStateError: If plan change not allowed
        """
        if not billing_model or not billing_model.stripe_subscription_id:
            raise NotFoundException("No active subscription found")

        if billing_model.cancel_at_period_end:
            raise InvalidStateError(
                "Cannot change plans while subscription is set to cancel. "
                "Please reactivate your subscription first."
            )

        new_price_id = stripe_client.get_price_id_for_plan(new_plan)
        if not new_price_id:
            raise InvalidStateError(f"Invalid plan: {new_plan}")

        return new_price_id

    def _determine_plan_change_type(
        self, current_plan: BillingPlan, new_plan: str, billing_model: Any
    ) -> tuple[bool, bool]:
        """Determine if plan change is upgrade and if it's trial to startup.

        Args:
            current_plan: Current billing plan
            new_plan: New plan name
            billing_model: Organization billing model

        Returns:
            Tuple of (is_upgrade, is_trial_to_startup)
        """
        plan_hierarchy = {
            BillingPlan.DEVELOPER: 1,
            BillingPlan.STARTUP: 2,
            BillingPlan.ENTERPRISE: 3,
        }

        is_upgrade = plan_hierarchy.get(new_plan, 0) > plan_hierarchy.get(current_plan, 0)

        is_trial_to_startup = (
            new_plan == "startup"
            and current_plan == BillingPlan.DEVELOPER
            and billing_model.trial_ends_at
            and billing_model.trial_ends_at > datetime.now(timezone.utc)
        )

        return is_upgrade, is_trial_to_startup

    async def _handle_trial_subscription_upgrade(
        self, billing_model: Any, organization_id: UUID, new_plan: str
    ) -> str:
        """Handle upgrading from a trial subscription with no items.

        Args:
            billing_model: Organization billing model
            organization_id: Organization ID
            new_plan: New plan name

        Returns:
            Checkout session URL
        """
        logger.info(
            f"Canceling trial subscription {billing_model.stripe_subscription_id} to "
            f"create new one for trial upgrade"
        )
        await stripe_client.cancel_subscription(
            subscription_id=billing_model.stripe_subscription_id,
            cancel_at_period_end=False,  # Cancel immediately
        )

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

    async def _handle_plan_downgrade(
        self,
        db: AsyncSession,
        billing_model: schemas.OrganizationBilling,
        organization_id: UUID,
        new_plan: str,
        new_price_id: str,
    ) -> str:
        """Handle plan downgrade (scheduled for end of period).

        Args:
            db: Database session
            billing_model: Organization billing model
            organization_id: Organization ID
            new_plan: New plan name
            new_price_id: Stripe price ID for new plan

        Returns:
            Success message
        """
        # Update Stripe subscription to change at period end
        await stripe_client.update_subscription(
            subscription_id=billing_model.stripe_subscription_id,
            price_id=new_price_id,
            proration_behavior="none",  # No proration for downgrades
        )

        # Create system auth context
        system_auth = AuthContext(
            organization_id=organization_id,
            user=None,
            auth_method="system",
            auth_metadata={"source": "billing_service"},
        )

        # Store pending change locally
        update_data = OrganizationBillingUpdate(
            pending_plan_change=BillingPlan(new_plan),
            pending_plan_change_at=billing_model.current_period_end,
        )

        # Get the billing model from the database to avoid issues with detached instances
        db_billing_model = await crud.organization_billing.get(
            db, id=billing_model.id, auth_context=system_auth
        )

        await crud.organization_billing.update(
            db,
            db_obj=db_billing_model,
            obj_in=update_data,
            auth_context=system_auth,
        )

        return (
            f"Subscription will be downgraded to {new_plan} at the end "
            f"of the current billing period"
        )

    async def _handle_plan_upgrade(
        self,
        db: AsyncSession,
        billing_model: Any,
        organization_id: UUID,
        new_plan: str,
        new_price_id: str,
        is_trial_to_startup: bool,
    ) -> str:
        """Handle plan upgrade (immediate change with proration).

        Args:
            db: Database session
            billing_model: Organization billing model
            organization_id: Organization ID
            new_plan: New plan name
            new_price_id: Stripe price ID for new plan
            is_trial_to_startup: Whether this is trial to startup upgrade

        Returns:
            Success message
        """
        # Reactivate if canceled
        if billing_model.cancel_at_period_end:
            logger.info(
                f"Reactivate canceled subscription before plan change for org {organization_id}"
            )
            await stripe_client.update_subscription(
                subscription_id=billing_model.stripe_subscription_id,
                cancel_at_period_end=False,
            )

        # Update the subscription in Stripe
        await stripe_client.update_subscription(
            subscription_id=billing_model.stripe_subscription_id,
            price_id=new_price_id,
            proration_behavior="create_prorations",
            cancel_at_period_end=False,
            trial_end="now" if is_trial_to_startup else None,
        )

        # Create system auth context
        system_auth = AuthContext(
            organization_id=organization_id,
            user=None,
            auth_method="system",
            auth_metadata={"source": "billing_service"},
        )

        # Update local billing record
        update_data = OrganizationBillingUpdate(
            cancel_at_period_end=False,
            billing_plan=BillingPlan(new_plan),
        )

        if is_trial_to_startup:
            update_data.trial_ends_at = None

        await crud.organization_billing.update(
            db,
            db_obj=billing_model,
            obj_in=update_data,
            auth_context=system_auth,
        )

        return f"Successfully upgraded to {new_plan} plan"

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

        # Validate plan change
        new_price_id = self._validate_plan_change(billing_model, new_plan)
        current_plan = billing_model.billing_plan

        # Determine plan change type
        is_upgrade, is_trial_to_startup = self._determine_plan_change_type(
            current_plan, new_plan, billing_model
        )

        try:
            # Get subscription details
            subscription = await stripe_client.get_subscription(
                billing_model.stripe_subscription_id
            )

            # Handle trial subscriptions with no items
            if (
                subscription.status == "trialing"
                and len(getattr(subscription.items, "data", [])) == 0
            ):
                return await self._handle_trial_subscription_upgrade(
                    billing_model, organization_id, new_plan
                )

            # For downgrades, schedule the change for end of period
            if not is_upgrade:
                return await self._handle_plan_downgrade(
                    db, billing_model, organization_id, new_plan, new_price_id
                )

            # For upgrades, proceed with immediate update
            return await self._handle_plan_upgrade(
                db,
                billing_model,
                organization_id,
                new_plan,
                new_price_id,
                is_trial_to_startup,
            )
        except Exception as e:
            logger.error(f"Failed to update subscription plan: {e}")
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
            await stripe_client.update_subscription(
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

    async def cancel_pending_plan_change(self, db: AsyncSession, organization_id: UUID) -> str:
        """Cancel a scheduled plan change (downgrade).

        Args:
            db: Database session
            organization_id: Organization ID

        Returns:
            Success message
        """
        billing_model = await crud.organization_billing.get_by_organization(
            db, organization_id=organization_id
        )

        if not billing_model or not billing_model.pending_plan_change:
            raise InvalidStateError("No pending plan change found")

        # Get current subscription from Stripe
        await stripe_client.get_subscription(billing_model.stripe_subscription_id)

        # Revert the plan change in Stripe by setting the price back
        # to the original plan
        current_price_id = stripe_client.get_price_id_for_plan(billing_model.billing_plan)

        await stripe_client.update_subscription(
            subscription_id=billing_model.stripe_subscription_id,
            price_id=current_price_id,
            proration_behavior="none",
        )

        # Clear the pending change in our database
        system_auth = AuthContext(
            organization_id=organization_id,
            user=None,
            auth_method="system",
            auth_metadata={"source": "billing_service"},
        )

        update_data = OrganizationBillingUpdate(
            pending_plan_change=None,
            pending_plan_change_at=None,
        )

        # Get the billing model from the database to avoid issues with detached instances
        db_billing_model = await crud.organization_billing.get(
            db, id=billing_model.id, auth_context=system_auth
        )

        await crud.organization_billing.update(
            db,
            db_obj=db_billing_model,
            obj_in=update_data,
            auth_context=system_auth,
        )

        return "Scheduled plan change has been canceled"

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

        # Create first billing period
        await self.create_billing_period(
            db=db,
            organization_id=UUID(org_id),
            period_start=datetime.fromtimestamp(subscription.current_period_start, tz=timezone.utc),
            period_end=datetime.fromtimestamp(subscription.current_period_end, tz=timezone.utc),
            plan=BillingPlan(plan),
            transition=BillingTransition.INITIAL_SIGNUP,
            stripe_subscription_id=subscription.id,
            status=BillingPeriodStatus.TRIAL if has_trial else BillingPeriodStatus.ACTIVE,
        )

        logger.info(f"Subscription created for org {org_id}: {plan} (trial: {has_trial})")

    def _extract_plan_from_subscription(
        self, subscription: stripe.Subscription, current_plan: BillingPlan
    ) -> tuple[BillingPlan, bool]:
        """Extract plan from subscription items.

        Args:
            subscription: Stripe subscription object
            current_plan: Current billing plan

        Returns:
            Tuple of (new_plan, plan_changed)
        """
        if not hasattr(subscription, "items") or not subscription.items:
            return current_plan, False

        items_data = subscription.items.data if hasattr(subscription.items, "data") else []
        if not items_data:
            return current_plan, False

        for price_id, plan_name in stripe_client.price_ids.items():
            if items_data[0].price.id == price_id:
                return plan_name, plan_name != current_plan

        return current_plan, False

    async def _handle_subscription_renewal(
        self,
        db: AsyncSession,
        org_id: UUID,
        subscription: stripe.Subscription,
        billing_model: Any,
        new_plan: BillingPlan,
        plan_changed: bool,
    ) -> None:
        """Handle subscription renewal event.

        Args:
            db: Database session
            org_id: Organization ID
            subscription: Stripe subscription
            billing_model: Organization billing model
            new_plan: New plan
            plan_changed: Whether plan changed
        """
        current_period = await self.get_current_billing_period(db, org_id)

        # Determine effective plan and transition type
        effective_plan = billing_model.pending_plan_change or new_plan

        if billing_model.pending_plan_change:
            transition = BillingTransition.DOWNGRADE
        elif plan_changed:
            transition = BillingTransition.UPGRADE
        else:
            transition = BillingTransition.RENEWAL

        # Create new period
        await self.create_billing_period(
            db=db,
            organization_id=org_id,
            period_start=datetime.fromtimestamp(subscription.current_period_start, tz=timezone.utc),
            period_end=datetime.fromtimestamp(subscription.current_period_end, tz=timezone.utc),
            plan=BillingPlan(effective_plan),
            transition=transition,
            stripe_subscription_id=subscription.id,
            previous_period_id=current_period.id if current_period else None,
        )

    async def _handle_immediate_plan_change(
        self,
        db: AsyncSession,
        org_id: UUID,
        subscription: stripe.Subscription,
        new_plan: BillingPlan,
    ) -> None:
        """Handle immediate plan change (upgrade).

        Args:
            db: Database session
            org_id: Organization ID
            subscription: Stripe subscription
            new_plan: New plan
        """
        current_period = await self.get_current_billing_period(db, org_id)

        await self.create_billing_period(
            db=db,
            organization_id=org_id,
            period_start=datetime.utcnow(),
            period_end=datetime.fromtimestamp(subscription.current_period_end, tz=timezone.utc),
            plan=BillingPlan(new_plan),
            transition=BillingTransition.UPGRADE,
            stripe_subscription_id=subscription.id,
            previous_period_id=current_period.id if current_period else None,
        )

    async def _handle_trial_conversion(
        self,
        db: AsyncSession,
        org_id: UUID,
        subscription: stripe.Subscription,
        new_plan: BillingPlan,
        system_auth: AuthContext,
    ) -> None:
        """Handle trial to paid conversion.

        Args:
            db: Database session
            org_id: Organization ID
            subscription: Stripe subscription
            new_plan: New plan
            system_auth: System auth context
        """
        current_period = await self.get_current_billing_period(db, org_id)
        if not current_period or current_period.status != BillingPeriodStatus.TRIAL:
            return

        # End trial period
        await crud.billing_period.update(
            db,
            db_obj=await crud.billing_period.get(
                db, id=current_period.id, auth_context=system_auth
            ),
            obj_in={"status": BillingPeriodStatus.COMPLETED},
            auth_context=system_auth,
        )

        # Create paid period
        await self.create_billing_period(
            db=db,
            organization_id=org_id,
            period_start=datetime.utcnow(),
            period_end=datetime.fromtimestamp(subscription.current_period_end, tz=timezone.utc),
            plan=BillingPlan(new_plan),
            transition=BillingTransition.TRIAL_CONVERSION,
            stripe_subscription_id=subscription.id,
            previous_period_id=current_period.id,
        )

    async def handle_subscription_updated(
        self,
        db: AsyncSession,
        subscription: stripe.Subscription,
        previous_attributes: Optional[dict] = None,
    ) -> None:
        """Handle subscription updated webhook event.

        Args:
            db: Database session
            subscription: Stripe subscription object
            previous_attributes: Previous values that changed
        """
        # Find billing by subscription ID
        billing_model = await crud.organization_billing.get_by_stripe_subscription(
            db, stripe_subscription_id=subscription.id
        )

        if not billing_model:
            logger.error(f"No billing record for subscription {subscription.id}")
            return

        # Store organization_id before any DB operations to avoid lazy loading issues
        org_id = billing_model.organization_id

        # Create system auth context
        system_auth = AuthContext(
            organization_id=org_id,
            user=None,
            auth_method="system",
            auth_metadata={"source": "stripe_webhook"},
        )

        # Extract plan information
        new_plan, plan_changed = self._extract_plan_from_subscription(
            subscription, billing_model.billing_plan
        )

        # Check if this is a renewal
        is_renewal = previous_attributes and "current_period_end" in previous_attributes

        # Check if this is a canceled plan change (plan matches current but we have pending change)
        is_canceled_plan_change = (
            billing_model.pending_plan_change
            and new_plan == billing_model.billing_plan
            and not is_renewal
        )

        # Handle renewal
        if is_renewal:
            await self._handle_subscription_renewal(
                db, org_id, subscription, billing_model, new_plan, plan_changed
            )

        # Handle immediate plan change
        elif plan_changed and previous_attributes and "items" in previous_attributes:
            await self._handle_immediate_plan_change(db, org_id, subscription, new_plan)

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

        # Update plan if changed
        if plan_changed:
            update_data.billing_plan = BillingPlan(new_plan)

        # Clear pending plan change if renewal with pending change OR if plan change was canceled
        if (is_renewal and billing_model.pending_plan_change) or is_canceled_plan_change:
            update_data.pending_plan_change = None
            update_data.pending_plan_change_at = None
            if is_canceled_plan_change:
                logger.info(f"Cleared canceled plan change for org {org_id}")

        # Handle trial end updates
        if hasattr(subscription, "trial_end"):
            if subscription.trial_end is None:
                update_data.trial_ends_at = None
                # Handle trial conversion if needed
                if previous_attributes and "trial_end" in previous_attributes:
                    await self._handle_trial_conversion(
                        db, org_id, subscription, new_plan, system_auth
                    )
            else:
                update_data.trial_ends_at = datetime.fromtimestamp(
                    subscription.trial_end, tz=timezone.utc
                )

        # Update billing record
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
            # Complete the final billing period
            current_period = await self.get_current_billing_period(db, org_id)
            if current_period:
                await crud.billing_period.update(
                    db,
                    db_obj=await crud.billing_period.get(
                        db, id=current_period.id, auth_context=system_auth
                    ),
                    obj_in={"status": BillingPeriodStatus.COMPLETED},
                    auth_context=system_auth,
                )
                logger.info(f"Completed final billing period {current_period.id} for org {org_id}")

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

        # Check if this is a renewal payment failure
        if hasattr(invoice, "billing_reason") and invoice.billing_reason == "subscription_cycle":
            # This is a renewal payment failure
            current_period = await self.get_current_billing_period(db, org_id)
            if current_period:
                # Mark current period as ended but unpaid
                await crud.billing_period.update(
                    db,
                    db_obj=await crud.billing_period.get(
                        db, id=current_period.id, auth_context=system_auth
                    ),
                    obj_in={"status": BillingPeriodStatus.ENDED_UNPAID},
                    auth_context=system_auth,
                )

                # Create grace period
                grace_period_days = 7  # TODO: Make this configurable
                grace_period_end = datetime.utcnow() + timedelta(days=grace_period_days)

                await self.create_billing_period(
                    db=db,
                    organization_id=org_id,
                    period_start=current_period.period_end,
                    period_end=grace_period_end,
                    plan=current_period.plan,
                    transition=BillingTransition.RENEWAL,  # Failed renewal
                    stripe_subscription_id=billing_model.stripe_subscription_id,
                    previous_period_id=current_period.id,
                    status=BillingPeriodStatus.GRACE,
                )

                # Update grace period end date
                update_data = OrganizationBillingUpdate(
                    last_payment_status="failed",
                    billing_status=BillingStatus.PAST_DUE,
                    grace_period_ends_at=grace_period_end,
                )
            else:
                # No current period, just update status
                update_data = OrganizationBillingUpdate(
                    last_payment_status="failed",
                    billing_status=BillingStatus.PAST_DUE,
                )
        else:
            # Not a renewal failure, just update status
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
            pending_plan_change=billing_model.pending_plan_change,
            pending_plan_change_at=billing_model.pending_plan_change_at,
        )

    async def create_billing_period(
        self,
        db: AsyncSession,
        organization_id: UUID,
        period_start: datetime,
        period_end: datetime,
        plan: BillingPlan,
        transition: BillingTransition,
        stripe_subscription_id: Optional[str] = None,
        previous_period_id: Optional[UUID] = None,
        status: Optional[BillingPeriodStatus] = None,
    ) -> schemas.BillingPeriod:
        """Create a new billing period and associated usage record.

        Args:
            db: Database session
            organization_id: Organization ID
            period_start: Period start datetime
            period_end: Period end datetime
            plan: Billing plan for this period
            transition: How this period was created
            stripe_subscription_id: Optional Stripe subscription ID
            previous_period_id: Optional previous period ID
            status: Optional status (defaults to ACTIVE)

        Returns:
            Created billing period
        """
        # Get any currently active periods
        active_periods = await crud.billing_period.get_by_organization(
            db, organization_id=organization_id, limit=10
        )

        # Find active periods that need to be completed
        for period in active_periods:
            if period.status in [
                BillingPeriodStatus.ACTIVE,
                BillingPeriodStatus.TRIAL,
                BillingPeriodStatus.GRACE,
            ]:
                # Update the period to be completed with exact end time
                await crud.billing_period.update(
                    db,
                    db_obj=period,
                    obj_in={
                        "status": BillingPeriodStatus.COMPLETED,
                        "period_end": period_start,  # Ensure continuity!
                    },
                    auth_context=AuthContext(
                        organization_id=organization_id,
                        user=None,
                        auth_method="system",
                        auth_metadata={"source": "billing_service"},
                    ),
                )

                # If no previous_period_id was provided, use the most recent active period
                if not previous_period_id and period.status == BillingPeriodStatus.ACTIVE:
                    previous_period_id = period.id

                logger.info(
                    f"Completed period {period.id} with adjusted end time {period_start} "
                    f"to ensure continuity with new period"
                )

        # Determine status if not provided
        if status is None:
            if transition == BillingTransition.INITIAL_SIGNUP and stripe_subscription_id:
                # Check if subscription has trial
                try:
                    subscription = await stripe_client.get_subscription(stripe_subscription_id)
                    status = (
                        BillingPeriodStatus.TRIAL
                        if subscription.trial_end
                        else BillingPeriodStatus.ACTIVE
                    )
                except Exception:
                    status = BillingPeriodStatus.ACTIVE
            else:
                status = BillingPeriodStatus.ACTIVE

        # Create system auth context
        system_auth = AuthContext(
            organization_id=organization_id,
            user=None,
            auth_method="system",
            auth_metadata={"source": "billing_service"},
        )

        # Create billing period
        period_create = BillingPeriodCreate(
            organization_id=organization_id,
            period_start=period_start,
            period_end=period_end,
            plan=plan,
            status=status,
            created_from=transition,
            stripe_subscription_id=stripe_subscription_id,
            previous_period_id=previous_period_id,
        )
        async with UnitOfWork(db) as uow:
            period = await crud.billing_period.create(
                db, obj_in=period_create, auth_context=system_auth, uow=uow
            )

            await db.flush()

            billing_period = schemas.BillingPeriod.model_validate(period, from_attributes=True)

            # Create associated usage record
            usage_create = UsageCreate(
                organization_id=organization_id,
                billing_period_id=period.id,
                # All counters default to 0
            )

            await crud.usage.create(db, obj_in=usage_create, auth_context=system_auth, uow=uow)

        logger.info(
            f"Created billing period for org {organization_id}: "
            f"{period_start} to {period_end}, plan={plan}, transition={transition}"
        )

        return billing_period

    async def get_current_billing_period(
        self, db: AsyncSession, organization_id: UUID
    ) -> Optional[schemas.BillingPeriod]:
        """Get the current active billing period for an organization.

        Args:
            db: Database session
            organization_id: Organization ID

        Returns:
            Current billing period or None
        """
        period = await crud.billing_period.get_current_period(db, organization_id=organization_id)
        return (
            schemas.BillingPeriod.model_validate(period, from_attributes=True) if period else None
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
