from datetime import datetime
from enum import Enum
from uuid import UUID

from pydantic import BaseModel


class ActionStatus(str, Enum):
    PENDING = "PENDING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    REJECTED = "REJECTED"


class ExecuteRequest(BaseModel):
    incident_id: UUID
    command: str
    approved: bool


class ActionLogResponse(BaseModel):
    id: UUID
    incident_id: UUID
    command: str
    status: ActionStatus
    result: str | None = None
    timestamp: datetime
    confidence_score: float | None = None


class ExecuteResponse(BaseModel):
    status: str
    action_log_id: UUID | None = None
    result: dict | None = None
