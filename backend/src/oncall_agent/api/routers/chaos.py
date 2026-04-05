"""Chaos engineering API endpoints for AutoSRE v2.0."""

import logging
from datetime import datetime
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ...config import get_config

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/chaos",
    tags=["chaos"],
    responses={404: {"description": "Not found"}},
)


class ChaosEventRequest(BaseModel):
    """Request model for triggering chaos events."""
    service: str | None = None
    action: str = "all"
    description: str | None = None


class ChaosEventResponse(BaseModel):
    """Response model for chaos event creation."""
    success: bool
    message: str
    pagerduty_response: dict[str, Any] | None = None
    dedup_key: str | None = None


@router.post("/trigger-alert", response_model=ChaosEventResponse)
async def trigger_chaos_alert(
    request: ChaosEventRequest
) -> ChaosEventResponse:
    """Trigger a PagerDuty alert for chaos engineering actions.

    This endpoint is used by the frontend to create PagerDuty incidents
    when chaos engineering actions are performed.

    Auth is handled by authentik reverse proxy.
    """
    config = get_config()

    # Check if we're in development mode
    if config.environment != "development":
        raise HTTPException(
            status_code=403,
            detail="Chaos engineering is only available in development mode"
        )

    # Build the alert summary based on the service
    service_descriptions = {
        "pod_crash": "Pod Crash - CrashLoopBackOff simulation",
        "image_pull": "Image Pull Error - ImagePullBackOff simulation",
        "oom_kill": "OOM Kill - Memory exhaustion simulation",
        "deployment_failure": "Deployment Failure - Failed rollout simulation",
        "service_unavailable": "Service Unavailable - Broken endpoints simulation"
    }

    if request.service and request.service in service_descriptions:
        summary = f"[CHAOS] {service_descriptions[request.service]}"
        affected_services = 1
    else:
        summary = "[CHAOS] All Services - Complete infrastructure chaos deployed"
        affected_services = 5

    # Custom details for the alert
    custom_details = {
        "chaos_type": request.service or "all_services",
        "action": request.action,
        "affected_services": affected_services,
        "triggered_by": "oncall-agent",
        "timestamp": datetime.utcnow().isoformat(),
        "environment": "development",
        "namespace": "oncall-test-apps",
        "remediation_hint": "This is a chaos engineering test. The oncall agent should automatically detect and fix these issues."
    }

    if request.description:
        custom_details["description"] = request.description

    # Dedup key to prevent duplicate incidents for the same chaos action
    dedup_key = f"chaos-{request.service or 'all'}-{datetime.utcnow().strftime('%Y%m%d')}"

    try:
        # Mock chaos event trigger for AutoSRE v2.0 (SuperPlane integration)
        # In production, this would trigger via SuperPlane Canvas
        superplane_response = {
            "status": "success",
            "incident_id": f"chaos-{dedup_key}",
            "message": f"Chaos event simulated: {summary}",
            "canvas_triggered": True
        }

        logger.info(f"🎯 [CHAOS] Simulated chaos event: {summary}")
        
        return ChaosEventResponse(
            success=True,
            message=f"Chaos alert simulated successfully: {summary}",
            pagerduty_incident_id=superplane_response["incident_id"],
            dedup_key=dedup_key
        )

    except Exception as e:
        logger.error(f"Error simulating chaos event: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to simulate chaos alert: {str(e)}"
        )


@router.get("/status")
async def get_chaos_status() -> dict[str, Any]:
    """Get chaos engineering status and configuration.

    Auth is handled by authentik reverse proxy.
    """
    config = get_config()

    return {
        "enabled": config.environment == "development",
        "environment": config.environment,
        "pagerduty_configured": bool(config.pagerduty_events_integration_key),
        "message": "Chaos engineering is enabled in development mode only"
    }
