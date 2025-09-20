"""Webhook processor for Stripe billing events.

This module handles incoming Stripe webhook events and delegates
to appropriate handlers using clean separation of concerns.
"""

from datetime import datetime
from uuid import UUID

import stripe
from sqlalchemy.ext.asyncio import AsyncSession

from airweave import crud, schemas
from airweave.core.logging import ContextualLogger, logger
from airweave.integrations.stripe_client import stripe_client
from airweave.platform.billing.billing_data_access import BillingRepository
from airweave.platform.billing.billing_service import BillingService
from airweave.platform.billing.plan_logic import (
    PlanInferenceContext,
    compare_plans,
    determine_period_transition,
    infer_plan_from_webhook,
    should_create_new_period,
)
from airweave.schemas.billing_period import BillingPeriodStatus, BillingTransition
from airweave.schemas.organization_billing import (
    BillingPlan,
    BillingStatus,
    OrganizationBillingUpdate,
)


class BillingWebhookProcessor:
    """Process Stripe webhook events for billing."""

    def __init__(self, db: AsyncSession):
        """Initialize webhook processor."""
        self.db = db
        self.repository = BillingRepository()
        self.service = BillingService()
        self.stripe = stripe_client

        # Event handler mapping
        self.handlers = {
            "customer.subscription.created": self._handle_subscription_created,
            "customer.subscription.updated": self._handle_subscription_updated,
            "customer.subscription.deleted": self._handle_subscription_deleted,
            "invoice.payment_succeeded": self._handle_payment_succeeded,
            "invoice.paid": self._handle_payment_succeeded,  # $0 invoices
            "invoice.payment_failed": self._handle_payment_failed,
            "invoice.upcoming": self._handle_invoice_upcoming,
            "checkout.session.completed": self._handle_checkout_completed,
        }

    async def _create_context_logger(self, event: stripe.Event) -> ContextualLogger:
        """Create contextual logger with organization context."""
        organization_id = None

        try:
            event_object = event.data.object

            # Try metadata first
            if hasattr(event_object, "metadata") and event_object.metadata:
                org_id_str = event_object.metadata.get("organization_id")
                if org_id_str:
                    organization_id = UUID(org_id_str)

            # If not in metadata, lookup by customer/subscription
            if not organization_id:
                billing_model = None

                if hasattr(event_object, "id") and event.type.startswith("customer.subscription"):
                    billing_model = await self.repository.get_billing_by_subscription(
                        self.db, event_object.id
                    )
                elif hasattr(event_object, "customer"):
                    billing_model = await crud.organization_billing.get_by_stripe_customer(
                        self.db, stripe_customer_id=event_object.customer
                    )
                elif hasattr(event_object, "subscription") and event_object.subscription:
                    billing_model = await self.repository.get_billing_by_subscription(
                        self.db, event_object.subscription
                    )

                if billing_model:
                    organization_id = billing_model.organization_id

        except Exception as e:
            logger.error(f"Failed to get organization context: {e}")

        if organization_id:
            return logger.with_context(
                organization_id=str(organization_id),
                auth_method="stripe_webhook",
                event_type=event.type,
                stripe_event_id=event.id,
            )

        return logger.with_context(
            auth_method="stripe_webhook",
            event_type=event.type,
            stripe_event_id=event.id,
        )

    async def process_event(self, event: stripe.Event) -> None:
        """Process a Stripe webhook event."""
        log = await self._create_context_logger(event)

        handler = self.handlers.get(event.type)
        if handler:
            try:
                log.info(f"Processing webhook event: {event.type}")
                await handler(event, log)
            except Exception as e:
                log.error(f"Error handling {event.type}: {e}", exc_info=True)
                raise
        else:
            log.info(f"Unhandled webhook event type: {event.type}")

    # Event handlers

    async def _handle_subscription_created(
        self,
        event: stripe.Event,
        log: ContextualLogger,
    ) -> None:
        """Handle new subscription creation."""
        subscription = event.data.object

        # Get organization from metadata
        org_id = subscription.metadata.get("organization_id")
        if not org_id:
            log.error(f"No organization_id in subscription {subscription.id} metadata")
            return

        # Get billing record
        billing_model = await crud.organization_billing.get_by_organization(
            self.db, organization_id=UUID(org_id)
        )
        if not billing_model:
            log.error(f"No billing record for organization {org_id}")
            return

        # Determine plan
        plan_str = subscription.metadata.get("plan", "pro")
        plan = BillingPlan(plan_str)

        # Create system context
        org = await self.repository.get_organization(self.db, UUID(org_id))
        if not org:
            log.error(f"Organization {org_id} not found")
            return

        org_schema = schemas.Organization.model_validate(org, from_attributes=True)
        ctx = self.service._create_system_context(org_schema, "stripe_webhook")

        # Detect payment method
        has_pm, pm_id = (
            self.stripe.detect_payment_method(subscription) if self.stripe else (False, None)
        )

        # Update billing record
        updates = OrganizationBillingUpdate(
            stripe_subscription_id=subscription.id,
            billing_plan=plan,
            billing_status=BillingStatus.ACTIVE,
            current_period_start=datetime.utcfromtimestamp(subscription.current_period_start),
            current_period_end=datetime.utcfromtimestamp(subscription.current_period_end),
            grace_period_ends_at=None,
            payment_method_added=has_pm,
            payment_method_id=pm_id,
        )

        await crud.organization_billing.update(
            self.db,
            db_obj=billing_model,
            obj_in=updates,
            ctx=ctx,
        )

        # Create first billing period
        await self.repository.create_billing_period(
            db=self.db,
            organization_id=UUID(org_id),
            period_start=datetime.utcfromtimestamp(subscription.current_period_start),
            period_end=datetime.utcfromtimestamp(subscription.current_period_end),
            plan=plan,
            transition=BillingTransition.INITIAL_SIGNUP,
            stripe_subscription_id=subscription.id,
            status=BillingPeriodStatus.ACTIVE,
            ctx=ctx,
        )

        log.info(f"Subscription created for org {org_id}: {plan}")

    async def _handle_subscription_updated(
        self,
        event: stripe.Event,
        log: ContextualLogger,
    ) -> None:
        """Handle subscription updates."""
        subscription = event.data.object
        previous_attributes = event.data.get("previous_attributes", {})

        # Get billing record
        billing_model = await self.repository.get_billing_by_subscription(self.db, subscription.id)
        if not billing_model:
            log.error(f"No billing record for subscription {subscription.id}")
            return

        org_id = billing_model.organization_id

        # Create context
        org = await self.repository.get_organization(self.db, org_id)
        if not org:
            log.error(f"Organization {org_id} not found")
            return

        org_schema = schemas.Organization.model_validate(org, from_attributes=True)
        ctx = self.service._create_system_context(org_schema, "stripe_webhook")

        # Get current billing state
        billing = await self.repository.get_billing_record(self.db, org_id)
        if not billing:
            log.error(f"No billing schema for org {org_id}")
            return

        # Infer new plan
        is_renewal = "current_period_end" in previous_attributes
        items_changed = "items" in previous_attributes

        if self.stripe:
            price_ids = self.stripe.extract_subscription_items(subscription)
            price_mapping = self.stripe.get_price_id_mapping()
        else:
            price_ids = []
            price_mapping = {}

        inference_context = PlanInferenceContext(
            current_plan=billing.billing_plan,
            pending_plan=billing.pending_plan_change,
            is_renewal=is_renewal,
            items_changed=items_changed,
            subscription_items=price_ids,
        )

        inferred = infer_plan_from_webhook(inference_context, price_mapping)

        log.info(
            f"Inferred plan: {inferred.plan} (changed={inferred.changed}, reason={inferred.reason})"
        )

        # Determine if we should create a new period
        change_type = compare_plans(billing.billing_plan, inferred.plan)
        if should_create_new_period(
            "renewal" if is_renewal else "immediate_change",
            inferred.changed,
            change_type,
        ):
            transition = determine_period_transition(
                billing.billing_plan,
                inferred.plan,
                is_first_period=False,
            )

            current_period = await self.repository.get_current_billing_period(self.db, org_id)

            await self.repository.create_billing_period(
                db=self.db,
                organization_id=org_id,
                period_start=datetime.utcfromtimestamp(subscription.current_period_start)
                if is_renewal
                else datetime.utcnow(),
                period_end=datetime.utcfromtimestamp(subscription.current_period_end),
                plan=inferred.plan,
                transition=transition,
                stripe_subscription_id=subscription.id,
                previous_period_id=current_period.id if current_period else None,
                ctx=ctx,
            )

        # Update billing record
        has_pm, pm_id = (
            self.stripe.detect_payment_method(subscription) if self.stripe else (False, None)
        )

        updates = OrganizationBillingUpdate(
            billing_plan=inferred.plan,
            billing_status=BillingStatus(subscription.status),
            cancel_at_period_end=subscription.cancel_at_period_end,
            current_period_start=datetime.utcfromtimestamp(subscription.current_period_start),
            current_period_end=datetime.utcfromtimestamp(subscription.current_period_end),
            payment_method_added=has_pm,
        )

        if pm_id:
            updates.payment_method_id = pm_id

        # Update plan when appropriate (for any plan change, not just upgrades)
        if is_renewal or (items_changed and inferred.changed):
            updates.billing_plan = inferred.plan

        # Clear pending change on renewal
        if is_renewal and inferred.should_clear_pending:
            updates.pending_plan_change = None
            updates.pending_plan_change_at = None

        await self.repository.update_billing_by_org(self.db, org_id, updates, ctx)

        log.info(f"Subscription updated for org {org_id}")

    async def _handle_subscription_deleted(
        self,
        event: stripe.Event,
        log: ContextualLogger,
    ) -> None:
        """Handle subscription deletion/cancellation."""
        subscription = event.data.object

        # Get billing record
        billing_model = await self.repository.get_billing_by_subscription(self.db, subscription.id)
        if not billing_model:
            log.error(f"No billing record for subscription {subscription.id}")
            return

        org_id = billing_model.organization_id

        # Create context
        org = await self.repository.get_organization(self.db, org_id)
        if not org:
            log.error(f"Organization {org_id} not found")
            return

        org_schema = schemas.Organization.model_validate(org, from_attributes=True)
        ctx = self.service._create_system_context(org_schema, "stripe_webhook")

        # Check if actually deleted or just scheduled
        sub_status = getattr(subscription, "status", None)
        if sub_status == "canceled":
            # Actually deleted
            current_period = await self.repository.get_current_billing_period(self.db, org_id)
            if current_period:
                await self.repository.complete_billing_period(
                    self.db, current_period.id, BillingPeriodStatus.COMPLETED, ctx
                )
                log.info(f"Completed final period {current_period.id} for org {org_id}")

            # Get current billing to check for pending downgrade
            billing = await self.repository.get_billing_record(self.db, org_id)
            new_plan = (
                billing.pending_plan_change or billing.billing_plan if billing else BillingPlan.PRO
            )

            updates = OrganizationBillingUpdate(
                billing_status=BillingStatus.ACTIVE,
                billing_plan=new_plan,
                stripe_subscription_id=None,
                cancel_at_period_end=False,
                pending_plan_change=None,
                pending_plan_change_at=None,
            )

            await crud.organization_billing.update(
                self.db,
                db_obj=billing_model,
                obj_in=updates,
                ctx=ctx,
            )

            log.info(f"Subscription fully canceled for org {org_id}")
        else:
            # Just scheduled to cancel
            updates = OrganizationBillingUpdate(cancel_at_period_end=True)
            await crud.organization_billing.update(
                self.db,
                db_obj=billing_model,
                obj_in=updates,
                ctx=ctx,
            )
            log.info(f"Subscription scheduled to cancel for org {org_id}")

    async def _handle_payment_succeeded(
        self,
        event: stripe.Event,
        log: ContextualLogger,
    ) -> None:
        """Handle successful payment."""
        invoice = event.data.object

        if not invoice.subscription:
            return  # One-time payment

        # Get billing record
        billing_model = await crud.organization_billing.get_by_stripe_customer(
            self.db, stripe_customer_id=invoice.customer
        )
        if not billing_model:
            log.error(f"No billing record for customer {invoice.customer}")
            return

        org_id = billing_model.organization_id

        # Create context
        org = await self.repository.get_organization(self.db, org_id)
        if not org:
            return

        org_schema = schemas.Organization.model_validate(org, from_attributes=True)
        ctx = self.service._create_system_context(org_schema, "stripe_webhook")

        # Update payment info
        updates = OrganizationBillingUpdate(
            last_payment_status="succeeded",
            last_payment_at=datetime.utcnow(),
        )

        # Clear past_due if needed
        if billing_model.billing_status == BillingStatus.PAST_DUE:
            updates.billing_status = BillingStatus.ACTIVE

        await crud.organization_billing.update(
            self.db,
            db_obj=billing_model,
            obj_in=updates,
            ctx=ctx,
        )

        log.info(f"Payment succeeded for org {org_id}")

    async def _handle_payment_failed(
        self,
        event: stripe.Event,
        log: ContextualLogger,
    ) -> None:
        """Handle failed payment."""
        invoice = event.data.object

        if not invoice.subscription:
            return  # One-time payment

        # Get billing record
        billing_model = await crud.organization_billing.get_by_stripe_customer(
            self.db, stripe_customer_id=invoice.customer
        )
        if not billing_model:
            log.error(f"No billing record for customer {invoice.customer}")
            return

        org_id = billing_model.organization_id

        # Create context
        org = await self.repository.get_organization(self.db, org_id)
        if not org:
            return

        org_schema = schemas.Organization.model_validate(org, from_attributes=True)
        ctx = self.service._create_system_context(org_schema, "stripe_webhook")

        # Check if renewal failure
        if hasattr(invoice, "billing_reason") and invoice.billing_reason == "subscription_cycle":
            # Create grace period
            from datetime import timedelta

            current_period = await self.repository.get_current_billing_period(self.db, org_id)
            if current_period:
                await self.repository.complete_billing_period(
                    self.db, current_period.id, BillingPeriodStatus.ENDED_UNPAID, ctx
                )

                grace_end = datetime.utcnow() + timedelta(days=7)
                await self.repository.create_billing_period(
                    db=self.db,
                    organization_id=org_id,
                    period_start=current_period.period_end,
                    period_end=grace_end,
                    plan=current_period.plan,
                    transition=BillingTransition.RENEWAL,
                    stripe_subscription_id=billing_model.stripe_subscription_id,
                    previous_period_id=current_period.id,
                    status=BillingPeriodStatus.GRACE,
                    ctx=ctx,
                )

                updates = OrganizationBillingUpdate(
                    last_payment_status="failed",
                    billing_status=BillingStatus.PAST_DUE,
                    grace_period_ends_at=grace_end,
                )
            else:
                updates = OrganizationBillingUpdate(
                    last_payment_status="failed",
                    billing_status=BillingStatus.PAST_DUE,
                )
        else:
            updates = OrganizationBillingUpdate(
                last_payment_status="failed",
                billing_status=BillingStatus.PAST_DUE,
            )

        await crud.organization_billing.update(
            self.db,
            db_obj=billing_model,
            obj_in=updates,
            ctx=ctx,
        )

        log.warning(f"Payment failed for org {org_id}")

    async def _handle_invoice_upcoming(
        self,
        event: stripe.Event,
        log: ContextualLogger,
    ) -> None:
        """Handle upcoming invoice notification."""
        invoice = event.data.object

        # Find organization
        billing_model = await crud.organization_billing.get_by_stripe_customer(
            self.db, stripe_customer_id=invoice.customer
        )

        if billing_model:
            log.info(
                f"Upcoming invoice for org {billing_model.organization_id}: "
                f"${invoice.amount_due / 100:.2f}"
            )
            # TODO: Send email notification if needed

    async def _handle_checkout_completed(
        self,
        event: stripe.Event,
        log: ContextualLogger,
    ) -> None:
        """Handle checkout session completion."""
        session = event.data.object

        log.info(
            f"Checkout completed: {session.id}, "
            f"Customer: {session.customer}, "
            f"Subscription: {session.subscription}"
        )
        # The subscription.created webhook will handle the actual setup
