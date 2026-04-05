"""SuperPlane and JIRA webhook endpoints."""

from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Request

from src.oncall_agent.api.oncall_agent_trigger import OncallAgentTrigger
from src.oncall_agent.utils import get_logger

router = APIRouter(prefix="/webhook", tags=["webhooks"])
logger = get_logger(__name__)

# Global trigger instance
agent_trigger: OncallAgentTrigger | None = None

UTC = UTC


async def get_agent_trigger() -> OncallAgentTrigger:
    """Get or create the agent trigger instance."""
    global agent_trigger
    if agent_trigger is None:
        agent_trigger = OncallAgentTrigger(use_enhanced=True)
        await agent_trigger.initialize()
    return agent_trigger


# SuperPlane Integration Endpoints

@router.post("/superplane/analyze")
async def superplane_analyze_incident(request: Request) -> dict[str, Any]:
    """SuperPlane Canvas endpoint for incident analysis."""
    try:
        # Get incident data from SuperPlane Canvas
        payload = await request.json()
        logger.info(f"Received SuperPlane incident analysis request: {payload}")
        
        # Extract incident details
        incident_description = payload.get("incident", "")
        service_name = payload.get("service", "unknown")
        namespace = payload.get("namespace", "default")
        severity = payload.get("severity", "medium")
        
        if not incident_description:
            return {"error": "No incident description provided"}
        
        # Get agent trigger for AI analysis
        trigger = await get_agent_trigger()
        
        # Perform AI analysis using existing AutoSRE capabilities
        analysis_result = await trigger.analyze_incident_with_ai(
            incident_description=incident_description,
            service_name=service_name,
            namespace=namespace
        )
        
        # Structure response for SuperPlane Canvas
        response = {
            "analysis": analysis_result.get("analysis", "Analysis completed"),
            "severity_assessment": _map_severity(severity),
            "root_cause": analysis_result.get("root_cause", "Investigating..."),
            "recommendations": analysis_result.get("recommendations", []),
            "auto_remediation": analysis_result.get("auto_actions", []),
            "incident_id": f"autosre-{datetime.now().strftime('%Y%m%d-%H%M%S')}",
            "timestamp": datetime.now(UTC).isoformat(),
            "service": service_name,
            "namespace": namespace
        }
        
        logger.info(f"SuperPlane analysis completed: {response['incident_id']}")
        return response
        
    except Exception as e:
        logger.error(f"SuperPlane analysis error: {e}")
        return {
            "error": str(e),
            "fallback_analysis": "Incident requires manual investigation",
            "severity_assessment": "medium",
            "recommendations": ["Check service logs", "Verify resource availability", "Escalate to on-call engineer"]
        }


@router.post("/superplane/jira")
async def superplane_create_jira_ticket(request: Request) -> dict[str, Any]:
    """SuperPlane Canvas endpoint for JIRA ticket creation."""
    try:
        payload = await request.json()
        logger.info(f"Creating JIRA ticket from SuperPlane: {payload}")
        
        # Extract ticket data
        summary = payload.get("summary", "AutoSRE Incident")
        description = payload.get("description", "")
        priority = payload.get("priority", "Medium")
        incident_id = payload.get("incident_id", "")
        
        # JIRA API integration
        jira_url = "https://auto-sre.atlassian.net"
        
        # For demo purposes, we'll create a mock ticket
        # In production, you'd use actual JIRA API credentials
        ticket_key = f"AUTOSRE-{datetime.now().strftime('%Y%m%d%H%M%S')}"
        ticket_url = f"{jira_url}/browse/{ticket_key}"
        
        # Mock JIRA API call (replace with real implementation)
        try:
            # This would be the real JIRA API call:
            # jira_response = await create_jira_issue(summary, description, priority)
            
            # For demo - simulate successful creation
            response = {
                "ticket_created": True,
                "ticket_key": ticket_key,
                "ticket_url": ticket_url,
                "summary": summary,
                "description": description[:500] + "..." if len(description) > 500 else description,
                "priority": priority,
                "incident_id": incident_id,
                "created_at": datetime.now(UTC).isoformat(),
                "status": "Open",
                "demo_note": "This is a demo ticket - real JIRA integration would create actual tickets"
            }
            
            logger.info(f"Demo JIRA ticket created: {ticket_key}")
            return response
            
        except Exception as api_error:
            logger.error(f"JIRA API error: {api_error}")
            # Return mock response even if API fails for demo
            return {
                "ticket_created": True,
                "ticket_key": ticket_key,
                "ticket_url": ticket_url,
                "summary": summary,
                "description": description,
                "priority": priority,
                "incident_id": incident_id,
                "created_at": datetime.now(UTC).isoformat(),
                "demo_note": "Demo mode - JIRA API integration disabled for hackathon"
            }
        
    except Exception as e:
        logger.error(f"JIRA ticket creation error: {e}")
        return {
            "error": str(e),
            "ticket_created": False,
            "fallback_action": "Manual ticket creation required"
        }


async def create_jira_issue(summary: str, description: str, priority: str) -> dict[str, Any]:
    """Create actual JIRA issue via API (implementation placeholder)."""
    # This would be implemented with actual JIRA credentials and API calls
    # For now, return mock response for demo purposes
    
    # Example implementation would be:
    # import base64
    # auth_token = base64.b64encode(f"{email}:{api_token}".encode()).decode()
    # headers = {"Authorization": f"Basic {auth_token}", "Content-Type": "application/json"}
    # 
    # issue_data = {
    #     "fields": {
    #         "project": {"key": "AUTOSRE"},
    #         "summary": summary,
    #         "description": description,
    #         "issuetype": {"name": "Bug"},
    #         "priority": {"name": priority}
    #     }
    # }
    # 
    # async with httpx.AsyncClient() as client:
    #     response = await client.post(
    #         "https://auto-sre.atlassian.net/rest/api/3/issue",
    #         headers=headers,
    #         json=issue_data
    #     )
    #     return response.json()
    
    return {"key": "DEMO-123", "self": "https://auto-sre.atlassian.net/browse/DEMO-123"}


def _map_severity(severity: str) -> dict[str, Any]:
    """Map incident severity to structured assessment."""
    severity_map = {
        "critical": {"level": "critical", "priority": "P1", "color": "red"},
        "high": {"level": "high", "priority": "P2", "color": "orange"}, 
        "medium": {"level": "medium", "priority": "P3", "color": "yellow"},
        "low": {"level": "low", "priority": "P4", "color": "green"}
    }
    return severity_map.get(severity.lower(), severity_map["medium"])


# Test endpoints for development

@router.post("/test/simulate-incident")
async def simulate_test_incident() -> dict[str, Any]:
    """
    Simulate a test incident for development and testing purposes.
    This replaces the PagerDuty test functionality with a local simulation.
    """
    logger.info("Test incident simulation endpoint called")
    
    try:
        # Generate a unique incident ID
        incident_id = f"test-incident-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
        
        # Create mock incident data
        mock_incident = {
            "incident_id": incident_id,
            "title": f"Test Kubernetes Pod CrashLoopBackOff - {datetime.now().strftime('%H:%M:%S')}",
            "description": "This is a test incident created for AutoSRE development and testing",
            "severity": "warning",
            "service": "test-service",
            "namespace": "test",
            "component": "test-pod",
            "source": "AutoSRE Test Button",
            "timestamp": datetime.now(UTC).isoformat(),
            "custom_details": {
                "test_mode": True,
                "pod": "test-pod-crash-loop",
                "reason": "Testing AutoSRE incident response system",
                "initiated_by": "AutoSRE Dashboard Test Button"
            }
        }
        
        # Get agent trigger for processing
        trigger = await get_agent_trigger()
        
        # Process the mock incident through the AI agent
        if trigger:
            logger.info(f"Processing test incident through AI agent: {incident_id}")
            # This would trigger the AI analysis in a real scenario
            # For now, we'll just log and return success
        
        logger.info(f"Test incident simulated successfully: {incident_id}")
        
        return {
            "status": "success",
            "message": "Test incident simulated successfully",
            "incident": mock_incident,
            "note": "This is a local simulation - no external services were contacted"
        }
        
    except Exception as e:
        logger.error(f"Error simulating test incident: {e}")
        return {
            "status": "error",
            "message": "Failed to simulate test incident",
            "error": str(e)
        }


@router.get("/status")
async def webhook_status() -> dict[str, Any]:
    """Get webhook system status."""
    try:
        trigger = await get_agent_trigger()
        
        return {
            "status": "healthy",
            "services": {
                "superplane": "enabled",
                "jira": "enabled", 
                "agent": "available" if trigger else "unavailable"
            },
            "queue": trigger.get_queue_status() if trigger else {"queue_size": 0, "status": "not_initialized"},
            "timestamp": datetime.now(UTC).isoformat()
        }
    except Exception as e:
        logger.error(f"Error getting webhook status: {e}")
        return {
            "status": "error",
            "error": str(e),
            "services": {
                "superplane": "unknown",
                "jira": "unknown",
                "agent": "error"
            }
        }