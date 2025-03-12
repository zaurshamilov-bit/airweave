"""add_next_scheduled_run_to_sync

Revision ID: 2a6c65061d05
Revises: 86c0732b1e07
Create Date: 2025-03-12 15:58:59.442253

"""

from datetime import datetime, timezone
from typing import List, Tuple

from alembic import op
import sqlalchemy as sa
from sqlalchemy import Column, String, text
from sqlalchemy.dialects.postgresql import UUID, TIMESTAMP
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import Session

# Try to import croniter, but don't fail if it's not available
try:
    from croniter import croniter

    HAS_CRONITER = True
except ImportError:
    HAS_CRONITER = False


# revision identifiers, used by Alembic.
revision = "2a6c65061d05"
down_revision = "86c0732b1e07"
branch_labels = None
depends_on = None


def upgrade():
    # Add next_scheduled_run column to sync table
    op.add_column(
        "sync", sa.Column("next_scheduled_run", sa.DateTime(timezone=True), nullable=True)
    )

    # Populate the next_scheduled_run field for existing syncs with cron schedules
    if HAS_CRONITER:
        # Create a temporary table model
        Base = declarative_base()

        class Sync(Base):
            __tablename__ = "sync"
            id = Column(UUID(as_uuid=True), primary_key=True)
            cron_schedule = Column(String(100))
            next_scheduled_run = Column(TIMESTAMP(timezone=True))

        # Get all syncs with cron schedules and calculate their next run time
        bind = op.get_bind()
        session = Session(bind=bind)

        try:
            # Get all syncs with cron schedules
            syncs_with_schedule = session.query(Sync).filter(Sync.cron_schedule.isnot(None)).all()

            # Calculate and update next_scheduled_run for each sync
            now = datetime.now(timezone.utc)
            updates = []

            for sync in syncs_with_schedule:
                try:
                    # Calculate next run time from now
                    cron = croniter(sync.cron_schedule, now)
                    next_run = cron.get_next(datetime)

                    # Add to updates list
                    sync.next_scheduled_run = next_run
                    updates.append(sync)
                except Exception as e:
                    print(f"Error calculating next run for sync {sync.id}: {e}")

            # Commit all updates
            if updates:
                session.bulk_save_objects(updates)
                session.commit()
                print(f"Updated next_scheduled_run for {len(updates)} syncs")
        except Exception as e:
            print(f"Error updating next_scheduled_run values: {e}")
            session.rollback()
        finally:
            session.close()
    else:
        print("croniter not available, skipping population of next_scheduled_run values")


def downgrade():
    # Remove next_scheduled_run column from sync table
    op.drop_column("sync", "next_scheduled_run")
