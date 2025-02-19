"""rename chunk to entity

Revision ID: 0cf098b4c987
Revises: 3a3c65856c56
Create Date: 2025-02-19 11:00:39.036935

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "0cf098b4c987"
down_revision = "3a3c65856c56"
branch_labels = None
depends_on = None


def upgrade():
    # Rename the table
    op.rename_table("chunk", "entity")

    # Rename foreign key constraints
    op.execute("ALTER TABLE entity RENAME CONSTRAINT fk_chunk_sync_job_id TO fk_entity_sync_job_id")
    op.execute("ALTER TABLE entity RENAME CONSTRAINT fk_chunk_sync_id TO fk_entity_sync_id")

    # Rename unique constraint
    op.execute("ALTER TABLE entity RENAME CONSTRAINT uq_sync_id_chunk_id TO uq_sync_id_entity_id")


def downgrade():
    # Rename foreign key constraints back
    op.execute("ALTER TABLE entity RENAME CONSTRAINT fk_entity_sync_job_id TO fk_chunk_sync_job_id")
    op.execute("ALTER TABLE entity RENAME CONSTRAINT fk_entity_sync_id TO fk_chunk_sync_id")

    # Rename unique constraint back
    op.execute("ALTER TABLE entity RENAME CONSTRAINT uq_sync_id_entity_id TO uq_sync_id_chunk_id")

    # Rename the table back
    op.rename_table("entity", "chunk")
