# backend/airweave/models/source_connection.py

"""Source connection model."""

from datetime import datetime
from time import sleep
from typing import TYPE_CHECKING, ClassVar, Optional
from uuid import UUID

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, String, Text, event
from sqlalchemy.orm import Mapped, Session, mapped_column, relationship

from airweave.core.shared_models import SourceConnectionStatus, SyncJobStatus
from airweave.models._base import OrganizationBase, UserMixin

if TYPE_CHECKING:
    from airweave.models.collection import Collection
    from airweave.models.connection import Connection
    from airweave.models.sync import Sync
    from airweave.models.white_label import WhiteLabel


class SourceConnection(OrganizationBase, UserMixin):
    """Source connection model for connecting to external data sources.

    This is a user-facing model that encompasses the connection and sync information for a
    specific source. Not to be confused with the connection model, which is a system table
    that contains the connection information for all integrations.
    """

    __tablename__ = "source_connection"
    # allow unmapped (non-Mapped[] / ClassVar) attributes without SQLAlchemy trying to map them
    __allow_unmapped__ = True

    name: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    short_name: Mapped[str] = mapped_column(String, nullable=False)  # Source short name

    # Configuration fields for the source connection
    config_fields: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    # Auth provider tracking fields
    readable_auth_provider_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey("connection.readable_id", ondelete="CASCADE"), nullable=True
    )
    auth_provider_config: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    # Related objects
    sync_id: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("sync.id", ondelete="CASCADE"), nullable=True
    )
    readable_collection_id: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("collection.readable_id", ondelete="CASCADE"), nullable=True
    )
    connection_id: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("connection.id", ondelete="CASCADE"), nullable=True
    )
    white_label_id: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("white_label.id", ondelete="SET NULL"), nullable=True
    )
    # Status is now ephemeral - removed from database model

    # --- authentication + OAuth persisted columns for the flow ---
    is_authenticated: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # Stored only for OAuth2 browser flows (never returned to clients)
    oauth_state: Mapped[Optional[str]] = mapped_column(
        String, unique=True, index=True, nullable=True
    )
    oauth_expires_at: Mapped[Optional["datetime"]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    oauth_redirect_uri: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    final_redirect_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # BYOC overrides (temp) — temp_client_secret_enc should be encrypted at rest
    temp_client_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    temp_client_secret_enc: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Desired sync settings captured at initiate-time (used after callback)
    pending_sync_immediately: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    pending_cron_schedule: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    # Relationships
    sync: Mapped[Optional["Sync"]] = relationship(
        "Sync",
        back_populates="source_connection",
        lazy="noload",
    )
    collection: Mapped[Optional["Collection"]] = relationship(
        "Collection",
        foreign_keys=[readable_collection_id],
        lazy="noload",
    )
    connection: Mapped[Optional["Connection"]] = relationship(
        "Connection",
        foreign_keys=[connection_id],
        back_populates="source_connection",
        lazy="noload",
        cascade="all, delete-orphan",
        single_parent=True,
    )
    white_label: Mapped[Optional["WhiteLabel"]] = relationship(
        "WhiteLabel",
        back_populates="source_connections",
        lazy="noload",
    )

    # Relationship to the auth provider connection
    auth_provider_connection: Mapped[Optional["Connection"]] = relationship(
        "Connection",
        foreign_keys=[readable_auth_provider_id],
        primaryjoin="SourceConnection.readable_auth_provider_id==Connection.readable_id",
        viewonly=True,
        lazy="noload",
    )

    # ---------------------------------------------------------------------
    # Ephemeral runtime-only backing fields (NOT DB columns)
    # Using ClassVar here prevents SQLAlchemy from trying to map them.
    # They are defaults; when you set them on an instance, Python creates
    # an instance attribute that shadows the class attribute.
    # ---------------------------------------------------------------------
    _status_ephemeral: ClassVar[Optional[SourceConnectionStatus]] = None
    _latest_sync_job_status_ephemeral: ClassVar[Optional[SyncJobStatus]] = None
    _latest_sync_job_id_ephemeral: ClassVar[Optional[UUID]] = None
    _latest_sync_job_started_at_ephemeral: ClassVar[Optional[datetime]] = None
    _latest_sync_job_completed_at_ephemeral: ClassVar[Optional[datetime]] = None
    _latest_sync_job_error_ephemeral: ClassVar[Optional[str]] = None
    _cron_schedule_ephemeral: ClassVar[Optional[str]] = None
    _next_scheduled_run_ephemeral: ClassVar[Optional[datetime]] = None
    _auth_url_ephemeral: ClassVar[Optional[str]] = None  # convenience for API layer if used

    # Properties to access the ephemeral fields safely
    @property
    def status(self) -> SourceConnectionStatus:
        """Ephemeral status; defaults to ACTIVE if not explicitly set."""
        return getattr(self, "_status_ephemeral", None) or SourceConnectionStatus.ACTIVE

    @status.setter
    def status(self, value: Optional[SourceConnectionStatus]) -> None:
        self._status_ephemeral = value

    @property
    def latest_sync_job_status(self) -> Optional[SyncJobStatus]:
        """Ephemeral: status of the most recent sync job, if known."""
        return getattr(self, "_latest_sync_job_status_ephemeral", None)

    @latest_sync_job_status.setter
    def latest_sync_job_status(self, value: Optional[SyncJobStatus]) -> None:
        self._latest_sync_job_status_ephemeral = value

    @property
    def latest_sync_job_id(self) -> Optional[UUID]:
        """Ephemeral: ID of the most recent sync job, if known."""
        return getattr(self, "_latest_sync_job_id_ephemeral", None)

    @latest_sync_job_id.setter
    def latest_sync_job_id(self, value: Optional[UUID]) -> None:
        self._latest_sync_job_id_ephemeral = value

    @property
    def latest_sync_job_started_at(self) -> Optional[datetime]:
        """Ephemeral: start time of the most recent sync job, if known."""
        return getattr(self, "_latest_sync_job_started_at_ephemeral", None)

    @latest_sync_job_started_at.setter
    def latest_sync_job_started_at(self, value: Optional[datetime]) -> None:
        self._latest_sync_job_started_at_ephemeral = value

    @property
    def latest_sync_job_completed_at(self) -> Optional[datetime]:
        """Ephemeral: completion time of the most recent sync job, if known."""
        return getattr(self, "_latest_sync_job_completed_at_ephemeral", None)

    @latest_sync_job_completed_at.setter
    def latest_sync_job_completed_at(self, value: Optional[datetime]) -> None:
        self._latest_sync_job_completed_at_ephemeral = value

    @property
    def latest_sync_job_error(self) -> Optional[str]:
        """Ephemeral: error message from the most recent sync job, if any."""
        return getattr(self, "_latest_sync_job_error_ephemeral", None)

    @latest_sync_job_error.setter
    def latest_sync_job_error(self, value: Optional[str]) -> None:
        self._latest_sync_job_error_ephemeral = value

    @property
    def cron_schedule(self) -> Optional[str]:
        """Ephemeral: cron expression used for scheduled syncs, if set."""
        return getattr(self, "_cron_schedule_ephemeral", None)

    @cron_schedule.setter
    def cron_schedule(self, value: Optional[str]) -> None:
        self._cron_schedule_ephemeral = value

    @property
    def next_scheduled_run(self) -> Optional[datetime]:
        """Ephemeral: next scheduled run time computed from the cron, if known."""
        return getattr(self, "_next_scheduled_run_ephemeral", None)

    @next_scheduled_run.setter
    def next_scheduled_run(self, value: Optional[datetime]) -> None:
        self._next_scheduled_run_ephemeral = value

    @property
    def auth_url(self) -> Optional[str]:
        """Ephemeral: authorization URL used by the API layer, if applicable."""
        return getattr(self, "_auth_url_ephemeral", None)

    @auth_url.setter
    def auth_url(self, value: Optional[str]) -> None:
        self._auth_url_ephemeral = value


# Ensure a sensible default whenever a row is loaded (belt & suspenders)
@event.listens_for(SourceConnection, "load")
def _sc_set_defaults_on_load(target, context):
    if getattr(target, "_status_ephemeral", None) is None:
        target._status_ephemeral = SourceConnectionStatus.ACTIVE


# Event to delete parent Sync when SourceConnection is deleted
@event.listens_for(SourceConnection, "before_delete")
def delete_parent_sync_and_connection(mapper, connection, target):
    """When a SourceConnection is deleted, also delete its parent Sync and Connection."""
    # Delete parent Sync if it exists
    if target.sync_id:
        # Get the session
        session = Session.object_session(target)
        if session:
            # If we're in a session, use the session to delete the Sync
            from airweave.models.sync import Sync

            sync = session.get(Sync, target.sync_id)
            if sync:
                session.delete(sync)
        else:
            # If we're not in a session, use the connection directly
            connection.execute(f"DELETE FROM sync WHERE id = '{target.sync_id}'")

    sleep(0.2)

    # Delete related Connection if it exists
    if target.connection_id:
        session = Session.object_session(target)
        if session:
            from airweave.models.connection import Connection

            related_connection = session.get(Connection, target.connection_id)
            if related_connection:
                session.delete(related_connection)
        else:
            connection.execute(f"DELETE FROM connection WHERE id = '{target.connection_id}'")
