from enum import Enum
from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.incident import K8sContext


class RiskLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class AIAnalysisRequest(BaseModel):
    incident_id: UUID
    context: K8sContext


class AIAnalysisResponse(BaseModel):
    root_cause: str
    suggested_action: str
    kubectl_command: str | None = None
    confidence_score: float = Field(ge=0.0, le=1.0)
    risk_level: RiskLevel
