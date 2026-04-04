import subprocess
import os
import asyncio
from dataclasses import dataclass
from typing import Optional
from app.core.whitelist import is_command_allowed
from app.services.risk_engine import should_auto_execute
from app.schemas.analysis import AIAnalysisResponse, RiskLevel
from app.services.kubernetes import (
    restart_pod, rollout_restart, rollout_undo,
)
from app.schemas.incident import IncidentStatus

KUBECONFIG = os.getenv("KUBECONFIG", "/root/.kube/config")
TIMEOUT_SECONDS = 30
MAX_ATTEMPTS = 2


@dataclass
class CommandResult:
    success: bool
    output: str
    error: str
    command: str


def execute_command(kubectl_command: str) -> CommandResult:
    """Execute a single kubectl command. MUST be validated via whitelist first."""
    if not is_command_allowed(kubectl_command):
        return CommandResult(
            success=False,
            output="",
            error="Command not in whitelist",
            command=kubectl_command,
        )

    env = os.environ.copy()
    env["KUBECONFIG"] = KUBECONFIG

    try:
        result = subprocess.run(
            kubectl_command.split(),
            capture_output=True,
            text=True,
            timeout=TIMEOUT_SECONDS,
            env=env,
        )
        return CommandResult(
            success=result.returncode == 0,
            output=result.stdout,
            error=result.stderr,
            command=kubectl_command,
        )
    except subprocess.TimeoutExpired:
        return CommandResult(
            success=False,
            output="",
            error=f"Command timed out after {TIMEOUT_SECONDS}s",
            command=kubectl_command,
        )
    except Exception as e:
        return CommandResult(
            success=False,
            output="",
            error=str(e),
            command=kubectl_command,
        )


def _parse_kubectl_command(kubectl_command: str) -> tuple[Optional[str], Optional[str], Optional[str]]:
    """Parse command into (action, resource_type, name). Returns None if can't parse."""
    parts = kubectl_command.split()
    if len(parts) < 3:
        return None, None, None

    action = parts[1] if len(parts) > 1 else None
    # Handle "delete pod NAME" or "rollout restart TYPE/NAME"
    if action == "delete" and len(parts) > 2:
        resource_type = parts[2]
        name = parts[3] if len(parts) > 3 else None
    elif action == "rollout":
        sub_action = parts[2] if len(parts) > 2 else None
        target = parts[3] if len(parts) > 3 else None
        if target and "/" in target:
            resource_type, name = target.split("/", 1)
        else:
            return sub_action, None, None
    else:
        return None, None, None

    return action, resource_type, name


def _execute_via_wrapper(kubectl_command: str) -> CommandResult:
    """Execute common kubectl commands via Python wrappers (more reliable)."""
    action, resource_type, name = _parse_kubectl_command(kubectl_command)
    if not action or not name:
        return execute_command(kubectl_command)  # Fall back to subprocess

    namespace = "default"
    parts = kubectl_command.split("-n")
    if len(parts) > 1:
        namespace = parts[-1].split()[0].strip()

    try:
        if action == "delete" and resource_type == "pod":
            success = restart_pod(name, namespace)
            return CommandResult(success=success, output=f"Pod {name} deleted", error="", command=kubectl_command)
        elif action == "rollout" and resource_type in ("restart", "restart"):
            success = rollout_restart(name, namespace)
            return CommandResult(success=success, output=f"Rollout restart triggered for {name}", error="", command=kubectl_command)
        elif action == "undo":
            success = rollout_undo(name, namespace)
            return CommandResult(success=success, output=f"Rollout undo triggered for {name}", error="", command=kubectl_command)
    except Exception as e:
        return CommandResult(success=False, output="", error=str(e), command=kubectl_command)

    return execute_command(kubectl_command)


async def execute_remediation(
    incident_id: str,
    ai_analysis: AIAnalysisResponse,
    attempt_count: int = 0,
) -> tuple[bool, str, Optional[CommandResult]]:
    """
    Execute remediation for an incident.
    Returns (should_continue, status, result).
    If should_continue=True: action was taken or queued for approval.
    If should_continue=False: escalation needed.
    """
    if ai_analysis.kubectl_command is None:
        return True, IncidentStatus.MONITOR_ONLY.value, None

    if not is_command_allowed(ai_analysis.kubectl_command):
        return False, IncidentStatus.WHITELIST_BLOCKED.value, CommandResult(
            success=False,
            output="",
            error="Command rejected by whitelist",
            command=ai_analysis.kubectl_command,
        )

    # Check if should auto-execute
    auto_execute = should_auto_execute(ai_analysis.risk_level, ai_analysis.confidence_score)

    if not auto_execute:
        # Requires manual approval
        return True, IncidentStatus.APPROVAL_REQUIRED.value, None

    # Auto-execute
    # Retry once on failure
    for attempt in range(MAX_ATTEMPTS):
        result = _execute_via_wrapper(ai_analysis.kubectl_command)
        if result.success:
            return True, IncidentStatus.RESOLVED.value, result

        if attempt < MAX_ATTEMPTS - 1:
            await asyncio.sleep(5)  # Wait 5s before retry

    # After max attempts, escalate
    return False, IncidentStatus.ESCALATED.value, result
