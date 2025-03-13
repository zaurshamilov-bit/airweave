"""Rename schema column

Revision ID: 456789abcdef
Revises:
Create Date: 2025-03-13 13:00:00.000000

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "456789abcdef"
down_revision = None  # Update this to point to your last migration
branch_labels = None
depends_on = None


def upgrade():
    # Rename column schema to entity_schema in entity_definition table
    op.alter_column("entity_definition", "schema", new_column_name="entity_schema")


def downgrade():
    # Rename column entity_schema back to schema in entity_definition table
    op.alter_column("entity_definition", "entity_schema", new_column_name="schema")
