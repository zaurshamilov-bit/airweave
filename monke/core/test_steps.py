"""Test step implementations with improved deletion testing (fixed sync wait & search)."""

import asyncio
import time
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from monke.core.test_config import TestConfig
from monke.utils.logging import get_logger


class TestStep(ABC):
    """Abstract base class for test steps."""

    def __init__(self, config: TestConfig):
        """Initialize the test step."""
        self.config = config
        self.logger = get_logger(f"test_step.{self.__class__.__name__}")

    def _display_name(self, entity: Dict[str, Any]) -> str:
        """Return a human-readable identifier for an entity regardless of type."""
        return (
            entity.get("path")
            or entity.get("title")
            or entity.get("id")
            or entity.get("url")
            or "<unknown>"
        )

    @abstractmethod
    async def execute(self):
        """Execute the test step."""
        raise NotImplementedError


class CreateStep(TestStep):
    """Create test entities step."""

    async def execute(self):
        """Create test entities via the connector."""
        self.logger.info("🥁 Creating test entities")

        bongo = self._get_bongo()
        entities = await bongo.create_entities()

        # Optional post-create delay to allow upstream APIs to propagate data
        delay_seconds = 0
        try:
            delay_override = (
                self.config.connector.config_fields.get("post_create_sleep_seconds")
                if hasattr(self.config, "connector")
                and hasattr(self.config.connector, "config_fields")
                else None
            )
            if delay_override is not None:
                delay_seconds = int(delay_override)
        except Exception:
            delay_seconds = 0

        if delay_seconds > 0:
            self.logger.info(
                f"⏸️ Waiting {delay_seconds}s after creation to allow source API propagation"
            )
            await asyncio.sleep(delay_seconds)

        self.logger.info(f"✅ Created {len(entities)} test entities")

        # Store entities for later steps and on bongo for deletes
        self.config._created_entities = entities
        if hasattr(self.config, "_bongo"):
            self.config._bongo.created_entities = entities

    def _get_bongo(self):
        return getattr(self.config, "_bongo", None)


class SyncStep(TestStep):
    """Sync data to Airweave step."""

    async def execute(self):
        """Trigger sync and wait for completion."""
        self.logger.info("🔄 Syncing data to Airweave")

        client = self._get_airweave_client()

        # Start the sync **and capture the job id** if returned
        run_resp = client.source_connections.run_source_connection(
            self.config._source_connection_id
        )
        target_job_id = (
            getattr(run_resp, "id", None)
            or getattr(run_resp, "job_id", None)
            or getattr(run_resp, "sync_job_id", None)
        )

        # Wait for completion of exactly that job (or discover it deterministically)
        await self._wait_for_sync_completion(client, target_job_id=target_job_id)

        self.logger.info("✅ Sync completed")

    def _get_airweave_client(self):
        return getattr(self.config, "_airweave_client", None)

    async def _wait_for_sync_completion(
        self,
        client,
        target_job_id: Optional[str],
        timeout_seconds: int = 300,
    ):
        """Wait for the started sync job to complete (robust & ID-aware)."""
        self.logger.info("⏳ Waiting for sync to complete...")

        def _job_status_fields(job) -> Dict[str, Any]:
            return {
                "status": (getattr(job, "status", "") or "").lower(),
                "is_complete": bool(getattr(job, "is_complete", False)),
                "is_failed": bool(getattr(job, "is_failed", False)),
                "error": getattr(job, "error", None),
                "created_at": getattr(job, "created_at", None),
                "started_at": getattr(job, "started_at", None),
                "completed_at": getattr(job, "completed_at", None),
                "id": str(getattr(job, "id", ""))
                or str(getattr(job, "job_id", ""))
                or str(getattr(job, "sync_job_id", "")),
            }

        # If we didn't get a job id, discover it by watching latest_sync_job_id flip
        if not target_job_id:
            self.logger.info(
                "ℹ️ run() did not return a job id; discovering via latest_sync_job_id …"
            )
            start = time.monotonic()
            prev_latest = getattr(self.config, "_last_sync_job_id", None)

            while time.monotonic() - start < timeout_seconds:
                sc = client.source_connections.get_source_connection(
                    self.config._source_connection_id
                )
                latest = getattr(sc, "latest_sync_job_id", None)
                if latest and latest != prev_latest:
                    target_job_id = latest
                    self.logger.info(f"🆔 Detected new sync job id: {target_job_id}")
                    break
                await asyncio.sleep(0.5)

            if not target_job_id:
                raise RuntimeError("Couldn’t obtain sync job id for the run that was just started.")

        ACTIVE = {"created", "pending", "in_progress", "running", "queued"}
        start = time.monotonic()

        while time.monotonic() - start < timeout_seconds:
            # Prefer a direct job lookup when available
            job = None
            try:
                if hasattr(client.source_connections, "get_source_connection_job"):
                    job = client.source_connections.get_source_connection_job(
                        source_connection_id=self.config._source_connection_id,
                        job_id=target_job_id,
                    )
                else:
                    # Fallback: scan the list and match by id
                    jobs = (
                        client.source_connections.list_source_connection_jobs(
                            self.config._source_connection_id
                        )
                        or []
                    )

                    # Sort by (started_at/created_at) desc to be safe
                    def _ts(j):
                        return getattr(j, "started_at", None) or getattr(j, "created_at", None) or 0

                    jobs_sorted = sorted(jobs, key=_ts, reverse=True)
                    job = next(
                        (
                            j
                            for j in jobs_sorted
                            if str(getattr(j, "id", "")) == str(target_job_id)
                            or str(getattr(j, "job_id", "")) == str(target_job_id)
                            or str(getattr(j, "sync_job_id", "")) == str(target_job_id)
                        ),
                        None,
                    )
            except Exception as e:
                self.logger.warning(f"⚠️ Error fetching job status: {e}")
                job = None

            if not job:
                await asyncio.sleep(1.0)
                continue

            fields = _job_status_fields(job)
            self.logger.info(
                f"🔍 Job {target_job_id} status={fields['status']}, complete={fields['is_complete']}"
            )

            if fields["is_failed"] or fields["status"] == "failed":
                raise RuntimeError(f"Sync failed: {fields['error'] or 'unknown error'}")

            # Only treat as done when status is completed AND we have is_complete or completed_at
            if fields["status"] == "completed" and (
                fields["is_complete"] or fields["completed_at"]
            ):
                self.config._last_sync_job_id = target_job_id  # cache for discovery next time
                self.logger.info(
                    "✅ Sync completed successfully (confirmed by is_complete/completed_at)"
                )
                return

            if fields["status"] in ACTIVE or not fields["status"]:
                await asyncio.sleep(1.0)
                continue

            # Unexpected state, keep polling briefly
            await asyncio.sleep(1.0)

        raise TimeoutError("Sync timeout reached")


# ---------- Shared search helper ----------


def _safe_results_from_search_response(resp) -> List[Dict[str, Any]]:
    """
    Accept either a Pydantic model or plain dict. Return list of result dicts.
    """
    if resp is None:
        return []

    try:
        data = resp.model_dump()
    except AttributeError:
        try:
            # Sometimes SDK returns an object with __dict__ that isn't Pydantic
            data = dict(resp)
        except Exception:
            data = {}

    # Most SDKs use 'results', some might use 'items'
    results = data.get("results")
    if results is None and "items" in data:
        results = data["items"]

    if isinstance(results, list):
        return results
    return []


# ---------- Verification steps ----------


class VerifyStep(TestStep):
    """Verify data in Qdrant step."""

    async def execute(self):
        self.logger.info("🔍 Verifying entities in Qdrant")
        client = self._get_airweave_client()

        for entity in self.config._created_entities:
            is_present = await self._verify_entity_in_qdrant(client, entity)
            if not is_present:
                raise Exception(f"Entity {self._display_name(entity)} not found in Qdrant")
            self.logger.info(f"✅ Entity {self._display_name(entity)} verified in Qdrant")

        self.logger.info("✅ All entities verified in Qdrant")

    def _get_airweave_client(self):
        return getattr(self.config, "_airweave_client", None)

    async def _verify_entity_in_qdrant(self, client, entity: Dict[str, Any]) -> bool:
        try:
            expected_token = entity.get("token")
            if not expected_token:
                self.logger.warning("⚠️ No token found in entity, falling back to filename")
                expected_token = (entity.get("path") or "").split("/")[-1]

            self.logger.info(f"🔍 Looking for token: {expected_token}")

            # Primary search
            resp = client.collections.search_collection(
                readable_id=self.config._collection_readable_id,
                query=expected_token,
                limit=1000,
            )
            results = _safe_results_from_search_response(resp)
            self.logger.info(f"📊 Token search returned {len(results)} results")

            # Substring match within payloads
            token_lower = expected_token.lower()
            for r in results:
                payload = r.get("payload", {})
                if token_lower in str(payload).lower():
                    name = payload.get("name") or payload.get("title") or "Unknown"
                    self.logger.info(f"✅ Found token '{expected_token}' in: {name}")
                    # Optionally show the field where token matched
                    for k, v in payload.items():
                        if v and token_lower in str(v).lower():
                            self.logger.info(f"   - Token found in field '{k}': {str(v)[:100]}...")
                            break
                    return True

            # Broad search fallback: fetch more docs (no empty query if not supported; just reuse)
            if not results:
                self.logger.info("🔎 Trying broader search fallback …")
                resp2 = client.collections.search_collection(
                    readable_id=self.config._collection_readable_id,
                    query=expected_token,
                    limit=1000,
                )
                results2 = _safe_results_from_search_response(resp2)
                for r in results2:
                    payload = r.get("payload", {})
                    if token_lower in str(payload).lower():
                        self.logger.info(f"✅ Found token '{expected_token}' via fallback")
                        return True

            self.logger.warning(f"⚠️ Token '{expected_token}' not found in search results")
            return False

        except Exception as e:
            self.logger.error(f"❌ Verification failed for {self._display_name(entity)}: {e}")
            return False


class UpdateStep(TestStep):
    """Update test entities step."""

    async def execute(self):
        self.logger.info("📝 Updating test entities")
        bongo = self._get_bongo()
        updated_entities = await bongo.update_entities()
        self.logger.info(f"✅ Updated {len(updated_entities)} test entities")
        self.config._updated_entities = updated_entities

    def _get_bongo(self):
        return getattr(self.config, "_bongo", None)


class PartialDeleteStep(TestStep):
    """Partial deletion step - delete subset of entities based on test size."""

    async def execute(self):
        self.logger.info("🗑️ Executing partial deletion")
        bongo = self._get_bongo()

        deletion_count = self._calculate_partial_deletion_count()
        entities_to_delete = self.config._created_entities[:deletion_count]
        entities_to_keep = self.config._created_entities[deletion_count:]

        self.logger.info(
            f"🗑️ Deleting {len(entities_to_delete)} entities: "
            f"{[self._display_name(e) for e in entities_to_delete]}"
        )
        self.logger.info(
            f"💾 Keeping {len(entities_to_keep)} entities: "
            f"{[self._display_name(e) for e in entities_to_keep]}"
        )

        deleted_paths = await bongo.delete_specific_entities(entities_to_delete)

        self.config._partially_deleted_entities = entities_to_delete
        self.config._remaining_entities = entities_to_keep

        self.logger.info(f"✅ Partial deletion completed: {len(deleted_paths)} entities deleted")

    def _get_bongo(self):
        return getattr(self.config, "_bongo", None)

    def _calculate_partial_deletion_count(self) -> int:
        return self.config.deletion.partial_delete_count


class VerifyPartialDeletionStep(TestStep):
    """Verify that partially deleted entities are removed from Qdrant."""

    async def execute(self):
        self.logger.info("🔍 Verifying partial deletion")

        if not self.config.deletion.verify_partial_deletion:
            self.logger.info("⏭️ Skipping partial deletion verification (disabled in config)")
            return

        client = self._get_airweave_client()

        self.logger.info("🔍 Expecting these entities to be deleted:")
        for entity in self.config._partially_deleted_entities:
            self.logger.info(
                f"   - {self._display_name(entity)} (token: {entity.get('token', 'N/A')})"
            )

        for entity in self.config._partially_deleted_entities:
            is_removed = await self._verify_entity_deleted_from_qdrant(client, entity)
            if not is_removed:
                raise Exception(
                    f"Entity {self._display_name(entity)} still exists in Qdrant after deletion"
                )
            self.logger.info(
                f"✅ Entity {self._display_name(entity)} confirmed removed from Qdrant"
            )

        self.logger.info("✅ Partial deletion verification completed")

    def _get_airweave_client(self):
        return getattr(self.config, "_airweave_client", None)

    async def _verify_entity_deleted_from_qdrant(self, client, entity: Dict[str, Any]) -> bool:
        try:
            expected_token = entity.get("token") or str(
                entity.get("id") or entity.get("gid") or entity.get("name", "")
            )
            if not expected_token:
                self.logger.error("❌ Cannot verify deletion - no identifying information")
                return False

            self.logger.info(f"🔍 Verifying deletion of entity with token: {expected_token}")

            resp = client.collections.search_collection(
                readable_id=self.config._collection_readable_id,
                query=expected_token,
                limit=200,
            )
            results = _safe_results_from_search_response(resp)
            self.logger.info(f"📊 Token search returned {len(results)} results")

            token_lower = expected_token.lower()
            for r in results:
                payload = r.get("payload", {})
                if token_lower in str(payload).lower():
                    name = payload.get("name") or payload.get("title") or "Unknown"
                    self.logger.warning(
                        f"❌ Entity with token '{expected_token}' still exists: {name}"
                    )
                    for k, v in payload.items():
                        if v and token_lower in str(v).lower():
                            self.logger.warning(
                                f"   - Token found in field '{k}': {str(v)[:100]}..."
                            )
                            break
                    return False

            self.logger.info(
                f"✅ Entity with token '{expected_token}' confirmed deleted from Qdrant"
            )
            return True

        except Exception as e:
            self.logger.error(f"❌ Error during deletion verification search: {e}")
            return False


class VerifyRemainingEntitiesStep(TestStep):
    """Verify that remaining entities are still present in Qdrant."""

    async def execute(self):
        self.logger.info("🔍 Verifying remaining entities are still present")

        if not self.config.deletion.verify_remaining_entities:
            self.logger.info("⏭️ Skipping remaining entities verification (disabled in config)")
            return

        client = self._get_airweave_client()

        for entity in self.config._remaining_entities:
            is_present = await self._verify_entity_still_in_qdrant(client, entity)
            if not is_present:
                raise Exception(
                    f"Entity {self._display_name(entity)} was incorrectly removed from Qdrant"
                )
            self.logger.info(
                f"✅ Entity {self._display_name(entity)} confirmed still present in Qdrant"
            )

        self.logger.info("✅ Remaining entities verification completed")

    def _get_airweave_client(self):
        return getattr(self.config, "_airweave_client", None)

    async def _verify_entity_still_in_qdrant(self, client, entity: Dict[str, Any]) -> bool:
        try:
            expected_token = entity.get("token") or (
                (entity.get("path", "").split("/")[-1])
                if entity.get("path")
                else str(entity.get("id", ""))
            )

            if not expected_token:
                self.logger.error("❌ Cannot verify entity presence - no identifying information")
                return False

            self.logger.info(f"🔍 Verifying entity still exists with token: {expected_token}")

            resp = client.collections.search_collection(
                readable_id=self.config._collection_readable_id,
                query=expected_token,
                limit=200,
            )
            results = _safe_results_from_search_response(resp)
            self.logger.info(f"📊 Token search returned {len(results)} results")

            token_lower = expected_token.lower()
            for r in results:
                payload = r.get("payload", {})
                if token_lower in str(payload).lower():
                    name = payload.get("name") or payload.get("title") or "Unknown"
                    self.logger.info(
                        f"✅ Entity with token '{expected_token}' still exists: {name}"
                    )
                    return True

            self.logger.warning(
                f"⚠️ Entity with token '{expected_token}' NOT found in search results"
            )
            return False

        except Exception as e:
            self.logger.error(f"❌ Error during entity presence verification: {e}")
            return False


class CompleteDeleteStep(TestStep):
    """Complete deletion step - delete all remaining entities."""

    async def execute(self):
        self.logger.info("🗑️ Executing complete deletion")

        bongo = self._get_bongo()

        remaining_entities = self.config._remaining_entities
        if not remaining_entities:
            self.logger.info("ℹ️ No remaining entities to delete")
            return

        self.logger.info(f"🗑️ Deleting remaining {len(remaining_entities)} entities")

        deleted_paths = await bongo.delete_specific_entities(remaining_entities)

        self.logger.info(f"✅ Complete deletion completed: {len(deleted_paths)} entities deleted")

    def _get_bongo(self):
        return getattr(self.config, "_bongo", None)


class VerifyCompleteDeletionStep(TestStep):
    """Verify that all test entities are completely removed from Qdrant."""

    async def execute(self):
        self.logger.info("🔍 Verifying complete deletion")

        if not self.config.deletion.verify_complete_deletion:
            self.logger.info("⏭️ Skipping complete deletion verification (disabled in config)")
            return

        client = self._get_airweave_client()

        all_test_entities = (
            self.config._partially_deleted_entities + self.config._remaining_entities
        )

        for entity in all_test_entities:
            is_removed = await self._verify_entity_deleted_from_qdrant(client, entity)
            if not is_removed:
                raise Exception(
                    f"Entity {self._display_name(entity)} still exists in Qdrant after complete deletion"
                )
            self.logger.info(
                f"✅ Entity {self._display_name(entity)} confirmed removed from Qdrant"
            )

        collection_empty = await self._verify_collection_empty_of_test_data(client)
        if not collection_empty:
            self.logger.warning(
                "⚠️ Qdrant collection still contains some data (may be metadata entities)"
            )
        else:
            self.logger.info("✅ Qdrant collection confirmed empty of test data")

        self.logger.info("✅ Complete deletion verification completed")

    def _get_airweave_client(self):
        return getattr(self.config, "_airweave_client", None)

    async def _verify_entity_deleted_from_qdrant(self, client, entity: Dict[str, Any]) -> bool:
        try:
            expected_token = entity.get("token") or (
                (entity.get("path", "").split("/")[-1])
                if entity.get("path")
                else str(entity.get("id", ""))
            )
            if not expected_token:
                self.logger.error("❌ Cannot verify deletion - no identifying information")
                return False

            self.logger.info(f"🔍 Verifying deletion of entity with identifier: {expected_token}")

            resp = client.collections.search_collection(
                readable_id=self.config._collection_readable_id,
                query=expected_token,
                limit=200,
            )
            results = _safe_results_from_search_response(resp)
            self.logger.info(f"📊 Token search returned {len(results)} results")

            token_lower = expected_token.lower()
            for r in results:
                payload = r.get("payload", {})
                if token_lower in str(payload).lower():
                    name = payload.get("name") or payload.get("title") or "Unknown"
                    self.logger.warning(
                        f"❌ Entity with identifier '{expected_token}' still exists: {name}"
                    )
                    return False

            self.logger.info(f"✅ Entity with identifier '{expected_token}' confirmed deleted")
            return True

        except Exception as e:
            self.logger.error(f"❌ Error during deletion verification: {e}")
            return False

    async def _verify_collection_empty_of_test_data(self, client) -> bool:
        try:
            test_patterns = ["monke-test", "Monke Test"]
            total = 0

            for pattern in test_patterns:
                resp = client.collections.search_collection(
                    readable_id=self.config._collection_readable_id,
                    query=pattern,
                )
                results = _safe_results_from_search_response(resp)
                total += len(results)

                if results:
                    self.logger.info(f"🔍 Found {len(results)} results for pattern '{pattern}'")
                    for r in results[:3]:
                        payload = r.get("payload", {})
                        score = r.get("score")
                        self.logger.info(f"   - {payload.get('name', 'Unknown')} (score: {score})")

            if total == 0:
                self.logger.info("✅ No test data found in collection")
                return True
            else:
                self.logger.warning(f"⚠️ Found {total} test data results in collection")
                return False

        except Exception as e:
            self.logger.error(f"❌ Error verifying collection emptiness: {e}")
            return False


class TestStepFactory:
    """Factory for creating test steps."""

    _steps = {
        "create": CreateStep,
        "sync": SyncStep,
        "verify": VerifyStep,
        "update": UpdateStep,
        "partial_delete": PartialDeleteStep,
        "verify_partial_deletion": VerifyPartialDeletionStep,
        "verify_remaining_entities": VerifyRemainingEntitiesStep,
        "complete_delete": CompleteDeleteStep,
        "verify_complete_deletion": VerifyCompleteDeletionStep,
    }

    def create_step(self, step_name: str, config: TestConfig) -> TestStep:
        if step_name not in self._steps:
            raise ValueError(f"Unknown test step: {step_name}")
        return self._steps[step_name](config)
