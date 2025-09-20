"""Stripe billing E2E test (standalone, no pytest).

This test exercises the happy-path subscription lifecycle using clear, reusable
abstractions. Each subtest follows the same structure:

  1) Request API
  2) Trigger Stripe webhook (or equivalent Stripe-side action)
  3) Validate results via API, DB and Stripe

If any subtest fails, the entire script exits with a non-zero code.

Requirements for local run:
  - Backend running locally (default API base: http://localhost:8001)
  - AUTH_DISABLED or X-Organization-ID header accepted by the API
  - STRIPE_SECRET_KEY set for Stripe SDK calls
  - Optionally: Stripe CLI logged in and `stripe listen` forwarding webhooks
    to /billing/webhook. The script will attempt CLI-based triggers when
    available; otherwise, it uses the Stripe SDK to produce equivalent effects.

Run:
  python backend/scripts/stripe_billing_e2e.py
"""

from __future__ import annotations

import asyncio
import json
import os
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

import requests
import stripe

# ---------------------------------------------------------------------------
# Environment defaults
# ---------------------------------------------------------------------------

os.environ.setdefault("AIRWEAVE_API_URL", "http://localhost:8001")
os.environ.setdefault("STRIPE_CLI_BIN", "stripe")

os.environ.setdefault("STRIPE_DEVELOPER_MONTHLY", "price_1S8K9GGhVYErrbTTNaqYR1MQ")
os.environ.setdefault("STRIPE_PRO_MONTHLY", "price_1S8HbSGhVYErrbTTztrvysu9")
os.environ.setdefault("STRIPE_TEAM_MONTHLY", "price_1S8HcgGhVYErrbTTfazXVcol")

os.environ.setdefault("POSTGRES_HOST", "localhost")
os.environ.setdefault("POSTGRES_PORT", "5432")
os.environ.setdefault("POSTGRES_USER", "airweave")
os.environ.setdefault("POSTGRES_PASSWORD", "airweave1234!")
os.environ.setdefault("POSTGRES_DB", "airweave")

os.environ.setdefault("FIRST_SUPERUSER", "admin@example.com")
os.environ.setdefault("FIRST_SUPERUSER_PASSWORD", "admin")
os.environ.setdefault("ENCRYPTION_KEY", "44OLJ/s4OjYSyzVk9FtOk6033GrFS4Q4KWBdEstPrgU=")


# Ensure the `airweave` package is importable when running from repo root
_BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))


# ---------------------------------------------------------------------------
# Logging helpers
# ---------------------------------------------------------------------------


def log_step(title: str) -> None:
    """Log a step."""
    print(f"\n▶ {title}")


def log_ok(message: str) -> None:
    """Log a success message."""
    print(f"  ✅ {message}")


def log_info(message: str) -> None:
    """Log an information message."""
    print(f"  • {message}")


def log_error(message: str) -> None:
    """Log an error message."""
    print(f"  ❌ {message}")


# ---------------------------------------------------------------------------
# Core abstractions
# ---------------------------------------------------------------------------


@dataclass
class Config:
    """Config."""

    api_base: str = os.environ.get("AIRWEAVE_API_URL", "http://localhost:8001")
    stripe_cli_bin: str = os.environ.get("STRIPE_CLI_BIN", "stripe")


class ApiClient:
    """API client."""

    def __init__(self, config: Config) -> None:
        """Initialize the API client."""
        self._base = config.api_base.rstrip("/")

    def post(
        self, path: str, json_body: Dict[str, Any], *, org_id: Optional[str] = None
    ) -> requests.Response:
        """Post to the API."""
        url = f"{self._base}{path}"
        headers = {"accept": "application/json", "Content-Type": "application/json"}
        if org_id:
            headers["X-Organization-ID"] = org_id
        return requests.post(url, json=json_body, headers=headers, timeout=30)

    def get(self, path: str, *, org_id: Optional[str] = None) -> requests.Response:
        """Get from the API."""
        url = f"{self._base}{path}"
        headers = {"accept": "application/json"}
        if org_id:
            headers["X-Organization-ID"] = org_id
        return requests.get(url, headers=headers, timeout=30)


class StripeClient:
    """Stripe client."""

    def __init__(self, config: Config) -> None:
        """Initialize the Stripe client."""
        api_key = os.environ.get("STRIPE_SECRET_KEY")
        if not api_key:
            raise RuntimeError("STRIPE_SECRET_KEY must be set to run Stripe checks")
        stripe.api_key = api_key
        self._cli = config.stripe_cli_bin

    def trigger(self, event: str, overrides: Optional[Dict[str, str]] = None) -> None:
        """Trigger a Stripe event."""
        cmd = [self._cli, "trigger", event]
        for key, value in (overrides or {}).items():
            cmd.extend(["--override", f"{key}={value}"])
        res = subprocess.run(cmd, capture_output=True, text=True)
        if res.returncode != 0:
            raise RuntimeError(
                f"Stripe CLI trigger failed (event={event}): {res.stdout}\n{res.stderr}"
            )

    def ensure_payment_method(self, customer_id: str) -> None:
        """Ensure a payment method is attached to the customer."""
        try:
            stripe.PaymentMethod.attach("pm_card_visa", customer=customer_id)
            stripe.Customer.modify(
                customer_id,
                invoice_settings={"default_payment_method": "pm_card_visa"},
            )
        except Exception:
            try:
                stripe.Customer.create_source(customer_id, source="tok_visa")
            except Exception as exc:  # noqa: BLE001
                raise RuntimeError(f"Failed to attach test payment method: {exc}") from exc

    def get_subscription(self, subscription_id: str) -> Any:
        """Get a subscription."""
        return stripe.Subscription.retrieve(subscription_id)

    def first_item_price_id(self, subscription: Any) -> Optional[str]:
        """Get the first item price ID from a subscription."""
        try:
            if hasattr(subscription, "items") and hasattr(subscription.items, "data"):
                data = subscription.items.data or []
                if data:
                    price_obj = getattr(data[0], "price", None)
                    if hasattr(price_obj, "id"):
                        return price_obj.id
            if isinstance(subscription, dict):
                data = ((subscription.get("items") or {}).get("data")) or []
                if isinstance(data, list) and data:
                    price_obj = data[0].get("price") if isinstance(data[0], dict) else None
                    if isinstance(price_obj, dict):
                        return price_obj.get("id")
        except Exception:
            return None
        return None

    def assert_active(self, subscription_id: str) -> None:
        """Assert a subscription is active."""
        sub = self.get_subscription(subscription_id)
        status = getattr(sub, "status", None)
        assert status == "active", f"Stripe subscription not active (status={status})"

    def assert_price(self, subscription_id: str, expected_price_id: str) -> None:
        """Assert a subscription has the correct price."""
        sub = self.get_subscription(subscription_id)
        actual = self.first_item_price_id(sub)
        assert actual == expected_price_id, (
            f"Stripe price mismatch: {actual} != {expected_price_id}"
        )

    def assert_downgrade_scheduled(
        self, subscription_id: str, *, expected_dev_price_id: Optional[str]
    ) -> None:
        """Assert a downgrade is scheduled."""
        sub = self.get_subscription(subscription_id)
        status = getattr(sub, "status", None)
        assert status == "active", (
            f"Stripe sub not active during scheduled downgrade (status={status})"
        )
        assert bool(getattr(sub, "cancel_at_period_end", False)) is False, (
            "Stripe: cancel_at_period_end should be False when downgrade is scheduled"
        )
        if expected_dev_price_id:
            current_price_id = self.first_item_price_id(sub)
            assert current_price_id == expected_dev_price_id, (
                f"Stripe: price {current_price_id} != expected developer {expected_dev_price_id}"
            )

    def create_test_clock(
        self, *, frozen_time: Optional[int] = None, name: str = "airweave-local"
    ) -> str:
        """Create a test clock."""
        if frozen_time is None:
            frozen_time = int(time.time())
        clock = stripe.test_helpers.TestClock.create(frozen_time=frozen_time, name=name)
        return clock.id

    def advance_test_clock(self, clock_id: str, new_time: int) -> None:
        """Advance a test clock."""
        stripe.test_helpers.TestClock.advance(test_clock=clock_id, frozen_time=new_time)

    def update_subscription_price(
        self, subscription_id: str, *, new_price_id: str, plan: str
    ) -> None:
        """Update a subscription price."""
        sub = stripe.Subscription.retrieve(subscription_id)
        item_id = sub["items"]["data"][0]["id"]
        stripe.Subscription.modify(
            subscription_id,
            items=[{"id": item_id, "price": new_price_id}],
            cancel_at_period_end=False,
            proration_behavior="create_prorations",
            metadata={"plan": plan},
        )


class DbInspector:
    """DB inspector."""

    def __init__(self) -> None:
        """Initialize the DB inspector."""
        from airweave import crud  # type: ignore
        from airweave.db.session import get_db_context  # type: ignore

        self._crud = crud
        self._get_db_context = get_db_context

    async def snapshot(
        self, organization_id: str, *, at_iso: Optional[str] = None
    ) -> Dict[str, Any]:
        """Snapshot the DB."""
        snapshot: Dict[str, Any] = {}
        async with self._get_db_context() as db:
            billing = await self._crud.organization_billing.get_by_organization(
                db, organization_id=organization_id
            )
            if billing:
                snapshot["organization_billing"] = {
                    "billing_plan": getattr(billing, "billing_plan", None),
                    "billing_status": getattr(billing, "billing_status", None),
                    "stripe_customer_id": getattr(billing, "stripe_customer_id", None),
                    "stripe_subscription_id": getattr(billing, "stripe_subscription_id", None),
                    "payment_method_added": getattr(billing, "payment_method_added", None),
                    "current_period_start": str(getattr(billing, "current_period_start", None)),
                    "current_period_end": str(getattr(billing, "current_period_end", None)),
                    "pending_plan_change": getattr(billing, "pending_plan_change", None),
                    "cancel_at_period_end": getattr(billing, "cancel_at_period_end", None),
                }

            if at_iso:
                try:
                    at_dt = datetime.fromisoformat(at_iso)
                    period = await self._crud.billing_period.get_current_period_at(
                        db, organization_id=organization_id, at=at_dt
                    )
                except Exception:
                    period = await self._crud.billing_period.get_current_period(
                        db, organization_id=organization_id
                    )
            else:
                period = await self._crud.billing_period.get_current_period(
                    db, organization_id=organization_id
                )

            if period:
                snapshot["current_billing_period"] = {
                    "id": str(getattr(period, "id", None)),
                    "plan": getattr(period, "plan", None),
                    "status": getattr(period, "status", None),
                    "period_start": str(getattr(period, "period_start", None)),
                    "period_end": str(getattr(period, "period_end", None)),
                    "stripe_subscription_id": getattr(period, "stripe_subscription_id", None),
                }
                usage_cur = await self._crud.usage.get_by_billing_period(
                    db, billing_period_id=period.id
                )
                if usage_cur:
                    snapshot["current_usage"] = {
                        "entities": usage_cur.entities,
                        "queries": usage_cur.queries,
                        "source_connections": usage_cur.source_connections,
                    }

            prev_list = await self._crud.billing_period.get_previous_periods(
                db, organization_id=organization_id, limit=1
            )
            if prev_list:
                prev = prev_list[0]
                snapshot["previous_billing_period"] = {
                    "id": str(getattr(prev, "id", None)),
                    "plan": getattr(prev, "plan", None),
                    "status": getattr(prev, "status", None),
                    "period_start": str(getattr(prev, "period_start", None)),
                    "period_end": str(getattr(prev, "period_end", None)),
                }
                usage_prev = await self._crud.usage.get_by_billing_period(
                    db, billing_period_id=prev.id
                )
                if usage_prev:
                    snapshot["previous_usage"] = {
                        "entities": usage_prev.entities,
                        "queries": usage_prev.queries,
                        "source_connections": usage_prev.source_connections,
                    }

        return snapshot


# ---------------------------------------------------------------------------
# Assertions and polling
# ---------------------------------------------------------------------------


def assert_api_subscription(
    data: Dict[str, Any],
    *,
    expected_plan: str,
    developer_expect_payment_method: Optional[bool] = None,
) -> None:
    """Assert a subscription is correct."""
    assert (data.get("plan") or "").lower() == expected_plan.lower(), (
        f"API plan mismatch: {data.get('plan')} != {expected_plan}"
    )
    assert (data.get("status") or "").lower() == "active", (
        f"API status not active: {data.get('status')}"
    )
    if expected_plan.lower() != "developer":
        assert data.get("has_active_subscription") is True, "API: subscription not marked active"

    if expected_plan.lower() == "developer":
        if developer_expect_payment_method is None:
            assert data.get("payment_method_added") in {False, None}, (
                "Developer should not have a payment method initially"
            )
        else:
            assert bool(data.get("payment_method_added")) is bool(
                developer_expect_payment_method
            ), "Developer payment method expectation mismatch"
    else:
        assert data.get("payment_method_added") is True, "API: payment method not marked added"

    assert data.get("requires_payment_method") is False, (
        "API: requires_payment_method should be False"
    )
    assert data.get("cancel_at_period_end") is False, "API: cancel_at_period_end should be False"

    cps = data.get("current_period_start")
    cpe = data.get("current_period_end")
    assert cps and cpe, "API: missing current period boundaries"
    start_dt = datetime.fromisoformat(str(cps))
    end_dt = datetime.fromisoformat(str(cpe))
    assert end_dt > start_dt, "API: period end must be after start"


def assert_db_snapshot(snapshot: Dict[str, Any], *, expected_plan: str) -> None:
    """Assert a DB snapshot is correct."""
    assert "organization_billing" in snapshot, "DB: missing organization_billing"
    ob = snapshot["organization_billing"]
    assert (ob.get("billing_plan") or "").lower() == expected_plan.lower(), "DB plan mismatch"
    assert (ob.get("billing_status") or "").lower() == "active", "DB: status not active"
    assert ob.get("stripe_subscription_id"), "DB: missing stripe_subscription_id"
    if expected_plan.lower() == "developer":
        assert ob.get("payment_method_added") in {False, None}, "DB: developer should not have PM"
    else:
        assert ob.get("payment_method_added") is True, "DB: payment_method_added should be True"

    if "current_billing_period" in snapshot:
        cp = snapshot["current_billing_period"]
        assert (cp.get("plan") or "").lower() == expected_plan.lower(), "DB period plan mismatch"
        assert (cp.get("status") or "").lower() in {"active"}, "DB: period status not ACTIVE"
        cps = cp.get("period_start")
        cpe = cp.get("period_end")
        start_dt = datetime.fromisoformat(str(cps))
        end_dt = datetime.fromisoformat(str(cpe))
        assert end_dt > start_dt, "DB: period end must be after start"


def assert_upgrade_pro_to_team(snapshot: Dict[str, Any]) -> None:
    """Assert an upgrade from PRO to TEAM is correct."""
    cp = snapshot.get("current_billing_period", {})
    assert (cp.get("plan") or "").lower() == "team", "DB: current plan should be team"
    assert (cp.get("status") or "").lower() == "active", "DB: current period not ACTIVE"
    pp = snapshot.get("previous_billing_period", {})
    assert pp, "DB: previous period missing after upgrade"
    assert (pp.get("plan") or "").lower() == "pro", "DB: previous plan should be pro"
    assert (pp.get("status") or "").lower() in {"completed"}, "DB: previous period not COMPLETED"
    assert "current_usage" in snapshot, "DB: current usage missing"
    assert "previous_usage" in snapshot, "DB: previous usage missing"


def poll_subscription_plan(
    api: ApiClient, *, org_id: str, expected_plan: str, timeout_sec: int = 30
) -> Dict[str, Any]:
    """Poll a subscription plan."""
    deadline = time.time() + timeout_sec
    last: Dict[str, Any] | None = None
    while time.time() < deadline:
        resp = api.get("/billing/subscription", org_id=org_id)
        if resp.ok:
            data = resp.json()
            last = data
            if (str(data.get("plan") or "").lower()) == expected_plan.lower():
                return data
        time.sleep(1.25)
    raise AssertionError(
        f"Timed out waiting for plan={expected_plan}. Last={json.dumps(last or {}, indent=2)}"
    )


def poll_subscription_flag_active(
    api: ApiClient, *, org_id: str, timeout_sec: int = 30
) -> Dict[str, Any]:
    """Poll a subscription flag active."""
    deadline = time.time() + timeout_sec
    last: Dict[str, Any] | None = None
    while time.time() < deadline:
        resp = api.get("/billing/subscription", org_id=org_id)
        if resp.ok:
            data = resp.json()
            last = data
            if bool(data.get("has_active_subscription")) is True:
                return data
        time.sleep(1.25)
    raise AssertionError(
        f"Timed out waiting for has_active_subscription. Last={json.dumps(last or {}, indent=2)}"
    )


def poll_subscription_complete(
    api: ApiClient, *, org_id: str, expected_plan: str, timeout_sec: int = 30
) -> Dict[str, Any]:
    """Poll until subscription has plan, active flag, and period boundaries."""
    deadline = time.time() + timeout_sec
    last: Dict[str, Any] | None = None
    while time.time() < deadline:
        resp = api.get("/billing/subscription", org_id=org_id)
        if resp.ok:
            data = resp.json()
            last = data
            # Check all required fields are present
            has_plan = (str(data.get("plan") or "").lower()) == expected_plan.lower()
            has_active = bool(data.get("has_active_subscription")) is True
            has_periods = data.get("current_period_start") and data.get("current_period_end")

            if has_plan and has_active and has_periods:
                return data
        time.sleep(1.25)
    raise AssertionError(
        f"Timed out waiting for complete subscription. Last={json.dumps(last or {}, indent=2)}"
    )


def _iso_to_epoch_seconds(dt_str: str) -> int:
    dt = datetime.fromisoformat(dt_str)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt.astimezone(timezone.utc)
    return int(dt.timestamp())


# ---------------------------------------------------------------------------
# Subtests
# ---------------------------------------------------------------------------


@dataclass
class CreatedOrg:
    """Created organization."""

    id: str
    name: str


def create_organization(api: ApiClient, *, plan: str) -> CreatedOrg:
    """Create an organization."""
    payload = {
        "name": f"Local Test Org {datetime.utcnow().isoformat()}Z",
        "description": "Stripe billing E2E",
        "org_metadata": {
            "onboarding": {
                "organizationSize": "2-5",
                "userRole": "engineering",
                "organizationType": "saas",
                "subscriptionPlan": plan,
                "teamInvites": [],
                "completedAt": datetime.utcnow().isoformat() + "Z",
                "stripe_test_clock": os.environ.get("STRIPE_TEST_CLOCK"),
            }
        },
    }
    resp = api.post("/organizations", payload)
    if not resp.ok:
        raise RuntimeError(f"Create organization failed: {resp.status_code} {resp.text}")
    data = resp.json()
    return CreatedOrg(id=data["id"], name=data["name"])


def start_checkout_session(api: ApiClient, *, org_id: str, plan: str) -> str:
    """Start a checkout session."""
    resp = api.post(
        "/billing/checkout-session",
        {
            "plan": plan,
            "success_url": "http://localhost:5173/organization/settings?tab=billing&success=true",
            "cancel_url": "http://localhost:5173/organization/settings?tab=billing",
        },
        org_id=org_id,
    )
    if not resp.ok:
        try:
            detail = resp.json().get("detail")
        except Exception:
            detail = resp.text
        raise RuntimeError(f"Checkout session failed: {resp.status_code} {detail}")
    return resp.json().get("checkout_url", "")


def update_plan(api: ApiClient, *, org_id: str, plan: str) -> None:
    """Update a plan."""
    resp = api.post("/billing/update-plan", {"plan": plan}, org_id=org_id)
    if not resp.ok:
        try:
            detail = resp.json().get("detail")
        except Exception:
            detail = resp.text
        raise RuntimeError(f"Update plan failed: {resp.status_code} {detail}")


def cancel_at_period_end(api: ApiClient, *, org_id: str) -> None:
    """Cancel at period end."""
    resp = api.post("/billing/cancel", {}, org_id=org_id)
    if not resp.ok:
        try:
            detail = resp.json().get("detail")
        except Exception:
            detail = resp.text
        raise RuntimeError(f"Cancel failed: {resp.status_code} {detail}")


def reactivate(api: ApiClient, *, org_id: str) -> None:
    """Reactivate."""
    resp = api.post("/billing/reactivate", {}, org_id=org_id)
    if not resp.ok:
        try:
            detail = resp.json().get("detail")
        except Exception:
            detail = resp.text
        raise RuntimeError(f"Reactivate failed: {resp.status_code} {detail}")


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------


class TestRunner:
    """Test runner."""

    def __init__(self, config: Config) -> None:
        """Initialize the test runner."""
        self.config = config
        self.api = ApiClient(config)
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        self.db = DbInspector()
        self.stripe = StripeClient(config)

    def close(self) -> None:
        """Close the test runner."""
        try:
            self.loop.close()
        except Exception:
            pass

    def run(self) -> None:  # noqa: C901
        """Run the test runner."""
        log_info(f"API base: {self.config.api_base}")

        # Ensure a Stripe Test Clock exists BEFORE creating any Stripe objects,
        # so the customer/subscription are attached to this clock.
        clock_id = os.environ.get("STRIPE_TEST_CLOCK")
        if not clock_id and os.environ.get("STRIPE_SECRET_KEY"):
            try:
                clock_id = self.stripe.create_test_clock(name="airweave-local")
                os.environ["STRIPE_TEST_CLOCK"] = clock_id
                log_info(f"Using Stripe test clock: {clock_id}")
            except Exception as exc:  # noqa: BLE001
                log_info(f"Skipping test clock creation: {exc}")
        elif clock_id:
            log_info(f"Using existing Stripe test clock: {clock_id}")

        log_step("Create organization on Developer plan")
        org = create_organization(self.api, plan="developer")
        log_ok(f"Org created: {org.id} ({org.name})")

        # Wait for webhook to fully process and set period boundaries
        sub_dev = poll_subscription_complete(
            self.api, org_id=org.id, expected_plan="developer", timeout_sec=30
        )
        assert_api_subscription(sub_dev, expected_plan="developer")
        log_ok("Developer subscription active via API")

        snap_dev = self.loop.run_until_complete(self.db.snapshot(org.id))
        assert_db_snapshot(snap_dev, expected_plan="developer")
        log_ok("Developer subscription correct in DB")

        sub_id_dev = snap_dev.get("organization_billing", {}).get("stripe_subscription_id")
        if sub_id_dev:
            self.stripe.assert_active(sub_id_dev)
            log_ok("Developer subscription active in Stripe")

        log_step("Upgrade Developer → Pro (requires checkout)")
        resp = self.api.post("/billing/update-plan", {"plan": "pro"}, org_id=org.id)
        assert resp.status_code == 400 and "Payment method" in resp.text, (
            f"Expected 400 requiring checkout, got {resp.status_code}: {resp.text}"
        )
        log_ok("Upgrade correctly requires checkout")

        checkout_url = start_checkout_session(self.api, org_id=org.id, plan="pro")
        assert checkout_url.startswith("https://"), "Missing/invalid checkout URL"
        log_ok("Checkout session created for Pro")

        snap_for_customer = self.loop.run_until_complete(self.db.snapshot(org.id))
        customer_id = (snap_for_customer.get("organization_billing", {}) or {}).get(
            "stripe_customer_id"
        )
        assert customer_id, "Missing Stripe customer id"
        self.stripe.ensure_payment_method(customer_id)

        current_sub_id = (snap_for_customer.get("organization_billing", {}) or {}).get(
            "stripe_subscription_id"
        )
        assert current_sub_id, "Missing Stripe subscription id"
        self.stripe.update_subscription_price(
            current_sub_id,
            new_price_id=os.environ["STRIPE_PRO_MONTHLY"],
            plan="pro",
        )
        log_info("Triggered Stripe subscription update (developer → pro)")

        sub_pro = poll_subscription_plan(
            self.api, org_id=org.id, expected_plan="pro", timeout_sec=30
        )
        assert_api_subscription(sub_pro, expected_plan="pro")
        log_ok("Pro subscription active via API")

        snap_pro = self.loop.run_until_complete(self.db.snapshot(org.id))
        assert_db_snapshot(snap_pro, expected_plan="pro")
        log_ok("Pro subscription correct in DB")

        sub_id_pro = snap_pro.get("organization_billing", {}).get("stripe_subscription_id")
        if sub_id_pro:
            self.stripe.assert_active(sub_id_pro)
            self.stripe.assert_price(sub_id_pro, os.environ["STRIPE_PRO_MONTHLY"])
            log_ok("Pro subscription active with correct price in Stripe")

        log_step("Upgrade Pro → Team (immediate)")
        update_plan(self.api, org_id=org.id, plan="team")
        sub_team = poll_subscription_plan(
            self.api, org_id=org.id, expected_plan="team", timeout_sec=30
        )
        assert_api_subscription(sub_team, expected_plan="team")
        log_ok("Team subscription active via API")

        snap_team = self.loop.run_until_complete(self.db.snapshot(org.id))
        assert_upgrade_pro_to_team(snap_team)
        log_ok("Team period created; Pro period completed in DB")

        sub_id_team = snap_team.get("organization_billing", {}).get("stripe_subscription_id")
        if sub_id_team:
            self.stripe.assert_active(sub_id_team)
            self.stripe.assert_price(sub_id_team, os.environ["STRIPE_TEAM_MONTHLY"])
            log_ok("Team subscription active with correct price in Stripe")

        log_step("Cancel Team at period end")
        cancel_at_period_end(self.api, org_id=org.id)
        for _ in range(20):
            cur = self.api.get("/billing/subscription", org_id=org.id).json()
            if cur.get("cancel_at_period_end") is True:
                break
            time.sleep(1.0)
        else:
            raise AssertionError("cancel_at_period_end not set after cancel")
        log_ok("cancel_at_period_end true via API")

        if sub_id_team:
            sub = self.stripe.get_subscription(sub_id_team)
            assert bool(getattr(sub, "cancel_at_period_end", False)) is True, (
                "Stripe: cancel_at_period_end not set"
            )
            log_ok("cancel_at_period_end true in Stripe")

        log_step("Reactivate Team (clear cancellation)")
        reactivate(self.api, org_id=org.id)
        for _ in range(20):
            cur = self.api.get("/billing/subscription", org_id=org.id).json()
            if cur.get("cancel_at_period_end") is False:
                break
            time.sleep(1.0)
        else:
            raise AssertionError("cancel_at_period_end not cleared after reactivate")
        log_ok("cancel_at_period_end false via API")

        if sub_id_team:
            sub2 = self.stripe.get_subscription(sub_id_team)
            assert bool(getattr(sub2, "cancel_at_period_end", False)) is False, (
                "Stripe: cancel_at_period_end still set after reactivation"
            )
            log_ok("cancel_at_period_end false in Stripe")

        log_step("Schedule downgrade Team → Developer at period end")
        update_plan(self.api, org_id=org.id, plan="developer")
        for _ in range(20):
            cur = self.api.get("/billing/subscription", org_id=org.id).json()
            if (cur.get("pending_plan_change") or "").lower() == "developer":
                break
            time.sleep(1.0)
        else:
            raise AssertionError("pending_plan_change not set to developer")
        log_ok("pending_plan_change developer via API")

        snap_dg = self.loop.run_until_complete(self.db.snapshot(org.id))
        ob = snap_dg.get("organization_billing", {})
        assert (ob.get("pending_plan_change") or "").lower() == "developer", (
            "DB: pending_plan_change not set to developer"
        )
        log_ok("pending_plan_change developer in DB")

        sub_id_for_dg = ob.get("stripe_subscription_id")
        if sub_id_for_dg:
            self.stripe.assert_downgrade_scheduled(
                sub_id_for_dg, expected_dev_price_id=os.environ.get("STRIPE_DEVELOPER_MONTHLY")
            )
            log_ok("Downgrade scheduled in Stripe (price prepared for next period)")

        clock_id = os.environ.get("STRIPE_TEST_CLOCK")
        if clock_id:
            log_step("Advance test clock to apply scheduled downgrade")
            snap_now = self.loop.run_until_complete(self.db.snapshot(org.id))
            cpe = snap_now.get("organization_billing", {}).get("current_period_end") or (
                snap_now.get("current_billing_period", {}) or {}
            ).get("period_end")
            if not cpe:
                raise AssertionError("Missing current_period_end to advance test clock")
            target_ts = _iso_to_epoch_seconds(str(cpe)) + 24 * 60 * 60
            try:
                self.stripe.advance_test_clock(clock_id, target_ts)
                log_info("Advanced Stripe test clock past current period end")
            except Exception as exc:  # noqa: BLE001
                log_info(f"Clock advance skipped: {exc}")
            deadline = time.time() + 30
            while time.time() < deadline:
                data = self.api.get("/billing/subscription", org_id=org.id).json()
                if (data.get("plan") or "").lower() == "developer":
                    break
                time.sleep(1.0)
            else:
                raise AssertionError("Downgrade not applied after clock advance")
            log_ok("Developer subscription active post-renewal via API")

        log_ok("All subtests passed")


def main() -> None:
    """Main function."""
    config = Config()
    runner = TestRunner(config)
    try:
        runner.run()
    finally:
        runner.close()


if __name__ == "__main__":
    """Main function."""
    try:
        main()
    except Exception as exc:  # noqa: BLE001
        log_error(str(exc))
        sys.exit(1)
