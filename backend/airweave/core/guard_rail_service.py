"""Guard rail service."""

from datetime import datetime, timedelta
from typing import Optional
from uuid import UUID

from airweave import crud
from airweave.core.exceptions import PaymentRequiredException, UsageLimitExceededException
from airweave.core.shared_models import ActionType, PaymentStatus, SubscriptionType
from airweave.db.session import get_db_context
from airweave.schemas.usage import Usage, UsageLimit

# NOTE: usage is always got from the database and we never directly update the usage in memory


class GuardRailService:
    """Guard rail service."""

    # Per-action-type flush thresholds
    FLUSH_THRESHOLDS = {
        ActionType.SYNCS: 1,
        ActionType.ENTITIES: 100,
        ActionType.QUERIES: 10,
        ActionType.COLLECTIONS: 1,
        ActionType.SOURCE_CONNECTIONS: 1,
    }

    # Cache TTL - refresh usage data after this duration
    USAGE_CACHE_TTL = timedelta(seconds=30)  # Refresh every 30 seconds

    # Payment status restrictions - which actions are blocked for each payment status
    PAYMENT_STATUS_RESTRICTIONS = {
        PaymentStatus.CURRENT: set(),  # No restrictions
        PaymentStatus.PAID: set(),  # No restrictions (recently paid)
        PaymentStatus.GRACE_PERIOD: {
            # During grace period, block resource creation but allow queries
            ActionType.COLLECTIONS,
            ActionType.SOURCE_CONNECTIONS,
        },
        PaymentStatus.LATE: {
            # When late, only allow queries - block all resource creation/modification
            ActionType.SYNCS,
            ActionType.ENTITIES,
            ActionType.COLLECTIONS,
            ActionType.SOURCE_CONNECTIONS,
        },
    }

    def __init__(self, organization_id: UUID):
        """Initialize the guard rail service.

        Args:
            organization_id: The organization ID to get usage for
        """
        self.organization_id = organization_id
        self.usage: Optional[Usage] = None
        self.usage_limit: Optional[UsageLimit] = None
        self.usage_fetched_at: Optional[datetime] = None
        # Track pending increments in memory
        self.pending_increments = {
            ActionType.SYNCS: 0,
            ActionType.ENTITIES: 0,
            ActionType.QUERIES: 0,
            ActionType.COLLECTIONS: 0,
            ActionType.SOURCE_CONNECTIONS: 0,
        }

    async def is_allowed(self, action_type: ActionType) -> bool:
        """Check if the action is allowed.

        Args:
            action_type: The type of action to check

        Returns:
            True if the action is allowed

        Raises:
            PaymentRequiredException: If action is blocked due to payment status
            UsageLimitExceededException: If action would exceed usage limits
        """
        # First check payment status
        payment_status = await self._get_payment_status()
        restricted_actions = self.PAYMENT_STATUS_RESTRICTIONS.get(payment_status, set())

        # If action is restricted due to payment status, raise exception
        if action_type in restricted_actions:
            raise PaymentRequiredException(
                action_type=action_type.value,
                payment_status=payment_status.value,
            )

        # Check if we need to refresh usage (TTL expired or never fetched)
        should_refresh = (
            self.usage is None
            or self.usage_fetched_at is None
            or datetime.utcnow() - self.usage_fetched_at > self.USAGE_CACHE_TTL
        )

        if should_refresh:
            self.usage = await self._get_usage()
            self.usage_fetched_at = datetime.utcnow()

        # Lazy load usage limit if not already loaded
        if self.usage_limit is None:
            self.usage_limit = await self._infer_usage_limit()

        # Get current value from usage plus pending increments
        current_value = getattr(self.usage, action_type.value, 0) if self.usage else 0
        pending = self.pending_increments.get(action_type, 0)
        total_usage = current_value + pending

        # Get the limit for this action type
        limit = getattr(self.usage_limit, action_type.value, None) if self.usage_limit else None

        # If no limit (None), it's unlimited - always allowed
        if limit is None:
            return True

        # Check if we're under the limit
        if total_usage >= limit:
            raise UsageLimitExceededException(
                action_type=action_type.value,
                limit=limit,
                current_usage=total_usage,
            )

        return True

    async def increment(self, action_type: ActionType, amount: int = 1) -> None:
        """Increment the usage for the action.

        Args:
            action_type: The type of action to increment
            amount: The amount to increment by (default 1)
        """
        # Add to pending increments
        self.pending_increments[action_type] = self.pending_increments.get(action_type, 0) + amount

        # Check if this specific action type should flush
        threshold = self.FLUSH_THRESHOLDS.get(action_type, 1)
        if self.pending_increments[action_type] >= threshold:
            await self._flush_usage(action_type)

    async def _flush_usage(self, action_type: Optional[ActionType] = None) -> None:
        """Flush pending increments to the database using atomic operations.

        Args:
            action_type: If specified, only flush this action type. Otherwise flush all.
        """
        # Determine what to flush
        if action_type is not None:
            # Flush specific action type if it has pending increments
            if self.pending_increments.get(action_type, 0) == 0:
                return
            increments_to_flush = {action_type: self.pending_increments[action_type]}
        else:
            # Flush all non-zero increments
            increments_to_flush = {
                action_type: count
                for action_type, count in self.pending_increments.items()
                if count > 0
            }

        if increments_to_flush:
            async with get_db_context() as db:
                await crud.usage.increment_usage(
                    db, organization_id=self.organization_id, increments=increments_to_flush
                )
                await db.commit()

                # Clear flushed increments
                for action_type in increments_to_flush:
                    self.pending_increments[action_type] = 0

                # Force immediate refresh on next is_allowed call
                self.usage_fetched_at = None

    async def _get_usage(self) -> Optional[Usage]:
        """Get usage from the database using crud_usage.

        Returns:
            The most recent usage record for the organization, or None if not found
        """
        async with get_db_context() as db:
            usage_record = await crud.usage.get_most_recent_by_organization_id(
                db, organization_id=self.organization_id
            )
            if usage_record:
                # Convert SQLAlchemy model to Pydantic schema
                return Usage.model_validate(usage_record)
            return None

    async def _get_payment_status(self) -> PaymentStatus:
        """Get payment status using the stripe service.

        Returns:
            PaymentStatus based on Stripe subscription/payment data
        """
        # TODO: Replace with actual Stripe service integration
        # Mock implementation - return a mocked payment status
        # In real implementation:
        # async with AsyncSessionLocal() as db:
        #     billing_record = await crud.billing.get_by_organization_id(
        #         db, organization_id=self.organization_id
        #     )
        #     stripe_subscription = await stripe_service.get_subscription(
        #         billing_record.stripe_subscription_id
        #     )
        #     return stripe_service.get_payment_status(stripe_subscription)

        # For now, return mock status
        return PaymentStatus.CURRENT

    async def _infer_usage_limit(self) -> UsageLimit:
        """Infer usage limit based on billing table in db.

        Returns:
            UsageLimit based on organization's subscription tier
        """
        # TODO: Replace with actual database query when billing table exists
        # Mock implementation - fetch subscription type from billing table
        # For now, we'll simulate getting a subscription type

        # In real implementation:
        # async with AsyncSessionLocal() as db:
        #     billing_record = await crud.billing.get_by_organization_id(
        #         db, organization_id=self.organization_id
        #     )
        #     subscription_type = billing_record.subscription_type

        # Mock subscription type for now
        subscription_type = SubscriptionType.PRO  # This would come from the billing table

        # Define limits based on subscription tier
        if subscription_type == SubscriptionType.FREE:
            return UsageLimit(
                max_syncs=6,
                max_entities=1000,
                max_queries=100,
                max_collections=1,
                max_source_connections=3,
            )
        elif subscription_type == SubscriptionType.BASIC:
            return UsageLimit(
                max_syncs=10,
                max_entities=10000,
                max_queries=1000,
                max_collections=5,
                max_source_connections=5,
            )
        elif subscription_type == SubscriptionType.PRO:
            return UsageLimit(
                max_syncs=50,
                max_entities=100000,
                max_queries=10000,
                max_collections=20,
                max_source_connections=25,
            )
        elif subscription_type == SubscriptionType.TEAM:
            return UsageLimit(
                max_syncs=200,
                max_entities=1000000,
                max_queries=50000,
                max_collections=100,
                max_source_connections=100,
            )
        else:
            # Enterprise - return unlimited
            return UsageLimit(
                max_syncs=None,  # Unlimited
                max_entities=None,
                max_queries=None,
                max_collections=None,
                max_source_connections=None,
            )
