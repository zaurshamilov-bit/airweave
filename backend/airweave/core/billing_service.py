"""Billing service for managing subscriptions and payments."""

from datetime import datetime, timedelta
from typing import Any, Optional, Union
from uuid import UUID, uuid4

import stripe
from sqlalchemy.ext.asyncio import AsyncSession

from airweave import crud, schemas
from airweave.api.context import ApiContext
from airweave.core.config import settings
from airweave.core.exceptions import InvalidStateError, NotFoundException
from airweave.core.logging import ContextualLogger, logger
from airweave.db.unit_of_work import UnitOfWork
from airweave.integrations.stripe_client import stripe_client
from airweave.models import Organization
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

    async def _create_system_context(
        self,
        db: AsyncSession,
        organization: Union[schemas.Organization, UUID],
        source: str = "billing_service",
    ) -> ApiContext:
        """Create a system ApiContext for internal operations.

        Args:
            db: Database session
            organization: Organization object or UUID
            source: Source identifier for tracking

        Returns:
            Properly configured ApiContext for system operations
        """
        # If we got an ID, fetch the organization
        if isinstance(organization, UUID):
            org_model = await crud.organization.get(
                db, id=organization, skip_access_validation=True
            )
            if not org_model:
                raise NotFoundException(f"Organization {organization} not found")
            organization_obj = schemas.Organization.model_validate(org_model, from_attributes=True)
        else:
            organization_obj = organization

        return ApiContext(
            request_id=str(uuid4()),
            organization=organization_obj,
            user=None,
            auth_method="system",
            auth_metadata={"source": source},
            logger=logger.with_context(
                organization_id=str(organization_obj.id),
                organization_name=organization_obj.name,
                auth_method="system",
                source=source,
            ),
        )

    # Plan limits configuration (matching GuardRailService)
    PLAN_LIMITS = {
        BillingPlan.DEVELOPER: {
            "max_syncs": None,
            "max_entities": 50000,
            "max_queries": 500,
            "max_collections": None,
            "max_source_connections": 10,
            "max_team_members": 1,  # community support, minimal team
        },
        BillingPlan.PRO: {
            "max_syncs": None,
            "max_entities": 100000,
            "max_queries": 2000,
            "max_collections": None,
            "max_source_connections": 50,
            "max_team_members": 2,
        },
        BillingPlan.TEAM: {
            "max_syncs": None,
            "max_entities": 1000000,
            "max_queries": 10000,
            "max_collections": None,
            "max_source_connections": 1000,
            "max_team_members": 10,
        },
        BillingPlan.ENTERPRISE: {
            "max_syncs": None,  # Unlimited
            "max_entities": None,
            "max_queries": None,
            "max_collections": None,
            "max_source_connections": None,
            "max_team_members": None,
        },
    }

    async def create_billing_record_with_transaction(
        self,
        db: AsyncSession,
        organization: Organization,
        stripe_customer_id: str,
        billing_email: str,
        ctx: ApiContext,
        uow: UnitOfWork,
        contextual_logger: Optional[ContextualLogger] = None,
    ) -> schemas.OrganizationBilling:
        """Create initial billing record within a transaction.

        Args:
            db: Database session
            organization: Organization to create billing for
            stripe_customer_id: Stripe customer ID
            billing_email: Billing contact email
            ctx: API context
            uow: Unit of work for transaction management
            contextual_logger: Optional contextual logger with auth context

        Returns:
            Created OrganizationBilling record
        """
        log = contextual_logger or logger

        # Check if billing already exists
        existing = await crud.organization_billing.get_by_organization(
            db, organization_id=organization.id
        )
        if existing:
            raise InvalidStateError("Billing record already exists for organization")

        # Get plan from organization metadata if available
        selected_plan = BillingPlan.PRO  # Default
        if hasattr(organization, "org_metadata") and organization.org_metadata:
            onboarding_data = organization.org_metadata.get("onboarding", {})
            plan_from_metadata = onboarding_data.get("subscriptionPlan", "pro")
            # Convert to BillingPlan enum
            if plan_from_metadata in ["developer", "pro", "team", "enterprise"]:
                selected_plan = BillingPlan(plan_from_metadata)

        billing_create = OrganizationBillingCreate(
            stripe_customer_id=stripe_customer_id,
            billing_plan=selected_plan,
            billing_status=BillingStatus.ACTIVE,  # Trials disabled
            billing_email=billing_email,
            # No grace period for new organizations - they need to complete setup
        )

        billing = await crud.organization_billing.create(
            db,
            obj_in=billing_create,
            ctx=ctx,
            uow=uow,
        )

        # Get local billing record
        await db.flush()

        log.info(
            f"Created billing record for organization {organization.id} with plan {selected_plan}"
        )

        # If free developer plan, create a $0 Stripe subscription to get webhook-driven periods
        if selected_plan == BillingPlan.DEVELOPER:
            developer_price_id = stripe_client.get_price_id_for_plan("developer")
            if developer_price_id:
                sub = await stripe_client.create_subscription(
                    customer_id=stripe_customer_id,
                    price_id=developer_price_id,
                    metadata={
                        "organization_id": str(organization.id),
                        "plan": "developer",
                    },
                )
                # We don't create the period here; webhook will set period boundaries
                await crud.organization_billing.update(
                    db,
                    db_obj=billing,
                    obj_in=OrganizationBillingUpdate(
                        stripe_subscription_id=sub.id,
                        billing_plan=BillingPlan.DEVELOPER,
                        billing_status=BillingStatus.ACTIVE,
                        current_period_start=datetime.utcfromtimestamp(sub.current_period_start),
                        current_period_end=datetime.utcfromtimestamp(sub.current_period_end),
                        payment_method_added=False,
                    ),
                    ctx=ctx,
                )
                log.info(
                    "Created $0 developer subscription %s for org %s",
                    sub.id,
                    organization.id,
                )
            else:
                log.warning("Developer price ID not configured; developer plan will be local-only")

        return schemas.OrganizationBilling.model_validate(billing, from_attributes=True)

    async def _detect_payment_method(
        self, subscription: stripe.Subscription
    ) -> tuple[bool, Optional[str]]:
        """Determine whether a default payment method exists for the customer.

        Checks subscription.default_payment_method first; if absent, falls back to
        customer.invoice_settings.default_payment_method or default_source.
        """
        try:
            # Subscription-level default payment method (string id or object)
            pm = getattr(subscription, "default_payment_method", None)
            if isinstance(pm, dict):
                pm_id = pm.get("id")
            else:
                pm_id = pm
            if pm_id:
                return True, pm_id

            # Fallback to customer invoice settings
            cust_id = getattr(subscription, "customer", None)
            if not cust_id:
                return False, None
            customer = await stripe.Customer.retrieve_async(cust_id)
            inv_pm = None
            try:
                inv_pm = (
                    customer.get("invoice_settings", {}).get("default_payment_method")
                    if isinstance(customer, dict)
                    else getattr(
                        getattr(customer, "invoice_settings", None), "default_payment_method", None
                    )
                )
            except Exception:
                inv_pm = None
            if isinstance(inv_pm, dict):
                inv_pm_id = inv_pm.get("id")
            else:
                inv_pm_id = inv_pm
            if inv_pm_id:
                return True, inv_pm_id

            # Legacy default source support
            default_source = getattr(customer, "default_source", None)
            if default_source:
                return True, default_source

            return False, None
        except Exception:
            # On API errors, be conservative and report no PM
            return False, None

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
        self,
        db: AsyncSession,
        plan: str,
        success_url: str,
        cancel_url: str,
        ctx: ApiContext,
    ) -> str:
        """Start subscription checkout flow.

        Args:
            db: Database session
            plan: Plan name (pro, team)
            success_url: URL to redirect on success
            cancel_url: URL to redirect on cancel
            ctx: Authentication context

        Returns:
            Checkout session URL

        Raises:
            NotFoundException: If billing record not found
            InvalidStateError: If invalid plan or state
        """
        log = ctx.logger

        # Get billing record
        billing_model = await crud.organization_billing.get_by_organization(
            db, organization_id=ctx.organization.id
        )
        if not billing_model:
            raise NotFoundException("No billing record found for organization")

        # Get price ID for plan
        price_id = stripe_client.get_price_id_for_plan(plan)
        if not price_id:
            raise InvalidStateError(f"Invalid plan: {plan}")

        # Determine if Checkout is required: only when target is paid AND no payment method
        is_target_paid = plan in {"pro", "team"}
        needs_checkout = is_target_paid and not bool(billing_model.payment_method_added)

        # Check if already has a subscription (active or scheduled to cancel)
        if billing_model.stripe_subscription_id:
            current_plan = billing_model.billing_plan

            if not needs_checkout and current_plan != plan:
                # Update existing subscription without Checkout
                log.info(
                    f"Updating existing subscription for plan change from {current_plan} "
                    f"to {plan} (existing subscription: {billing_model.stripe_subscription_id})"
                )
                return await self.update_subscription_plan(db, ctx, plan)

            if not needs_checkout and current_plan == plan:
                # Same plan; if it was set to cancel, reactivate
                if billing_model.cancel_at_period_end:
                    log.info(f"Reactivating canceled {plan} subscription")
                    return await self.update_subscription_plan(db, ctx, plan)
                raise InvalidStateError(f"Organization already has an active {plan} subscription")

        # Trials disabled
        use_trial_period_days = None

        # Create checkout session
        checkout_metadata = {
            "organization_id": str(ctx.organization.id),
            "plan": plan,
        }

        # If lacking payment method, include previous subscription id for context
        if billing_model.stripe_subscription_id and needs_checkout:
            checkout_metadata["previous_subscription_id"] = billing_model.stripe_subscription_id

        session = await stripe_client.create_checkout_session(
            customer_id=billing_model.stripe_customer_id,
            price_id=price_id,
            success_url=success_url,
            cancel_url=cancel_url,
            metadata=checkout_metadata,
            trial_period_days=use_trial_period_days,
        )

        return session.url

    def _validate_plan_change(self, billing_model: Any, new_plan: str) -> Optional[str]:
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
            BillingPlan.PRO: 1,
            BillingPlan.TEAM: 2,
            BillingPlan.ENTERPRISE: 3,
        }

        is_upgrade = plan_hierarchy.get(new_plan, 0) > plan_hierarchy.get(current_plan, 0)

        # Trials disabled
        is_trial_to_startup = False

        return is_upgrade, is_trial_to_startup

    async def _handle_trial_subscription_upgrade(
        self,
        billing_model: Any,
        ctx: ApiContext,
        new_plan: str,
    ) -> str:
        """Handle upgrading from a trial subscription with no items.

        This method creates a new checkout session WITHOUT canceling the existing
        trial subscription. The old subscription will only be canceled after the
        new subscription is successfully created (handled in the webhook).

        Args:
            billing_model: Organization billing model
            ctx: Authentication context
            new_plan: New plan name

        Returns:
            Checkout session URL
        """
        log = ctx.logger

        log.info(
            f"Creating checkout session for trial upgrade from "
            f"{billing_model.stripe_subscription_id} to {new_plan} plan "
            f"(keeping trial active until checkout completes)"
        )

        # Will handle the trial subscription cancellation in the webhook
        price_id = stripe_client.get_price_id_for_plan(new_plan)
        session = await stripe_client.create_checkout_session(
            customer_id=billing_model.stripe_customer_id,
            price_id=price_id,
            success_url=f"{settings.app_url}/organization/settings?tab=billing&success=true",
            cancel_url=f"{settings.app_url}/organization/settings?tab=billing",
            metadata={
                "organization_id": str(ctx.organization.id),
                "plan": new_plan,
                "upgrade_from_trial": "true",
                "previous_subscription_id": billing_model.stripe_subscription_id,
            },
            trial_period_days=None,  # No trial for the new subscription
        )

        return f"Please complete checkout at: {session.url}"

    async def _handle_plan_downgrade(
        self,
        db: AsyncSession,
        billing_model: schemas.OrganizationBilling,
        organization: schemas.Organization,
        new_plan: str,
        new_price_id: str,
    ) -> str:
        """Handle plan downgrade (scheduled for end of period).

        Args:
            db: Database session
            billing_model: Organization billing model
            organization: Organization object
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
        ctx = await self._create_system_context(db, organization)

        # Store pending change locally
        update_data = OrganizationBillingUpdate(
            pending_plan_change=BillingPlan(new_plan),
            pending_plan_change_at=billing_model.current_period_end,
        )

        # Get the billing model from the database to avoid issues with detached instances
        db_billing_model = await crud.organization_billing.get(db, id=billing_model.id, ctx=ctx)

        await crud.organization_billing.update(
            db,
            db_obj=db_billing_model,
            obj_in=update_data,
            ctx=ctx,
        )

        return (
            f"Subscription will be downgraded to {new_plan} at the end "
            f"of the current billing period"
        )

    async def _handle_plan_upgrade(
        self,
        db: AsyncSession,
        billing_model: Any,
        organization: schemas.Organization,
        new_plan: str,
        new_price_id: str,
        is_trial_to_startup: bool,
    ) -> str:
        """Handle plan upgrade (immediate change with proration).

        Args:
            db: Database session
            billing_model: Organization billing model
            organization: Organization
            new_plan: New plan name
            new_price_id: Stripe price ID for new plan
            is_trial_to_startup: Whether this is trial to startup upgrade

        Returns:
            Success message
        """
        log = logger  # TODO: Accept contextual logger parameter

        # Reactivate if canceled
        if billing_model.cancel_at_period_end:
            log.info(
                f"Reactivate canceled subscription before plan change for org {organization.id}"
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
        system_ctx = await self._create_system_context(db, organization)

        # Update local billing record
        # Do not update billing_plan here. Let the Stripe webhook drive the
        # authoritative plan change and create the new billing period to avoid
        # races where the webhook cannot detect the change.
        update_data = OrganizationBillingUpdate(
            cancel_at_period_end=False,
        )

        if is_trial_to_startup:
            update_data.trial_ends_at = None

        await crud.organization_billing.update(
            db,
            db_obj=billing_model,
            obj_in=update_data,
            ctx=system_ctx,
        )

        return f"Successfully upgraded to {new_plan} plan"

    async def update_subscription_plan(
        self,
        db: AsyncSession,
        ctx: ApiContext,
        new_plan: str,
    ) -> str:
        """Update subscription to a different plan (upgrade/downgrade).

        For upgrades: Changes take effect immediately with proration
        For downgrades: Changes take effect at the end of the current billing period

        Args:
            db: Database session
            ctx: Authentication context
            new_plan: Target plan name

        Returns:
            Success message or checkout URL if payment update needed

        Raises:
            NotFoundException: If billing record not found
            InvalidStateError: If subscription update not allowed
        """
        log = ctx.logger

        billing_model = await crud.organization_billing.get_by_organization(
            db, organization_id=ctx.organization.id
        )

        # Developer is treated like any other plan (0$). No cancel path here.

        # Validate plan change for target plans
        # If upgrading to a paid plan without a payment method, require Checkout
        if new_plan in {"pro", "team"} and not billing_model.payment_method_added:
            raise InvalidStateError("Payment method required for upgrade; use checkout-session")

        new_price_id = self._validate_plan_change(billing_model, new_plan)
        current_plan = billing_model.billing_plan

        # Determine plan change type
        is_upgrade, is_trial_to_startup = self._determine_plan_change_type(
            current_plan, new_plan, billing_model
        )

        try:
            # Trials disabled: skip trial-only upgrade path

            # For downgrades, schedule the change for end of period
            if not is_upgrade:
                return await self._handle_plan_downgrade(
                    db, billing_model, ctx.organization, new_plan, new_price_id
                )

            # For upgrades, proceed with immediate update
            return await self._handle_plan_upgrade(
                db,
                billing_model,
                ctx.organization,
                new_plan,
                new_price_id,
                is_trial_to_startup,
            )
        except Exception as e:
            log.error(f"Failed to update subscription plan: {e}")
            raise InvalidStateError(f"Failed to update subscription plan: {str(e)}") from e

    async def cancel_subscription(
        self,
        db: AsyncSession,
        ctx: ApiContext,
    ) -> str:
        """Cancel a subscription.

        Args:
            db: Database session
            ctx: Authentication context

        Returns:
            Success message

        Raises:
            NotFoundException: If no active subscription
        """
        billing_model = await crud.organization_billing.get_by_organization(
            db, organization_id=ctx.organization.id
        )
        if not billing_model or not billing_model.stripe_subscription_id:
            raise NotFoundException("No active subscription found")

        try:
            # Cancel in Stripe - schedule cancellation at period end
            await stripe_client.update_subscription(
                subscription_id=billing_model.stripe_subscription_id,
                cancel_at_period_end=True,
            )

            update_data = OrganizationBillingUpdate(
                cancel_at_period_end=True,
            )

            await crud.organization_billing.update(
                db,
                db_obj=billing_model,
                obj_in=update_data,
                ctx=ctx,
            )

            return "Subscription will be canceled at the end of the current billing period"

        except Exception as e:
            ctx.logger.error(f"Failed to cancel subscription: {e}")
            raise InvalidStateError(f"Failed to cancel subscription: {str(e)}") from e

    async def reactivate_subscription(
        self,
        db: AsyncSession,
        ctx: ApiContext,
    ) -> str:
        """Reactivate a subscription that's set to cancel at period end.

        Args:
            db: Database session
            ctx: Authentication context

        Returns:
            Success message

        Raises:
            NotFoundException: If no subscription found
            InvalidStateError: If subscription not set to cancel
        """
        billing_model = await crud.organization_billing.get_by_organization(
            db, organization_id=ctx.organization.id
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
                ctx=ctx,
            )

            return "Subscription reactivated successfully"

        except Exception as e:
            ctx.logger.error(f"Failed to reactivate subscription: {e}")
            raise InvalidStateError(f"Failed to reactivate subscription: {str(e)}") from e

    async def cancel_pending_plan_change(
        self,
        db: AsyncSession,
        ctx: ApiContext,
    ) -> str:
        """Cancel a scheduled plan change (downgrade).

        Args:
            db: Database session
            ctx: Authentication context

        Returns:
            Success message
        """
        billing_model = await crud.organization_billing.get_by_organization(
            db, organization_id=ctx.organization.id
        )

        if not billing_model or not billing_model.pending_plan_change:
            raise InvalidStateError("No pending plan change found")

        # Get current subscription from Stripe (ensures it exists)
        _ = await stripe_client.get_subscription(billing_model.stripe_subscription_id)

        # Revert scheduled price change by setting price back to current plan
        current_price_id = stripe_client.get_price_id_for_plan(billing_model.billing_plan)
        await stripe_client.update_subscription(
            subscription_id=billing_model.stripe_subscription_id,
            price_id=current_price_id,
            proration_behavior="none",
        )
        update_data = OrganizationBillingUpdate(
            pending_plan_change=None,
            pending_plan_change_at=None,
        )

        # Get the billing model from the database to avoid issues with detached instances
        db_billing_model = await crud.organization_billing.get(db, id=billing_model.id, ctx=ctx)

        await crud.organization_billing.update(
            db,
            db_obj=db_billing_model,
            obj_in=update_data,
            ctx=ctx,
        )

        return "Scheduled plan change has been canceled"

    async def create_customer_portal_session(
        self,
        db: AsyncSession,
        ctx: ApiContext,
        return_url: str,
    ) -> str:
        """Create customer portal session for billing management.

        Args:
            db: Database session
            ctx: Authentication context
            return_url: URL to return to

        Returns:
            Portal session URL

        Raises:
            NotFoundException: If billing record not found
        """
        billing_model = await crud.organization_billing.get_by_organization(
            db, organization_id=ctx.organization.id
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
        contextual_logger: Optional[ContextualLogger] = None,
    ) -> None:
        """Handle subscription created webhook event.

        Args:
            db: Database session
            subscription: Stripe subscription object
            contextual_logger: Optional contextual logger with organization context
        """
        log = contextual_logger or logger

        # Get organization ID from metadata
        org_id = subscription.metadata.get("organization_id")
        if not org_id:
            log.error(f"No organization_id in subscription {subscription.id} metadata")
            return

        # Get billing record using CRUD
        billing_model = await crud.organization_billing.get_by_organization(
            db, organization_id=UUID(org_id)
        )
        if not billing_model:
            log.error(f"No billing record for organization {org_id}")
            return

        # Check if this is a trial upgrade
        is_trial_upgrade = subscription.metadata.get("upgrade_from_trial") == "true"
        previous_subscription_id = subscription.metadata.get("previous_subscription_id")

        # If this is a trial upgrade, cancel the old subscription
        # This happens AFTER the new subscription is successfully created
        if is_trial_upgrade and previous_subscription_id:
            log.info(
                f"Trial upgrade successful: New subscription {subscription.id} created. "
                f"Now canceling previous trial subscription {previous_subscription_id}"
            )
            try:
                # First check if the old subscription still exists and is active
                old_sub = await stripe_client.get_subscription(previous_subscription_id)
                if old_sub and old_sub.status not in ["canceled", "incomplete_expired"]:
                    await stripe_client.cancel_subscription(
                        subscription_id=previous_subscription_id,
                        cancel_at_period_end=False,  # Cancel immediately
                    )
                    log.info(
                        f"Successfully canceled previous trial subscription "
                        f"{previous_subscription_id}"
                    )
                else:
                    log.info(
                        f"Previous subscription {previous_subscription_id} "
                        f"already canceled or expired"
                    )
            except Exception as e:
                log.error(f"Failed to cancel previous subscription {previous_subscription_id}: {e}")
                # Continue processing even if cancellation fails - the new subscription is active

        # Determine plan from metadata or price
        plan = subscription.metadata.get("plan", "pro")

        # Trials disabled
        has_trial = False
        trial_ends_at = None

        # Create system auth context for update
        ctx = await self._create_system_context(db, UUID(org_id), "stripe_webhook")

        # Update billing record using CRUD
        has_pm, pm_id = await self._detect_payment_method(subscription)

        update_data = OrganizationBillingUpdate(
            stripe_subscription_id=subscription.id,
            billing_plan=BillingPlan(plan),
            billing_status=BillingStatus.ACTIVE,
            current_period_start=datetime.utcfromtimestamp(subscription.current_period_start),
            current_period_end=datetime.utcfromtimestamp(subscription.current_period_end),
            trial_ends_at=trial_ends_at,
            grace_period_ends_at=None,  # Clear grace period
            payment_method_added=has_pm,
            payment_method_id=pm_id,
        )

        await crud.organization_billing.update(
            db,
            db_obj=billing_model,
            obj_in=update_data,
            ctx=ctx,
        )

        # Create first billing period
        await self.create_billing_period(
            db=db,
            organization_id=UUID(org_id),
            period_start=datetime.utcfromtimestamp(subscription.current_period_start),
            period_end=datetime.utcfromtimestamp(subscription.current_period_end),
            plan=BillingPlan(plan),
            transition=(
                BillingTransition.INITIAL_SIGNUP
                if not is_trial_upgrade
                else BillingTransition.UPGRADE
            ),
            stripe_subscription_id=subscription.id,
            status=BillingPeriodStatus.ACTIVE,
            contextual_logger=log,
        )

        log.info(
            f"Subscription created for org {org_id}: {plan} "
            f"(trial: {has_trial}, upgrade: {is_trial_upgrade})"
        )

    def _infer_new_plan(  # Noqa: C901
        self,
        subscription: stripe.Subscription,
        previous_attributes: Optional[dict],
        current_plan: BillingPlan,
        pending_plan_change: Optional[BillingPlan],
        log: ContextualLogger,
    ) -> tuple[BillingPlan, bool, str]:
        """Infer the new plan deterministically using event context and local intent.

        This function avoids relying on subscription.items ordering and uses the
        following priority rules:
          1) Renewal (previous_attributes contains current_period_end):
             - If pending_plan_change exists: choose it
             - Else choose the single candidate, or the single candidate different from current
             - Else fallback to current_plan
          2) Immediate items change (previous_attributes contains items):
             - If exactly one candidate: choose it
             - Else if exactly one candidate differs from current_plan: choose it
             - Else if pending_plan_change exists and present among candidates: choose it
             - Else if previous_attributes carries an old price id, choose the candidate
               different from that, if unique
             - Else fallback to current_plan
          3) Neither renewal nor items change: keep current_plan

        Returns:
            Tuple of (new_plan, plan_changed, reason)
        """
        # Build reverse mapping price_id -> BillingPlan from configured price IDs
        price_id_to_plan: dict[str, BillingPlan] = {}
        try:
            for key, configured_price_id in (stripe_client.price_ids or {}).items():
                if not configured_price_id:
                    continue
                if key == "developer_monthly":
                    price_id_to_plan[configured_price_id] = BillingPlan.DEVELOPER
                elif key == "pro_monthly":
                    price_id_to_plan[configured_price_id] = BillingPlan.PRO
                elif key == "team_monthly":
                    price_id_to_plan[configured_price_id] = BillingPlan.TEAM
        except Exception:
            # If mapping fails, log and keep current
            log.error("Failed to build price_id_to_plan map from configuration")
            return current_plan, False, "mapping_error_fallback_current"

        # Extract all plan candidates from subscription items (ignore order)
        candidates: set[BillingPlan] = set()

        def _safe_get_items(obj: Any) -> list[Any]:
            try:
                if hasattr(obj, "items") and hasattr(obj.items, "data"):
                    return obj.items.data or []
                if isinstance(obj, dict):
                    return (obj.get("items") or {}).get("data") or []
            except Exception:
                pass
            return []

        items_data = _safe_get_items(subscription)

        def _extract_price_id(item: Any) -> Optional[str]:
            try:
                price_obj = None
                if hasattr(item, "price"):
                    price_obj = item.price
                elif isinstance(item, dict):
                    price_obj = item.get("price")
                if hasattr(price_obj, "id"):
                    return price_obj.id
                if isinstance(price_obj, dict):
                    return price_obj.get("id")
            except Exception:
                return None
            return None

        for item in items_data:
            price_id = _extract_price_id(item)
            plan = price_id_to_plan.get(price_id) if price_id else None
            if plan is not None:
                candidates.add(plan)

        prev_keys = (
            list(previous_attributes.keys()) if isinstance(previous_attributes, dict) else []
        )
        is_renewal = bool(previous_attributes and "current_period_end" in previous_attributes)
        items_changed = bool(previous_attributes and "items" in previous_attributes)

        log.info(
            "Plan inference context",
            extra={
                "current_plan": getattr(current_plan, "value", str(current_plan)),
                "pending_plan_change": (
                    getattr(pending_plan_change, "value", str(pending_plan_change))
                    if pending_plan_change
                    else None
                ),
                "prev_attr_keys": prev_keys,
                "candidates": [
                    getattr(c, "value", str(c)) for c in sorted(candidates, key=lambda p: p.value)
                ],
                "subscription_id": getattr(subscription, "id", None),
            },
        )

        # Helper to choose single candidate or differing candidate
        def _choose_single_or_diff() -> tuple[BillingPlan, str] | None:
            if len(candidates) == 1:
                chosen = next(iter(candidates))
                return chosen, "single_candidate"
            diffs = [p for p in candidates if p != current_plan]
            if len(diffs) == 1:
                return diffs[0], "single_diff_from_current"
            return None

        # 1) Renewal boundary
        if is_renewal:
            if pending_plan_change:
                log.info(
                    "Renewal with pending change; choosing pending plan",
                    extra={
                        "pending": getattr(pending_plan_change, "value", str(pending_plan_change))
                    },
                )
                return pending_plan_change, pending_plan_change != current_plan, "renewal_pending"
            maybe = _choose_single_or_diff()
            if maybe is not None:
                chosen, reason = maybe
                log.info(
                    "Renewal chose plan",
                    extra={
                        "chosen": getattr(chosen, "value", str(chosen)),
                        "reason": reason,
                    },
                )
                return chosen, chosen != current_plan, f"renewal_{reason}"
            log.warning(
                "Renewal ambiguous; fallback current",
                extra={
                    "current_plan": getattr(current_plan, "value", str(current_plan)),
                    "candidates": [getattr(c, "value", str(c)) for c in candidates],
                },
            )
            return current_plan, False, "renewal_ambiguous_fallback_current"

        # 2) Immediate items change
        if items_changed:
            maybe = _choose_single_or_diff()
            if maybe is not None:
                chosen, reason = maybe
                log.info(
                    "Items change chose plan",
                    extra={
                        "chosen": getattr(chosen, "value", str(chosen)),
                        "reason": reason,
                    },
                )
                return chosen, chosen != current_plan, f"items_{reason}"

            if pending_plan_change and pending_plan_change in candidates:
                log.info(
                    "Items change tie-break to pending plan",
                    extra={
                        "pending": getattr(pending_plan_change, "value", str(pending_plan_change))
                    },
                )
                return (
                    pending_plan_change,
                    pending_plan_change != current_plan,
                    "items_tiebreak_pending",
                )

            # Try to read old price from previous_attributes if present
            try:
                old_items = (
                    (previous_attributes or {}).get("items")
                    if isinstance(previous_attributes, dict)
                    else None
                )
                old_price_id = None
                if isinstance(old_items, dict):
                    # various shapes; best effort
                    old_data = old_items.get("data") or []
                    if old_data:
                        pid = _extract_price_id(old_data[0])
                        old_price_id = pid
                old_plan = price_id_to_plan.get(old_price_id) if old_price_id else None
                if old_plan is not None:
                    diffs2 = [p for p in candidates if p != old_plan]
                    if len(diffs2) == 1:
                        chosen = diffs2[0]
                        log.info(
                            "Items change chose plan via prev old",
                            extra={
                                "chosen": chosen.value,
                                "old_plan": old_plan.value,
                            },
                        )
                        return chosen, chosen != current_plan, "items_diff_from_old"
            except Exception:
                pass

            log.warning(
                "Items change ambiguous; fallback current",
                extra={
                    "current_plan": getattr(current_plan, "value", str(current_plan)),
                    "candidates": [getattr(c, "value", str(c)) for c in candidates],
                },
            )
            return current_plan, False, "items_ambiguous_fallback_current"

        # 3) Neither renewal nor items change -> keep current
        log.info("No renewal/items change; keeping current plan")
        return current_plan, False, "no_change"

    async def _handle_subscription_renewal(
        self,
        db: AsyncSession,
        org_id: UUID,
        subscription: stripe.Subscription,
        billing_snapshot: schemas.OrganizationBilling,
        new_plan: BillingPlan,
        plan_changed: bool,
    ) -> None:
        """Handle subscription renewal event.

        Args:
            db: Database session
            org_id: Organization ID
            subscription: Stripe subscription
            billing_snapshot: Organization billing snapshot
            new_plan: New plan
            plan_changed: Whether plan changed
        """
        current_period = await self.get_current_billing_period(db, org_id)

        # Determine effective plan and transition type using snapshot (no ORM access)
        effective_plan = billing_snapshot.pending_plan_change or new_plan

        if billing_snapshot.pending_plan_change:
            transition = BillingTransition.DOWNGRADE
        elif plan_changed:
            transition = BillingTransition.UPGRADE
        else:
            transition = BillingTransition.RENEWAL

        # Create new period
        await self.create_billing_period(
            db=db,
            organization_id=org_id,
            period_start=datetime.utcfromtimestamp(subscription.current_period_start),
            period_end=datetime.utcfromtimestamp(subscription.current_period_end),
            plan=(
                effective_plan
                if isinstance(effective_plan, BillingPlan)
                else BillingPlan(effective_plan)
            ),
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
            period_end=datetime.utcfromtimestamp(subscription.current_period_end),
            plan=BillingPlan(new_plan),
            transition=BillingTransition.UPGRADE,
            stripe_subscription_id=subscription.id,
            previous_period_id=current_period.id if current_period else None,
        )

    async def _handle_trial_conversion(
        self,
        db: AsyncSession,
        ctx: ApiContext,
        subscription: stripe.Subscription,
        new_plan: BillingPlan,
    ) -> None:
        """Handle trial to paid conversion.

        Args:
            db: Database session
            ctx: Authentication context
            subscription: Stripe subscription
            new_plan: New plan
        """
        current_period = await self.get_current_billing_period(db, ctx.organization.id)
        if not current_period or current_period.status != BillingPeriodStatus.TRIAL:
            return

        # End trial period
        await crud.billing_period.update(
            db,
            db_obj=await crud.billing_period.get(db, id=current_period.id, ctx=ctx),
            obj_in={"status": BillingPeriodStatus.COMPLETED},
            ctx=ctx,
        )

        # Create paid period
        await self.create_billing_period(
            db=db,
            organization_id=ctx.organization.id,
            period_start=datetime.utcnow(),
            period_end=datetime.utcfromtimestamp(subscription.current_period_end),
            plan=BillingPlan(new_plan),
            transition=BillingTransition.TRIAL_CONVERSION,
            stripe_subscription_id=subscription.id,
            previous_period_id=current_period.id,
        )

    async def handle_subscription_updated(  # noqa: C901
        self,
        db: AsyncSession,
        subscription: stripe.Subscription,
        previous_attributes: Optional[dict] = None,
        contextual_logger: Optional[ContextualLogger] = None,
    ) -> None:
        """Handle subscription updated webhook event.

        Args:
            db: Database sessionone i
            subscription: Stripe subscription object
            previous_attributes: Previous values that changed
            contextual_logger: Logger with organization context
        """
        log = contextual_logger or logger

        # Find billing by subscription ID
        billing_model = await crud.organization_billing.get_by_stripe_subscription(
            db, stripe_subscription_id=subscription.id
        )

        if not billing_model:
            log.error(f"No billing record for subscription {subscription.id}")
            return

        # Store ids before any DB operations to avoid lazy loading issues
        org_id = billing_model.organization_id
        billing_id = billing_model.id

        # Create webhook auth context for CRUD operations
        # Fetch the organization for the context
        org_model = await crud.organization.get(db, id=org_id, skip_access_validation=True)
        if not org_model:
            log.error(f"Organization {org_id} not found")
            return

        organization = schemas.Organization.model_validate(org_model, from_attributes=True)

        ctx = ApiContext(
            request_id=str(uuid4()),
            organization=organization,
            user=None,
            auth_method="stripe_webhook",
            auth_metadata={
                "source": "stripe_subscription_updated",
                "subscription_id": subscription.id,
            },
            logger=log,
        )

        # Load a fresh billing model instance and freeze values to avoid async lazy-loads
        db_billing_fresh = await crud.organization_billing.get(db, id=billing_id, ctx=ctx)
        billing_snapshot = schemas.OrganizationBilling.model_validate(
            db_billing_fresh, from_attributes=True
        )

        current_plan_snapshot = billing_snapshot.billing_plan
        pending_plan_change_snapshot = billing_snapshot.pending_plan_change

        # Extract/infer plan information using event-aware logic
        new_plan, plan_changed, inference_reason = self._infer_new_plan(
            subscription=subscription,
            previous_attributes=previous_attributes,
            current_plan=current_plan_snapshot,
            pending_plan_change=pending_plan_change_snapshot,
            log=log,
        )
        # Determine change kind (upgrade/downgrade/same)
        rank = {
            BillingPlan.DEVELOPER: 0,
            BillingPlan.PRO: 1,
            BillingPlan.TEAM: 2,
            BillingPlan.ENTERPRISE: 3,
        }
        current_rank = rank.get(current_plan_snapshot, 0)
        new_rank = rank.get(new_plan, current_rank)
        change_kind = (
            "UPGRADE"
            if new_rank > current_rank
            else "DOWNGRADE"
            if new_rank < current_rank
            else "SAME"
        )
        log.info(
            "Inferred plan",
            extra={
                "current_plan": getattr(current_plan_snapshot, "value", str(current_plan_snapshot)),
                "new_plan": getattr(new_plan, "value", str(new_plan)),
                "plan_changed": plan_changed,
                "inference_reason": inference_reason,
                "change_kind": change_kind,
            },
        )

        # Check if this is a renewal
        is_renewal = previous_attributes and "current_period_end" in previous_attributes

        # Pending changes are only cleared at renewal (when they take effect)

        # Handle renewal
        if is_renewal:
            await self._handle_subscription_renewal(
                db, org_id, subscription, billing_snapshot, new_plan, plan_changed
            )

        # Handle immediate plan change only for upgrades
        # For downgrades we keep the current period active until renewal to avoid
        # splitting the period mid-cycle and to prevent race conditions.
        elif previous_attributes and "items" in previous_attributes:
            if plan_changed and change_kind == "UPGRADE":
                await self._handle_immediate_plan_change(db, org_id, subscription, new_plan)
            else:
                log.info(
                    "Items changed but not an upgrade; skipping immediate period creation",
                    extra={
                        "plan_changed": plan_changed,
                        "change_kind": change_kind,
                        "current_plan": getattr(
                            current_plan_snapshot, "value", str(current_plan_snapshot)
                        ),
                        "new_plan": getattr(new_plan, "value", str(new_plan)),
                    },
                )

        # Prepare update data
        update_data = OrganizationBillingUpdate(
            billing_status=BillingStatus(subscription.status),
            cancel_at_period_end=subscription.cancel_at_period_end,
            current_period_start=datetime.utcfromtimestamp(subscription.current_period_start),
            current_period_end=datetime.utcfromtimestamp(subscription.current_period_end),
        )

        # Keep payment_method_added accurate based on Stripe
        has_pm, pm_id = await self._detect_payment_method(subscription)
        update_data.payment_method_added = has_pm
        if pm_id:
            update_data.payment_method_id = pm_id

        # Update plan only when appropriate:
        # - On renewal: always apply (pending change becomes active)
        # - On immediate items change: only if it's an UPGRADE
        try:
            plan_enum = new_plan if hasattr(new_plan, "value") else BillingPlan(str(new_plan))
        except Exception:
            plan_enum = BillingPlan.PRO
        if is_renewal:
            update_data.billing_plan = plan_enum
        elif previous_attributes and "items" in previous_attributes and change_kind == "UPGRADE":
            update_data.billing_plan = plan_enum

        # Clear pending plan change only when renewal applies it
        if is_renewal and pending_plan_change_snapshot:
            update_data.pending_plan_change = None
            update_data.pending_plan_change_at = None

        # Trials disabled: ignore trial_end updates

        # Update billing record using a freshly loaded instance to avoid
        # lazy-loading on an expired object in async context (MissingGreenlet).
        db_billing_model = await crud.organization_billing.get(db, id=billing_id, ctx=ctx)
        await crud.organization_billing.update(
            db,
            db_obj=db_billing_model,
            obj_in=update_data,
            ctx=ctx,
        )

        log.info(f"Subscription updated for org {org_id}")

    async def handle_subscription_deleted(
        self,
        db: AsyncSession,
        subscription: Any,  # stripe.Subscription
        contextual_logger: Optional[ContextualLogger] = None,
    ) -> None:
        """Handle subscription deleted/canceled webhook event.

        This event is sent both when:
        1. A subscription is scheduled to cancel (cancel_at_period_end=true)
        2. A subscription is actually deleted/ended

        We need to check the subscription status to determine which case it is.

        Args:
            db: Database session
            subscription: Stripe subscription object
            contextual_logger: Optional contextual logger with organization context
        """
        log = contextual_logger or logger

        # Find billing by subscription ID using CRUD
        billing_model = await crud.organization_billing.get_by_stripe_subscription(
            db, stripe_subscription_id=subscription.id
        )

        if not billing_model:
            log.error(f"No billing record for subscription {subscription.id}")
            return

        # Store organization_id before any DB operations to avoid lazy loading issues
        org_id = billing_model.organization_id

        # Create system auth context for update
        ctx = await self._create_system_context(db, org_id, "stripe_webhook")

        # Determine deletion vs scheduled-cancel update
        # For customer.subscription.deleted, Stripe sets status='canceled' at end-of-period
        sub_status = getattr(subscription, "status", None)
        if sub_status == "canceled":
            # Subscription is actually deleted/ended
            # Complete the final billing period
            current_period = await self.get_current_billing_period(db, org_id)
            if current_period:
                await crud.billing_period.update(
                    db,
                    db_obj=await crud.billing_period.get(db, id=current_period.id, ctx=ctx),
                    obj_in={"status": BillingPeriodStatus.COMPLETED},
                    ctx=ctx,
                )
                log.info(f"Completed final billing period {current_period.id} for org {org_id}")

            # Snapshot billing to avoid lazy-loading anything
            fresh = await crud.organization_billing.get(db, id=billing_model.id, ctx=ctx)
            snap = schemas.OrganizationBilling.model_validate(fresh, from_attributes=True)
            # If there was a pending downgrade, apply it; else keep plan but no sub
            new_plan = snap.pending_plan_change or snap.billing_plan
            update_data = OrganizationBillingUpdate(
                billing_status=BillingStatus.ACTIVE,
                billing_plan=new_plan,
                stripe_subscription_id=None,
                cancel_at_period_end=False,
                pending_plan_change=None,
                pending_plan_change_at=None,
            )
            await crud.organization_billing.update(
                db,
                db_obj=billing_model,
                obj_in=update_data,
                ctx=ctx,
            )

            # Developer is a normal plan now; no auto-create here. Deletion means real cancel.
            log.info(f"Subscription fully canceled for org {org_id}")
        else:
            # Not a final deletion – treat as scheduled cancel flag update
            update_data = OrganizationBillingUpdate(
                cancel_at_period_end=True,
            )
            await crud.organization_billing.update(
                db,
                db_obj=billing_model,
                obj_in=update_data,
                ctx=ctx,
            )
            log.info(
                f"Subscription scheduled to cancel at period end "
                f"for org {org_id} (status={sub_status})"
            )

    async def handle_payment_succeeded(
        self,
        db: AsyncSession,
        invoice: stripe.Invoice,
        contextual_logger: Optional[ContextualLogger] = None,
    ) -> None:
        """Handle successful payment webhook event.

        Args:
            db: Database session
            invoice: Stripe invoice object
            contextual_logger: Optional contextual logger with organization context
        """
        log = contextual_logger or logger

        if not invoice.subscription:
            return  # One-time payment, ignore

        # Find billing by customer ID using CRUD
        billing_model = await crud.organization_billing.get_by_stripe_customer(
            db, stripe_customer_id=invoice.customer
        )
        if not billing_model:
            log.error(f"No billing record for customer {invoice.customer}")
            return

        # Store organization_id before any DB operations to avoid lazy loading issues
        org_id = billing_model.organization_id

        # Create system auth context for update
        ctx = await self._create_system_context(db, org_id, "stripe_webhook")

        # Update payment info using CRUD
        update_data = OrganizationBillingUpdate(
            last_payment_status="succeeded",
            last_payment_at=datetime.utcnow(),  # Use utcnow() for timezone-naive
        )

        # If was past_due, update to active
        if billing_model.billing_status == BillingStatus.PAST_DUE:
            update_data.billing_status = BillingStatus.ACTIVE

        await crud.organization_billing.update(
            db,
            db_obj=billing_model,
            obj_in=update_data,
            ctx=ctx,
        )

        log.info(f"Payment succeeded for org {org_id}")

    async def handle_payment_failed(
        self,
        db: AsyncSession,
        invoice: stripe.Invoice,
        contextual_logger: Optional[ContextualLogger] = None,
    ) -> None:
        """Handle failed payment webhook event.

        Args:
            db: Database session
            invoice: Stripe invoice object
            contextual_logger: Optional contextual logger with organization context
        """
        log = contextual_logger or logger

        if not invoice.subscription:
            return  # One-time payment, ignore

        # Find billing by customer ID using CRUD
        billing_model = await crud.organization_billing.get_by_stripe_customer(
            db, stripe_customer_id=invoice.customer
        )
        if not billing_model:
            log.error(f"No billing record for customer {invoice.customer}")
            return

        # Store organization_id before any DB operations to avoid lazy loading issues
        org_id = billing_model.organization_id

        # Create system auth context for update
        ctx = await self._create_system_context(db, org_id, "stripe_webhook")

        # Check if this is a renewal payment failure
        if hasattr(invoice, "billing_reason") and invoice.billing_reason == "subscription_cycle":
            # This is a renewal payment failure
            current_period = await self.get_current_billing_period(db, org_id)
            if current_period:
                # Mark current period as ended but unpaid
                await crud.billing_period.update(
                    db,
                    db_obj=await crud.billing_period.get(db, id=current_period.id, ctx=ctx),
                    obj_in={"status": BillingPeriodStatus.ENDED_UNPAID},
                    ctx=ctx,
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
            ctx=ctx,
        )

        log.warning(f"Payment failed for org {org_id}")

    async def get_subscription_info(
        self, db: AsyncSession, organization_id: UUID, *, at: Optional[datetime] = None
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
                plan=BillingPlan.PRO,
                status=BillingStatus.ACTIVE,
                limits=self.PLAN_LIMITS.get(BillingPlan.PRO, {}),
                is_oss=True,
                has_active_subscription=False,
                in_trial=False,
                in_grace_period=False,
                payment_method_added=False,
                requires_payment_method=False,
            )

        # Trials disabled
        in_trial = False

        # Check if in grace period (only for existing subscriptions with payment failures)
        in_grace_period = (
            billing_model.grace_period_ends_at is not None
            and billing_model.grace_period_ends_at > datetime.utcnow()
            and not billing_model.payment_method_added
            and billing_model.stripe_subscription_id
            is not None  # Grace period only applies to existing subscriptions
        )

        # Check if grace period expired
        grace_period_expired = (
            billing_model.grace_period_ends_at is not None
            and billing_model.grace_period_ends_at <= datetime.utcnow()
            and not billing_model.payment_method_added
            and billing_model.stripe_subscription_id
            is not None  # Grace period only applies to existing subscriptions
        )

        # Needs setup when plan is paid and no subscription
        is_paid_plan = billing_model.billing_plan in {
            BillingPlan.PRO,
            BillingPlan.TEAM,
            BillingPlan.ENTERPRISE,
        }
        needs_initial_setup = is_paid_plan and not billing_model.stripe_subscription_id

        # Determine if payment method is required now
        requires_payment_method = needs_initial_setup or in_grace_period or grace_period_expired

        # Update status if grace period expired
        if grace_period_expired and billing_model.billing_status != BillingStatus.TRIAL_EXPIRED:
            # Create system auth context for update
            ctx = await self._create_system_context(db, organization_id)

            update_data = OrganizationBillingUpdate(
                billing_status=BillingStatus.TRIAL_EXPIRED,
            )

            await crud.organization_billing.update(
                db,
                db_obj=billing_model,
                obj_in=update_data,
                ctx=ctx,
            )

        # Consider subscription "active" only if we have an active/current billing period.
        # This gates access when Stripe webhooks are not processed yet (both paid and developer).
        current_period = (
            await self.get_current_billing_period_at(db, organization_id, at)
            if at is not None
            else await self.get_current_billing_period(db, organization_id)
        )

        return SubscriptionInfo(
            plan=billing_model.billing_plan,
            status=billing_model.billing_status,
            trial_ends_at=billing_model.trial_ends_at,
            grace_period_ends_at=billing_model.grace_period_ends_at,
            current_period_start=billing_model.current_period_start,
            current_period_end=billing_model.current_period_end,
            cancel_at_period_end=billing_model.cancel_at_period_end,
            limits=self.PLAN_LIMITS.get(billing_model.billing_plan, {}),
            is_oss=False,
            has_active_subscription=bool(current_period),
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
        contextual_logger: Optional[ContextualLogger] = None,
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
            contextual_logger: Optional contextual logger with auth context

        Returns:
            Created billing period
        """
        log = contextual_logger or logger

        # Complete the current active period (if any), avoiding iteration over ORM rows
        fresh_ctx = await self._create_system_context(db, organization_id)
        current_active = await crud.billing_period.get_current_period(
            db, organization_id=organization_id
        )
        if current_active and current_active.status in [
            BillingPeriodStatus.ACTIVE,
            BillingPeriodStatus.TRIAL,
            BillingPeriodStatus.GRACE,
        ]:
            # Re-fetch by id to ensure a live instance scoped to this context
            db_period = await crud.billing_period.get(db, id=current_active.id, ctx=fresh_ctx)
            if db_period:
                await crud.billing_period.update(
                    db,
                    db_obj=db_period,
                    obj_in={
                        "status": BillingPeriodStatus.COMPLETED,
                        "period_end": period_start,  # Ensure continuity!
                    },
                    ctx=fresh_ctx,
                )

                if not previous_period_id:
                    previous_period_id = db_period.id

                log.info(
                    f"Completed period {db_period.id} with adjusted end time {period_start} "
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
        ctx = await self._create_system_context(db, organization_id)

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
            period = await crud.billing_period.create(db, obj_in=period_create, ctx=ctx, uow=uow)

            await db.flush()

            billing_period = schemas.BillingPeriod.model_validate(period, from_attributes=True)

            # Create associated usage record
            usage_create = UsageCreate(
                organization_id=organization_id,
                billing_period_id=period.id,
                # All counters default to 0
            )

            await crud.usage.create(db, obj_in=usage_create, ctx=ctx, uow=uow)

        log.info(
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

    async def get_current_billing_period_at(
        self, db: AsyncSession, organization_id: UUID, at: datetime
    ) -> Optional[schemas.BillingPeriod]:
        """Get the active billing period for an organization at a specific time.

        Useful for tests that simulate time (e.g., Stripe Test Clock).
        """
        period = await crud.billing_period.get_current_period_at(
            db, organization_id=organization_id, at=at
        )
        return (
            schemas.BillingPeriod.model_validate(period, from_attributes=True) if period else None
        )

    async def handle_trial_expired(
        self,
        db: AsyncSession,
        organization_id: UUID,
        contextual_logger: Optional[ContextualLogger] = None,
    ) -> None:
        """Handle trial expiration for an organization.

        This should be called when a trial period ends without an active subscription.
        Updates the billing status to indicate the trial has expired.

        Args:
            db: Database session
            organization_id: Organization ID
            contextual_logger: Optional contextual logger with auth context
        """
        log = contextual_logger or logger

        billing_model = await crud.organization_billing.get_by_organization(
            db, organization_id=organization_id
        )
        if not billing_model:
            log.error(f"No billing record for organization {organization_id}")
            return

        # Only process if actually in trial without subscription
        if (
            billing_model.trial_ends_at
            and billing_model.trial_ends_at <= datetime.utcnow()
            and not billing_model.stripe_subscription_id
        ):
            # Create system auth context for update
            ctx = await self._create_system_context(db, organization_id)

            update_data = OrganizationBillingUpdate(
                billing_status=BillingStatus.TRIAL_EXPIRED,
                trial_ends_at=None,  # Clear trial end date
            )

            await crud.organization_billing.update(
                db,
                db_obj=billing_model,
                obj_in=update_data,
                ctx=ctx,
            )

            log.info(f"Trial expired for organization {organization_id}")


# Singleton instance
billing_service = BillingService()
