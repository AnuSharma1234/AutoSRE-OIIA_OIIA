import asyncio
import uuid
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.whitelist import is_command_allowed
from app.models.action_log import ActionLog
from app.models.incident import Incident
from app.schemas.action import (
    ActionLogResponse,
    ActionStatus,
    ExecuteRequest,
    ExecuteResponse,
)
from app.schemas.incident import IncidentStatus
from app.services.remediation import execute_command

router = APIRouter()


@router.post("/", response_model=ExecuteResponse)
async def execute_action(
    request: ExecuteRequest,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Incident).where(Incident.id == request.incident_id))
    incident = result.scalar_one_or_none()

    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")

    if incident.status != IncidentStatus.APPROVAL_REQUIRED.value:
        raise HTTPException(
            status_code=400,
            detail=f"Incident is in '{incident.status}' status. Expected 'APPROVAL_REQUIRED'."
        )

    if not is_command_allowed(request.command):
        raise HTTPException(
            status_code=400,
            detail="Command not allowed by whitelist"
        )

    action_log: Optional[ActionLog] = None
    command_result = None

    if request.approved:
        incident.status = IncidentStatus.EXECUTING.value
        await db.commit()

        loop = asyncio.get_event_loop()
        command_result = await loop.run_in_executor(None, execute_command, request.command)

        if command_result.success:
            log_status = ActionStatus.SUCCESS.value
            incident.status = IncidentStatus.RESOLVED.value
            incident.resolved_at = datetime.utcnow()
        else:
            log_status = ActionStatus.FAILED.value
            incident.status = IncidentStatus.FAILED.value

        action_log = ActionLog(
            id=uuid.uuid4(),
            incident_id=request.incident_id,
            command=request.command,
            status=log_status,
            result=command_result.output + command_result.error if not command_result.success else command_result.output,
            timestamp=datetime.utcnow(),
            confidence_score=None,
        )
        db.add(action_log)
    else:
        incident.status = IncidentStatus.ESCALATED.value

        action_log = ActionLog(
            id=uuid.uuid4(),
            incident_id=request.incident_id,
            command=request.command,
            status=ActionStatus.REJECTED.value,
            result="Rejected by operator",
            timestamp=datetime.utcnow(),
            confidence_score=None,
        )
        db.add(action_log)

    await db.commit()
    await db.refresh(action_log)

    return ExecuteResponse(
        status=action_log.status,
        action_log_id=action_log.id,
        result={
            "output": command_result.output if command_result else None,
            "error": command_result.error if command_result else None,
            "success": command_result.success if command_result else None,
        } if request.approved else None,
    )


@router.get("/{action_log_id}", response_model=ActionLogResponse)
async def get_action_status(
    action_log_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(ActionLog).where(ActionLog.id == action_log_id))
    action_log = result.scalar_one_or_none()

    if not action_log:
        raise HTTPException(status_code=404, detail="Action log not found")

    return ActionLogResponse(
        id=action_log.id,
        incident_id=action_log.incident_id,
        command=action_log.command,
        status=ActionStatus(action_log.status),
        result=action_log.result,
        timestamp=action_log.timestamp,
        confidence_score=action_log.confidence_score,
    )
