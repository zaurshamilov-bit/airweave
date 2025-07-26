"""CRUD operations for Usage model."""

from typing import Dict, Optional
from uuid import UUID

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from airweave.core.shared_models import ActionType
from airweave.crud._base_organization import CRUDBaseOrganization
from airweave.models.usage import Usage
from airweave.schemas.usage import UsageCreate, UsageUpdate


class CRUDUsage(CRUDBaseOrganization[Usage, UsageCreate, UsageUpdate]):
    """CRUD operations for Usage model."""

    async def get_by_billing_period(
        self,
        db: AsyncSession,
        *,
        billing_period_id: UUID,
    ) -> Optional[Usage]:
        """Get usage record by billing period ID.

        Args:
            db: Database session
            billing_period_id: Billing period ID

        Returns:
            Usage record for the billing period or None
        """
        query = select(self.model).where(self.model.billing_period_id == billing_period_id)
        result = await db.execute(query)
        return result.scalar_one_or_none()

    async def get_current_usage(
        self,
        db: AsyncSession,
        *,
        organization_id: UUID,
    ) -> Optional[Usage]:
        """Get usage for the current active billing period.

        Args:
            db: Database session
            organization_id: Organization ID

        Returns:
            Current usage record or None if no active period
        """
        from airweave import crud

        # Get current billing period
        current_period = await crud.billing_period.get_current_period(
            db, organization_id=organization_id
        )

        if not current_period:
            return None

        # Get usage for this period
        return await self.get_by_billing_period(db, billing_period_id=current_period.id)

    async def increment_usage(
        self,
        db: AsyncSession,
        *,
        organization_id: UUID,
        increments: Dict[ActionType, int],
    ) -> Optional[Usage]:
        """Atomically increment usage counters for the current billing period.

        This method uses raw SQL to ensure atomic updates that add to existing
        values rather than overwriting them, which is crucial for concurrent access.

        Args:
            db: Database session
            organization_id: The organization ID to increment usage for
            increments: Dictionary mapping ActionType to increment amount

        Returns:
            The updated usage record after increment, or None if no active period
        """
        # Get current usage record
        current_usage = await self.get_current_usage(db, organization_id=organization_id)
        if not current_usage:
            return None

        # Build the atomic UPDATE query
        update_parts = []
        params = {"usage_id": current_usage.id}

        for action_type, increment in increments.items():
            if increment > 0:
                field = action_type.value
                update_parts.append(f"{field} = {field} + :{field}_inc")
                params[f"{field}_inc"] = increment

        if update_parts:
            # Execute atomic update
            query = text(
                f"""
                UPDATE usage
                SET {", ".join(update_parts)},
                    modified_at = NOW()
                WHERE id = :usage_id
            """
            )

            await db.execute(query, params)

            # Commit the transaction
            await db.commit()

            # Fetch and return the updated record
            return await self.get(db, id=current_usage.id)

        return current_usage


# Create instance
usage = CRUDUsage(Usage, track_user=False)
