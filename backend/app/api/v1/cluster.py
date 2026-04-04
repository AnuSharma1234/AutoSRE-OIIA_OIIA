from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.models.incident import Incident
from app.schemas.incident import IncidentResponse, IncidentStatus, AlertType
from app.services.kubernetes import get_cluster_info

router = APIRouter()


@router.get("/overview")
async def get_cluster_overview(
    db: AsyncSession = Depends(get_db),
):
    """Return cluster overview: nodes, namespaces, pod summary, and recent incidents."""
    try:
        cluster_data = get_cluster_info()
    except Exception:
        cluster_data = {"nodes": [], "namespaces": [], "pod_summary": {"total": 0, "running": 0, "pending": 0, "failed": 0}}

    nodes = cluster_data.get("nodes", [])
    namespaces = cluster_data.get("namespaces", [])
    pod_summary = cluster_data.get("pod_summary", {"total": 0, "running": 0, "pending": 0, "failed": 0})

    query = (
        select(Incident)
        .order_by(Incident.created_at.desc())
        .limit(10)
    )
    result = await db.execute(query)
    incidents = result.scalars().all()

    recent_incidents = [
        {
            "id": str(i.id),
            "alert_type": i.alert_type,
            "status": i.status,
            "created_at": i.created_at.isoformat() if i.created_at else None,
        }
        for i in incidents
    ]

    return {
        "nodes": nodes,
        "namespaces": namespaces,
        "pod_summary": pod_summary,
        "recent_incidents": recent_incidents,
    }
