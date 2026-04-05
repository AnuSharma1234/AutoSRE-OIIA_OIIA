"""API endpoints for JIRA insights and analysis (AutoSRE v2.0)."""

from datetime import datetime, timedelta
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse

from src.oncall_agent.utils import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/insights", tags=["insights"])


@router.get("/analysis")
async def get_incident_analysis(
    days: int = Query(30, description="Number of days to analyze", ge=1, le=90)
) -> JSONResponse:
    """Get incident analysis and insights from JIRA tickets (AutoSRE v2.0)."""
    try:
        # Mock JIRA analysis data for AutoSRE v2.0 demo
        mock_analysis = {
            "total_incidents": 42,
            "resolved_incidents": 38,
            "avg_resolution_time": "12.5 minutes",
            "success_rate": 90.5,
            "top_issues": [
                {"type": "Kubernetes Pod Crashes", "count": 15, "avg_fix_time": "8.2 min"},
                {"type": "Database Connection Issues", "count": 12, "avg_fix_time": "15.1 min"},
                {"type": "Memory/OOM Issues", "count": 8, "avg_fix_time": "6.7 min"},
                {"type": "Network Latency", "count": 7, "avg_fix_time": "18.3 min"}
            ],
            "ai_remediation_stats": {
                "auto_resolved": 34,
                "manual_intervention": 8,
                "success_rate": 81.0
            },
            "period": f"Last {days} days",
            "generated_at": datetime.now().isoformat()
        }

        return JSONResponse(content={
            "success": True,
            "data": mock_analysis
        })

    except Exception as e:
        logger.error(f"Error getting incident analysis: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/report")
async def get_incident_report() -> JSONResponse:
    """Get a formatted incident report (AutoSRE v2.0)."""
    try:
        # Mock JIRA report for AutoSRE v2.0 demo
        mock_report = """# AutoSRE v2.0 Incident Report

## Summary
- **Total Incidents**: 42
- **Resolution Rate**: 90.5%
- **Average Resolution Time**: 12.5 minutes
- **AI Auto-Resolution**: 81%

## Top Incident Types
1. **Kubernetes Pod Crashes** (15 incidents) - Avg Fix: 8.2 min
2. **Database Connection Issues** (12 incidents) - Avg Fix: 15.1 min  
3. **Memory/OOM Issues** (8 incidents) - Avg Fix: 6.7 min
4. **Network Latency** (7 incidents) - Avg Fix: 18.3 min

## AI Performance
- **34 incidents** resolved automatically by AutoSRE
- **8 incidents** required manual intervention
- **Success rate improved 45%** since implementing AutoSRE

## Recommendations
- Consider increasing memory limits for high-usage pods
- Implement connection pooling for database services
- Add proactive monitoring for network latency spikes
"""

        return JSONResponse(content={
            "success": True,
            "report": mock_report,
            "format": "markdown"
        })

    except Exception as e:
        logger.error(f"Error generating report: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/recommendations")
async def get_recommendations() -> JSONResponse:
    """Get actionable recommendations based on incident patterns (AutoSRE v2.0)."""
    try:
        # Mock JIRA-based recommendations for AutoSRE v2.0 demo
        mock_recommendations = [
            {
                "id": 1,
                "recommendation": "Increase memory limits for high-usage pods to prevent OOM kills",
                "priority": "high",
                "category": "resource_optimization"
            },
            {
                "id": 2,
                "recommendation": "Implement database connection pooling to reduce connection timeouts",
                "priority": "high", 
                "category": "database_performance"
            },
            {
                "id": 3,
                "recommendation": "Add proactive health checks for critical services",
                "priority": "medium",
                "category": "monitoring"
            },
            {
                "id": 4,
                "recommendation": "Set up automated scaling for pods experiencing frequent restarts",
                "priority": "medium",
                "category": "auto_scaling"
            },
            {
                "id": 5,
                "recommendation": "Configure network policies to reduce latency between services",
                "priority": "low",
                "category": "networking"
            }
        ]

        return JSONResponse(content={
            "success": True,
            "total_incidents_analyzed": 42,
            "recommendations": mock_recommendations
        })

    except Exception as e:
        logger.error(f"Error getting recommendations: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/trends")
async def get_incident_trends() -> JSONResponse:
    """Get incident trends over time (AutoSRE v2.0)."""
    try:
        # Mock trend data for AutoSRE v2.0 demo
        mock_trends = []
        base_date = datetime.now() - timedelta(days=30)
        
        for i in range(30):
            current_date = base_date + timedelta(days=i)
            # Simulate varying incident counts
            incident_count = max(0, int(3 + 2 * (0.5 - abs(i - 15) / 30)))
            mock_trends.append({
                "date": current_date.strftime("%Y-%m-%d"),
                "incidents": incident_count,
                "resolved": max(0, incident_count - 1),
                "auto_resolved": max(0, int(incident_count * 0.8))
            })

        return JSONResponse(content={
            "success": True,
            "trends": mock_trends,
            "period_days": 30
        })

    except Exception as e:
        logger.error(f"Error getting trends: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/analyze-chaos")
async def analyze_chaos_results() -> JSONResponse:
    """Analyze results after chaos engineering session (AutoSRE v2.0)."""
    try:
        # Mock chaos analysis for AutoSRE v2.0 demo
        one_hour_ago = datetime.now() - timedelta(hours=1)
        
        mock_chaos_analysis = {
            "chaos_incidents_created": 5,
            "services_affected": ["web-app", "database", "api-gateway", "user-service", "payment-service"],
            "issue_types": ["Pod Crash", "OOM Kill", "Image Pull Error", "Service Unavailable", "Network Timeout"],
            "all_documented": True,
            "resolution_time": "8.3 minutes average",
            "auto_resolved": 4,
            "manual_intervention": 1,
            "success_rate": 80.0,
            "incidents": [
                {
                    "id": f"chaos-{int(datetime.now().timestamp())}",
                    "service_name": "web-app",
                    "incident_type": "Pod Crash",
                    "status": "resolved",
                    "created_at": one_hour_ago.isoformat(),
                    "resolved_at": (one_hour_ago + timedelta(minutes=5)).isoformat()
                }
            ],
            "jira_tickets_created": 5,
            "analysis_timestamp": datetime.now().isoformat()
        }

        # Generate insights based on chaos results
        insights = []
        if mock_chaos_analysis["chaos_incidents_created"] == 0:
            insights.append("No incidents detected from recent chaos engineering")
        else:
            insights.append(f"Successfully documented {mock_chaos_analysis['chaos_incidents_created']} incidents from chaos engineering")
            insights.append("AutoSRE v2.0 demonstrated strong resilience with 80% auto-resolution rate")
            insights.append("JIRA tickets created for all incidents with AI-generated analysis")
            insights.append("SuperPlane Canvas successfully orchestrated end-to-end incident response")

        mock_chaos_analysis["insights"] = insights

        return JSONResponse(content={
            "success": True,
            "data": mock_chaos_analysis
        })

    except Exception as e:
        logger.error(f"Error analyzing chaos results: {e}")
        raise HTTPException(status_code=500, detail=str(e))
