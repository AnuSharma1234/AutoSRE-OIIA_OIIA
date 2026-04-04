import uuid
from datetime import datetime
from enum import Enum
from typing import Optional, Union
from fastapi import APIRouter, Depends, Query, HTTPException
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.models.incident import Incident
from app.models.analysis import AIAnalysis
from app.models.action_log import ActionLog
from app.schemas.incident import (
    IncidentCreate, IncidentResponse, IncidentListResponse,
    IncidentUpdate, IncidentStatus, AlertType,
)
from app.schemas.analysis import AIAnalysisResponse
from app.schemas.action import ActionLogResponse

router = APIRouter()


class AuditEntryType(str, Enum):
    ACTION = "action"
    ANALYSIS = "analysis"


class AuditEntry(BaseModel):
    """Single entry in the audit trail for an incident."""
    type: AuditEntryType
    timestamp: datetime
    details: dict

# Valid status transitions
VALID_TRANSITIONS = {
    IncidentStatus.PENDING.value: [IncidentStatus.ANALYZING.value, IncidentStatus.APPROVAL_REQUIRED.value],
    IncidentStatus.ANALYZING.value: [IncidentStatus.APPROVAL_REQUIRED.value, IncidentStatus.RESOLVED.value, IncidentStatus.ESCALATED.value],
    IncidentStatus.APPROVAL_REQUIRED.value: [IncidentStatus.EXECUTING.value, IncidentStatus.ESCALATED.value],
    IncidentStatus.EXECUTING.value: [IncidentStatus.RESOLVED.value, IncidentStatus.FAILED.value, IncidentStatus.ESCALATED.value],
    IncidentStatus.RESOLVED.value: [],
    IncidentStatus.ESCALATED.value: [],
    IncidentStatus.FAILED.value: [IncidentStatus.PENDING.value],
}


@router.get("/", response_model=IncidentListResponse)
async def list_incidents(
    status: Optional[str] = Query(None, description="Filter by status"),
    alert_type: Optional[str] = Query(None, description="Filter by alert type"),
    cluster_id: Optional[str] = Query(None, description="Filter by cluster ID"),
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(20, ge=1, le=100, description="Items per page"),
    db: AsyncSession = Depends(get_db),
):
    """List incidents with optional filtering and pagination."""
    query = select(Incident)
    count_query = select(func.count(Incident.id))

    if status:
        query = query.where(Incident.status == status)
        count_query = count_query.where(Incident.status == status)
    if alert_type:
        query = query.where(Incident.alert_type == alert_type)
        count_query = count_query.where(Incident.alert_type == alert_type)
    if cluster_id:
        query = query.where(Incident.cluster_id == cluster_id)
        count_query = count_query.where(Incident.cluster_id == cluster_id)

    query = query.order_by(Incident.created_at.desc())
    query = query.offset((page - 1) * limit).limit(limit)

    result = await db.execute(query)
    incidents = result.scalars().all()

    count_result = await db.execute(count_query)
    total = count_result.scalar() or 0

    return IncidentListResponse(
        incidents=[IncidentResponse(
            id=i.id,
            alert_type=AlertType(i.alert_type),
            cluster_id=i.cluster_id,
            status=IncidentStatus(i.status),
            metadata=i.extra_data or {},
            created_at=i.created_at,
            resolved_at=i.resolved_at,
        ) for i in incidents],
        total=total,
        page=page,
        limit=limit,
    )


@router.get("/{incident_id}", response_model=dict)
async def get_incident(
    incident_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """Get full incident detail with AI analysis and action logs."""
    result = await db.execute(select(Incident).where(Incident.id == incident_id))
    incident = result.scalar_one_or_none()

    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")

    analysis_result = await db.execute(
        select(AIAnalysis).where(AIAnalysis.incident_id == incident_id)
    )
    analysis_records = analysis_result.scalars().all()

    logs_result = await db.execute(
        select(ActionLog).where(ActionLog.incident_id == incident_id).order_by(ActionLog.timestamp)
    )
    action_logs = logs_result.scalars().all()

    return {
        "incident": IncidentResponse(
            id=incident.id,
            alert_type=AlertType(incident.alert_type),
            cluster_id=incident.cluster_id,
            status=IncidentStatus(incident.status),
            metadata=incident.extra_data or {},
            created_at=incident.created_at,
            resolved_at=incident.resolved_at,
        ),
        "analysis": [
            AIAnalysisResponse(
                root_cause=a.root_cause,
                suggested_action=a.recommended_action,
                kubectl_command=a.kubectl_command,
                confidence_score=a.confidence_score,
                risk_level=a.risk_level,
            ) for a in analysis_records
        ] if analysis_records else None,
        "action_logs": [
            ActionLogResponse(
                id=a.id,
                incident_id=a.incident_id,
                command=a.command,
                status=a.status,
                result=a.result,
                timestamp=a.timestamp,
                confidence_score=a.confidence_score,
            ) for a in action_logs
        ],
    }


@router.get("/{incident_id}/audit", response_model=list[AuditEntry])
async def get_incident_audit(
    incident_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """Return full audit trail for an incident: all action_logs + analysis records."""
    result = await db.execute(select(Incident).where(Incident.id == incident_id))
    incident = result.scalar_one_or_none()

    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")

    action_result = await db.execute(
        select(ActionLog).where(ActionLog.incident_id == incident_id).order_by(ActionLog.timestamp)
    )
    analysis_result = await db.execute(
        select(AIAnalysis).where(AIAnalysis.incident_id == incident_id).order_by(AIAnalysis.created_at)
    )
    action_logs = action_result.scalars().all()
    analysis_records = analysis_result.scalars().all()

    entries: list[AuditEntry] = []

    for log in action_logs:
        entries.append(AuditEntry(
            type=AuditEntryType.ACTION,
            timestamp=log.timestamp,
            details={
                "id": str(log.id),
                "command": log.command,
                "status": log.status,
                "result": log.result,
                "confidence_score": log.confidence_score,
            },
        ))

    for analysis in analysis_records:
        entries.append(AuditEntry(
            type=AuditEntryType.ANALYSIS,
            timestamp=analysis.created_at,
            details={
                "id": str(analysis.id),
                "root_cause": analysis.root_cause,
                "suggested_action": analysis.recommended_action,
                "kubectl_command": analysis.kubectl_command,
                "confidence_score": analysis.confidence_score,
                "risk_level": analysis.risk_level,
            },
        ))

    entries.sort(key=lambda e: e.timestamp)
    return entries


@router.patch("/{incident_id}")
async def update_incident_status(
    incident_id: uuid.UUID,
    update: IncidentUpdate,
    db: AsyncSession = Depends(get_db),
):
    """Update incident status with transition validation."""
    result = await db.execute(select(Incident).where(Incident.id == incident_id))
    incident = result.scalar_one_or_none()

    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")

    current_status = incident.status
    new_status = update.status.value

    if new_status not in VALID_TRANSITIONS.get(current_status, []):
        raise HTTPException(
            status_code=400,
            detail=f"Invalid status transition: {current_status} -> {new_status}"
        )

    incident.status = new_status
    if new_status == IncidentStatus.RESOLVED.value:
        incident.resolved_at = datetime.utcnow()
    await db.commit()

    return {"id": incident_id, "status": new_status}
