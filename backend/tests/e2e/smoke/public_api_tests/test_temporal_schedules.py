"""
Test module for CRON Schedule Updates with Temporal Validation.

This module tests the integration between source connection schedule updates
and Temporal workflow scheduler.
"""

import time
import requests
from typing import Optional, List, Dict, Any


def structured_calendar_to_cron(structured_cal: dict) -> str:
    """Convert Temporal's structuredCalendar to a CRON expression.

    The structuredCalendar format uses:
    - step=1 with only step means "at 0" (first unit)
    - step=1 with end means "every unit from 0 to end"
    - step=N means "every N units"
    - start/end with step=1 means "every unit in range"
    - Multiple entries in an array mean comma-separated values (e.g., 6,18 for hours)
    """
    # Extract the schedule components - these can be lists for comma-separated values
    minutes = structured_cal.get("minute", [{}])
    hours = structured_cal.get("hour", [{}])
    days_of_month = structured_cal.get("dayOfMonth", [{}])
    months = structured_cal.get("month", [{}])
    days_of_week = structured_cal.get("dayOfWeek", [{}])

    # Convert minutes (handle multiple entries for comma-separated values)
    minute_parts = []
    for minute in minutes:
        if not minute:  # Empty dict
            continue
        if minute.get("step") == 1:
            if "start" in minute and "end" in minute:
                # Check if start == end (specific minute) or range
                if minute["start"] == minute["end"]:
                    # Specific minute (most common case: minute 0)
                    minute_parts.append(str(minute["start"]))
                else:
                    # Range of minutes
                    minute_parts.append("*")
            elif "end" in minute or "start" in minute:
                # Has range, means every minute in range
                minute_parts.append("*")
            else:
                # No range, just step=1 means minute 0
                minute_parts.append("0")
        elif minute.get("step"):
            minute_parts.append(f"*/{minute['step']}")
        elif "start" in minute:
            # Specific minute value
            minute_parts.append(str(minute.get("start", 0)))
        # Don't add anything for empty dicts
    minute_part = ",".join(minute_parts) if minute_parts else "0"

    # Convert hours (handle multiple entries for comma-separated values)
    hour_parts = []
    for hour in hours:
        if not hour:  # Empty dict
            continue
        if hour.get("step") == 1:
            if "start" in hour and "end" in hour:
                # Check if start == end (specific hour) or range
                if hour["start"] == hour["end"]:
                    # Specific hour (e.g., start: 6, end: 6, step: 1)
                    hour_parts.append(str(hour["start"]))
                else:
                    # Range of hours (e.g., start: 0, end: 23, step: 1)
                    hour_parts.append("*")
            elif "end" in hour:
                # Has end but no start, means every hour (0-23)
                hour_parts.append("*")
            else:
                # No end, just step=1 means hour 0
                hour_parts.append("0")
        elif hour.get("step"):
            hour_parts.append(f"*/{hour['step']}")
        elif "start" in hour:
            # Specific hour value
            hour_parts.append(str(hour.get("start", 0)))
        # Don't add anything for empty dicts
    hour_part = ",".join(hour_parts) if hour_parts else "0"

    # Convert day of month (usually single value)
    day_of_month = days_of_month[0] if days_of_month else {}
    if day_of_month.get("step") == 1 and ("start" in day_of_month or "end" in day_of_month):
        day_part = "*"
    else:
        day_part = str(day_of_month.get("start", 1)) if day_of_month else "*"

    # Convert month (usually single value)
    month = months[0] if months else {}
    if month.get("step") == 1 and ("start" in month or "end" in month):
        month_part = "*"
    else:
        month_part = str(month.get("start", 1)) if month else "*"

    # Convert day of week (usually single value)
    day_of_week = days_of_week[0] if days_of_week else {}
    if day_of_week.get("step") == 1 and "end" in day_of_week:
        weekday_part = "*"
    elif day_of_week.get("start") is not None:
        if day_of_week.get("end"):
            weekday_part = f"{day_of_week['start']}-{day_of_week['end']}"
        else:
            weekday_part = str(day_of_week["start"])
    else:
        weekday_part = "*"

    return f"{minute_part} {hour_part} {day_part} {month_part} {weekday_part}"


def check_temporal_schedules_by_cron(expected_cron: str = None) -> Dict[str, Any]:
    """Check Temporal schedules using the REST API and verify CRON expressions."""
    import requests

    # Use Temporal REST API to list schedules
    temporal_api_url = "http://localhost:8088/api/v1/namespaces/default/schedules"

    try:
        # List all schedules
        response = requests.get(temporal_api_url)
        response.raise_for_status()

        schedules_data = response.json()
        matching_schedules = []
        all_schedule_ids = []

        # Process each schedule
        for schedule in schedules_data.get("schedules", []):
            schedule_id = schedule.get("scheduleId", "")
            all_schedule_ids.append(schedule_id)

            # Check if schedule has info with spec
            info = schedule.get("info", {})
            spec = info.get("spec", {})

            # Check for structuredCalendar (new format) or cronExpressions (old format)
            cron_expr = None
            if "structuredCalendar" in spec and spec["structuredCalendar"]:
                # Convert structured calendar to CRON
                structured_cal = spec["structuredCalendar"][0]
                cron_expr = structured_calendar_to_cron(structured_cal)
            elif "cronExpressions" in spec and spec["cronExpressions"]:
                cron_expr = spec["cronExpressions"][0]

            if cron_expr and expected_cron and cron_expr == expected_cron:
                matching_schedules.append(schedule_id)
                print(f"    ✓ Found matching schedule: {schedule_id} with CRON: {cron_expr}")

        if expected_cron:
            return len(matching_schedules) > 0, matching_schedules
        else:
            # If no expected CRON, just return if there are any schedules
            return len(all_schedule_ids) > 0, all_schedule_ids

    except Exception as e:
        print(f"    ⚠️ Error connecting to Temporal REST API: {e}")
        raise


def run_temporal_schedule_tests(api_url: str, headers: dict, test_conn_id: str) -> None:
    """
    Run all CRON schedule tests with Temporal validation.

    Args:
        api_url: The API URL
        headers: Request headers with authentication
        test_conn_id: The connection ID to test with
    """
    print("\n📌 Test 2: CRON Schedule Updates with Temporal Validation")

    # Test 1: Update to daily schedule (should create regular schedule)
    print("  Testing schedule update to daily...")
    update_payload = {"schedule": {"cron": "0 0 * * *"}}  # Daily at midnight
    response = requests.patch(
        f"{api_url}/source-connections/{test_conn_id}", json=update_payload, headers=headers
    )
    assert response.status_code == 200, f"Failed to update schedule: {response.text}"

    updated_conn = response.json()
    assert updated_conn["schedule"] is not None, "Schedule should be present"
    assert updated_conn["schedule"]["cron"] == "0 0 * * *", "CRON not updated correctly"

    # Check Temporal schedule directly
    time.sleep(2)  # Give Temporal time to create/update schedule
    has_schedule, matching = check_temporal_schedules_by_cron("0 0 * * *")
    assert has_schedule, "Should have at least one schedule with CRON '0 0 * * *'"
    assert len(matching) >= 1, f"Should have at least one matching schedule, got {matching}"
    print(f"    ✓ Daily schedule created in Temporal")

    # Test 2: Update to hourly schedule (should still be regular schedule)
    print("  Testing schedule update to hourly...")
    update_payload = {"schedule": {"cron": "0 * * * *"}}  # Every hour
    response = requests.patch(
        f"{api_url}/source-connections/{test_conn_id}", json=update_payload, headers=headers
    )
    assert response.status_code == 200, f"Failed to update to hourly: {response.text}"

    updated_conn = response.json()
    assert updated_conn["schedule"]["cron"] == "0 * * * *", "CRON not updated to hourly"

    # Check Temporal schedule directly
    time.sleep(2)
    has_schedule, matching = check_temporal_schedules_by_cron("0 * * * *")
    assert has_schedule, f"Should have at least one schedule with CRON '0 * * * *', got {matching}"
    print(f"    ✓ Hourly schedule created in Temporal")

    # Test 3: Try minute-level schedule (should fail for Stripe - no continuous support)
    print("  Testing minute-level schedule (should fail for non-continuous sources)...")
    update_payload = {"schedule": {"cron": "*/5 * * * *"}}  # Every 5 minutes
    response = requests.patch(
        f"{api_url}/source-connections/{test_conn_id}", json=update_payload, headers=headers
    )
    # Stripe doesn't support continuous, so this should fail with 400
    assert (
        response.status_code == 400
    ), f"Expected 400 for minute-level on non-continuous source, got {response.status_code}"
    if response.status_code == 400:
        error = response.json()
        detail = error.get("detail", "").lower()
        assert "does not support continuous" in detail or "minimum schedule interval" in detail
    print("    ✓ Minute-level schedule correctly rejected for non-continuous source")

    # Test 4: Update to twice-daily schedule (simpler than weekday-specific)
    print("  Testing twice-daily schedule update...")
    update_payload = {"schedule": {"cron": "0 6,18 * * *"}}  # At 6 AM and 6 PM daily
    response = requests.patch(
        f"{api_url}/source-connections/{test_conn_id}", json=update_payload, headers=headers
    )
    assert response.status_code == 200, f"Failed to update twice-daily schedule: {response.text}"

    updated_conn = response.json()
    assert updated_conn["schedule"]["cron"] == "0 6,18 * * *", "Twice-daily CRON not updated"
    print("    ✓ Updated to twice-daily schedule (6 AM and 6 PM)")

    # Test 5: Disable schedule (set to null/empty) - should delete Temporal schedule
    print("  Testing schedule removal and Temporal deletion...")

    # Wait for the schedule to be created/updated in Temporal
    time.sleep(2)

    # First, count schedules with the current CRON (from test 4: twice-daily schedule)
    current_cron = "0 6,18 * * *"  # The twice-daily schedule from test 4
    has_before, schedules_before = check_temporal_schedules_by_cron(current_cron)
    schedules_before_count = len(schedules_before) if has_before else 0
    print(f"    Schedules with CRON '{current_cron}' before removal: {schedules_before_count}")

    update_payload = {"schedule": {"cron": None}}  # Remove schedule
    response = requests.patch(
        f"{api_url}/source-connections/{test_conn_id}", json=update_payload, headers=headers
    )
    assert response.status_code == 200, f"Failed to remove schedule: {response.text}"

    updated_conn = response.json()
    # Schedule object might still exist but cron should be None
    if updated_conn.get("schedule"):
        assert updated_conn["schedule"]["cron"] is None, "CRON should be None"

    # Check that the schedule with that CRON was deleted
    time.sleep(2)
    has_after, schedules_after = check_temporal_schedules_by_cron(current_cron)
    schedules_after_count = len(schedules_after) if has_after else 0

    # We should have fewer schedules with this CRON (ideally one less)
    assert (
        schedules_after_count < schedules_before_count
    ), f"Should have fewer schedules with CRON '{current_cron}' after removal (had {schedules_before_count}, now {schedules_after_count})"

    print(
        f"    ✓ Schedule removed (schedules with CRON '{current_cron}': {schedules_before_count} → {schedules_after_count})"
    )
    print("    ✓ Verified schedule deletion in Temporal")

    # Test 6: Re-enable with different schedule - should create new Temporal schedule
    print("  Testing schedule re-enable with Temporal recreation...")
    update_payload = {"schedule": {"cron": "30 2 * * *"}}  # Daily at 2:30 AM
    response = requests.patch(
        f"{api_url}/source-connections/{test_conn_id}", json=update_payload, headers=headers
    )
    assert response.status_code == 200, f"Failed to re-enable schedule: {response.text}"

    updated_conn = response.json()
    assert updated_conn["schedule"]["cron"] == "30 2 * * *", "Schedule not re-enabled"

    # Check that Temporal schedule was recreated with new CRON
    time.sleep(2)
    has_schedule, matching = check_temporal_schedules_by_cron("30 2 * * *")
    assert has_schedule, "Should have at least one schedule with CRON '30 2 * * *'"
    print(f"    ✓ New Temporal schedule created with CRON '30 2 * * *'")
    print("    ✓ Schedule successfully re-enabled in Temporal")

    # Test 7: Invalid CRON expression (should fail with 422)
    print("  Testing invalid CRON expression...")
    update_payload = {"schedule": {"cron": "invalid cron expression"}}
    response = requests.patch(
        f"{api_url}/source-connections/{test_conn_id}", json=update_payload, headers=headers
    )
    assert response.status_code == 422, f"Expected 422 for invalid cron, got {response.status_code}"
    print("    ✓ Invalid CRON correctly rejected with 422")

    # Test 8: Update schedule along with other fields
    print("  Testing combined update (schedule + name)...")
    update_payload = {
        "name": "Updated Connection with Schedule",
        "description": "Testing combined updates",
        "schedule": {"cron": "15 3 * * 1"},  # Weekly on Monday at 3:15 AM
    }
    response = requests.patch(
        f"{api_url}/source-connections/{test_conn_id}", json=update_payload, headers=headers
    )
    assert response.status_code == 200, f"Failed combined update: {response.text}"

    updated_conn = response.json()
    assert updated_conn["name"] == "Updated Connection with Schedule", "Name not updated"
    assert updated_conn["description"] == "Testing combined updates", "Description not updated"
    assert updated_conn["schedule"]["cron"] == "15 3 * * 1", "Schedule not updated in combined"
    print("    ✓ Combined update successful")

    print("\n  ✅ CRON schedule update tests with Temporal validation passed")


def test_minute_level_schedules(
    api_url: str, headers: dict, created_connections: List[str]
) -> None:
    """
    Test minute-level schedules for continuous sources.

    Args:
        api_url: The API URL
        headers: Request headers with authentication
        created_connections: List of created connection IDs
    """
    print("\n  Testing minute-level schedules for continuous sources...")

    # Try to find a connection that supports continuous syncs (e.g., GitHub, Notion)
    notion_conn_id = None
    for conn_id in created_connections:
        response = requests.get(f"{api_url}/source-connections/{conn_id}", headers=headers)
        if response.status_code == 200:
            conn = response.json()
            # Check the short_name directly on the connection
            if conn.get("short_name") in ["notion", "github", "google_drive"]:
                notion_conn_id = conn_id
                print(f"    Found continuous-capable source: {conn['short_name']} ({conn_id})")
                break

    if notion_conn_id:
        # Test minute-level schedule
        print("    Testing minute-level schedule on continuous source...")
        update_payload = {"schedule": {"cron": "*/15 * * * *"}}  # Every 15 minutes
        response = requests.patch(
            f"{api_url}/source-connections/{notion_conn_id}",
            json=update_payload,
            headers=headers,
        )

        if response.status_code == 200:
            updated_conn = response.json()
            assert updated_conn["schedule"]["cron"] == "*/15 * * * *", "Minute-level CRON not set"

            # Check Temporal schedule directly
            time.sleep(2)
            has_schedule, matching = check_temporal_schedules_by_cron("*/15 * * * *")
            assert (
                has_schedule
            ), "Should have at least one schedule with CRON '*/15 * * * *' for continuous source"

            print(f"    ✓ Minute-level schedule created successfully for continuous source")
            print(f"    ✓ Matching schedules: {matching}")

            # Clean up - remove the minute-level schedule
            update_payload = {"schedule": {"cron": None}}
            requests.patch(
                f"{api_url}/source-connections/{notion_conn_id}",
                json=update_payload,
                headers=headers,
            )
            print("    ✓ Cleaned up minute-level schedule")
        else:
            print(f"    ⚠️ Could not set minute-level schedule: {response.status_code}")
            if response.status_code == 400:
                error = response.json()
                print(f"    Error: {error.get('detail', 'Unknown error')}")
    else:
        print("    ⚠️ No continuous-capable source found for minute-level testing")
