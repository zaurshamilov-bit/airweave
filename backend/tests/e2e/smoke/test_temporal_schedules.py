"""
Async test module for Temporal Schedule functionality.

Tests integration between source connection schedule updates and Temporal workflow scheduler.
NOTE: These tests only run in local environment as they require Temporal API access.
"""

import pytest
import httpx
import asyncio
from typing import Dict, List, Optional, Tuple


@pytest.mark.asyncio
@pytest.mark.requires_temporal
class TestTemporalSchedules:
    """Test suite for Temporal schedule integration."""

    async def _check_temporal_schedules(
        self, expected_cron: Optional[str] = None
    ) -> Tuple[bool, List[str]]:
        """Check Temporal schedules via REST API."""
        temporal_url = "http://localhost:8088/api/v1/namespaces/default/schedules"

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(temporal_url)
                response.raise_for_status()

                schedules_data = response.json()
                matching_schedules = []
                all_schedule_ids = []

                for schedule in schedules_data.get("schedules", []):
                    schedule_id = schedule.get("scheduleId", "")
                    all_schedule_ids.append(schedule_id)

                    info = schedule.get("info", {})
                    spec = info.get("spec", {})

                    # Extract CRON expression
                    cron_expr = None
                    if "structuredCalendar" in spec and spec["structuredCalendar"]:
                        # Convert structured calendar to CRON (simplified)
                        structured_cal = spec["structuredCalendar"][0]
                        cron_expr = self._structured_calendar_to_cron(structured_cal)
                    elif "cronExpressions" in spec and spec["cronExpressions"]:
                        cron_expr = spec["cronExpressions"][0]

                    if cron_expr and expected_cron and cron_expr == expected_cron:
                        matching_schedules.append(schedule_id)

                if expected_cron:
                    return len(matching_schedules) > 0, matching_schedules
                else:
                    return len(all_schedule_ids) > 0, all_schedule_ids

        except Exception:
            # Temporal might not be available
            pytest.skip("Temporal API not available")

    def _structured_calendar_to_cron(self, structured_cal: dict) -> str:
        """Convert Temporal's structuredCalendar to CRON expression."""
        # Simplified conversion - in real implementation would be more complex
        minutes = structured_cal.get("minute", [{}])
        hours = structured_cal.get("hour", [{}])

        minute_part = "0"
        hour_part = "*"

        if minutes and minutes[0]:
            minute = minutes[0]
            if "start" in minute:
                minute_part = str(minute["start"])
            elif minute.get("step"):
                minute_part = f"*/{minute['step']}"

        if hours and hours[0]:
            hour = hours[0]
            if "start" in hour and "end" not in hour:
                hour_part = str(hour["start"])
            elif hour.get("step"):
                hour_part = f"*/{hour['step']}"
            elif "start" in hour and "end" in hour:
                if hour["start"] == hour["end"]:
                    hour_part = str(hour["start"])
                else:
                    hour_part = "*"

        return f"{minute_part} {hour_part} * * *"

    async def test_daily_schedule(
        self, api_client: httpx.AsyncClient, test_source_connection: dict, config
    ):
        """Test updating to daily schedule."""
        if not config.is_local:
            pytest.skip("Temporal tests only run locally")

        conn_id = test_source_connection["id"]

        # Update to daily schedule
        update_payload = {"schedule": {"cron": "0 0 * * *"}}
        response = await api_client.patch(f"/source-connections/{conn_id}", json=update_payload)

        assert response.status_code == 200
        updated = response.json()
        assert updated["schedule"]["cron"] == "0 0 * * *"

        # Wait for Temporal to update
        await asyncio.sleep(2)

        # Check Temporal
        has_schedule, matching = await self._check_temporal_schedules("0 0 * * *")
        assert has_schedule, "Should have daily schedule in Temporal"

    async def test_hourly_schedule(
        self, api_client: httpx.AsyncClient, test_source_connection: dict, config
    ):
        """Test updating to hourly schedule."""
        if not config.is_local:
            pytest.skip("Temporal tests only run locally")

        conn_id = test_source_connection["id"]

        # Update to hourly schedule
        update_payload = {"schedule": {"cron": "0 * * * *"}}
        response = await api_client.patch(f"/source-connections/{conn_id}", json=update_payload)

        assert response.status_code == 200
        updated = response.json()
        assert updated["schedule"]["cron"] == "0 * * * *"

        # Wait and check Temporal
        await asyncio.sleep(2)
        has_schedule, matching = await self._check_temporal_schedules("0 * * * *")
        assert has_schedule, "Should have hourly schedule in Temporal"

    async def test_minute_level_schedule_rejection(
        self, api_client: httpx.AsyncClient, test_source_connection: dict, config
    ):
        """Test that minute-level schedules are rejected for non-continuous sources."""
        if not config.is_local:
            pytest.skip("Temporal tests only run locally")

        conn_id = test_source_connection["id"]

        # Try minute-level schedule (should fail for Stripe)
        update_payload = {"schedule": {"cron": "*/5 * * * *"}}
        response = await api_client.patch(f"/source-connections/{conn_id}", json=update_payload)

        # Should be rejected
        assert response.status_code == 400
        error = response.json()
        detail = error.get("detail", "").lower()
        assert "does not support continuous" in detail or "minimum schedule interval" in detail

    async def test_schedule_removal(
        self, api_client: httpx.AsyncClient, test_source_connection: dict, config
    ):
        """Test removing schedule deletes Temporal schedule."""
        if not config.is_local:
            pytest.skip("Temporal tests only run locally")

        conn_id = test_source_connection["id"]

        # First set a schedule
        update_payload = {"schedule": {"cron": "0 2 * * *"}}
        response = await api_client.patch(f"/source-connections/{conn_id}", json=update_payload)
        assert response.status_code == 200

        await asyncio.sleep(2)
        has_before, schedules_before = await self._check_temporal_schedules("0 2 * * *")

        # Remove schedule
        update_payload = {"schedule": {"cron": None}}
        response = await api_client.patch(f"/source-connections/{conn_id}", json=update_payload)
        assert response.status_code == 200

        # Check schedule was removed
        await asyncio.sleep(2)
        has_after, schedules_after = await self._check_temporal_schedules("0 2 * * *")

        # Should have fewer schedules with this CRON
        assert len(schedules_after) < len(schedules_before)

    async def test_schedule_re_enable(
        self, api_client: httpx.AsyncClient, test_source_connection: dict, config
    ):
        """Test re-enabling schedule creates new Temporal schedule."""
        if not config.is_local:
            pytest.skip("Temporal tests only run locally")

        conn_id = test_source_connection["id"]

        # Remove any existing schedule
        update_payload = {"schedule": {"cron": None}}
        await api_client.patch(f"/source-connections/{conn_id}", json=update_payload)

        await asyncio.sleep(2)

        # Re-enable with new schedule
        update_payload = {"schedule": {"cron": "30 2 * * *"}}
        response = await api_client.patch(f"/source-connections/{conn_id}", json=update_payload)

        assert response.status_code == 200
        updated = response.json()
        assert updated["schedule"]["cron"] == "30 2 * * *"

        # Check Temporal
        await asyncio.sleep(2)
        has_schedule, matching = await self._check_temporal_schedules("30 2 * * *")
        assert has_schedule, "Should have new schedule in Temporal"

    async def test_invalid_cron(self, api_client: httpx.AsyncClient, test_source_connection: dict):
        """Test invalid CRON expression is rejected."""
        conn_id = test_source_connection["id"]

        update_payload = {"schedule": {"cron": "invalid cron expression"}}
        response = await api_client.patch(f"/source-connections/{conn_id}", json=update_payload)

        assert response.status_code == 422

    async def test_combined_update(
        self, api_client: httpx.AsyncClient, test_source_connection: dict
    ):
        """Test updating schedule along with other fields."""
        conn_id = test_source_connection["id"]

        update_payload = {
            "name": "Updated Connection with Schedule",
            "description": "Testing combined updates",
            "schedule": {"cron": "15 3 * * 1"},  # Weekly on Monday
        }

        response = await api_client.patch(f"/source-connections/{conn_id}", json=update_payload)

        assert response.status_code == 200
        updated = response.json()
        assert updated["name"] == "Updated Connection with Schedule"
        assert updated["description"] == "Testing combined updates"
        assert updated["schedule"]["cron"] == "15 3 * * 1"

    async def test_minute_level_for_continuous_source(self, api_client: httpx.AsyncClient, config):
        """Test minute-level schedules work for continuous sources."""
        if not config.is_local:
            pytest.skip("Temporal tests only run locally")

        # Create a Notion connection (supports continuous)
        collection_data = {"name": "Continuous Test Collection"}
        response = await api_client.post("/collections/", json=collection_data)
        assert response.status_code == 200
        collection = response.json()

        connection_data = {
            "name": "Continuous Test Connection",
            "short_name": "notion",
            "readable_collection_id": collection["readable_id"],
            "authentication": {"access_token": config.test_notion_token},
        }

        response = await api_client.post("/source-connections", json=connection_data)

        if response.status_code == 200:
            connection = response.json()
            conn_id = connection["id"]

            # Set minute-level schedule
            update_payload = {"schedule": {"cron": "*/15 * * * *"}}
            response = await api_client.patch(f"/source-connections/{conn_id}", json=update_payload)

            assert response.status_code == 200
            updated = response.json()
            assert updated["schedule"]["cron"] == "*/15 * * * *"

            # Check Temporal
            await asyncio.sleep(2)
            has_schedule, matching = await self._check_temporal_schedules("*/15 * * * *")
            assert has_schedule, "Should have minute-level schedule for continuous source"

            # Cleanup
            await api_client.delete(f"/source-connections/{conn_id}")

        # Cleanup collection
        await api_client.delete(f"/collections/{collection['readable_id']}")
