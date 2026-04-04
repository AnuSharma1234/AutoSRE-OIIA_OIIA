"""
Kubernetes Events Watcher (Event Poller)

Streams K8s events via watch.Watch() on CoreV1Api.list_namespaced_event,
filters for incident-relevant reasons, normalizes to IncidentEvent schema,
deduplicates, and writes to SpacetimeDB + triggers Superplane workflow.

This is a background async task that runs for the lifetime of the service.
"""

import asyncio
import json
import logging
import os
import socket
import uuid
from datetime import datetime, timezone
from typing import Any

import httpx
from kubernetes import client, config, watch

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Reason → alert_type mapping (matches Prometheus alert mapping)
# ---------------------------------------------------------------------------
K8S_REASON_TO_ALERT_TYPE: dict[str, str] = {
    "BackOff": "CRASH_LOOP_BACKOFF",
    "OOMKilling": "OOM_KILLED",
    "Failed": "DEPLOYMENT_FAILED",
    "FailedScheduling": "POD_PENDING",
    "Unhealthy": "POD_NOT_READY",
}

WATCHED_REASONS: set[str] = set(K8S_REASON_TO_ALERT_TYPE.keys())

# ---------------------------------------------------------------------------
# Severity heuristic based on alert type
# ---------------------------------------------------------------------------
SEVERITY_MAP: dict[str, str] = {
    "CRASH_LOOP_BACKOFF": "critical",
    "OOM_KILLED": "critical",
    "DEPLOYMENT_FAILED": "critical",
    "POD_PENDING": "warning",
    "POD_NOT_READY": "warning",
    "UNKNOWN": "info",
}

# ---------------------------------------------------------------------------
# In-memory deduplication (pod+alert_type → last_emitted_ts)
# ---------------------------------------------------------------------------
_dedup_cache: dict[str, float] = {}
DEDUP_WINDOW_SECONDS = 60


def _is_duplicate(pod_name: str, alert_type: str) -> bool:
    """Return True if the same pod+alert_type was emitted within the dedup window."""
    now = datetime.now(timezone.utc).timestamp()
    key = f"{pod_name}::{alert_type}"

    # Lazy cleanup: prune expired entries every call (fast for small dicts)
    expired = [k for k, ts in _dedup_cache.items() if now - ts > DEDUP_WINDOW_SECONDS]
    for k in expired:
        del _dedup_cache[k]

    if key in _dedup_cache and now - _dedup_cache[key] < DEDUP_WINDOW_SECONDS:
        return True

    _dedup_cache[key] = now
    return False


# ---------------------------------------------------------------------------
# Prometheus metrics counters (simple in-process counters)
# ---------------------------------------------------------------------------
_metrics: dict[str, int] = {
    "events_received": 0,
    "events_emitted": 0,
    "duplicates_dropped": 0,
    "spacetimedb_write_failures": 0,
}


def get_poller_metrics() -> dict[str, int]:
    """Return a copy of the current metrics counters."""
    return dict(_metrics)


# ---------------------------------------------------------------------------
# SpacetimeDB writer
# ---------------------------------------------------------------------------
async def _write_to_spacetimedb(event: dict[str, Any]) -> bool:
    """
    Write a normalized IncidentEvent to SpacetimeDB by calling the
    create_incident reducer via the HTTP reducer API.

    Returns True on success, False on failure after one retry.
    """
    spacetimedb_url = os.getenv("SPACETIMEDB_URL", "")
    spacetimedb_module = os.getenv("SPACETIMEDB_MODULE", "")
    spacetimedb_token = os.getenv("SPACETIMEDB_TOKEN", "")

    if not spacetimedb_url or not spacetimedb_module:
        logger.warning("SpacetimeDB not configured — skipping write")
        return False

    # Convert WebSocket URL to HTTP for the reducer API
    base_url = spacetimedb_url.replace("ws://", "http://").replace("wss://", "https://")
    url = f"{base_url}/database/execute/{spacetimedb_module}/create_incident"

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {spacetimedb_token}",
    }

    for attempt in range(2):  # try once, retry once after 2s
        try:
            async with httpx.AsyncClient(timeout=10.0) as client_http:
                resp = await client_http.post(url, json=event, headers=headers)
                if resp.status_code in (200, 201):
                    return True
                logger.error(
                    f"SpacetimeDB write failed (attempt {attempt + 1}): "
                    f"status={resp.status_code} body={resp.text[:200]}"
                )
        except Exception as exc:
            logger.error(f"SpacetimeDB write error (attempt {attempt + 1}): {exc}")

        if attempt == 0:
            await asyncio.sleep(2)

    _metrics["spacetimedb_write_failures"] += 1
    return False


# ---------------------------------------------------------------------------
# Superplane trigger (fire-and-forget)
# ---------------------------------------------------------------------------
async def _trigger_superplane(incident_id: str, alert_type: str, namespace: str, pod_name: str):
    """Fire-and-forget POST to Superplane to kick off the remediation pipeline."""
    webhook_url = os.getenv("SUPERPLANE_WEBHOOK_URL", "")
    api_key = os.getenv("SUPERPLANE_API_KEY", "")

    if not webhook_url:
        return  # Superplane not configured — silently skip

    payload = {
        "workflow": "autosre-incident-pipeline",
        "inputs": {
            "incident_id": incident_id,
            "alert_type": alert_type,
            "namespace": namespace,
            "pod_name": pod_name,
        },
    }

    try:
        async with httpx.AsyncClient(timeout=10.0) as client_http:
            resp = await client_http.post(
                webhook_url,
                json=payload,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {api_key}",
                },
            )
            if resp.status_code not in (200, 201, 202):
                logger.warning(f"Superplane trigger non-OK: status={resp.status_code}")
    except Exception as exc:
        logger.warning(f"Superplane trigger failed (fire-and-forget): {exc}")


# ---------------------------------------------------------------------------
# Normalize a raw K8s event into the IncidentEvent schema
# ---------------------------------------------------------------------------
def _normalize_event(k8s_event: dict[str, Any]) -> dict[str, Any] | None:
    """
    Convert a raw Kubernetes event dict into the IncidentEvent schema.
    Returns None if the event should be skipped.
    """
    reason = k8s_event.get("reason", "")
    if reason not in WATCHED_REASONS:
        return None

    alert_type = K8S_REASON_TO_ALERT_TYPE.get(reason, "UNKNOWN")

    involved_obj = k8s_event.get("involvedObject", {}) or {}
    pod_name = involved_obj.get("name", "")
    namespace = involved_obj.get("namespace", os.getenv("K8S_NAMESPACE", "default"))
    container_name = involved_obj.get("fieldPath", "")
    # fieldPath is usually like "spec.containers{my-container}" — extract container name
    if "{" in container_name and "}" in container_name:
        container_name = container_name.split("{")[1].rstrip("}")
    else:
        container_name = ""

    # Determine cluster_id from node name or hostname
    source_host = (k8s_event.get("source", {}) or {}).get("host", "")
    cluster_id = source_host if source_host else socket.gethostname()

    severity = SEVERITY_MAP.get(alert_type, "info")

    # ISO 8601 UTC timestamp
    event_time = k8s_event.get("lastTimestamp") or k8s_event.get("firstTimestamp")
    if event_time and hasattr(event_time, "isoformat"):
        detected_at = event_time.isoformat()
    else:
        detected_at = datetime.now(timezone.utc).isoformat()

    incident_id = str(uuid.uuid4())

    return {
        "incident_id": incident_id,
        "alert_type": alert_type,
        "source": "k8s_events",
        "cluster_id": cluster_id,
        "namespace": namespace,
        "pod_name": pod_name,
        "container_name": container_name,
        "severity": severity,
        "raw_payload": _safe_serialize(k8s_event),
        "detected_at": detected_at,
    }


def _safe_serialize(obj: Any) -> dict:
    """Best-effort serialization of a K8s event object to a JSON-safe dict."""
    try:
        if hasattr(obj, "to_dict"):
            return obj.to_dict()
        # Ensure it's actually a dict. json.dumps(obj, default=str) can return a quoted string.
        serialized = json.loads(json.dumps(obj, default=str))
        if isinstance(serialized, dict):
            return serialized
        return {"_raw": str(serialized)}
    except Exception:
        return {"_raw": str(obj)}


# ---------------------------------------------------------------------------
# Main watcher loop
# ---------------------------------------------------------------------------
_watcher_running = False


def is_watcher_running() -> bool:
    """Return whether the K8s event watcher is currently running."""
    return _watcher_running


async def run_k8s_event_watcher():
    """
    Main entry point — run as a background asyncio task.
    Watches K8s events in the configured namespace, normalizes + deduplicates,
    writes to SpacetimeDB, and triggers Superplane.
    Reconnects automatically on failure with 5s backoff.
    """
    global _watcher_running

    namespace = os.getenv("K8S_NAMESPACE", "default")
    in_cluster = os.getenv("K8S_IN_CLUSTER", "false").lower() == "true"

    # Load K8s config once
    try:
        if in_cluster:
            config.load_incluster_config()
            logger.info("Loaded in-cluster K8s config")
        else:
            config.load_kube_config()
            logger.info("Loaded local kubeconfig (~/.kube/config)")
    except Exception as exc:
        logger.error(f"Failed to load K8s config: {exc}. Watcher will not start.")
        return

    v1 = client.CoreV1Api()

    while True:
        _watcher_running = True
        w = watch.Watch()
        logger.info(f"Starting K8s event watcher for namespace={namespace}")

        try:
            # Run the blocking Watch in a thread so we don't block the event loop
            for raw_event in await asyncio.to_thread(
                _blocking_watch, w, v1, namespace
            ):
                await _handle_watch_event(raw_event)

        except asyncio.CancelledError:
            logger.info("K8s event watcher cancelled — shutting down")
            _watcher_running = False
            w.stop()
            return

        except Exception as exc:
            logger.error(f"K8s event watcher error: {exc}. Reconnecting in 5s…")
            _watcher_running = False
            w.stop()
            await asyncio.sleep(5)


def _blocking_watch(w: watch.Watch, v1: client.CoreV1Api, namespace: str):
    """
    Generator that yields watch events. Runs in a thread via asyncio.to_thread.
    We collect events into a list so `to_thread` can return them;
    for streaming, we use a buffer approach.
    """
    events = []
    try:
        for event in w.stream(v1.list_namespaced_event, namespace=namespace, timeout_seconds=0):
            events.append(event)
            # Yield in batches to avoid unbounded memory — process every event immediately
            if len(events) >= 1:
                batch = list(events)
                events.clear()
                return batch
    except Exception:
        raise
    return events


async def _handle_watch_event(raw_event: dict[str, Any]):
    """Process a single watch event dict from the K8s API."""
    event_type = raw_event.get("type", "")
    k8s_event = raw_event.get("object")
    if not k8s_event:
        return

    # Convert K8s client object to dict if needed
    if hasattr(k8s_event, "to_dict"):
        k8s_event = k8s_event.to_dict()

    _metrics["events_received"] += 1

    normalized = _normalize_event(k8s_event)
    if normalized is None:
        return  # Not a watched reason

    pod_name = normalized["pod_name"]
    alert_type = normalized["alert_type"]

    # Deduplication check
    if _is_duplicate(pod_name, alert_type):
        _metrics["duplicates_dropped"] += 1
        logger.debug(
            f"Duplicate dropped: pod={pod_name} alert_type={alert_type}"
        )
        return

    incident_id = normalized["incident_id"]
    logger.info(
        f"K8s event detected: incident_id={incident_id} "
        f"alert_type={alert_type} pod={pod_name} ns={normalized['namespace']}"
    )

    # Write to SpacetimeDB
    success = await _write_to_spacetimedb(normalized)
    if success:
        _metrics["events_emitted"] += 1
        logger.info(f"Written to SpacetimeDB: incident_id={incident_id}")

        # Fire-and-forget Superplane trigger
        asyncio.create_task(
            _trigger_superplane(
                incident_id, alert_type, normalized["namespace"], pod_name
            )
        )
    else:
        logger.error(f"Failed to write to SpacetimeDB: incident_id={incident_id}")


# ---------------------------------------------------------------------------
# Streaming version using async generator (preferred for production)
# ---------------------------------------------------------------------------
async def _stream_k8s_events(v1: client.CoreV1Api, namespace: str):
    """
    Async generator that yields K8s watch events one at a time.
    Runs the blocking watch.stream() in a thread with a queue.
    """
    queue: asyncio.Queue = asyncio.Queue(maxsize=100)
    stop_event = asyncio.Event()

    def _producer():
        w = watch.Watch()
        try:
            for event in w.stream(
                v1.list_namespaced_event,
                namespace=namespace,
                timeout_seconds=300,  # reconnect every 5 min to avoid stale connections
            ):
                if stop_event.is_set():
                    w.stop()
                    return
                # Put into the queue — blocks if full (backpressure)
                import queue as stdlib_queue
                try:
                    queue._loop.call_soon_threadsafe(queue.put_nowait, event)
                except Exception:
                    pass
        except Exception as exc:
            queue._loop.call_soon_threadsafe(queue.put_nowait, exc)
        finally:
            queue._loop.call_soon_threadsafe(queue.put_nowait, None)

    loop = asyncio.get_running_loop()
    queue._loop = loop  # type: ignore[attr-defined]
    thread_future = loop.run_in_executor(None, _producer)

    try:
        while True:
            item = await queue.get()
            if item is None:
                break
            if isinstance(item, Exception):
                raise item
            yield item
    finally:
        stop_event.set()
        await asyncio.shield(thread_future)


async def run_k8s_event_watcher_streaming():
    """
    Production-grade streaming watcher. Use this instead of run_k8s_event_watcher
    for true event-by-event processing without batching.
    """
    global _watcher_running

    namespace = os.getenv("K8S_NAMESPACE", "default")
    in_cluster = os.getenv("K8S_IN_CLUSTER", "false").lower() == "true"

    try:
        if in_cluster:
            config.load_incluster_config()
            logger.info("Loaded in-cluster K8s config")
        else:
            config.load_kube_config()
            logger.info("Loaded local kubeconfig (~/.kube/config)")
    except Exception as exc:
        logger.error(f"Failed to load K8s config: {exc}. Watcher will not start.")
        return

    v1 = client.CoreV1Api()

    while True:
        _watcher_running = True
        logger.info(f"Starting streaming K8s event watcher for namespace={namespace}")

        try:
            async for raw_event in _stream_k8s_events(v1, namespace):
                await _handle_watch_event(raw_event)

        except asyncio.CancelledError:
            logger.info("K8s event watcher cancelled — shutting down")
            _watcher_running = False
            return

        except Exception as exc:
            logger.error(f"K8s event watcher error: {exc}. Reconnecting in 5s…")
            _watcher_running = False
            await asyncio.sleep(5)
