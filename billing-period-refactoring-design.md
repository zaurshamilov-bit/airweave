# Billing Period Management Refactoring Design

## Executive Summary

This document outlines a refactoring of Airweave's billing system to introduce explicit billing period tracking. The current system tracks usage with date ranges but lacks a clear representation of billing periods and their state transitions. This refactoring introduces a `BillingPeriod` model to provide clear period lifecycle management while maintaining the existing `OrganizationBilling` model for subscription-level state.

## Problem Statement

### Current Issues

1. **No Clear Billing Period Entity**: Usage is tracked with `start_period` and `end_period` dates, but there's no explicit billing period model that represents the lifecycle of a subscription period.

2. **State Transitions Scattered**: Billing state changes are handled reactively through webhooks without a clear state machine or audit trail.

3. **Period Boundary Ambiguity**: No guarantee that `end_period` of one usage record matches `start_period` of the next.

4. **Grace Period Complexity**: Grace periods are tracked on the billing model itself, making it hard to understand which period a user is in.

5. **Usage Attribution**: Difficult to determine which billing period usage belongs to, especially during transitions.

## Proposed Solution

### Architecture Overview

The solution introduces a three-tier model:

1. **OrganizationBilling**: Tracks current subscription state and future intentions
2. **BillingPeriod**: Represents individual billing periods with their lifecycle
3. **Usage**: Tracks resource consumption within a specific period

### Data Model Changes

#### 1. New Model: `BillingPeriod`

```python
class BillingPeriod(Base):
    """Represents a discrete billing period for an organization."""

    __tablename__ = "billing_period"

    # Identity
    id: Mapped[UUID] = mapped_column(primary_key=True)
    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organization.id"))

    # Period boundaries (inclusive start, exclusive end)
    period_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    period_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    # Billing details at time of period
    plan: Mapped[BillingPlan] = mapped_column(Enum(BillingPlan), nullable=False)
    status: Mapped[BillingPeriodStatus] = mapped_column(Enum(BillingPeriodStatus), nullable=False)

    # Stripe references
    stripe_subscription_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    stripe_invoice_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    # Payment tracking
    amount_cents: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    currency: Mapped[Optional[str]] = mapped_column(String(3), nullable=True)
    paid_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # State transition metadata
    created_from: Mapped[BillingTransition] = mapped_column(Enum(BillingTransition), nullable=False)
    previous_period_id: Mapped[Optional[UUID]] = mapped_column(ForeignKey("billing_period.id"), nullable=True)

    # Relationships
    usage: Mapped["Usage"] = relationship("Usage", back_populates="billing_period", uselist=False)
    organization: Mapped["Organization"] = relationship("Organization", back_populates="billing_periods")
```

#### 2. New Enums

```python
class BillingPeriodStatus(str, Enum):
    """Status of a billing period."""
    ACTIVE = "active"              # Currently active period
    COMPLETED = "completed"        # Period ended, successfully paid
    ENDED_UNPAID = "ended_unpaid" # Period ended, payment failed/pending
    TRIAL = "trial"               # Trial period (no payment required)
    GRACE = "grace"               # Grace period after failed payment

class BillingTransition(str, Enum):
    """How this billing period was created."""
    INITIAL_SIGNUP = "initial_signup"      # First subscription
    RENEWAL = "renewal"                    # Automatic renewal
    UPGRADE = "upgrade"                    # Plan upgrade (immediate)
    DOWNGRADE = "downgrade"                # Plan downgrade (at period end)
    REACTIVATION = "reactivation"         # Reactivated after cancellation
    TRIAL_CONVERSION = "trial_conversion"  # Trial to paid
```

#### 3. Modified `Usage` Model

```python
class Usage(OrganizationBase):
    """Usage within a specific billing period."""

    __tablename__ = "usage"

    # Link to billing period instead of dates
    billing_period_id: Mapped[UUID] = mapped_column(
        ForeignKey("billing_period.id", ondelete="CASCADE"),
        unique=True  # One usage record per billing period
    )

    # Remove start_period and end_period fields
    # Keep all counter fields as-is:
    syncs: Mapped[int]
    entities: Mapped[int]
    queries: Mapped[int]
    collections: Mapped[int]
    source_connections: Mapped[int]

    # Relationship
    billing_period: Mapped["BillingPeriod"] = relationship(
        "BillingPeriod",
        back_populates="usage"
    )
```

#### 4. Updated `OrganizationBilling` Role

The `OrganizationBilling` model continues to track subscription-level state:

- **Stripe subscription reference** (current or most recent)
- **Current subscription plan** (may differ from active period during downgrades)
- **Overall subscription status** (ACTIVE, PAST_DUE, CANCELED, etc.)
- **Future state flags** (cancel_at_period_end, pending_plan_change)
- **Quick access to current period dates** (denormalized from BillingPeriod)
- **Payment method and trial info**

#### 5. OrganizationBilling Model Updates

Add the following field to support downgrade scheduling:

```python
class OrganizationBilling(Base):
    # ... existing fields ...

    # Add this field for tracking pending plan changes
    pending_plan_change: Mapped[Optional[BillingPlan]] = mapped_column(
        Enum(BillingPlan), nullable=True
    )

    # This field will store when a downgrade is scheduled to take effect
    pending_plan_change_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
```

### Service Layer Updates

#### Enhanced `BillingService`

The existing `BillingService` will be enhanced with period management capabilities:

```python
class BillingService:
    """Manages subscriptions and billing periods."""

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
    ) -> BillingPeriod:
        """Creates a new billing period and associated usage record."""

    async def get_current_billing_period(
        self,
        db: AsyncSession,
        organization_id: UUID,
    ) -> Optional[BillingPeriod]:
        """Gets the active billing period for an organization."""

    # Existing webhook handlers updated to manage periods
    async def handle_subscription_created(self, ...)
    async def handle_subscription_updated(self, ...)
    async def handle_payment_succeeded(self, ...)
```

### State Transitions

#### 1. New Subscription (Developer Plan with Trial)

```
OrganizationBilling:
  billing_plan: DEVELOPER
  billing_status: TRIALING
  trial_ends_at: <14 days>

BillingPeriod #1:
  status: TRIAL
  plan: DEVELOPER
  created_from: INITIAL_SIGNUP
```

#### 2. Upgrade (Developer → Startup, Immediate)

```
BillingPeriod #1: status → COMPLETED
BillingPeriod #2:
  status: ACTIVE
  plan: STARTUP
  created_from: UPGRADE
```

#### 3. Downgrade (Startup → Developer, End of Period)

```
OrganizationBilling:
  billing_plan: STARTUP (unchanged)
  pending_plan_change: DEVELOPER

# At renewal:
BillingPeriod #2:
  plan: DEVELOPER
  created_from: DOWNGRADE
```

#### 4. Cancellation

```
OrganizationBilling:
  cancel_at_period_end: true

# Current period remains ACTIVE
# No new period created after cancellation
```

### Detailed Transition Event Flows

#### Transition 1: Nothing → Subscribed (Initial Signup)

**Trigger**: User completes Stripe Checkout
**API Flow**:
1. `POST /billing/checkout-session` creates Stripe checkout
2. User redirected to Stripe
3. User completes payment

**Webhook Events & State Changes**:

```python
# Event 1: checkout.session.completed
# - Payment method collected but subscription not yet created
# - No state change yet

# Event 2: customer.subscription.created
async def handle_subscription_created(subscription):
    # 1. Create first billing period
    period = await create_billing_period(
        organization_id=subscription.metadata.organization_id,
        period_start=subscription.current_period_start,
        period_end=subscription.current_period_end,
        plan=subscription.metadata.plan,
        status=BillingPeriodStatus.TRIAL if subscription.trial_end else BillingPeriodStatus.ACTIVE,
        transition=BillingTransition.INITIAL_SIGNUP,
        stripe_subscription_id=subscription.id
    )

    # 2. Create usage record for this period
    await crud.usage.create(
        billing_period_id=period.id,
        # All counters start at 0
    )

    # 3. Update OrganizationBilling
    await crud.organization_billing.update(
        stripe_subscription_id=subscription.id,
        billing_plan=plan,
        billing_status=BillingStatus.TRIALING if subscription.trial_end else BillingStatus.ACTIVE,
        current_period_start=subscription.current_period_start,
        current_period_end=subscription.current_period_end,
        trial_ends_at=subscription.trial_end
    )

# Event 3: invoice.payment_succeeded (if not trial)
async def handle_payment_succeeded(invoice):
    # Mark the period as paid
    period = await get_period_by_stripe_invoice(invoice.id)
    if period:
        period.paid_at = now()
        period.amount_cents = invoice.amount_paid
```

#### Transition 2: Upgrade (Immediate Effect)

**Trigger**: User upgrades plan (Developer → Startup)
**API Flow**:
1. `POST /billing/update-plan` with new plan

**State Changes & Events**:

```python
# API Handler
async def update_plan(new_plan):
    if is_upgrade(current_plan, new_plan):
        # For upgrades, Stripe changes immediately with proration
        subscription = await stripe.update_subscription(
            items=[{"price": new_price_id}],
            proration_behavior="create_prorations"
        )
        # Stripe will send webhook events

# Event 1: customer.subscription.updated
async def handle_subscription_updated(subscription, previous_attributes):
    if "items" in previous_attributes:  # Plan changed
        current_period = await get_current_billing_period(org_id)

        # 1. End current period
        current_period.status = BillingPeriodStatus.COMPLETED
        current_period.period_end = now()  # Truncate to now

        # 2. Create new period for upgraded plan
        new_period = await create_billing_period(
            organization_id=org_id,
            period_start=now(),
            period_end=subscription.current_period_end,  # Prorated end
            plan=new_plan,
            status=BillingPeriodStatus.ACTIVE,
            transition=BillingTransition.UPGRADE,
            previous_period_id=current_period.id
        )

        # 3. Create fresh usage for new period
        await crud.usage.create(billing_period_id=new_period.id)

        # 4. Update OrganizationBilling
        await crud.organization_billing.update(
            billing_plan=new_plan,
            current_period_start=now(),
            current_period_end=subscription.current_period_end
        )

# Event 2: invoice.created (for proration)
# Event 3: invoice.payment_succeeded
async def handle_payment_succeeded(invoice):
    # Update the new period with payment info
    period.paid_at = now()
    period.stripe_invoice_id = invoice.id
```

#### Transition 3: Downgrade (End of Period)

**Trigger**: User downgrades plan (Startup → Developer)
**API Flow**:
1. `POST /billing/update-plan` with new plan

**State Changes & Events**:

```python
# API Handler
async def update_plan(new_plan):
    if is_downgrade(current_plan, new_plan):
        # Schedule change for end of period
        subscription = await stripe.update_subscription(
            items=[{"price": new_price_id}],
            proration_behavior="none",  # No immediate change
            # The new price takes effect at next renewal
        )

        # Store pending change locally
        await crud.organization_billing.update(
            pending_plan_change=new_plan
        )

# Event 1: customer.subscription.updated (schedule confirmed)
# - No immediate period change
# - OrganizationBilling tracks pending_plan_change

# Event 2: invoice.payment_succeeded (at period end)
# Event 3: customer.subscription.updated (at renewal)
async def handle_subscription_updated(subscription, previous_attributes):
    if "current_period_end" in previous_attributes:  # Renewal occurred
        org_billing = await get_org_billing(subscription.customer)

        # 1. Complete current period
        current_period = await get_current_billing_period(org_id)
        current_period.status = BillingPeriodStatus.COMPLETED

        # 2. Create new period with downgraded plan
        effective_plan = org_billing.pending_plan_change or org_billing.billing_plan
        new_period = await create_billing_period(
            organization_id=org_id,
            period_start=subscription.current_period_start,
            period_end=subscription.current_period_end,
            plan=effective_plan,
            status=BillingPeriodStatus.ACTIVE,
            transition=BillingTransition.DOWNGRADE if org_billing.pending_plan_change else BillingTransition.RENEWAL,
            previous_period_id=current_period.id
        )

        # 3. Clear pending change
        await crud.organization_billing.update(
            billing_plan=effective_plan,
            pending_plan_change=None,
            current_period_start=subscription.current_period_start,
            current_period_end=subscription.current_period_end
        )
```

#### Transition 4: Cancel (End of Period)

**Trigger**: User cancels subscription
**API Flow**:
1. `POST /billing/cancel`

**State Changes & Events**:

```python
# API Handler
async def cancel_subscription():
    # Cancel at period end
    subscription = await stripe.update_subscription(
        cancel_at_period_end=True
    )

    await crud.organization_billing.update(
        cancel_at_period_end=True
    )

# Event 1: customer.subscription.updated
# - Sets cancel_at_period_end = true
# - Current period remains ACTIVE

# Event 2: customer.subscription.deleted (at period end)
async def handle_subscription_deleted(subscription):
    if not subscription.cancel_at_period_end:
        # Immediate cancellation (shouldn't happen in our flow)
        return

    # 1. Complete final period
    current_period = await get_current_billing_period(org_id)
    current_period.status = BillingPeriodStatus.COMPLETED

    # 2. Update OrganizationBilling
    await crud.organization_billing.update(
        billing_status=BillingStatus.CANCELED,
        stripe_subscription_id=None,  # Clear subscription
        cancel_at_period_end=False
    )

    # 3. No new period created - subscription ended
```

### Edge Cases & Error Handling

#### Failed Payments During Renewal

```python
# Event: invoice.payment_failed
async def handle_payment_failed(invoice):
    if invoice.billing_reason == "subscription_cycle":  # Renewal payment
        # 1. Current period ends but unpaid
        current_period = await get_current_billing_period(org_id)
        current_period.status = BillingPeriodStatus.ENDED_UNPAID

        # 2. Create grace period
        grace_period = await create_billing_period(
            organization_id=org_id,
            period_start=current_period.period_end,
            period_end=current_period.period_end + timedelta(days=7),  # Grace duration
            plan=current_plan,
            status=BillingPeriodStatus.GRACE,
            transition=BillingTransition.RENEWAL,  # Failed renewal
            previous_period_id=current_period.id
        )

        # 3. Update billing status
        await crud.organization_billing.update(
            billing_status=BillingStatus.PAST_DUE,
            grace_period_ends_at=grace_period.period_end
        )
```

#### Trial Conversion

```python
# Event: customer.subscription.updated (trial_end removed)
async def handle_trial_conversion(subscription):
    # 1. End trial period
    trial_period = await get_current_billing_period(org_id)
    trial_period.status = BillingPeriodStatus.COMPLETED

    # 2. Create paid period
    paid_period = await create_billing_period(
        plan=subscription.plan,
        status=BillingPeriodStatus.ACTIVE,
        transition=BillingTransition.TRIAL_CONVERSION
    )
```

### Key Implementation Rules

1. **Period Continuity**: New period's `period_start` must equal previous period's `period_end`
2. **Single Active Period**: Only one period can have status ACTIVE/TRIAL/GRACE per organization
3. **Atomic Transitions**: Period creation and previous period completion must be atomic
4. **Webhook Idempotency**: Use Stripe event IDs to prevent duplicate processing
5. **State Reconciliation**: Always trust Stripe as source of truth, update local state to match

### Webhook Event Summary

| Stripe Event | Trigger | Our Actions |
|-------------|---------|-------------|
| `checkout.session.completed` | User completes checkout | Wait for subscription creation |
| `customer.subscription.created` | New subscription created | Create first BillingPeriod + Usage |
| `customer.subscription.updated` | Plan change, renewal, or cancellation scheduled | Handle based on what changed |
| `customer.subscription.deleted` | Subscription ends | Complete final period, no new period |
| `invoice.payment_succeeded` | Payment collected | Update period payment info |
| `invoice.payment_failed` | Payment fails | Create grace period if renewal |
| `invoice.created` | Upcoming payment | No action (informational) |

### Webhook Decision Tree

```python
async def handle_subscription_updated(subscription, previous_attributes):
    # Decision tree for subscription.updated events

    if "items" in previous_attributes:
        # Plan changed
        if is_immediate_change():
            # Upgrade: Close current period, create new one
            await handle_immediate_plan_change()
        else:
            # Downgrade: Just record pending change
            await record_pending_plan_change()

    elif "current_period_end" in previous_attributes:
        # Renewal occurred
        await handle_period_renewal()

    elif "cancel_at_period_end" in previous_attributes:
        # Cancellation scheduled or unscheduled
        await update_cancellation_status()

    elif "trial_end" in previous_attributes:
        # Trial ended or extended
        await handle_trial_change()
```

### Integration Points

#### Guard Rail Service

```python
class GuardRailService:
    async def _get_current_usage(self) -> Usage:
        """Gets usage for current billing period."""
        current_period = await billing_service.get_current_billing_period(
            self.db,
            self.organization_id
        )
        if not current_period:
            raise NoBillingPeriodError()

        return await crud.usage.get_by_billing_period(
            self.db,
            billing_period_id=current_period.id
        )
```

#### Webhook Handler

The webhook handler ensures period continuity by detecting period renewals and creating new periods atomically.

### Benefits

1. **Clear State Tracking**: Each period has explicit status and transition type
2. **Accurate Usage Attribution**: Usage is clearly tied to specific billing periods
3. **Audit Trail**: Complete history of billing transitions
4. **Grace Period Support**: Grace periods are first-class period statuses
5. **Stripe Alignment**: Model matches Stripe's subscription lifecycle

### Migration Strategy

#### Phase 1: Add New Models
- Create `billing_period` table
- Add `billing_period_id` to `usage` table (nullable initially)
- Deploy without breaking existing functionality

#### Phase 2: Backfill Historical Data
- Create billing periods from existing subscription data
- Link existing usage records to appropriate periods
- Validate data integrity

#### Phase 3: Update Services
- Update `BillingService` to create periods
- Update `GuardRailService` to use periods
- Update webhook handlers

#### Phase 4: Cleanup
- Remove `start_period` and `end_period` from usage
- Make `billing_period_id` non-nullable
- Remove deprecated code

### Open Questions

1. **Grace Period Duration**: How long should grace periods last? Should this be configurable per plan?

2. **Period Overlap**: How do we handle prorated periods during upgrades? Should we allow overlapping periods?

3. **Historical Data**: How far back should we backfill billing periods? Only active subscriptions or all historical data?

4. **Timezone Handling**: All period boundaries use UTC. Should we store timezone information for reporting?

### Next Steps

1. Review and approve design
2. Create database migrations
3. Implement model changes
4. Update service layer
5. Test with production-like data
6. Deploy in phases
