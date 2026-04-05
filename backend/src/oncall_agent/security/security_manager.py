"""
AutoSRE Enhanced Security Module
Advanced security features including RBAC, audit logging, and threat detection
"""

import asyncio
import hashlib
import hmac
import json
import time
from dataclasses import dataclass, asdict
from enum import Enum
from typing import Dict, List, Optional, Set, Any
import jwt
from datetime import datetime, timedelta
import ipaddress

from src.oncall_agent.utils.logger import get_logger
from src.oncall_agent.caching.cache_manager import cache_manager

logger = get_logger(__name__)


class SecurityLevel(Enum):
    """Security clearance levels."""
    PUBLIC = 0
    INTERNAL = 1
    CONFIDENTIAL = 2
    RESTRICTED = 3
    TOP_SECRET = 4


class ActionType(Enum):
    """Types of actions for audit logging."""
    LOGIN = "login"
    LOGOUT = "logout"
    CREATE = "create"
    READ = "read"
    UPDATE = "update"
    DELETE = "delete"
    EXECUTE = "execute"
    ADMIN = "admin"
    SECURITY = "security"


@dataclass
class Permission:
    """Represents a permission with resource and action."""
    resource: str
    action: str
    conditions: Dict[str, Any] = None
    security_level: SecurityLevel = SecurityLevel.INTERNAL
    
    def __post_init__(self):
        if self.conditions is None:
            self.conditions = {}


@dataclass
class Role:
    """User role with associated permissions."""
    name: str
    permissions: List[Permission]
    description: str = ""
    is_admin: bool = False
    max_security_level: SecurityLevel = SecurityLevel.INTERNAL
    
    def has_permission(self, resource: str, action: str, security_level: SecurityLevel = SecurityLevel.INTERNAL) -> bool:
        """Check if role has specific permission."""
        # Admin roles have all permissions
        if self.is_admin:
            return True
        
        # Check security level
        if security_level.value > self.max_security_level.value:
            return False
        
        # Check specific permissions
        for perm in self.permissions:
            if (
                (perm.resource == "*" or perm.resource == resource) and
                (perm.action == "*" or perm.action == action) and
                perm.security_level.value >= security_level.value
            ):
                return True
        
        return False


@dataclass
class AuditEvent:
    """Audit log entry."""
    timestamp: float
    user_id: str
    user_email: str
    action: ActionType
    resource: str
    resource_id: Optional[str]
    ip_address: str
    user_agent: str
    success: bool
    error_message: Optional[str] = None
    additional_data: Dict[str, Any] = None
    risk_score: int = 0
    
    def __post_init__(self):
        if self.additional_data is None:
            self.additional_data = {}


@dataclass
class SecurityAlert:
    """Security threat alert."""
    alert_id: str
    timestamp: float
    severity: str  # low, medium, high, critical
    alert_type: str
    source_ip: str
    user_id: Optional[str]
    description: str
    indicators: List[str]
    mitigation_steps: List[str]
    auto_resolved: bool = False


class ThreatDetector:
    """Advanced threat detection system."""
    
    def __init__(self):
        self.suspicious_ips: Set[str] = set()
        self.failed_attempts: Dict[str, List[float]] = {}  # user_id -> timestamps
        self.rate_limits: Dict[str, List[float]] = {}  # ip -> timestamps
        self.known_attack_patterns = [
            "union select",
            "script>",
            "../../../",
            "cmd.exe",
            "/etc/passwd"
        ]
    
    async def analyze_request(self, user_id: str, ip_address: str, user_agent: str, endpoint: str, payload: str = "") -> List[SecurityAlert]:
        """Analyze request for security threats."""
        alerts = []
        
        # SQL Injection Detection
        payload_lower = payload.lower()
        for pattern in self.known_attack_patterns:
            if pattern in payload_lower:
                alerts.append(SecurityAlert(
                    alert_id=f"sql_injection_{int(time.time())}",
                    timestamp=time.time(),
                    severity="high",
                    alert_type="sql_injection_attempt",
                    source_ip=ip_address,
                    user_id=user_id,
                    description=f"Potential SQL injection attempt detected from {ip_address}",
                    indicators=[f"Pattern '{pattern}' found in payload"],
                    mitigation_steps=[
                        "Block IP address temporarily",
                        "Review user permissions",
                        "Alert security team"
                    ]
                ))
        
        # Rate Limiting Check
        now = time.time()
        if ip_address not in self.rate_limits:
            self.rate_limits[ip_address] = []
        
        # Clean old entries (last 5 minutes)
        self.rate_limits[ip_address] = [
            ts for ts in self.rate_limits[ip_address]
            if now - ts < 300
        ]
        
        self.rate_limits[ip_address].append(now)
        
        # Check if rate limit exceeded (more than 100 requests in 5 minutes)
        if len(self.rate_limits[ip_address]) > 100:
            alerts.append(SecurityAlert(
                alert_id=f"rate_limit_{int(time.time())}",
                timestamp=time.time(),
                severity="medium",
                alert_type="rate_limit_exceeded",
                source_ip=ip_address,
                user_id=user_id,
                description=f"Rate limit exceeded from {ip_address}",
                indicators=[f"{len(self.rate_limits[ip_address])} requests in 5 minutes"],
                mitigation_steps=[
                    "Implement temporary rate limiting",
                    "Monitor for continued abuse"
                ]
            ))
        
        # Suspicious User Agent Detection
        suspicious_agents = ["sqlmap", "nikto", "dirb", "gobuster", "burp"]
        if any(agent in user_agent.lower() for agent in suspicious_agents):
            alerts.append(SecurityAlert(
                alert_id=f"suspicious_agent_{int(time.time())}",
                timestamp=time.time(),
                severity="high",
                alert_type="suspicious_user_agent",
                source_ip=ip_address,
                user_id=user_id,
                description=f"Suspicious user agent detected: {user_agent}",
                indicators=[f"User agent: {user_agent}"],
                mitigation_steps=[
                    "Block user agent temporarily",
                    "Investigate further activity"
                ]
            ))
        
        return alerts
    
    async def track_failed_login(self, user_id: str, ip_address: str) -> Optional[SecurityAlert]:
        """Track failed login attempts."""
        now = time.time()
        
        if user_id not in self.failed_attempts:
            self.failed_attempts[user_id] = []
        
        # Clean old attempts (last 1 hour)
        self.failed_attempts[user_id] = [
            ts for ts in self.failed_attempts[user_id]
            if now - ts < 3600
        ]
        
        self.failed_attempts[user_id].append(now)
        
        # Check for brute force attempt (more than 5 failures in 1 hour)
        if len(self.failed_attempts[user_id]) > 5:
            return SecurityAlert(
                alert_id=f"brute_force_{int(time.time())}",
                timestamp=time.time(),
                severity="critical",
                alert_type="brute_force_attempt",
                source_ip=ip_address,
                user_id=user_id,
                description=f"Brute force login attempt detected for user {user_id}",
                indicators=[f"{len(self.failed_attempts[user_id])} failed attempts in 1 hour"],
                mitigation_steps=[
                    "Lock user account temporarily",
                    "Block IP address",
                    "Notify user of suspicious activity",
                    "Alert security team immediately"
                ]
            )
        
        return None


class AutoSRESecurityManager:
    """Enhanced security manager for AutoSRE."""
    
    def __init__(self):
        self.threat_detector = ThreatDetector()
        self.audit_events: List[AuditEvent] = []
        self.security_alerts: List[SecurityAlert] = []
        self.roles = self._initialize_roles()
        self.user_roles: Dict[str, List[str]] = {}  # user_id -> role_names
        
        logger.info("AutoSRE Security Manager initialized")
    
    def _initialize_roles(self) -> Dict[str, Role]:
        """Initialize default roles."""
        return {
            "admin": Role(
                name="admin",
                permissions=[],  # Admin has all permissions
                description="Full system administrator",
                is_admin=True,
                max_security_level=SecurityLevel.TOP_SECRET
            ),
            "sre_engineer": Role(
                name="sre_engineer",
                permissions=[
                    Permission("incidents", "*", security_level=SecurityLevel.CONFIDENTIAL),
                    Permission("monitoring", "*", security_level=SecurityLevel.CONFIDENTIAL),
                    Permission("kubernetes", "*", security_level=SecurityLevel.RESTRICTED),
                    Permission("ai_agent", "read", security_level=SecurityLevel.INTERNAL),
                    Permission("analytics", "read", security_level=SecurityLevel.INTERNAL)
                ],
                description="Site Reliability Engineer with operational access",
                max_security_level=SecurityLevel.RESTRICTED
            ),
            "developer": Role(
                name="developer",
                permissions=[
                    Permission("incidents", "read", security_level=SecurityLevel.INTERNAL),
                    Permission("monitoring", "read", security_level=SecurityLevel.INTERNAL),
                    Permission("analytics", "read", security_level=SecurityLevel.INTERNAL)
                ],
                description="Developer with read access to operational data",
                max_security_level=SecurityLevel.INTERNAL
            ),
            "viewer": Role(
                name="viewer",
                permissions=[
                    Permission("dashboard", "read", security_level=SecurityLevel.INTERNAL),
                    Permission("incidents", "read", security_level=SecurityLevel.INTERNAL)
                ],
                description="Read-only access to dashboards and incidents",
                max_security_level=SecurityLevel.INTERNAL
            )
        }
    
    async def authenticate_user(self, token: str) -> Optional[Dict[str, Any]]:
        """Authenticate user with JWT token."""
        try:
            # In production, use proper secret key management
            payload = jwt.decode(token, "your-secret-key", algorithms=["HS256"])
            
            user_data = {
                "user_id": payload.get("user_id"),
                "email": payload.get("email"),
                "roles": self.user_roles.get(payload.get("user_id"), ["viewer"])
            }
            
            return user_data
        
        except jwt.ExpiredSignatureError:
            logger.warning("Expired JWT token provided")
            return None
        except jwt.InvalidTokenError:
            logger.warning("Invalid JWT token provided")
            return None
    
    async def check_permission(
        self,
        user_id: str,
        resource: str,
        action: str,
        security_level: SecurityLevel = SecurityLevel.INTERNAL
    ) -> bool:
        """Check if user has permission for resource and action."""
        user_role_names = self.user_roles.get(user_id, ["viewer"])
        
        for role_name in user_role_names:
            if role_name in self.roles:
                role = self.roles[role_name]
                if role.has_permission(resource, action, security_level):
                    return True
        
        return False
    
    async def log_audit_event(
        self,
        user_id: str,
        user_email: str,
        action: ActionType,
        resource: str,
        resource_id: Optional[str],
        ip_address: str,
        user_agent: str,
        success: bool,
        error_message: Optional[str] = None,
        additional_data: Dict[str, Any] = None
    ) -> AuditEvent:
        """Log an audit event."""
        event = AuditEvent(
            timestamp=time.time(),
            user_id=user_id,
            user_email=user_email,
            action=action,
            resource=resource,
            resource_id=resource_id,
            ip_address=ip_address,
            user_agent=user_agent,
            success=success,
            error_message=error_message,
            additional_data=additional_data or {}
        )
        
        # Calculate risk score
        event.risk_score = await self._calculate_risk_score(event)
        
        # Store audit event
        self.audit_events.append(event)
        
        # Cache recent events
        await cache_manager.get_or_set(
            f"audit_event_{event.timestamp}",
            lambda: asdict(event),
            cache_level='l2',
            ttl=86400,  # 24 hours
            tags=['audit', 'security']
        )
        
        logger.info(f"Audit event logged: {action.value} on {resource} by {user_email}")
        
        return event
    
    async def _calculate_risk_score(self, event: AuditEvent) -> int:
        """Calculate risk score for audit event."""
        risk_score = 0
        
        # High-risk actions
        if event.action in [ActionType.DELETE, ActionType.ADMIN, ActionType.SECURITY]:
            risk_score += 30
        elif event.action in [ActionType.UPDATE, ActionType.EXECUTE]:
            risk_score += 20
        elif event.action == ActionType.CREATE:
            risk_score += 10
        
        # Failed actions increase risk
        if not event.success:
            risk_score += 25
        
        # High-risk resources
        high_risk_resources = ["users", "roles", "security", "kubernetes", "secrets"]
        if any(resource in event.resource for resource in high_risk_resources):
            risk_score += 20
        
        # Time-based risk (activity outside business hours)
        event_time = datetime.fromtimestamp(event.timestamp)
        if event_time.hour < 8 or event_time.hour > 18 or event_time.weekday() >= 5:
            risk_score += 10
        
        return min(risk_score, 100)  # Cap at 100
    
    async def analyze_security_threats(
        self,
        user_id: str,
        ip_address: str,
        user_agent: str,
        endpoint: str,
        payload: str = ""
    ) -> List[SecurityAlert]:
        """Analyze request for security threats."""
        alerts = await self.threat_detector.analyze_request(
            user_id, ip_address, user_agent, endpoint, payload
        )
        
        # Store alerts
        for alert in alerts:
            self.security_alerts.append(alert)
            
            # Cache alert for quick access
            await cache_manager.get_or_set(
                f"security_alert_{alert.alert_id}",
                lambda: asdict(alert),
                cache_level='l1',
                ttl=3600,  # 1 hour
                tags=['security', 'alerts']
            )
        
        return alerts
    
    async def get_audit_summary(self, hours: int = 24) -> Dict[str, Any]:
        """Get audit summary for specified time period."""
        cutoff_time = time.time() - (hours * 3600)
        recent_events = [e for e in self.audit_events if e.timestamp > cutoff_time]
        
        summary = {
            "total_events": len(recent_events),
            "successful_events": len([e for e in recent_events if e.success]),
            "failed_events": len([e for e in recent_events if not e.success]),
            "high_risk_events": len([e for e in recent_events if e.risk_score > 70]),
            "unique_users": len(set(e.user_id for e in recent_events)),
            "unique_ips": len(set(e.ip_address for e in recent_events)),
            "action_breakdown": {},
            "resource_breakdown": {},
            "top_risk_events": sorted(recent_events, key=lambda x: x.risk_score, reverse=True)[:10]
        }
        
        # Count actions and resources
        for event in recent_events:
            action = event.action.value
            resource = event.resource
            
            summary["action_breakdown"][action] = summary["action_breakdown"].get(action, 0) + 1
            summary["resource_breakdown"][resource] = summary["resource_breakdown"].get(resource, 0) + 1
        
        return summary
    
    async def get_security_dashboard_data(self) -> Dict[str, Any]:
        """Get security dashboard data."""
        # Recent alerts (last 24 hours)
        cutoff_time = time.time() - 86400
        recent_alerts = [a for a in self.security_alerts if a.timestamp > cutoff_time]
        
        # Risk metrics
        audit_summary = await self.get_audit_summary(24)
        
        return {
            "active_alerts": len([a for a in recent_alerts if not a.auto_resolved]),
            "total_alerts_24h": len(recent_alerts),
            "critical_alerts": len([a for a in recent_alerts if a.severity == "critical"]),
            "high_risk_events": audit_summary["high_risk_events"],
            "unique_threat_ips": len(set(a.source_ip for a in recent_alerts)),
            "threat_types": {
                alert_type: len([a for a in recent_alerts if a.alert_type == alert_type])
                for alert_type in set(a.alert_type for a in recent_alerts)
            },
            "recent_alerts": sorted(recent_alerts, key=lambda x: x.timestamp, reverse=True)[:10],
            "audit_summary": audit_summary
        }
    
    async def assign_role(self, user_id: str, role_name: str) -> bool:
        """Assign role to user."""
        if role_name not in self.roles:
            logger.error(f"Role {role_name} does not exist")
            return False
        
        if user_id not in self.user_roles:
            self.user_roles[user_id] = []
        
        if role_name not in self.user_roles[user_id]:
            self.user_roles[user_id].append(role_name)
            logger.info(f"Assigned role {role_name} to user {user_id}")
        
        return True
    
    async def revoke_role(self, user_id: str, role_name: str) -> bool:
        """Revoke role from user."""
        if user_id in self.user_roles and role_name in self.user_roles[user_id]:
            self.user_roles[user_id].remove(role_name)
            logger.info(f"Revoked role {role_name} from user {user_id}")
            return True
        
        return False


# Global security manager instance
security_manager = AutoSRESecurityManager()


def require_permission(resource: str, action: str, security_level: SecurityLevel = SecurityLevel.INTERNAL):
    """Decorator to require specific permission."""
    def decorator(func):
        async def wrapper(*args, **kwargs):
            # Extract user info from request context
            # This would be populated by authentication middleware
            user_id = kwargs.get('current_user_id')
            
            if not user_id:
                raise PermissionError("Authentication required")
            
            has_permission = await security_manager.check_permission(
                user_id, resource, action, security_level
            )
            
            if not has_permission:
                raise PermissionError(f"Insufficient permissions for {action} on {resource}")
            
            return await func(*args, **kwargs)
        return wrapper
    return decorator