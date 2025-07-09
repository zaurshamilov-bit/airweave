"""add description and config to connection

Revision ID: 288623eaf91f
Revises: a1b2c3d4e5f6
Create Date: 2024-12-20 17:14:25.754432

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '288623eaf91f'
down_revision: Union[str, None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add description column to connection table
    op.add_column('connection', sa.Column('description', sa.Text(), nullable=True))

    # Add config_fields column to connection table
    op.add_column('connection', sa.Column('config_fields', sa.JSON(), nullable=True))


def downgrade() -> None:
    # Remove config_fields column from connection table
    op.drop_column('connection', 'config_fields')

    # Remove description column from connection table
    op.drop_column('connection', 'description')
