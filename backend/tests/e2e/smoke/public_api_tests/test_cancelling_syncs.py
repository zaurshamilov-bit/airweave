"""
Test module for cancelling sync jobs end-to-end via the public API.

Flow:
1) Create a Stripe direct-auth source connection (no immediate sync)
2) Trigger a manual sync and capture the job_id
3) Wait a few seconds to ensure the job is running
4) Send a cancel request and verify immediate 'cancelling' status
5) Poll jobs until the job reaches 'cancelled' (or timeout)
"""

import time
import uuid
import requests


def test_cancelling_syncs(api_url: str, headers: dict, collection_id: str, stripe_api_key: str) -> None:
    print("\n📌 Test: Cancelling Sync Jobs")

    # 1) Create a Stripe connection with direct auth, do not start immediately
    print("  Creating Stripe connection (no immediate sync)...")
    payload = {
        "name": f"Stripe Cancel Test {int(time.time())}",
        "short_name": "stripe",
        "readable_collection_id": collection_id,
        "authentication": {"credentials": {"api_key": stripe_api_key}},
        "sync_immediately": False,
    }

    response = requests.post(f"{api_url}/source-connections", json=payload, headers=headers)
    assert response.status_code == 200, f"Failed to create connection: {response.text}"
    conn = response.json()
    source_connection_id = conn["id"]
    print(f"  ✓ Connection created: {source_connection_id}")

    # 2) Trigger a manual sync
    print("  Starting sync job...")
    run_resp = requests.post(
        f"{api_url}/source-connections/{source_connection_id}/run", headers=headers
    )
    assert run_resp.status_code == 200, f"Failed to start sync: {run_resp.text}"
    job = run_resp.json()
    job_id = job["id"]
    print(f"  ✓ Sync job started: {job_id}")

    # 3) Wait briefly to ensure workflow has actually started
    wait_before_cancel_s = 20
    print(f"  Waiting {wait_before_cancel_s}s before cancelling...")
    time.sleep(wait_before_cancel_s)

    # 4) Send cancel request (should immediately mark as 'cancelling')
    print("  Requesting cancellation...")
    cancel_resp = requests.post(
        f"{api_url}/source-connections/{source_connection_id}/jobs/{job_id}/cancel",
        headers=headers,
    )
    assert cancel_resp.status_code == 200, (
        f"Cancel request failed: {cancel_resp.status_code} - {cancel_resp.text}"
    )
    cancelled_job = cancel_resp.json()
    immediate_status = str(cancelled_job.get("status", "")).lower()
    print(f"  ✓ Cancel request acknowledged, immediate job status: {immediate_status}")
    assert (
        immediate_status == "cancelling"
    ), f"Expected immediate status 'cancelling', got '{immediate_status}'"

    # 5) Poll until job reaches 'cancelled'
    timeout_s = 120
    interval_s = 3
    elapsed = 0
    final_status = immediate_status

    print("  Polling for final 'cancelled' status...")
    while elapsed < timeout_s:
        jobs_resp = requests.get(
            f"{api_url}/source-connections/{source_connection_id}/jobs", headers=headers
        )
        assert jobs_resp.status_code == 200, f"Failed to fetch jobs: {jobs_resp.text}"
        jobs = jobs_resp.json()
        alive = next((j for j in jobs if str(j.get("id")) == str(job_id)), None)
        if alive:
            final_status = str(alive.get("status", "")).lower()
            print(f"    Status after {elapsed:>3}s: {final_status}")
            if final_status in ("cancelled",):
                break
            # If it somehow completed/failed before cancellation landed, surface that
            if final_status in ("completed", "failed"):
                raise AssertionError(
                    f"Job reached terminal state '{final_status}' before cancellation completed"
                )
        else:
            print("    ⚠️ Job not found in listing; will continue polling")

        time.sleep(interval_s)
        elapsed += interval_s

    assert (
        final_status == "cancelled"
    ), f"Expected final status 'cancelled' within {timeout_s}s, got '{final_status}'"

    print("  ✓ Job successfully cancelled")
