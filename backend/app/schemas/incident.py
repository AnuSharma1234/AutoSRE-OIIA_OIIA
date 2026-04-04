from datetime import datetime
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, Field


class AlertType(str, Enum):
    CRASHLOOP = "CRASHLOOP"
    OOMKILLED = "OOMKILLED"
    FAILED_DEPLOYMENT = "FAILED_DEPLOYMENT"
    PENDING_POD = "PENDING_POD"
    IMAGE_PULL_ERROR = "IMAGE_PULL_ERROR"
    UNKNOWN = "UNKNOWN"


class IncidentStatus(str, Enum):
    PENDING = "PENDING"
    ANALYZING = "ANALYZING"
    APPROVAL_REQUIRED = "APPROVAL_REQUIRED"
    EXECUTING = "EXECUTING"
    RESOLVED = "RESOLVED"
    ESCALATED = "ESCALATED"
    FAILED = "FAILED"
    WHITELIST_BLOCKED = "WHITELIST_BLOCKED"
    MONITOR_ONLY = "MONITOR_ONLY"


class IncidentCreate(BaseModel):
    alert_type: AlertType
    cluster_id: str
    metadata: dict = Field(default_factory=dict)


class IncidentResponse(BaseModel):
    id: UUID
    alert_type: AlertType
    cluster_id: str
    status: IncidentStatus
    metadata: dict
    created_at: datetime
    resolved_at: datetime | None = None


class IncidentListResponse(BaseModel):
    incidents: list[IncidentResponse]
    total: int
    page: int
    limit: int


class IncidentUpdate(BaseModel):
    status: IncidentStatus


class PrometheusAlertPayload(BaseModel):
    alerts: list[dict]


class K8sContext(BaseModel):
    pod_logs: str
    deployment_config: dict | None = None
    events: list[dict] = Field(default_factory=list)
    container_status: dict | None = None
    context_incomplete: bool = False
