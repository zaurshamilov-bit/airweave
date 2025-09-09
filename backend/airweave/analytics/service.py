"""Core PostHog analytics service for Airweave."""

from typing import Any, Dict, Optional

import posthog

from airweave.core.config import settings
from airweave.core.logging import logger


class AnalyticsService:
    """Centralized analytics service for PostHog integration.

    Handles all PostHog interactions and provides a clean interface
    for tracking events throughout the Airweave application.
    """

    def __init__(self):
        """Initialize the analytics service with PostHog configuration."""
        # Enable analytics based on ANALYTICS_ENABLED setting
        self.enabled = bool(settings.POSTHOG_API_KEY and settings.ANALYTICS_ENABLED)
        self.logger = logger.with_context(component="analytics")

        if self.enabled:
            posthog.api_key = settings.POSTHOG_API_KEY
            posthog.host = settings.POSTHOG_HOST or "https://app.posthog.com"
            self.logger.info(f"PostHog analytics initialized (environment: {settings.ENVIRONMENT})")
        else:
            self.logger.info(
                f"PostHog analytics disabled (environment: {settings.ENVIRONMENT}, "
                f"api_key: {bool(settings.POSTHOG_API_KEY)}, "
                f"enabled: {settings.ANALYTICS_ENABLED})"
            )

    def identify_user(self, user_id: str, properties: Dict[str, Any]) -> None:
        """Identify a user with properties.

        Args:
        ----
            user_id: Unique identifier for the user
            properties: User properties to set
        """
        if not self.enabled:
            return

        try:
            # Create a copy to avoid mutating the caller's properties dict
            user_properties = dict(properties) if properties else {}
            user_properties["environment"] = settings.ENVIRONMENT

            posthog.capture(
                distinct_id=user_id, event="$identify", properties={"$set": user_properties}
            )
            self.logger.debug(f"User identified: {user_id}")
        except Exception as e:
            self.logger.error(f"Failed to identify user {user_id}: {e}")

    def track_event(
        self,
        event_name: str,
        distinct_id: str,
        properties: Optional[Dict[str, Any]] = None,
        groups: Optional[Dict[str, str]] = None,
    ) -> None:
        """Track an event with optional properties and groups.

        Args:
        ----
            event_name: Name of the event to track
            distinct_id: Unique identifier for the user/entity
            properties: Event properties
            groups: Group associations (e.g., organization)
        """
        if not self.enabled:
            return

        try:
            # Create a copy to avoid mutating the caller's properties dict
            event_properties = dict(properties) if properties else {}
            event_properties["environment"] = settings.ENVIRONMENT

            posthog.capture(
                distinct_id=distinct_id,
                event=event_name,
                properties=event_properties,
                groups=groups or {},
            )
            self.logger.debug(f"Event tracked: {event_name} for {distinct_id}")
        except Exception as e:
            self.logger.error(f"Failed to track event {event_name}: {e}")

    def set_group_properties(
        self, group_type: str, group_key: str, properties: Dict[str, Any]
    ) -> None:
        """Set properties for a group (e.g., organization).

        Args:
        ----
            group_type: Type of group (e.g., 'organization')
            group_key: Unique identifier for the group
            properties: Properties to set for the group
        """
        if not self.enabled:
            return

        try:
            # Create a copy to avoid mutating the caller's properties dict
            group_properties = dict(properties) if properties else {}
            group_properties["environment"] = settings.ENVIRONMENT

            posthog.capture(
                distinct_id=group_key,
                event="$groupidentify",
                properties={
                    "$group_type": group_type,
                    "$group_key": group_key,
                    "$group_set": group_properties,
                },
            )
            self.logger.debug(f"Group properties set: {group_type}:{group_key}")
        except Exception as e:
            self.logger.error(f"Failed to set group properties for {group_type}:{group_key}: {e}")


# Global analytics service instance
analytics = AnalyticsService()
