"""
AutoSRE Enhanced Monitoring System
Advanced performance monitoring, health checks, and alerting
"""

import asyncio
import json
import psutil
import time
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, List, Optional, Any, Callable
import aiohttp
from prometheus_client import Counter, Histogram, Gauge, start_http_server, CollectorRegistry

from src.oncall_agent.utils.logger import get_logger
from src.oncall_agent.caching.cache_manager import cache_manager

logger = get_logger(__name__)


class HealthStatus(Enum):
    """Health check status levels."""
    HEALTHY = "healthy"
    WARNING = "warning"
    CRITICAL = "critical"
    UNKNOWN = "unknown"


class AlertSeverity(Enum):
    """Alert severity levels."""
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"
    EMERGENCY = "emergency"


@dataclass
class HealthCheck:
    """Represents a health check configuration."""
    name: str
    check_function: Callable
    interval_seconds: int
    timeout_seconds: int
    tags: List[str]
    critical: bool = False
    retries: int = 3
    
    def __post_init__(self):
        if self.tags is None:
            self.tags = []


@dataclass
class HealthResult:
    """Result of a health check."""
    check_name: str
    status: HealthStatus
    timestamp: float
    response_time_ms: float
    message: str
    details: Dict[str, Any] = None
    error: Optional[str] = None
    
    def __post_init__(self):
        if self.details is None:
            self.details = {}


@dataclass
class SystemMetrics:
    """System performance metrics."""
    timestamp: float
    cpu_usage_percent: float
    memory_usage_percent: float
    memory_available_mb: float
    disk_usage_percent: float
    disk_free_gb: float
    network_bytes_sent: int
    network_bytes_recv: int
    active_connections: int
    process_count: int
    load_average: List[float]
    
    @classmethod
    def collect_current_metrics(cls) -> 'SystemMetrics':
        """Collect current system metrics."""
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        network = psutil.net_io_counters()
        
        return cls(
            timestamp=time.time(),
            cpu_usage_percent=psutil.cpu_percent(interval=1),
            memory_usage_percent=memory.percent,
            memory_available_mb=memory.available / (1024 * 1024),
            disk_usage_percent=disk.percent,
            disk_free_gb=disk.free / (1024 * 1024 * 1024),
            network_bytes_sent=network.bytes_sent,
            network_bytes_recv=network.bytes_recv,
            active_connections=len(psutil.net_connections()),
            process_count=len(psutil.pids()),
            load_average=list(psutil.getloadavg()) if hasattr(psutil, 'getloadavg') else [0.0, 0.0, 0.0]
        )


@dataclass
class ApplicationMetrics:
    """Application-specific metrics."""
    timestamp: float
    active_incidents: int
    resolved_incidents_24h: int
    ai_agent_requests: int
    ai_agent_errors: int
    cache_hit_rate: float
    database_connections: int
    api_response_time_avg: float
    kubernetes_pods_healthy: int
    kubernetes_pods_total: int
    
    @property
    def ai_agent_error_rate(self) -> float:
        """Calculate AI agent error rate."""
        if self.ai_agent_requests == 0:
            return 0.0
        return (self.ai_agent_errors / self.ai_agent_requests) * 100
    
    @property
    def kubernetes_health_rate(self) -> float:
        """Calculate Kubernetes health rate."""
        if self.kubernetes_pods_total == 0:
            return 100.0
        return (self.kubernetes_pods_healthy / self.kubernetes_pods_total) * 100


@dataclass
class MonitoringAlert:
    """Monitoring alert definition."""
    alert_id: str
    name: str
    description: str
    severity: AlertSeverity
    threshold: float
    metric_name: str
    operator: str  # >, <, ==, !=
    duration_minutes: int
    tags: List[str]
    enabled: bool = True
    
    def evaluate(self, current_value: float, duration_violated: int) -> bool:
        """Evaluate if alert should trigger."""
        if not self.enabled:
            return False
        
        # Check threshold
        threshold_violated = False
        if self.operator == ">":
            threshold_violated = current_value > self.threshold
        elif self.operator == "<":
            threshold_violated = current_value < self.threshold
        elif self.operator == "==":
            threshold_violated = current_value == self.threshold
        elif self.operator == "!=":
            threshold_violated = current_value != self.threshold
        
        # Check duration
        return threshold_violated and duration_violated >= self.duration_minutes


class PrometheusMetrics:
    """Prometheus metrics collector."""
    
    def __init__(self):
        self.registry = CollectorRegistry()
        
        # System metrics
        self.cpu_usage = Gauge('autosre_cpu_usage_percent', 'CPU usage percentage', registry=self.registry)
        self.memory_usage = Gauge('autosre_memory_usage_percent', 'Memory usage percentage', registry=self.registry)
        self.disk_usage = Gauge('autosre_disk_usage_percent', 'Disk usage percentage', registry=self.registry)
        
        # Application metrics
        self.incident_counter = Counter('autosre_incidents_total', 'Total incidents', ['severity'], registry=self.registry)
        self.ai_requests = Counter('autosre_ai_requests_total', 'Total AI requests', ['model'], registry=self.registry)
        self.ai_errors = Counter('autosre_ai_errors_total', 'Total AI errors', ['model'], registry=self.registry)
        self.api_request_duration = Histogram('autosre_api_request_duration_seconds', 'API request duration', ['endpoint'], registry=self.registry)
        self.cache_operations = Counter('autosre_cache_operations_total', 'Cache operations', ['operation', 'level'], registry=self.registry)
        
        # Health check metrics
        self.health_check_duration = Histogram('autosre_health_check_duration_seconds', 'Health check duration', ['check_name'], registry=self.registry)
        self.health_check_status = Gauge('autosre_health_check_status', 'Health check status (1=healthy, 0=unhealthy)', ['check_name'], registry=self.registry)
        
    def update_system_metrics(self, metrics: SystemMetrics):
        """Update system metrics."""
        self.cpu_usage.set(metrics.cpu_usage_percent)
        self.memory_usage.set(metrics.memory_usage_percent)
        self.disk_usage.set(metrics.disk_usage_percent)
    
    def record_incident(self, severity: str):
        """Record incident occurrence."""
        self.incident_counter.labels(severity=severity).inc()
    
    def record_ai_request(self, model: str):
        """Record AI request."""
        self.ai_requests.labels(model=model).inc()
    
    def record_ai_error(self, model: str):
        """Record AI error."""
        self.ai_errors.labels(model=model).inc()
    
    def record_api_request(self, endpoint: str, duration: float):
        """Record API request duration."""
        self.api_request_duration.labels(endpoint=endpoint).observe(duration)
    
    def record_cache_operation(self, operation: str, level: str):
        """Record cache operation."""
        self.cache_operations.labels(operation=operation, level=level).inc()
    
    def record_health_check(self, check_name: str, duration: float, is_healthy: bool):
        """Record health check result."""
        self.health_check_duration.labels(check_name=check_name).observe(duration)
        self.health_check_status.labels(check_name=check_name).set(1 if is_healthy else 0)


class AutoSREMonitoringSystem:
    """Enhanced monitoring system for AutoSRE."""
    
    def __init__(self, prometheus_port: int = 8000):
        self.health_checks: Dict[str, HealthCheck] = {}
        self.health_results: Dict[str, List[HealthResult]] = {}
        self.system_metrics_history: List[SystemMetrics] = []
        self.app_metrics_history: List[ApplicationMetrics] = []
        self.alerts: Dict[str, MonitoringAlert] = {}
        self.alert_states: Dict[str, Dict[str, Any]] = {}  # Track alert state
        
        # Prometheus metrics
        self.prometheus = PrometheusMetrics()
        
        # Start Prometheus HTTP server
        try:
            start_http_server(prometheus_port, registry=self.prometheus.registry)
            logger.info(f"Prometheus metrics server started on port {prometheus_port}")
        except Exception as e:
            logger.error(f"Failed to start Prometheus server: {e}")
        
        # Background tasks
        self.monitoring_task = None
        self.is_running = False
        
        # Initialize default health checks and alerts
        self._initialize_default_checks()
        self._initialize_default_alerts()
        
        logger.info("AutoSRE Monitoring System initialized")
    
    def _initialize_default_checks(self):
        """Initialize default health checks."""
        # Database health check
        self.add_health_check(
            name="database",
            check_function=self._check_database_health,
            interval_seconds=30,
            timeout_seconds=5,
            tags=["database", "critical"],
            critical=True
        )
        
        # Cache health check
        self.add_health_check(
            name="cache",
            check_function=self._check_cache_health,
            interval_seconds=60,
            timeout_seconds=3,
            tags=["cache", "performance"]
        )
        
        # AI service health check
        self.add_health_check(
            name="ai_service",
            check_function=self._check_ai_service_health,
            interval_seconds=120,
            timeout_seconds=10,
            tags=["ai", "external"]
        )
        
        # Kubernetes health check
        self.add_health_check(
            name="kubernetes",
            check_function=self._check_kubernetes_health,
            interval_seconds=45,
            timeout_seconds=8,
            tags=["kubernetes", "infrastructure"],
            critical=True
        )
    
    def _initialize_default_alerts(self):
        """Initialize default monitoring alerts."""
        self.alerts.update({
            "high_cpu_usage": MonitoringAlert(
                alert_id="high_cpu_usage",
                name="High CPU Usage",
                description="CPU usage is above 80% for extended period",
                severity=AlertSeverity.WARNING,
                threshold=80.0,
                metric_name="cpu_usage_percent",
                operator=">",
                duration_minutes=5,
                tags=["system", "performance"]
            ),
            "critical_cpu_usage": MonitoringAlert(
                alert_id="critical_cpu_usage",
                name="Critical CPU Usage",
                description="CPU usage is above 95%",
                severity=AlertSeverity.CRITICAL,
                threshold=95.0,
                metric_name="cpu_usage_percent",
                operator=">",
                duration_minutes=1,
                tags=["system", "performance"]
            ),
            "high_memory_usage": MonitoringAlert(
                alert_id="high_memory_usage",
                name="High Memory Usage",
                description="Memory usage is above 85%",
                severity=AlertSeverity.WARNING,
                threshold=85.0,
                metric_name="memory_usage_percent",
                operator=">",
                duration_minutes=10,
                tags=["system", "memory"]
            ),
            "low_disk_space": MonitoringAlert(
                alert_id="low_disk_space",
                name="Low Disk Space",
                description="Disk usage is above 90%",
                severity=AlertSeverity.CRITICAL,
                threshold=90.0,
                metric_name="disk_usage_percent",
                operator=">",
                duration_minutes=5,
                tags=["system", "storage"]
            ),
            "high_ai_error_rate": MonitoringAlert(
                alert_id="high_ai_error_rate",
                name="High AI Error Rate",
                description="AI agent error rate is above 10%",
                severity=AlertSeverity.WARNING,
                threshold=10.0,
                metric_name="ai_agent_error_rate",
                operator=">",
                duration_minutes=15,
                tags=["ai", "reliability"]
            )
        })
        
        # Initialize alert states
        for alert_id in self.alerts:
            self.alert_states[alert_id] = {
                "is_active": False,
                "triggered_at": None,
                "violation_start": None,
                "last_notification": None
            }
    
    def add_health_check(
        self,
        name: str,
        check_function: Callable,
        interval_seconds: int,
        timeout_seconds: int = 5,
        tags: List[str] = None,
        critical: bool = False,
        retries: int = 3
    ):
        """Add a new health check."""
        self.health_checks[name] = HealthCheck(
            name=name,
            check_function=check_function,
            interval_seconds=interval_seconds,
            timeout_seconds=timeout_seconds,
            tags=tags or [],
            critical=critical,
            retries=retries
        )
        self.health_results[name] = []
        logger.info(f"Added health check: {name}")
    
    async def start_monitoring(self):
        """Start the monitoring system."""
        if self.is_running:
            logger.warning("Monitoring system is already running")
            return
        
        self.is_running = True
        self.monitoring_task = asyncio.create_task(self._monitoring_loop())
        logger.info("Monitoring system started")
    
    async def stop_monitoring(self):
        """Stop the monitoring system."""
        self.is_running = False
        if self.monitoring_task:
            self.monitoring_task.cancel()
            try:
                await self.monitoring_task
            except asyncio.CancelledError:
                pass
        logger.info("Monitoring system stopped")
    
    async def _monitoring_loop(self):
        """Main monitoring loop."""
        last_check_times = {name: 0 for name in self.health_checks}
        
        while self.is_running:
            try:
                current_time = time.time()
                
                # Collect system metrics
                system_metrics = SystemMetrics.collect_current_metrics()
                self.system_metrics_history.append(system_metrics)
                self.prometheus.update_system_metrics(system_metrics)
                
                # Keep only last 24 hours of metrics (assuming 1-minute intervals)
                if len(self.system_metrics_history) > 1440:
                    self.system_metrics_history = self.system_metrics_history[-1440:]
                
                # Collect application metrics
                app_metrics = await self._collect_application_metrics()
                self.app_metrics_history.append(app_metrics)
                
                if len(self.app_metrics_history) > 1440:
                    self.app_metrics_history = self.app_metrics_history[-1440:]
                
                # Run health checks
                for name, health_check in self.health_checks.items():
                    if current_time - last_check_times[name] >= health_check.interval_seconds:
                        asyncio.create_task(self._run_health_check(health_check))
                        last_check_times[name] = current_time
                
                # Evaluate alerts
                await self._evaluate_alerts(system_metrics, app_metrics)
                
                # Sleep for 1 second before next iteration
                await asyncio.sleep(1)
                
            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}")
                await asyncio.sleep(5)
    
    async def _run_health_check(self, health_check: HealthCheck):
        """Run a single health check."""
        start_time = time.time()
        attempts = 0
        
        while attempts < health_check.retries:
            try:
                # Run health check with timeout
                result = await asyncio.wait_for(
                    health_check.check_function(),
                    timeout=health_check.timeout_seconds
                )
                
                response_time = (time.time() - start_time) * 1000
                
                health_result = HealthResult(
                    check_name=health_check.name,
                    status=result.get("status", HealthStatus.UNKNOWN),
                    timestamp=time.time(),
                    response_time_ms=response_time,
                    message=result.get("message", ""),
                    details=result.get("details", {}),
                    error=result.get("error")
                )
                
                # Store result
                if health_check.name not in self.health_results:
                    self.health_results[health_check.name] = []
                
                self.health_results[health_check.name].append(health_result)
                
                # Keep only last 100 results per check
                if len(self.health_results[health_check.name]) > 100:
                    self.health_results[health_check.name] = self.health_results[health_check.name][-100:]
                
                # Update Prometheus metrics
                is_healthy = health_result.status == HealthStatus.HEALTHY
                self.prometheus.record_health_check(
                    health_check.name,
                    response_time / 1000,  # Convert to seconds
                    is_healthy
                )
                
                # Cache result
                await cache_manager.get_or_set(
                    f"health_check_{health_check.name}",
                    lambda: asdict(health_result),
                    cache_level='l1',
                    ttl=health_check.interval_seconds * 2,
                    tags=['health', 'monitoring']
                )
                
                break
                
            except asyncio.TimeoutError:
                attempts += 1
                if attempts >= health_check.retries:
                    # Create failure result
                    health_result = HealthResult(
                        check_name=health_check.name,
                        status=HealthStatus.CRITICAL,
                        timestamp=time.time(),
                        response_time_ms=(time.time() - start_time) * 1000,
                        message="Health check timed out",
                        error=f"Timeout after {health_check.timeout_seconds} seconds"
                    )
                    
                    self.health_results[health_check.name].append(health_result)
                    self.prometheus.record_health_check(health_check.name, health_check.timeout_seconds, False)
            
            except Exception as e:
                attempts += 1
                if attempts >= health_check.retries:
                    health_result = HealthResult(
                        check_name=health_check.name,
                        status=HealthStatus.CRITICAL,
                        timestamp=time.time(),
                        response_time_ms=(time.time() - start_time) * 1000,
                        message="Health check failed",
                        error=str(e)
                    )
                    
                    self.health_results[health_check.name].append(health_result)
                    self.prometheus.record_health_check(health_check.name, 0, False)
                    logger.error(f"Health check {health_check.name} failed: {e}")
    
    async def _collect_application_metrics(self) -> ApplicationMetrics:
        """Collect application-specific metrics."""
        # This would integrate with your actual services
        # For now, return mock data
        return ApplicationMetrics(
            timestamp=time.time(),
            active_incidents=5,
            resolved_incidents_24h=23,
            ai_agent_requests=1250,
            ai_agent_errors=15,
            cache_hit_rate=85.4,
            database_connections=12,
            api_response_time_avg=150.0,
            kubernetes_pods_healthy=18,
            kubernetes_pods_total=20
        )
    
    async def _evaluate_alerts(self, system_metrics: SystemMetrics, app_metrics: ApplicationMetrics):
        """Evaluate all alerts against current metrics."""
        current_values = {
            "cpu_usage_percent": system_metrics.cpu_usage_percent,
            "memory_usage_percent": system_metrics.memory_usage_percent,
            "disk_usage_percent": system_metrics.disk_usage_percent,
            "ai_agent_error_rate": app_metrics.ai_agent_error_rate
        }
        
        for alert_id, alert in self.alerts.items():
            if alert.metric_name not in current_values:
                continue
            
            current_value = current_values[alert.metric_name]
            alert_state = self.alert_states[alert_id]
            
            # Check if threshold is violated
            threshold_violated = False
            if alert.operator == ">":
                threshold_violated = current_value > alert.threshold
            elif alert.operator == "<":
                threshold_violated = current_value < alert.threshold
            
            if threshold_violated:
                if alert_state["violation_start"] is None:
                    alert_state["violation_start"] = time.time()
                
                # Check if duration threshold is met
                violation_duration = (time.time() - alert_state["violation_start"]) / 60  # minutes
                
                if violation_duration >= alert.duration_minutes and not alert_state["is_active"]:
                    # Trigger alert
                    alert_state["is_active"] = True
                    alert_state["triggered_at"] = time.time()
                    await self._trigger_alert(alert, current_value)
            else:
                # Reset alert state
                if alert_state["is_active"]:
                    await self._resolve_alert(alert)
                
                alert_state["is_active"] = False
                alert_state["violation_start"] = None
    
    async def _trigger_alert(self, alert: MonitoringAlert, current_value: float):
        """Trigger an alert."""
        logger.warning(f"Alert triggered: {alert.name} - Current value: {current_value}")
        
        # Store alert in cache for dashboard
        alert_data = {
            "alert_id": alert.alert_id,
            "name": alert.name,
            "description": alert.description,
            "severity": alert.severity.value,
            "current_value": current_value,
            "threshold": alert.threshold,
            "triggered_at": time.time(),
            "tags": alert.tags
        }
        
        await cache_manager.get_or_set(
            f"active_alert_{alert.alert_id}",
            lambda: alert_data,
            cache_level='l1',
            ttl=3600,
            tags=['alerts', 'monitoring']
        )
    
    async def _resolve_alert(self, alert: MonitoringAlert):
        """Resolve an active alert."""
        logger.info(f"Alert resolved: {alert.name}")
        
        # Remove from active alerts cache
        await cache_manager.l1_cache.delete(f"active_alert_{alert.alert_id}")
    
    # Health check implementations
    async def _check_database_health(self) -> Dict[str, Any]:
        """Check database connectivity."""
        try:
            # This would perform actual database health check
            # For now, simulate
            await asyncio.sleep(0.1)
            
            return {
                "status": HealthStatus.HEALTHY,
                "message": "Database connection healthy",
                "details": {
                    "connection_pool_size": 10,
                    "active_connections": 3
                }
            }
        except Exception as e:
            return {
                "status": HealthStatus.CRITICAL,
                "message": "Database connection failed",
                "error": str(e)
            }
    
    async def _check_cache_health(self) -> Dict[str, Any]:
        """Check cache system health."""
        try:
            cache_stats = await cache_manager.get_global_stats()
            
            return {
                "status": HealthStatus.HEALTHY,
                "message": f"Cache system healthy - {cache_stats['global_hit_rate']:.1f}% hit rate",
                "details": cache_stats
            }
        except Exception as e:
            return {
                "status": HealthStatus.WARNING,
                "message": "Cache system issues",
                "error": str(e)
            }
    
    async def _check_ai_service_health(self) -> Dict[str, Any]:
        """Check AI service availability."""
        try:
            # Simulate AI service health check
            await asyncio.sleep(0.2)
            
            return {
                "status": HealthStatus.HEALTHY,
                "message": "AI services operational",
                "details": {
                    "anthropic_available": True,
                    "openai_available": True,
                    "response_time_ms": 200
                }
            }
        except Exception as e:
            return {
                "status": HealthStatus.WARNING,
                "message": "AI service issues detected",
                "error": str(e)
            }
    
    async def _check_kubernetes_health(self) -> Dict[str, Any]:
        """Check Kubernetes cluster health."""
        try:
            # This would perform actual kubectl commands
            # For now, simulate
            await asyncio.sleep(0.3)
            
            return {
                "status": HealthStatus.HEALTHY,
                "message": "Kubernetes cluster healthy",
                "details": {
                    "nodes_ready": 3,
                    "pods_running": 18,
                    "pods_total": 20,
                    "cluster_version": "v1.28.0"
                }
            }
        except Exception as e:
            return {
                "status": HealthStatus.CRITICAL,
                "message": "Kubernetes cluster issues",
                "error": str(e)
            }
    
    async def get_monitoring_dashboard_data(self) -> Dict[str, Any]:
        """Get comprehensive monitoring dashboard data."""
        # Get latest metrics
        latest_system = self.system_metrics_history[-1] if self.system_metrics_history else None
        latest_app = self.app_metrics_history[-1] if self.app_metrics_history else None
        
        # Get health check summary
        health_summary = {}
        for check_name, results in self.health_results.items():
            if results:
                latest_result = results[-1]
                health_summary[check_name] = {
                    "status": latest_result.status.value,
                    "last_check": latest_result.timestamp,
                    "response_time": latest_result.response_time_ms,
                    "message": latest_result.message
                }
        
        # Get active alerts
        active_alerts = []
        for alert_id, state in self.alert_states.items():
            if state["is_active"]:
                alert = self.alerts[alert_id]
                active_alerts.append({
                    "alert_id": alert_id,
                    "name": alert.name,
                    "severity": alert.severity.value,
                    "description": alert.description,
                    "triggered_at": state["triggered_at"]
                })
        
        return {
            "timestamp": time.time(),
            "system_metrics": asdict(latest_system) if latest_system else None,
            "application_metrics": asdict(latest_app) if latest_app else None,
            "health_checks": health_summary,
            "active_alerts": active_alerts,
            "alert_summary": {
                "total_alerts": len(self.alerts),
                "active_alerts": len(active_alerts),
                "critical_alerts": len([a for a in active_alerts if a["severity"] == "critical"]),
                "warning_alerts": len([a for a in active_alerts if a["severity"] == "warning"])
            },
            "uptime_seconds": time.time() - (self.system_metrics_history[0].timestamp if self.system_metrics_history else time.time())
        }


# Global monitoring system instance
monitoring_system = AutoSREMonitoringSystem()