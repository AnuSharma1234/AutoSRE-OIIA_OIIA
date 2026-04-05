"""Incident models for AutoSRE v2.0 - Generic incident handling."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional


@dataclass
class IncidentData:
    """Generic incident data model compatible with various alerting systems."""
    
    # Core fields
    id: str
    title: str = ""
    description: str = ""
    status: str = "triggered"
    
    # Metadata
    service: Optional[str] = None
    urgency: str = "low"
    severity: str = "info"
    source: str = "manual"  # pagerduty, superplane, manual, etc.
    
    # Timestamps
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    # Additional context
    details: Dict[str, Any] = field(default_factory=dict)
    labels: Dict[str, str] = field(default_factory=dict)
    annotations: Dict[str, str] = field(default_factory=dict)
    
    def __post_init__(self):
        """Set default timestamps if not provided."""
        if self.created_at is None:
            self.created_at = datetime.now()
        if self.updated_at is None:
            self.updated_at = datetime.now()


# For backward compatibility, alias the old PagerDuty model
PagerDutyIncidentData = IncidentData


@dataclass
class SuperPlaneIncidentData(IncidentData):
    """SuperPlane-specific incident data with Canvas context."""
    
    canvas_id: Optional[str] = None
    canvas_name: Optional[str] = None
    trigger_type: str = "manual"  # manual, webhook, scheduled
    
    @classmethod
    def from_canvas_input(cls, data: Dict[str, Any]) -> "SuperPlaneIncidentData":
        """Create incident from SuperPlane Canvas input."""
        return cls(
            id=data.get("id", f"sp-{datetime.now().strftime('%Y%m%d%H%M%S')}"),
            title=data.get("title", "SuperPlane Incident"),
            description=data.get("description", ""),
            source="superplane",
            canvas_id=data.get("canvas_id"),
            canvas_name=data.get("canvas_name", "AutoSRE Canvas"),
            trigger_type=data.get("trigger_type", "manual"),
            details=data.get("details", {}),
            labels=data.get("labels", {}),
            annotations=data.get("annotations", {})
        )


@dataclass  
class JIRATicketData:
    """JIRA ticket creation data."""
    
    project_key: str
    summary: str
    description: str
    issue_type: str = "Task"
    priority: str = "Medium"
    labels: List[str] = field(default_factory=list)
    
    def to_jira_format(self) -> Dict[str, Any]:
        """Convert to JIRA API format."""
        return {
            "fields": {
                "project": {"key": self.project_key},
                "summary": self.summary,
                "description": self.description,
                "issuetype": {"name": self.issue_type},
                "priority": {"name": self.priority},
                "labels": self.labels
            }
        }


# Legacy models for backward compatibility
@dataclass
class PagerDutyService:
    """Legacy PagerDuty service model."""
    id: str
    name: str = ""
    description: str = ""


@dataclass
class PagerDutyLogEntry:
    """Legacy PagerDuty log entry model."""
    id: str
    type: str
    summary: str
    created_at: Optional[datetime] = None


@dataclass
class PagerDutyMessage:
    """Legacy PagerDuty message model."""
    id: str
    content: str
    created_at: Optional[datetime] = None


@dataclass
class PagerDutyV3Agent:
    """Legacy PagerDuty V3 agent model."""
    id: str
    type: str = "user"
    summary: str = ""


@dataclass
class PagerDutyV3Event:
    """Legacy PagerDuty V3 event model."""
    id: str
    event_type: str
    resource_type: str
    occurred_at: Optional[datetime] = None
    data: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PagerDutyV3WebhookPayload:
    """Legacy PagerDuty V3 webhook payload."""
    event: PagerDutyV3Event
    log_entries: List[PagerDutyLogEntry] = field(default_factory=list)


@dataclass
class PagerDutyWebhookPayload:
    """Legacy PagerDuty webhook payload."""
    messages: List[PagerDutyMessage] = field(default_factory=list)