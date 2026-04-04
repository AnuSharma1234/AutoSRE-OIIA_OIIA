import uuid
import logging
import asyncio
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Header, HTTPException, Request
from app.config import settings
from app.services.event_poller import _write_to_spacetimedb, _trigger_superplane, _safe_serialize

logger = logging.getLogger(__name__)

router = APIRouter()

# ---------------------------------------------------------------------------
# AlertManager → alert_type mapping
# ---------------------------------------------------------------------------
ALERT_NAME_MAP = {
    "KubePodCrashLooping": "CRASH_LOOP_BACKOFF",
    "KubePodNotReady": "POD_NOT_READY",
    "KubeContainerOOMKilled": "OOM_KILLED",
    "KubeDeploymentRolloutStuck": "DEPLOYMENT_FAILED",
    "KubePodPending": "POD_PENDING",
}


def _map_alert_name(alertname: str) -> str:
    """Map AlertManager alert name to normalized alert_type."""
    return ALERT_NAME_MAP.get(alertname, "UNKNOWN")


# ---------------------------------------------------------------------------
# Severity heuristic
# ---------------------------------------------------------------------------
SEVERITY_MAP = {
    "critical": "critical",
    "warning": "warning",
    "info": "info",
}


@router.post("/alertmanager")
async def alertmanager_webhook(
    request: Request,
    x_webhook_secret: str | None = Header(None, alias="X-Webhook-Secret"),
):
    """
    Prometheus AlertManager Webhook Receiver.
    Validates secret, normalizes alerts, and writes to SpacetimeDB.
    """
    # 1. Validate Secret
    if not settings.alertmanager_webhook_secret:
        logger.warning("ALERTMANAGER_WEBHOOK_SECRET not configured. Validation skipped.")
    elif x_webhook_secret != settings.alertmanager_webhook_secret:
        logger.error(f"Invalid webhook secret received: {x_webhook_secret}")
        raise HTTPException(status_code=401, detail="Unauthorized")

    try:
        payload = await request.json()
    except Exception as exc:
        logger.error(f"Failed to parse AlertManager JSON: {exc}")
        raise HTTPException(status_code=400, detail="Invalid JSON")

    # AlertManager v2 payload standard has an 'alerts' list
    alerts = payload.get("alerts", [])
    if not alerts:
        return {"status": "ok", "message": "No alerts found in payload"}

    for alert in alerts:
        labels = alert.get("labels", {})
        alertname = labels.get("alertname", "unknown")
        namespace = labels.get("namespace", labels.get("kubernetes_namespace", "default"))
        pod_name = labels.get("pod", labels.get("exported_pod", ""))
        container_name = labels.get("container", "")
        severity_label = labels.get("severity", "warning").lower()
        
        # Mapping
        alert_type = _map_alert_name(alertname)
        severity = SEVERITY_MAP.get(severity_label, "warning")
        incident_id = str(uuid.uuid4())
        
        # Detected at (AlertManager startsAt)
        starts_at = alert.get("startsAt")
        if starts_at:
            detected_at = starts_at
        else:
            detected_at = datetime.now(timezone.utc).isoformat()

        # Normalize
        normalized = {
            "incident_id": incident_id,
            "alert_type": alert_type,
            "source": "prometheus",
            "cluster_id": "local",  # User specified "local" for Docker Desktop/Default
            "namespace": namespace,
            "pod_name": pod_name,
            "container_name": container_name,
            "severity": severity,
            "raw_payload": _safe_serialize(alert),
            "detected_at": detected_at,
        }

        logger.info(f"Prometheus alert received: incident_id={incident_id} alert={alertname} type={alert_type}")

        # Write to SpacetimeDB (reducer create_incident)
        # Note: _write_to_spacetimedb handles retries internally.
        # We don't await it to block the response if there are many alerts, 
        # but the requirement says "Respond with 200 immediately after writing to SpacetimeDB".
        # This implies we should at least try once.
        success = await _write_to_spacetimedb(normalized)
        
        if success:
            # Trigger Superplane
            asyncio.create_task(
                _trigger_superplane(
                    incident_id, alert_type, namespace, pod_name
                )
            )
        else:
            logger.error(f"Failed to write Prometheus alert to SpacetimeDB: {incident_id}")

    return {"status": "ok"}
