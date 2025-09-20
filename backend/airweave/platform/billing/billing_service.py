"""Main billing service orchestrator.

This module coordinates billing operations by orchestrating
between the business logic, repository, and Stripe client.
"""

from datetime import datetime
from typing import Optional
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from airweave import schemas
from airweave.api.context import ApiContext
from airweave.core.exceptions import InvalidStateError, NotFoundException
from airweave.core.logging import ContextualLogger, logger
from airweave.db.unit_of_work import UnitOfWork
from airweave.integrations.stripe_client import stripe_client
from airweave.models import Organization
from airweave.platform.billing.billing_data_access import BillingRepository
from airweave.platform.billing.plan_logic import (
    PlanChangeContext,
    analyze_plan_change,
    get_plan_limits,
    is_paid_plan,
)
from airweave.schemas.organization_billing import (
    BillingPlan,
    BillingStatus,
    OrganizationBillingUpdate,
    SubscriptionInfo,
)


class BillingService:
    """Service for managing organization billing and subscriptions."""

    def __init__(self):
        """Initialize billing service."""
        self.repository = BillingRepository()
        self.stripe = stripe_client

    def _create_system_context(
        self,
        organization: schemas.Organization,
        source: str = "billing_service",
    ) -> ApiContext:
        """Create a system context for billing operations."""
        request_id = str(uuid4())
        return ApiContext(
            request_id=request_id,
            auth_method="internal_system",
            auth_subject_id=str(uuid4()),
            auth_subject_name=f"billing_{source}",
            organization=organization,
            user=None,
            logger=logger.with_context(
                request_id=request_id,
                organization_id=str(organization.id),
                auth_method="internal_system",
                source=source,
            ),
        )

    async def _get_organization(
        self, db: AsyncSession, organization_id: UUID
    ) -> schemas.Organization:
        """Get organization by ID."""
        org_model = await self.repository.get_organization(db, organization_id)
        if not org_model:
            raise NotFoundException(f"Organization {organization_id} not found")
        return schemas.Organization.model_validate(org_model, from_attributes=True)

    # Billing record management

    async def create_billing_record(
        self,
        db: AsyncSession,
        organization: Organization,
        stripe_customer_id: str,
        billing_email: str,
        ctx: ApiContext,
        uow: UnitOfWork,
        contextual_logger: Optional[ContextualLogger] = None,
    ) -> schemas.OrganizationBilling:
        """Create initial billing record for an organization.

        Handles both paid and free (developer) plans.
        """
        log = contextual_logger or logger

        # Extract plan from organization metadata
        selected_plan = BillingPlan.PRO  # Default
        if hasattr(organization, "org_metadata") and organization.org_metadata:
            # Check for plan in onboarding metadata (from test/frontend)
            onboarding = organization.org_metadata.get("onboarding", {})
            subscription_plan = onboarding.get("subscriptionPlan")
            # Also check direct plan field for backwards compatibility
            direct_plan = organization.org_metadata.get("plan")

            plan_from_metadata = subscription_plan or direct_plan
            if plan_from_metadata and plan_from_metadata.lower() in [
                "developer",
                "pro",
                "team",
                "enterprise",
            ]:
                selected_plan = BillingPlan(plan_from_metadata.lower())

        # Create billing record
        billing = await self.repository.create_billing_record(
            db=db,
            organization_id=organization.id,
            stripe_customer_id=stripe_customer_id,
            billing_email=billing_email,
            plan=selected_plan,
            ctx=ctx,
            uow=uow,
        )

        log.info(f"Created billing record for org {organization.id} with plan {selected_plan}")

        # For free developer plan, create $0 subscription for webhook-driven periods
        if selected_plan == BillingPlan.DEVELOPER and self.stripe:
            price_id = self.stripe.get_price_for_plan(BillingPlan.DEVELOPER)
            if price_id:
                try:
                    sub = await self.stripe.create_subscription(
                        customer_id=stripe_customer_id,
                        price_id=price_id,
                        metadata={
                            "organization_id": str(organization.id),
                            "plan": "developer",
                        },
                    )

                    await self.repository.update_billing_by_org(
                        db=db,
                        organization_id=organization.id,
                        updates=OrganizationBillingUpdate(
                            stripe_subscription_id=sub.id,
                        ),
                        ctx=ctx,
                    )

                    log.info(
                        f"Created $0 developer subscription {sub.id} for org {organization.id}"
                    )
                except Exception as e:
                    log.warning(f"Failed to create developer subscription: {e}")
            else:
                log.warning("Developer price ID not configured; developer plan will be local-only")

        return billing

    # Subscription management

    async def start_subscription_checkout(
        self,
        db: AsyncSession,
        plan: str,
        success_url: str,
        cancel_url: str,
        ctx: ApiContext,
    ) -> str:
        """Start a subscription checkout flow."""
        billing = await self.repository.get_billing_record(db, ctx.organization.id)
        if not billing:
            raise NotFoundException("No billing record found for organization")

        if not self.stripe:
            raise InvalidStateError("Stripe is not enabled")

        # Get price ID for plan
        billing_plan = BillingPlan(plan)
        price_id = self.stripe.get_price_for_plan(billing_plan)
        if not price_id:
            raise InvalidStateError(f"Invalid plan: {plan}")

        # Check if checkout is needed
        is_target_paid = is_paid_plan(billing_plan)
        needs_checkout = is_target_paid and not billing.payment_method_added

        # If has subscription and doesn't need checkout, update instead
        if billing.stripe_subscription_id and not needs_checkout:
            if billing.billing_plan != billing_plan:
                ctx.logger.info(f"Updating existing subscription to {plan}")
                return await self.update_subscription_plan(db, ctx, plan)

            if billing.cancel_at_period_end:
                ctx.logger.info(f"Reactivating canceled {plan} subscription")
                return await self.update_subscription_plan(db, ctx, plan)

            raise InvalidStateError(f"Already has active {plan} subscription")

        # Create checkout session
        metadata = {
            "organization_id": str(ctx.organization.id),
            "plan": plan,
        }

        if billing.stripe_subscription_id and needs_checkout:
            metadata["previous_subscription_id"] = billing.stripe_subscription_id

        session = await self.stripe.create_checkout_session(
            customer_id=billing.stripe_customer_id,
            price_id=price_id,
            success_url=success_url,
            cancel_url=cancel_url,
            metadata=metadata,
        )

        return session.url

    async def update_subscription_plan(
        self,
        db: AsyncSession,
        ctx: ApiContext,
        new_plan: str,
    ) -> str:
        """Update subscription to a new plan."""
        billing = await self.repository.get_billing_record(db, ctx.organization.id)
        if not billing:
            raise NotFoundException("No billing record found")

        if not billing.stripe_subscription_id:
            raise NotFoundException("No active subscription found")

        if not self.stripe:
            raise InvalidStateError("Stripe is not enabled")

        # Analyze the plan change
        context = PlanChangeContext(
            current_plan=billing.billing_plan,
            target_plan=BillingPlan(new_plan),
            has_payment_method=billing.payment_method_added,
            is_canceling=billing.cancel_at_period_end,
            pending_plan=billing.pending_plan_change,
            current_period_end=billing.current_period_end,
        )

        decision = analyze_plan_change(context)

        if not decision.allowed:
            if decision.requires_checkout:
                raise InvalidStateError(decision.message)
            raise InvalidStateError(decision.message)

        # Get new price ID
        new_price_id = self.stripe.get_price_for_plan(BillingPlan(new_plan))
        if not new_price_id:
            raise InvalidStateError(f"Invalid plan: {new_plan}")

        # Apply the change
        if decision.apply_immediately:
            # Immediate change (upgrade or reactivation)
            await self.stripe.update_subscription(
                subscription_id=billing.stripe_subscription_id,
                price_id=new_price_id if decision.new_plan != billing.billing_plan else None,
                cancel_at_period_end=False,
                proration_behavior="create_prorations",
            )

            updates = OrganizationBillingUpdate(
                cancel_at_period_end=False,
            )

            if decision.clear_pending:
                updates.pending_plan_change = None
                updates.pending_plan_change_at = None

            await self.repository.update_billing_by_org(db, ctx.organization.id, updates, ctx)
        else:
            # Scheduled change (downgrade)
            await self.stripe.update_subscription(
                subscription_id=billing.stripe_subscription_id,
                price_id=new_price_id,
                proration_behavior="none",
            )

            updates = OrganizationBillingUpdate(
                pending_plan_change=BillingPlan(new_plan),
                pending_plan_change_at=billing.current_period_end,
            )

            await self.repository.update_billing_by_org(db, ctx.organization.id, updates, ctx)

        return decision.message

    async def cancel_subscription(
        self,
        db: AsyncSession,
        ctx: ApiContext,
    ) -> str:
        """Cancel subscription at period end."""
        billing = await self.repository.get_billing_record(db, ctx.organization.id)
        if not billing or not billing.stripe_subscription_id:
            raise NotFoundException("No active subscription found")

        if not self.stripe:
            raise InvalidStateError("Stripe is not enabled")

        # Cancel in Stripe
        await self.stripe.cancel_subscription(
            billing.stripe_subscription_id,
            at_period_end=True,
        )

        # Update local record
        await self.repository.update_billing_by_org(
            db,
            ctx.organization.id,
            OrganizationBillingUpdate(cancel_at_period_end=True),
            ctx,
        )

        return "Subscription will be canceled at the end of the current billing period"

    async def reactivate_subscription(
        self,
        db: AsyncSession,
        ctx: ApiContext,
    ) -> str:
        """Reactivate a canceled subscription."""
        billing = await self.repository.get_billing_record(db, ctx.organization.id)
        if not billing or not billing.stripe_subscription_id:
            raise NotFoundException("No active subscription found")

        if not billing.cancel_at_period_end:
            raise InvalidStateError("Subscription is not set to cancel")

        if not self.stripe:
            raise InvalidStateError("Stripe is not enabled")

        # Reactivate in Stripe
        await self.stripe.update_subscription(
            subscription_id=billing.stripe_subscription_id,
            cancel_at_period_end=False,
        )

        # Update local record
        await self.repository.update_billing_by_org(
            db,
            ctx.organization.id,
            OrganizationBillingUpdate(cancel_at_period_end=False),
            ctx,
        )

        return "Subscription reactivated successfully"

    async def cancel_pending_plan_change(
        self,
        db: AsyncSession,
        ctx: ApiContext,
    ) -> str:
        """Cancel a pending plan change."""
        billing = await self.repository.get_billing_record(db, ctx.organization.id)
        if not billing or not billing.pending_plan_change:
            raise InvalidStateError("No pending plan change found")

        if not self.stripe:
            raise InvalidStateError("Stripe is not enabled")

        # Revert Stripe subscription to current plan
        current_price_id = self.stripe.get_price_for_plan(billing.billing_plan)
        if not current_price_id:
            raise InvalidStateError(f"Invalid current plan: {billing.billing_plan}")

        await self.stripe.update_subscription(
            subscription_id=billing.stripe_subscription_id,
            price_id=current_price_id,
            proration_behavior="none",
        )

        # Clear pending change
        await self.repository.update_billing_by_org(
            db,
            ctx.organization.id,
            OrganizationBillingUpdate(
                pending_plan_change=None,
                pending_plan_change_at=None,
            ),
            ctx,
        )

        return "Scheduled plan change has been canceled"

    async def create_customer_portal_session(
        self,
        db: AsyncSession,
        ctx: ApiContext,
        return_url: str,
    ) -> str:
        """Create Stripe customer portal session."""
        billing = await self.repository.get_billing_record(db, ctx.organization.id)
        if not billing:
            raise NotFoundException("No billing record found")

        if not self.stripe:
            raise InvalidStateError("Stripe is not enabled")

        session = await self.stripe.create_portal_session(
            customer_id=billing.stripe_customer_id,
            return_url=return_url,
        )

        return session.url

    # Subscription information

    async def get_subscription_info(
        self,
        db: AsyncSession,
        organization_id: UUID,
        at: Optional[datetime] = None,
    ) -> SubscriptionInfo:
        """Get comprehensive subscription information."""
        billing = await self.repository.get_billing_record(db, organization_id)

        if not billing:
            # Return free/OSS tier info
            return SubscriptionInfo(
                plan=BillingPlan.PRO,
                status=BillingStatus.ACTIVE,
                cancel_at_period_end=False,
                current_period_start=None,
                current_period_end=None,
                pending_plan_change=None,
                pending_plan_change_at=None,
                limits=get_plan_limits(BillingPlan.PRO),
                payment_method_added=False,
                in_grace_period=False,
                requires_payment_method=False,
                is_oss=False,
                has_active_subscription=False,
                in_trial=False,
                trial_ends_at=None,
                grace_period_ends_at=None,
            )

        # Check grace period
        in_grace_period = (
            billing.grace_period_ends_at is not None
            and datetime.utcnow() < billing.grace_period_ends_at
            and billing.stripe_subscription_id is not None
        )

        grace_period_expired = (
            billing.grace_period_ends_at is not None
            and datetime.utcnow() >= billing.grace_period_ends_at
            and billing.stripe_subscription_id is not None
        )

        # Check if needs setup
        is_paid = is_paid_plan(billing.billing_plan)
        needs_initial_setup = is_paid and not billing.stripe_subscription_id
        requires_payment_method = needs_initial_setup or in_grace_period or grace_period_expired

        # Update status if grace period expired
        if grace_period_expired and billing.billing_status != BillingStatus.PAST_DUE:
            org = await self._get_organization(db, organization_id)
            ctx = self._create_system_context(org, "get_subscription_info")
            await self.repository.update_billing_by_org(
                db,
                organization_id,
                OrganizationBillingUpdate(billing_status=BillingStatus.PAST_DUE),
                ctx,
            )

        return SubscriptionInfo(
            plan=billing.billing_plan,
            status=billing.billing_status,
            cancel_at_period_end=billing.cancel_at_period_end,
            current_period_start=billing.current_period_start,
            current_period_end=billing.current_period_end,
            pending_plan_change=billing.pending_plan_change,
            pending_plan_change_at=billing.pending_plan_change_at,
            limits=get_plan_limits(billing.billing_plan),
            payment_method_added=billing.payment_method_added,
            in_grace_period=in_grace_period,
            grace_period_ends_at=billing.grace_period_ends_at,
            requires_payment_method=requires_payment_method,
            is_oss=False,
            has_active_subscription=bool(billing.stripe_subscription_id),
            in_trial=False,  # We don't track trials currently
            trial_ends_at=None,
        )


# Singleton instance
billing_service = BillingService()
