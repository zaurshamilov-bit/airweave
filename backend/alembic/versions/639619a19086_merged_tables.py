"""merged tables

Revision ID: 639619a19086
Revises: 2f1e0b5013e8
Create Date: 2025-09-02 03:07:33.378609
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "639619a19086"
down_revision = "2f1e0b5013e8"
branch_labels = None
depends_on = None


def upgrade():
    # --- ONLY: source_connection + connection_init_session ---

    # Add new columns to source_connection
    op.add_column(
        "source_connection",
        sa.Column(
            "is_authenticated",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )
    op.add_column("source_connection", sa.Column("oauth_state", sa.String(), nullable=True))
    op.add_column(
        "source_connection",
        sa.Column("oauth_expires_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column("source_connection", sa.Column("oauth_redirect_uri", sa.Text(), nullable=True))
    op.add_column("source_connection", sa.Column("final_redirect_url", sa.Text(), nullable=True))
    op.add_column("source_connection", sa.Column("temp_client_id", sa.String(), nullable=True))
    op.add_column(
        "source_connection", sa.Column("temp_client_secret_enc", sa.Text(), nullable=True)
    )
    op.add_column(
        "source_connection",
        sa.Column(
            "pending_sync_immediately",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
    )
    op.add_column(
        "source_connection", sa.Column("pending_cron_schedule", sa.String(), nullable=True)
    )

    # Unique index for oauth_state (NULLs allowed)
    op.create_index(
        "ix_source_connection_oauth_state",
        "source_connection",
        ["oauth_state"],
        unique=True,
    )

    # Drop legacy init-session table (indexes drop with the table)
    op.drop_table("connection_init_session")

    # Drop server defaults now that existing rows are populated
    op.alter_column("source_connection", "is_authenticated", server_default=None)
    op.alter_column("source_connection", "pending_sync_immediately", server_default=None)


def downgrade():
    # Reverse source_connection changes
    op.drop_index("ix_source_connection_oauth_state", table_name="source_connection")
    op.drop_column("source_connection", "pending_cron_schedule")
    op.drop_column("source_connection", "pending_sync_immediately")
    op.drop_column("source_connection", "temp_client_secret_enc")
    op.drop_column("source_connection", "temp_client_id")
    op.drop_column("source_connection", "final_redirect_url")
    op.drop_column("source_connection", "oauth_redirect_uri")
    op.drop_column("source_connection", "oauth_expires_at")
    op.drop_column("source_connection", "oauth_state")
    op.drop_column("source_connection", "is_authenticated")

    # Recreate connection_init_session exactly as before
    op.create_table(
        "connection_init_session",
        sa.Column("short_name", sa.VARCHAR(), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("overrides", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("state", sa.VARCHAR(), nullable=False),
        sa.Column(
            "status",
            sa.VARCHAR(),
            server_default=sa.text("'pending'::character varying"),
            nullable=False,
        ),
        sa.Column("expires_at", postgresql.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("final_connection_id", sa.UUID(), nullable=True),
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column(
            "created_at",
            postgresql.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "modified_at",
            postgresql.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["final_connection_id"],
            ["connection.id"],
            name="connection_init_session_final_connection_id_fkey",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organization.id"],
            name="connection_init_session_organization_id_fkey",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="connection_init_session_pkey"),
    )
    op.create_index(
        "ix_connection_init_session_state", "connection_init_session", ["state"], unique=True
    )
    op.create_index(
        "ix_connection_init_session_organization_id",
        "connection_init_session",
        ["organization_id"],
    )
    op.create_index(
        "ix_connection_init_session_expires_at",
        "connection_init_session",
        ["expires_at"],
    )
