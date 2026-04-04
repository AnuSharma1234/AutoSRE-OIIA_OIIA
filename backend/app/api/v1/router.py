from fastapi import APIRouter
from app.api.v1 import incidents, execute, cluster, webhooks

api_router = APIRouter()

api_router.include_router(incidents.router, prefix="/incidents", tags=["incidents"])
api_router.include_router(execute.router, prefix="/execute", tags=["execute"])
api_router.include_router(cluster.router, prefix="/cluster", tags=["cluster"])
api_router.include_router(webhooks.router, prefix="/webhooks", tags=["webhooks"])
