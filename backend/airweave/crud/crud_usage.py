"""CRUD operations for Usage model."""

from typing import Dict, Optional
from uuid import UUID

from sqlalchemy import desc, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from airweave.core.shared_models import ActionType
from airweave.crud._base_organization import CRUDBaseOrganization
from airweave.models.usage import Usage
from airweave.schemas.usage import UsageCreate, UsageUpdate


class CRUDUsage(CRUDBaseOrganization[Usage, UsageCreate, UsageUpdate]):
    """CRUD operations for Usage model."""

    async def get_most_recent_by_organization_id(
        self,
        db: AsyncSession,
        *,
        organization_id: UUID,
    ) -> Optional[Usage]:
        """Get the most recent usage record by organization ID.

        Args:
        ----
            db: Database session
            organization_id: The organization ID to get usage for

        Returns:
        -------
            Optional[Usage]: The most recent usage record for the organization based on end_period,
            or None if not found
        """
        query = (
            select(self.model)
            .where(self.model.organization_id == organization_id)
            .order_by(desc(self.model.end_period))
            .limit(1)
        )
        result = await db.execute(query)
        return result.unique().scalar_one_or_none()

    async def increment_usage(
        self,
        db: AsyncSession,
        *,
        organization_id: UUID,
        increments: Dict[ActionType, int],
    ) -> None:
        """Atomically increment usage counters for the most recent period.

        This method uses raw SQL to ensure atomic updates that add to existing
        values rather than overwriting them, which is crucial for concurrent access.

        Args:
        ----
            db: Database session
            organization_id: The organization ID to increment usage for
            increments: Dictionary mapping ActionType to increment amount
        """
        # Build the atomic UPDATE query
        update_parts = []
        params = {"org_id": organization_id}

        for action_type, increment in increments.items():
            if increment > 0:
                field = action_type.value
                update_parts.append(f"{field} = {field} + :{field}_inc")
                params[f"{field}_inc"] = increment

        if update_parts:
            # Execute atomic update on the most recent usage record
            query = text(f"""
                UPDATE usage
                SET {", ".join(update_parts)},
                    modified_at = NOW()
                WHERE organization_id = :org_id
                AND end_period = (
                    SELECT MAX(end_period)
                    FROM usage
                    WHERE organization_id = :org_id
                )
            """)

            await db.execute(query, params)
            # Note: Commit should be handled by the caller/UnitOfWork


# Create singleton instance with track_user=False since Usage doesn't have UserMixin
usage = CRUDUsage(Usage, track_user=False)
