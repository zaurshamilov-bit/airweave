"""Webhook processor for Stripe billing events.

This module handles incoming Stripe webhook events and delegates
to appropriate handlers using clean separation of concerns.
"""

from datetime import datetime
from typing import Any
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
            "payment_intent.succeeded": self._handle_payment_intent_succeeded,
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

    async def _handle_subscription_updated(  # noqa: C901
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

        # On renewal with a pending plan, ensure Stripe price switches accordingly
        if is_renewal and inferred.changed and inferred.should_clear_pending and self.stripe:
            try:
                new_price_id = self.stripe.get_price_for_plan(inferred.plan)
                if new_price_id:
                    await self.stripe.update_subscription(
                        subscription_id=subscription.id,
                        price_id=new_price_id,
                        proration_behavior="none",
                    )
            except Exception as e:
                log.warning(f"Failed to switch subscription price on renewal: {e}")

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

            # Use Stripe period start to locate the period that was active at that time
            # This ensures correct linkage under Stripe test clock advances
            at_dt = (
                datetime.utcfromtimestamp(subscription.current_period_start)
                if is_renewal
                else datetime.utcnow()
            )
            current_period = await self.repository.get_current_billing_period(
                self.db, org_id, at=at_dt
            )

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

        # Yearly prepay expiry handling: if we've passed the expiry window, clear the flag
        try:
            billing_model_current = await self.repository.get_billing_record(self.db, org_id)
            if not billing_model_current or not billing_model_current.has_yearly_prepay:
                pass
            else:
                expiry = billing_model_current.yearly_prepay_expires_at
                # Prefer authoritative check using most recent billing period end
                latest_period = await self.repository.get_current_billing_period(self.db, org_id)
                latest_end = None
                if latest_period:
                    latest_end = latest_period.period_end

                compare_time = latest_end or datetime.utcfromtimestamp(
                    getattr(subscription, "current_period_end", 0)
                )

                if expiry and compare_time and compare_time >= expiry:
                    updates.has_yearly_prepay = False
        except Exception:
            pass

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

        # Stamp the most recent ACTIVE/GRACE period with invoice details (best effort)
        try:
            period = await self.repository.get_current_billing_period(self.db, org_id)
            if period and period.status in {BillingPeriodStatus.ACTIVE, BillingPeriodStatus.GRACE}:
                from airweave import crud as _crud

                inv_paid_at = None
                try:
                    transitions = getattr(invoice, "status_transitions", None)
                    if transitions and isinstance(transitions, dict):
                        paid_at_ts = transitions.get("paid_at")
                        if paid_at_ts:
                            inv_paid_at = datetime.utcfromtimestamp(int(paid_at_ts))
                except Exception:
                    inv_paid_at = None

                await _crud.billing_period.update(
                    self.db,
                    db_obj=await _crud.billing_period.get(self.db, id=period.id, ctx=ctx),
                    obj_in={
                        "stripe_invoice_id": getattr(invoice, "id", None),
                        "amount_cents": getattr(invoice, "amount_paid", None),
                        "currency": getattr(invoice, "currency", None),
                        "paid_at": inv_paid_at or datetime.utcnow(),
                    },
                    ctx=ctx,
                )
        except Exception:
            # Best effort; do not fail webhook
            pass

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
            f"Mode: {getattr(session, 'mode', None)}, "
            f"Subscription: {getattr(session, 'subscription', None)}"
        )

        # If this is a yearly prepay payment (mode=payment), finalize yearly flow.
        if getattr(session, "mode", None) == "payment":
            await self._finalize_yearly_prepay(session, log)

        # For subscription mode, the subscription.created webhook will handle setup

    async def _handle_payment_intent_succeeded(
        self,
        event: stripe.Event,
        log: ContextualLogger,
    ) -> None:
        """Optional handler for payment_intent.succeeded (not strictly needed)."""
        # No-op; checkout.session.completed covers our flow.
        return

    async def _finalize_yearly_prepay(self, session: Any, log: ContextualLogger) -> None:  # noqa: C901
        """Finalize yearly prepay: credit balance, create subscription with coupon."""
        try:
            if not getattr(session, "metadata", None):
                return
            if session.metadata.get("type") != "yearly_prepay":
                return

            org_id_str = session.metadata.get("organization_id")
            plan_str = session.metadata.get("plan")
            coupon_id = session.metadata.get("coupon_id")
            payment_intent_id = getattr(session, "payment_intent", None)
            if not (org_id_str and plan_str and coupon_id and payment_intent_id):
                log.error("Missing metadata for yearly prepay finalization")
                return

            organization_id = UUID(org_id_str)

            # Hydrate context
            org = await self.repository.get_organization(self.db, organization_id)
            if not org:
                log.error(f"Organization {organization_id} not found for prepay finalization")
                return
            org_schema = schemas.Organization.model_validate(org, from_attributes=True)
            ctx = self.service._create_system_context(org_schema, "stripe_webhook")

            # Credit customer's balance by the captured amount
            billing = await self.repository.get_billing_record(self.db, organization_id)
            if not billing:
                log.error("Billing record missing for yearly prepay finalization")
                return

            try:
                pi = stripe.PaymentIntent.retrieve(payment_intent_id)
                amount_received = getattr(pi, "amount_received", None)
            except Exception:
                amount_received = None

            if amount_received and self.stripe:
                try:
                    await self.stripe.credit_customer_balance(
                        customer_id=billing.stripe_customer_id,
                        amount_cents=int(amount_received),
                        description=f"Yearly prepay credit ({plan_str})",
                    )
                except Exception as e:
                    log.warning(f"Failed to credit balance: {e}")

            # Update existing subscription or create new one
            if self.stripe:
                price_id = self.stripe.get_price_for_plan(BillingPlan(plan_str))
                if price_id:
                    if billing.stripe_subscription_id:
                        # Update existing subscription (e.g., Developer → Pro yearly)
                        # Apply the coupon to the existing subscription
                        try:
                            await self.stripe.apply_coupon_to_subscription(
                                subscription_id=billing.stripe_subscription_id,
                                coupon_id=coupon_id,
                            )
                        except Exception as e:
                            log.warning(f"Failed to apply coupon to subscription: {e}")

                        # Get the payment method from the payment intent and set as default
                        payment_method_id = None
                        try:
                            payment_intent_id = getattr(session, "payment_intent", None)
                            if payment_intent_id:
                                pi = stripe.PaymentIntent.retrieve(payment_intent_id)
                                payment_method_id = getattr(pi, "payment_method", None)
                        except Exception as e:
                            log.warning(f"Failed to get payment method from payment intent: {e}")

                        # Update the subscription to the new price with default payment method
                        update_params = {
                            "subscription_id": billing.stripe_subscription_id,
                            "price_id": price_id,
                            "cancel_at_period_end": False,
                            "proration_behavior": "create_prorations",
                        }
                        if payment_method_id:
                            update_params["default_payment_method"] = payment_method_id

                        sub = await self.stripe.update_subscription(**update_params)
                        log.info(
                            f"Updated existing subscription {billing.stripe_subscription_id} "
                            f"to {plan_str} yearly"
                        )
                    else:
                        # Create new subscription (no existing subscription)
                        # Get the payment method from the payment intent
                        payment_method_id = None
                        try:
                            payment_intent_id = getattr(session, "payment_intent", None)
                            if payment_intent_id:
                                pi = stripe.PaymentIntent.retrieve(payment_intent_id)
                                payment_method_id = getattr(pi, "payment_method", None)
                        except Exception as e:
                            log.warning(f"Failed to get payment method from payment intent: {e}")

                        create_params = {
                            "customer_id": billing.stripe_customer_id,
                            "price_id": price_id,
                            "metadata": {
                                "organization_id": org_id_str,
                                "plan": plan_str,
                            },
                            "coupon_id": coupon_id,
                        }
                        if payment_method_id:
                            create_params["default_payment_method"] = payment_method_id

                        sub = await self.stripe.create_subscription(**create_params)
                        log.info(f"Created new subscription for {plan_str} yearly")

                    # Update DB: set subscription and finalize prepay window
                    from datetime import timedelta

                    # Derive expiry based on Stripe subscription start (respects test clock)
                    sub_start = datetime.utcfromtimestamp(sub.current_period_start)
                    expires_at = sub_start + timedelta(days=365)
                    # Check if subscription has payment method
                    has_pm, pm_id = (
                        self.stripe.detect_payment_method(sub) if self.stripe else (False, None)
                    )

                    await self.repository.update_billing_by_org(
                        self.db,
                        organization_id,
                        OrganizationBillingUpdate(
                            stripe_subscription_id=sub.id,
                            billing_plan=BillingPlan(plan_str),
                            payment_method_added=True,  # They just paid, so they have a pm
                            payment_method_id=pm_id,
                        ),
                        ctx,
                    )
                    await self.repository.record_yearly_prepay_finalized(
                        self.db,
                        organization_id,
                        coupon_id=coupon_id,
                        payment_intent_id=str(payment_intent_id),
                        expires_at=expires_at,
                        ctx=ctx,
                    )

                    log.info(f"Yearly prepay finalized for org {organization_id}: sub {sub.id}")
        except Exception as e:
            log.error(f"Error finalizing yearly prepay: {e}", exc_info=True)
            raise
