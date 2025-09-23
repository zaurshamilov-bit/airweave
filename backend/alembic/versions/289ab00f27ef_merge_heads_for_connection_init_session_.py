"""merge heads for connection init session and usage table changes

Revision ID: 289ab00f27ef
Revises: 4ee815df1fed, remove_syncs_collections
Create Date: 2025-09-23 17:28:40.897674

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '289ab00f27ef'
down_revision = ('4ee815df1fed', 'remove_syncs_collections')
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
