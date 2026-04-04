"""
Tests for the K8s Event Poller / Trigger Service.

Run with: pytest tests/test_event_poller.py -v
"""

import asyncio
import json
import os
import time
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Set env vars BEFORE importing the module under test
os.environ.setdefault("GEMINI_API_KEY", "test-key")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///test.db")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("CLUSTER_ID", "test-cluster")
os.environ.setdefault("API_SECRET_KEY", "test-secret")
os.environ.setdefault("SPACETIMEDB_URL", "ws://localhost:3000")
os.environ.setdefault("SPACETIMEDB_MODULE", "autosre")
os.environ.setdefault("SPACETIMEDB_TOKEN", "test-token")
os.environ.setdefault("K8S_NAMESPACE", "default")
os.environ.setdefault("K8S_IN_CLUSTER", "false")
os.environ.setdefault("ALERTMANAGER_WEBHOOK_SECRET", "test-secret")

from app.services.event_poller import (
    K8S_REASON_TO_ALERT_TYPE,
    WATCHED_REASONS,
    _dedup_cache,
    _is_duplicate,
    _normalize_event,
    _safe_serialize,
    get_poller_metrics,
    is_watcher_running,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture(autouse=True)
def clear_dedup():
    """Clear the dedup cache before each test."""
    _dedup_cache.clear()
    yield
    _dedup_cache.clear()


def _make_k8s_event(
    reason: str = "BackOff",
    pod_name: str = "my-pod-abc-123",
    namespace: str = "default",
    container: str = "app",
    host: str = "node-1",
    message: str = "Back-off restarting failed container",
) -> dict:
    """Build a fake K8s event dict that resembles a real one."""
    return {
        "reason": reason,
        "message": message,
        "type": "Warning",
        "involvedObject": {
            "kind": "Pod",
            "name": pod_name,
            "namespace": namespace,
            "fieldPath": f"spec.containers{{{container}}}",
        },
        "source": {"component": "kubelet", "host": host},
        "firstTimestamp": datetime.now(timezone.utc).isoformat(),
        "lastTimestamp": datetime.now(timezone.utc).isoformat(),
        "count": 5,
    }


# ---------------------------------------------------------------------------
# Test: reason → alert_type mapping
# ---------------------------------------------------------------------------
class TestReasonMapping:
    def test_all_watched_reasons_are_mapped(self):
        """Every reason in WATCHED_REASONS must have a mapping."""
        for reason in WATCHED_REASONS:
            assert reason in K8S_REASON_TO_ALERT_TYPE

    def test_backoff_maps_to_crash_loop(self):
        assert K8S_REASON_TO_ALERT_TYPE["BackOff"] == "CRASH_LOOP_BACKOFF"

    def test_oomkilling_maps_to_oom_killed(self):
        assert K8S_REASON_TO_ALERT_TYPE["OOMKilling"] == "OOM_KILLED"

    def test_failed_maps_to_deployment_failed(self):
        assert K8S_REASON_TO_ALERT_TYPE["Failed"] == "DEPLOYMENT_FAILED"

    def test_failedscheduling_maps_to_pod_pending(self):
        assert K8S_REASON_TO_ALERT_TYPE["FailedScheduling"] == "POD_PENDING"

    def test_unhealthy_maps_to_pod_not_ready(self):
        assert K8S_REASON_TO_ALERT_TYPE["Unhealthy"] == "POD_NOT_READY"


# ---------------------------------------------------------------------------
# Test: normalization
# ---------------------------------------------------------------------------
class TestNormalize:
    def test_normalize_backoff_event(self):
        raw = _make_k8s_event(reason="BackOff", pod_name="web-abc-1")
        result = _normalize_event(raw)

        assert result is not None
        assert result["alert_type"] == "CRASH_LOOP_BACKOFF"
        assert result["source"] == "k8s_events"
        assert result["pod_name"] == "web-abc-1"
        assert result["namespace"] == "default"
        assert result["container_name"] == "app"
        assert result["severity"] == "critical"
        assert result["incident_id"]  # UUID string
        assert result["detected_at"]  # ISO timestamp

    def test_normalize_oomkilling(self):
        raw = _make_k8s_event(reason="OOMKilling")
        result = _normalize_event(raw)
        assert result["alert_type"] == "OOM_KILLED"
        assert result["severity"] == "critical"

    def test_normalize_unhealthy(self):
        raw = _make_k8s_event(reason="Unhealthy")
        result = _normalize_event(raw)
        assert result["alert_type"] == "POD_NOT_READY"
        assert result["severity"] == "warning"

    def test_normalize_skips_unwatched_reason(self):
        raw = _make_k8s_event(reason="Pulled")
        result = _normalize_event(raw)
        assert result is None

    def test_normalize_extracts_container_from_fieldpath(self):
        raw = _make_k8s_event(container="nginx-sidecar")
        result = _normalize_event(raw)
        assert result["container_name"] == "nginx-sidecar"

    def test_normalize_cluster_id_from_source_host(self):
        raw = _make_k8s_event(host="worker-node-3")
        result = _normalize_event(raw)
        assert result["cluster_id"] == "worker-node-3"

    def test_normalize_includes_raw_payload(self):
        raw = _make_k8s_event()
        result = _normalize_event(raw)
        assert "raw_payload" in result
        assert isinstance(result["raw_payload"], dict)

    def test_each_call_generates_unique_incident_id(self):
        raw = _make_k8s_event()
        r1 = _normalize_event(raw)
        r2 = _normalize_event(raw)
        assert r1["incident_id"] != r2["incident_id"]


# ---------------------------------------------------------------------------
# Test: deduplication
# ---------------------------------------------------------------------------
class TestDeduplication:
    def test_first_event_is_not_duplicate(self):
        assert _is_duplicate("pod-a", "CRASH_LOOP_BACKOFF") is False

    def test_same_event_within_window_is_duplicate(self):
        _is_duplicate("pod-a", "CRASH_LOOP_BACKOFF")
        assert _is_duplicate("pod-a", "CRASH_LOOP_BACKOFF") is True

    def test_different_pod_same_type_is_not_duplicate(self):
        _is_duplicate("pod-a", "CRASH_LOOP_BACKOFF")
        assert _is_duplicate("pod-b", "CRASH_LOOP_BACKOFF") is False

    def test_same_pod_different_type_is_not_duplicate(self):
        _is_duplicate("pod-a", "CRASH_LOOP_BACKOFF")
        assert _is_duplicate("pod-a", "OOM_KILLED") is False

    def test_expired_entry_is_not_duplicate(self):
        """Manually set timestamp in the past to simulate expiry."""
        _dedup_cache["pod-a::CRASH_LOOP_BACKOFF"] = time.time() - 120  # 2 min ago
        assert _is_duplicate("pod-a", "CRASH_LOOP_BACKOFF") is False


# ---------------------------------------------------------------------------
# Test: safe_serialize
# ---------------------------------------------------------------------------
class TestSafeSerialize:
    def test_dict_passes_through(self):
        d = {"a": 1, "b": "two"}
        assert _safe_serialize(d) == d

    def test_object_with_to_dict(self):
        obj = MagicMock()
        obj.to_dict.return_value = {"kind": "Event"}
        assert _safe_serialize(obj) == {"kind": "Event"}

    def test_non_serializable_fallback(self):
        result = _safe_serialize(object())
        assert "_raw" in result


# ---------------------------------------------------------------------------
# Test: metrics & watcher status
# ---------------------------------------------------------------------------
class TestMetricsAndStatus:
    def test_get_poller_metrics_returns_expected_keys(self):
        m = get_poller_metrics()
        assert "events_received" in m
        assert "events_emitted" in m
        assert "duplicates_dropped" in m
        assert "spacetimedb_write_failures" in m

    def test_is_watcher_running_default_false(self):
        assert is_watcher_running() is False


# ---------------------------------------------------------------------------
# Test: SpacetimeDB write (mocked)
# ---------------------------------------------------------------------------
class TestSpacetimeDBWrite:
    @pytest.mark.asyncio
    async def test_write_succeeds(self):
        from app.services.event_poller import _write_to_spacetimedb

        event = _normalize_event(_make_k8s_event())
        mock_resp = MagicMock()
        mock_resp.status_code = 200

        with patch("app.services.event_poller.httpx.AsyncClient") as MockClient:
            mock_instance = AsyncMock()
            mock_instance.post.return_value = mock_resp
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = mock_instance

            result = await _write_to_spacetimedb(event)
            assert result is True

    @pytest.mark.asyncio
    async def test_write_retries_on_failure(self):
        from app.services.event_poller import _write_to_spacetimedb

        event = _normalize_event(_make_k8s_event())

        fail_resp = MagicMock()
        fail_resp.status_code = 500
        fail_resp.text = "Internal Server Error"

        with patch("app.services.event_poller.httpx.AsyncClient") as MockClient:
            mock_instance = AsyncMock()
            mock_instance.post.return_value = fail_resp
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = mock_instance

            result = await _write_to_spacetimedb(event)
            assert result is False
            # Should have been called twice (initial + 1 retry)
            assert mock_instance.post.call_count == 2


# ---------------------------------------------------------------------------
# Test: Superplane trigger (mocked, fire-and-forget)
# ---------------------------------------------------------------------------
class TestSuperplaneTrigger:
    @pytest.mark.asyncio
    async def test_trigger_succeeds_silently(self):
        from app.services.event_poller import _trigger_superplane

        os.environ["SUPERPLANE_WEBHOOK_URL"] = "https://api.superplane.dev/v1/runs"
        os.environ["SUPERPLANE_API_KEY"] = "test-key"

        mock_resp = MagicMock()
        mock_resp.status_code = 202

        with patch("app.services.event_poller.httpx.AsyncClient") as MockClient:
            mock_instance = AsyncMock()
            mock_instance.post.return_value = mock_resp
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = mock_instance

            # Should not raise
            await _trigger_superplane("abc-123", "CRASH_LOOP_BACKOFF", "default", "pod-a")

    @pytest.mark.asyncio
    async def test_trigger_skips_when_not_configured(self):
        from app.services.event_poller import _trigger_superplane

        os.environ["SUPERPLANE_WEBHOOK_URL"] = ""

        with patch("app.services.event_poller.httpx.AsyncClient") as MockClient:
            await _trigger_superplane("abc-123", "CRASH_LOOP_BACKOFF", "default", "pod-a")
            MockClient.assert_not_called()
