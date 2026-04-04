import asyncio
import logging
import uuid
from datetime import datetime, timedelta

from sqlalchemy import select

from app.core.database import async_session
from app.core.redis import dequeue_task, enqueue_task, update_task_status
from app.models.incident import Incident
from app.models.action_log import ActionLog
from app.models.analysis import AIAnalysis
from app.schemas.action import ActionStatus
from app.schemas.incident import IncidentStatus, K8sContext
from app.services.kubernetes import (
    get_pod_logs,
    get_pod_events,
    get_container_status,
    get_deployment_config,
    validate_cluster_context,
)
from app.services.ai_engine import analyze_incident
from app.services.remediation import execute_remediation
from app.schemas.analysis import AIAnalysisResponse

STALE_THRESHOLD_SECONDS = 300  # 5 minutes
STALE_CHECK_INTERVAL_SECONDS = 60
PROCESSING_TIMEOUT_SECONDS = 120

logger = logging.getLogger(__name__)


def _gather_k8s_context(incident: Incident) -> K8sContext:
    """Gather Kubernetes context for an incident."""
    extra_data = incident.extra_data or {}
    pod_name = extra_data.get("pod_name", "")
    namespace = extra_data.get("namespace", "default")

    if not pod_name:
        return K8sContext(
            pod_logs="No pod name in incident metadata",
            events=[],
            context_incomplete=True,
        )

    pod_logs = get_pod_logs(pod_name, namespace)
    events = get_pod_events(pod_name, namespace)
    container_status = get_container_status(pod_name, namespace)

    deployment_name = extra_data.get("deployment_name", "")
    if not deployment_name:
        deployment_name = pod_name.rsplit("-", 2)[0]

    deployment_config = None
    if deployment_name:
        deployment_config = get_deployment_config(deployment_name, namespace)

    context_incomplete = not pod_logs or pod_logs.startswith("Error")

    return K8sContext(
        pod_logs=pod_logs,
        deployment_config=deployment_config,
        events=[{"type": e.get("type"), "reason": e.get("reason"), "message": e.get("message")} for e in events],
        container_status=container_status,
        context_incomplete=context_incomplete,
    )


async def _process_incident_task(task_data: dict):
    """Process a single incident from the queue."""
    task_id = task_data.get("task_id", "unknown")
    incident_id = task_data.get("incident_id")
    if not incident_id:
        logger.warning(f"Task {task_id}: no incident_id")
        return

    logger.info(f"Processing incident {incident_id}")

    try:
        async with async_session() as db:
            result = await db.execute(
                select(Incident).where(Incident.id == uuid.UUID(incident_id))
            )
            incident = result.scalar_one_or_none()

            if not incident:
                logger.error(f"Incident {incident_id} not found")
                return

            incident.status = IncidentStatus.ANALYZING.value
            await db.commit()

            try:
                context = _gather_k8s_context(incident)
            except Exception as e:
                logger.error(f"Failed to gather context for {incident_id}: {e}")
                context = K8sContext(
                    pod_logs=f"Context gathering failed: {e}",
                    events=[],
                    context_incomplete=True,
                )

            incident_data = {
                "alert_type": incident.alert_type,
                "cluster_id": incident.cluster_id,
                "metadata": incident.extra_data or {},
            }

            analysis: AIAnalysisResponse = await analyze_incident(incident_data, context)

            analysis_record = AIAnalysis(
                id=uuid.uuid4(),
                incident_id=incident.id,
                root_cause=analysis.root_cause,
                recommended_action=analysis.suggested_action,
                kubectl_command=analysis.kubectl_command,
                confidence_score=analysis.confidence_score,
                risk_level=analysis.risk_level.value,
                created_at=datetime.utcnow(),
            )
            db.add(analysis_record)
            await db.commit()

            attempt_count = int(str(incident.attempt_count) or "0")
            should_continue, status, result = await execute_remediation(
                incident_id, analysis, attempt_count
            )

            if result is not None:
                log_status = ActionStatus.SUCCESS.value if result.success else ActionStatus.FAILED.value
                action_log = ActionLog(
                    id=uuid.uuid4(),
                    incident_id=incident.id,
                    command=analysis.kubectl_command or "",
                    status=log_status,
                    result=(result.output + "\n" + result.error).strip() or None,
                    timestamp=datetime.utcnow(),
                    confidence_score=analysis.confidence_score,
                )
                db.add(action_log)

            incident.status = status
            await db.commit()

            await update_task_status(task_id, "completed", {"status": status})

            logger.info(f"Incident {incident_id}: {status}")

    except Exception as e:
        logger.exception(f"Error processing incident {incident_id}: {e}")
        await update_task_status(task_id, "failed", {"error": str(e)})

        try:
            async with async_session() as db:
                result = await db.execute(
                    select(Incident).where(Incident.id == uuid.UUID(incident_id))
                )
                incident = result.scalar_one_or_none()
                if incident:
                    incident.status = IncidentStatus.ESCALATED.value
                    await db.commit()
        except Exception:
            pass


async def _stale_incident_detector():
    """Background task: detect incidents stuck in ANALYZING for > 5 minutes and re-enqueue."""
    while True:
        await asyncio.sleep(STALE_CHECK_INTERVAL_SECONDS)
        try:
            stale_cutoff = datetime.utcnow() - timedelta(seconds=STALE_THRESHOLD_SECONDS)
            async with async_session() as db:
                result = await db.execute(
                    select(Incident).where(
                        Incident.status == IncidentStatus.ANALYZING.value,
                        Incident.created_at < stale_cutoff,
                    )
                )
                stale_incidents = result.scalars().all()
                for inc in stale_incidents:
                    logger.warning(f"Stale incident detected: {inc.id}, re-enqueueing")
                    await enqueue_task(str(inc.id), "analyze")
                    inc.status = IncidentStatus.PENDING.value
                await db.commit()
        except Exception as e:
            logger.error(f"Stale detector error: {e}")


async def run_queue_worker():
    """
    Main queue worker loop. Runs as a background task in FastAPI lifespan.
    Continuously polls Redis queue and processes incidents.
    """
    logger.info("Queue worker starting...")

    stale_task = asyncio.create_task(_stale_incident_detector())

    try:
        while True:
            try:
                task_data = await dequeue_task(timeout=5)
                if task_data:
                    asyncio.create_task(_process_incident_task(task_data))
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Queue worker error: {e}")
                await asyncio.sleep(1)
    finally:
        stale_task.cancel()
        try:
            await stale_task
        except asyncio.CancelledError:
            pass
        logger.info("Queue worker stopped")
