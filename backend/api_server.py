"""FastAPI server for webhook endpoints and API."""

import json
import logging
import os
import signal
import sys
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from src.oncall_agent.api import webhooks
from src.oncall_agent.api.routers import (
    # admin_integrations,  # Temporarily disabled - requires auth
    agent_logs,
    agent_router,
    alert_crud,
    alert_tracking,
    analytics_router,
    api_keys,
    chaos,
    dashboard_router,
    dev_config,
    incidents_router,
    insights,
    integrations_router,
    kubernetes_agno,
    kubernetes_improved,
    monitoring_router,
    # notion_activity,  # Removed - replaced with JIRA integration
    security_router,
    settings_router,
    # user_integrations,  # Temporarily disabled - requires auth
)
from src.oncall_agent.config import get_config
from src.oncall_agent.utils import get_logger, setup_logging

# Setup logging FIRST before creating any loggers
config = get_config()
setup_logging(level=config.log_level)

logger = get_logger(__name__)

# Log configuration for debugging
logger.info(f"Configuration loaded - NODE_ENV: {config.node_env}, ENVIRONMENT: {getattr(config, 'environment', 'not set')}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Handle application lifecycle events."""
    # Startup
    logger.info("Starting Oncall Agent API Server")
    logger.info(f"API Server running on {config.api_host}:{config.api_port}")
    logger.info(f"SuperPlane integration: {'enabled' if config.superplane_enabled else 'disabled'}")
    logger.info(f"SuperPlane webhook secret configured: {bool(config.superplane_webhook_secret)}")
    logger.info(f"JIRA integration: {'enabled' if config.jira_enabled else 'disabled'}")
    logger.info(f"Log level: {config.log_level}")

    # Initialize database connection
    postgres_url = config.postgres_url or config.database_url or getattr(config, 'neon_database_url', None)
    if postgres_url:
        try:
            from src.oncall_agent.services.incident_service import get_pool
            await get_pool()
            logger.info("PostgreSQL database connection pool initialized")

            # Initialize agent settings table
            from src.oncall_agent.services.agent_settings_service import init_agent_settings_table
            await init_agent_settings_table()
            logger.info("Agent settings table initialized")

            # Initialize dashboard tables for frontend data
            from src.oncall_agent.services.dashboard_sync_service import init_dashboard_tables
            await init_dashboard_tables()
            logger.info("Dashboard tables initialized")
        except Exception as e:
            logger.error(f"Failed to initialize database: {e}")
            logger.warning("Continuing without database persistence - data will be lost on restart!")
    else:
        logger.warning("No PostgreSQL URL configured - incidents will not be persisted!")

    # Initialize webhook handler
    if config.superplane_enabled:
        from src.oncall_agent.api.webhooks import get_agent_trigger
        trigger = await get_agent_trigger()
        logger.info("OncallAgent initialized for SuperPlane webhook handling")

    # Start Kubernetes MCP server if enabled
    if config.k8s_enabled and config.k8s_use_mcp_server:
        logger.info("Starting Kubernetes MCP server...")
        try:
            import asyncio
            import subprocess

            # Extract port from MCP server URL
            mcp_port = '8080'
            if config.k8s_mcp_server_url:
                parts = config.k8s_mcp_server_url.split(':')
                if len(parts) >= 3:
                    mcp_port = parts[-1]

            # Start the official MCP Kubernetes server
            env = os.environ.copy()
            env['K8S_MCP_SERVER_PORT'] = mcp_port

            # Use the kubernetes-mcp-server by manusa with HTTP port
            mcp_process = subprocess.Popen(
                ['pnpm', 'exec', 'kubernetes-mcp-server', '--http-port', mcp_port],
                env=env
            )
            app.state.mcp_process = mcp_process

            # Wait for server to start
            await asyncio.sleep(2)
            logger.info(f"Kubernetes MCP server started on port {mcp_port}")
        except Exception as e:
            logger.error(f"Failed to start Kubernetes MCP server: {e}")
            app.state.mcp_process = None

    yield

    # Shutdown
    logger.info("Shutting down Oncall Agent API Server")

    # Close database connection
    try:
        from src.oncall_agent.services.incident_service import close_pool
        await close_pool()
        logger.info("Database connection pool closed")
    except Exception as e:
        logger.error(f"Error closing database pool: {e}")

    if config.superplane_enabled:
        from src.oncall_agent.api.webhooks import agent_trigger
        if agent_trigger:
            try:
                await agent_trigger.shutdown()
            except (RuntimeError, BaseExceptionGroup) as e:
                # Suppress common MCP shutdown errors that don't affect functionality
                if "cancel scope" in str(e) or "unhandled errors in a TaskGroup" in str(e):
                    logger.debug(f"Suppressed MCP shutdown error (harmless): {e}")
                else:
                    logger.warning(f"Agent shutdown warning: {e}")
            except Exception as e:
                logger.error(f"Error shutting down agent: {e}")

    # Stop MCP server if running
    if hasattr(app.state, 'mcp_process') and app.state.mcp_process:
        logger.info("Stopping Kubernetes MCP server...")
        try:
            app.state.mcp_process.terminate()
            app.state.mcp_process.wait(timeout=5)
        except:
            app.state.mcp_process.kill()


# Create FastAPI app
# NOTE: redirect_slashes=False prevents 307 redirects that cause CORS issues
# When frontend calls /api/v1/agent/config/ FastAPI would redirect to /api/v1/agent/config
# but the redirect loses the port, going to port 80 (K3s ingress) instead of 8001
app = FastAPI(
    title="AutoSRE API",
    description="Autonomous Site Reliability Engineering platform. AI-powered infrastructure management with intelligent incident response and automated remediation capabilities.",
    version="2.0.0",
    lifespan=lifespan,
    redirect_slashes=False
)

# Add CORS middleware
origins = config.cors_origins.split(",") if hasattr(config, 'cors_origins') else ["http://localhost:3000"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Add request logging middleware - MUST be added BEFORE CORS to ensure proper order
async def log_requests(request: Request, call_next):
    """Log all incoming requests for debugging."""
    # Log request details
    logger.info(f"Incoming request: {request.method} {request.url.path}")

    # Skip body reading for OPTIONS requests to prevent interference with CORS
    if request.method == "OPTIONS":
        response = await call_next(request)
        return response

    # Note: Auth logging removed - auth is handled by authentik reverse proxy

    # Log webhook requests in detail
    if request.url.path.startswith("/webhook/superplane"):
        body = await request.body()
        logger.info(f"SuperPlane webhook headers: {dict(request.headers)}")
        try:
            payload = json.loads(body) if body else {}
            # logger.info(f"SuperPlane webhook payload: {json.dumps(payload, indent=2)}")
        except:
            logger.info(f"SuperPlane webhook raw body: {body}")

        # Important: Create a new request with the body we read
        from starlette.requests import Request as StarletteRequest

        async def receive():
            return {"type": "http.request", "body": body}

        request = StarletteRequest(
            scope=request.scope,
            receive=receive
        )

    response = await call_next(request)
    return response


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "service": "Oncall Agent API",
        "version": "0.1.0",
        "status": "healthy",
        "features": {
            "superplane_webhooks": config.superplane_enabled,
            "kubernetes_integration": config.k8s_enabled,
            "jira_integration": config.jira_enabled,
        }
    }


@app.get("/routes")
async def list_routes():
    """List all registered routes for debugging."""
    routes = []
    for route in app.routes:
        if hasattr(route, "path") and hasattr(route, "methods"):
            routes.append({
                "path": getattr(route, "path", ""),
                "methods": list(getattr(route, "methods", set())),
                "name": getattr(route, "name", "")
            })
    return {"routes": sorted(routes, key=lambda x: x["path"])}



@app.get("/health")
async def health_check():
    """Health check endpoint."""
    health_status = {
        "status": "healthy",
        "checks": {
            "api": "ok",
            "config": "ok",
            "superplane_enabled": config.superplane_enabled,
            "jira_enabled": config.jira_enabled,
        }
    }

    # Check database connection
    try:
        from src.oncall_agent.services.incident_service import check_database_health
        db_health = await check_database_health()
        health_status["checks"]["database"] = db_health["status"]
        if db_health.get("connected"):
            health_status["checks"]["incident_count"] = db_health.get("incident_count", 0)
        elif db_health.get("error"):
            health_status["checks"]["database_error"] = db_health["error"]
            health_status["status"] = "degraded"
    except Exception as e:
        health_status["checks"]["database"] = f"error: {str(e)}"
        health_status["status"] = "degraded"

    # Check agent if initialized
    if config.superplane_enabled:
        try:
            from src.oncall_agent.api.webhooks import agent_trigger
            if agent_trigger:
                queue_status = agent_trigger.get_queue_status()
                health_status["checks"]["agent"] = "ok"
                health_status["checks"]["queue_size"] = queue_status["queue_size"]

                # Check K8s MCP integration status (with timeout to avoid blocking health checks)
                if agent_trigger.agent and hasattr(agent_trigger.agent, 'mcp_integrations'):
                    k8s_integration = agent_trigger.agent.mcp_integrations.get('kubernetes')
                    if k8s_integration:
                        try:
                            import asyncio
                            # Use 3 second timeout to avoid blocking health checks
                            k8s_healthy = await asyncio.wait_for(
                                k8s_integration.health_check(),
                                timeout=3.0
                            )
                            health_status["checks"]["k8s_mcp"] = "connected" if k8s_healthy else "disconnected"
                        except asyncio.TimeoutError:
                            health_status["checks"]["k8s_mcp"] = "timeout"
                        except Exception as k8s_err:
                            health_status["checks"]["k8s_mcp"] = f"error: {str(k8s_err)}"
                    else:
                        health_status["checks"]["k8s_mcp"] = "not_configured"
                else:
                    health_status["checks"]["k8s_mcp"] = "agent_not_ready"
            else:
                health_status["checks"]["agent"] = "not_initialized"
                health_status["checks"]["k8s_mcp"] = "agent_not_initialized"
        except Exception as e:
            health_status["checks"]["agent"] = f"error: {str(e)}"
            health_status["status"] = "degraded"

    return health_status


@app.get("/metrics")
async def prometheus_metrics():
    """Prometheus metrics endpoint."""
    from src.oncall_agent.metrics import get_metrics
    return get_metrics()


@app.get("/integrations")
async def get_mcp_integrations():
    """Get MCP integration status for frontend."""
    try:
        integrations = []

        # Define all available MCP integrations for AutoSRE v2.0
        available_mcp_integrations = {
            "kubernetes_mcp": {
                "name": "kubernetes_mcp",
                "display_name": "Kubernetes MCP",
                "description": "Kubernetes cluster management and monitoring with automated remediation",
                "capabilities": {
                    "context_types": ["pods", "deployments", "services", "events", "logs"],
                    "actions": ["restart_pod", "scale_deployment", "rollback_deployment", "execute_kubectl"],
                    "features": ["risk_assessment", "dry_run", "auto_approval"],
                    "execution_modes": ["direct", "dry_run", "approval_required"],
                    "risk_assessment": ["low", "medium", "high"],
                    "command_types": ["get", "describe", "logs", "version", "cluster-info", "top", "api-resources", "explain", "scale", "rollout", "restart", "label", "annotate", "set", "expose", "delete", "apply", "create", "replace", "patch", "edit", "exec", "port-forward", "proxy", "drain", "cordon", "uncordon"]
                }
            },
            "jira": {
                "name": "jira",
                "display_name": "JIRA Integration",
                "description": "JIRA ticket creation and incident tracking with AI-generated summaries",
                "capabilities": {
                    "context_types": ["tickets", "projects", "users", "workflows"],
                    "actions": ["create_ticket", "update_ticket", "transition_ticket", "add_comment"],
                    "features": ["incident_tracking", "automated_documentation", "ai_analysis"],
                    "ticket_operations": ["create", "update", "transition", "comment", "link"]
                }
            }
        }

        # Try to get agent instance for real status
        try:
            from src.oncall_agent.api.webhooks import agent_trigger, get_agent_trigger
            if agent_trigger and hasattr(agent_trigger, 'agent') and agent_trigger.agent:
                agent = agent_trigger.agent
            else:
                # Initialize agent if not already done
                trigger = await get_agent_trigger()
                agent = trigger.agent

            # Get real status from agent if available
            for mcp_name, mcp_info in available_mcp_integrations.items():
                try:
                    if agent and mcp_name in agent.mcp_integrations:
                        integration = agent.mcp_integrations[mcp_name]
                        is_healthy = await integration.health_check()
                        real_capabilities = await integration.get_capabilities()
                        integrations.append({
                            "name": mcp_name,
                            "display_name": mcp_info["display_name"],
                            "description": mcp_info["description"],
                            "capabilities": real_capabilities if real_capabilities else mcp_info["capabilities"],
                            "connected": is_healthy,
                            "configured": True
                        })
                    else:
                        # Show as available but not configured
                        integrations.append({
                            "name": mcp_name,
                            "display_name": mcp_info["display_name"],
                            "description": mcp_info["description"],
                            "capabilities": mcp_info["capabilities"],
                            "connected": False,
                            "configured": False
                        })
                except Exception as e:
                    logger.error(f"Error checking integration {mcp_name}: {e}")
                    integrations.append({
                        "name": mcp_name,
                        "display_name": mcp_info["display_name"],
                        "description": mcp_info["description"],
                        "capabilities": mcp_info["capabilities"],
                        "connected": False,
                        "configured": False
                    })
        except Exception as e:
            logger.error(f"Error getting agent instance: {e}")
            # Fallback: return all available integrations as not configured
            for mcp_name, mcp_info in available_mcp_integrations.items():
                integrations.append({
                    "name": mcp_name,
                    "display_name": mcp_info["display_name"],
                    "description": mcp_info["description"],
                    "capabilities": mcp_info["capabilities"],
                    "connected": False,
                    "configured": False
                })

        return {"integrations": integrations}
    except Exception as e:
        logger.error(f"Error getting MCP integrations: {e}")
        return {"integrations": []}


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global exception handler."""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "message": str(exc) if config.log_level == "DEBUG" else "An error occurred processing your request"
        }
    )


# Include routers
# Always include core routers
app.include_router(dashboard_router, prefix="/api/v1")
app.include_router(incidents_router, prefix="/api/v1")
app.include_router(agent_router, prefix="/api/v1")
app.include_router(agent_logs.router, prefix="/api/v1")
app.include_router(integrations_router, prefix="/api/v1")
app.include_router(insights.router, prefix="/api/v1")
# JIRA integration handled via SuperPlane Canvas
app.include_router(analytics_router, prefix="/api/v1")
app.include_router(security_router, prefix="/api/v1")
app.include_router(monitoring_router, prefix="/api/v1")
app.include_router(settings_router, prefix="/api/v1")
app.include_router(alert_tracking, prefix="/api/v1")
app.include_router(alert_crud, prefix="/api/v1")
app.include_router(api_keys.router)
# app.include_router(user_integrations.router)  # Already has /api/v1 prefix - Temporarily disabled (requires auth)
# app.include_router(admin_integrations.router)  # Admin integration verification routes - Temporarily disabled (requires auth)
app.include_router(kubernetes_agno.router)  # Kubernetes Agno MCP integration
app.include_router(kubernetes_improved.router)  # Improved Kubernetes integration with kubeconfig support

# Include dev config router only in development mode
if config.node_env == "development" or config.environment == "development":
    app.include_router(dev_config.router)
    app.include_router(chaos.router, prefix="/api/v1")
    logger.info("Dev config and chaos routes registered (development mode)")
else:
    logger.info(f"Dev routes not registered (node_env={config.node_env}, environment={config.environment})")

# Always include webhook router (includes SuperPlane endpoints)
app.include_router(webhooks.router)
logger.info("Webhook routes registered (SuperPlane + JIRA + Test Simulation)")

# Clean up legacy webhook registration comments

logger.info("All API routes registered successfully")

# Add request logging middleware AFTER routes are registered
@app.middleware("http")
async def log_requests_middleware(request: Request, call_next):
    """Log all incoming requests for debugging."""
    return await log_requests(request, call_next)

# Mount Socket.IO application - TEMPORARILY DISABLED
# app.mount("/socket.io", socket_app)
# logger.info("Socket.IO server mounted at /socket.io")


def signal_handler(sig, frame):
    """Handle shutdown signals gracefully."""
    logger.info(f"Received signal {sig}, shutting down...")
    sys.exit(0)


def main():
    """Run the API server."""
    # Setup signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Filter out ONLY WebSocket connection logs
    class WebSocketFilter(logging.Filter):
        def filter(self, record):
            # Filter out WebSocket connection messages ONLY
            msg = record.getMessage()
            if "/socket.io/" in msg and ("WebSocket" in msg or "connection" in msg):
                return False
            # Allow all other logs including SuperPlane webhooks
            return True

    # Apply filter to uvicorn access logger
    uvicorn_access = logging.getLogger("uvicorn.access")
    uvicorn_access.addFilter(WebSocketFilter())

    # Get port from environment variable or use default
    port = int(os.environ.get("PORT", config.api_port))

    # Run server
    uvicorn.run(
        "api_server:app",
        host="0.0.0.0",  # Bind to all interfaces for Render
        port=port,
        reload=config.api_reload,
        workers=config.api_workers if not config.api_reload else 1,
        log_level=config.api_log_level.lower(),
    )


if __name__ == "__main__":
    main()
