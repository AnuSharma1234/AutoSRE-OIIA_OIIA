import uuid
import hashlib
from datetime import datetime
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from app.core.database import get_db
from app.models.incident import Incident
from app.schemas.incident import AlertType, IncidentStatus
from app.core.redis import enqueue_task

router = APIRouter()

# Prometheus alert name to AlertType mapping
ALERT_NAME_MAP = {
    "KubePodCrashLoopBackOff": AlertType.CRASHLOOP,
    "KubePodNotReady": AlertType.OOMKILLED,  # Will be refined by AI
    "KubeDeploymentReplicasMismatch": AlertType.FAILED_DEPLOYMENT,
    "KubePodPending": AlertType.PENDING_POD,
    "KubeImagePullBackOff": AlertType.IMAGE_PULL_ERROR,
    "KubePodOOMKilled": AlertType.OOMKILLED,
}

DEDUP_WINDOW_SECONDS = 300  # 5 minutes


def _map_alert_name(alertname: str) -> AlertType:
    """Map Prometheus alert name to AlertType enum."""
    return ALERT_NAME_MAP.get(alertname, AlertType.UNKNOWN)


def _get_dedup_key(alertname: str, namespace: str, pod_name: str) -> str:
    """Generate deduplication key."""
    key_string = f"{alertname}:{namespace}:{pod_name}"
    return hashlib.sha256(key_string.encode()).hexdigest()[:16]


async def _check_dedup(dedup_key: str) -> str | None:
    """Check if this alert was seen recently. Returns incident_id if duplicate."""
    from app.core.redis import redis_client
    existing = await redis_client.get(f"autosre:dedup:{dedup_key}")
    if existing:
        return existing.decode() if isinstance(existing, bytes) else existing
    return None


async def _set_dedup(dedup_key: str, incident_id: str):
    """Set dedup key with TTL."""
    from app.core.redis import redis_client
    await redis_client.setex(f"autosre:dedup:{dedup_key}", DEDUP_WINDOW_SECONDS, incident_id)


class PrometheusAlert(BaseModel):
    status: str
    labels: dict
    annotations: dict | None = None
    startsAt: str | None = None
    endsAt: str | None = None


class PrometheusWebhookPayload(BaseModel):
    alerts: list[PrometheusAlert]


@router.post("/prometheus")
async def prometheus_webhook(
    payload: PrometheusWebhookPayload,
    db: AsyncSession = Depends(get_db),
):
    """
    Receive Prometheus Alertmanager webhook notifications.
    Creates incidents for firing alerts, with 5-minute deduplication.
    """
    created_incidents = []
    skipped_incidents = []

    for alert in payload.alerts:
        # Skip resolved alerts
        if alert.status != "firing":
            skipped_incidents.append({"alert": alert.labels.get("alertname"), "reason": "resolved"})
            continue

        alertname = alert.labels.get("alertname", "unknown")
        namespace = alert.labels.get("namespace", alert.labels.get("kubernetes_namespace", "default"))
        pod_name = alert.labels.get("pod", alert.labels.get("exported_pod", ""))
        cluster_id = alert.labels.get("cluster", "default")

        alert_type = _map_alert_name(alertname)
        dedup_key = _get_dedup_key(alertname, namespace, pod_name)

        # Check deduplication
        existing_incident_id = await _check_dedup(dedup_key)
        if existing_incident_id:
            skipped_incidents.append({"alert": alertname, "incident_id": existing_incident_id, "reason": "duplicate"})
            continue

        # Create incident
        incident_id = str(uuid.uuid4())
        extra_data = {
            "alertname": alertname,
            "namespace": namespace,
            "pod_name": pod_name,
            "description": alert.annotations.get("description", "") if alert.annotations else "",
            "summary": alert.annotations.get("summary", "") if alert.annotations else "",
            "severity": alert.labels.get("severity", "warning"),
            "starts_at": alert.startsAt,
        }

        incident = Incident(
            id=uuid.UUID(incident_id),
            alert_type=alert_type.value,
            cluster_id=cluster_id,
            status=IncidentStatus.PENDING.value,
            extra_data=extra_data,
            created_at=datetime.utcnow(),
            attempt_count="0",
        )
        db.add(incident)
        await db.commit()

        # Set dedup key
        await _set_dedup(dedup_key, incident_id)

        # Enqueue analysis task
        await enqueue_task(incident_id, "analyze")

        created_incidents.append({
            "incident_id": incident_id,
            "alert_type": alert_type.value,
            "cluster_id": cluster_id,
        })

    return {
        "status": "accepted",
        "created": len(created_incidents),
        "skipped": len(skipped_incidents),
        "incident_ids": [i["incident_id"] for i in created_incidents],
        "skipped_detail": skipped_incidents[:10],  # Limit detail
    }
