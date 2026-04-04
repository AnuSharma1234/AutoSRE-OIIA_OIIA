import os
from app.schemas.analysis import RiskLevel
from app.schemas.incident import AlertType

# Configurable thresholds from env (defaults per plan: 0.9)
LOW_THRESHOLD = float(os.getenv("AUTO_EXECUTE_LOW_THRESHOLD", "0.9"))
MEDIUM_THRESHOLD = float(os.getenv("AUTO_EXECUTE_MEDIUM_THRESHOLD", "0.9"))

# Commands that indicate LOW risk
LOW_RISK_COMMANDS = [
    "kubectl delete pod",
    "kubectl rollout restart",
]

# Commands that indicate MEDIUM risk
MEDIUM_RISK_COMMANDS = [
    "kubectl rollout undo",
]


def evaluate_risk(alert_type: AlertType, kubectl_command: str | None, confidence_score: float) -> RiskLevel:
    """Evaluate risk level for a given command."""
    if kubectl_command is None:
        return RiskLevel.LOW  # No remediation = monitoring only = low risk

    cmd = kubectl_command.strip()

    # HIGH: delete namespace or node
    if "delete" in cmd and ("namespace" in cmd or "node" in cmd):
        return RiskLevel.HIGH

    # MEDIUM: rollout undo
    if "kubectl rollout undo" in cmd:
        return RiskLevel.MEDIUM

    # LOW: delete pod or rollout restart
    if any(pattern in cmd for pattern in LOW_RISK_COMMANDS):
        return RiskLevel.LOW

    # MEDIUM: any other kubectl command (edge case)
    if cmd.startswith("kubectl "):
        return RiskLevel.MEDIUM

    # HIGH: non-kubectl commands or anything else
    return RiskLevel.HIGH


def should_auto_execute(risk_level: RiskLevel, confidence_score: float) -> bool:
    """Determine if action should auto-execute without human approval."""
    if confidence_score < 0.0 or confidence_score > 1.0:
        return False

    if risk_level == RiskLevel.HIGH:
        return False  # Never auto-execute HIGH risk

    if risk_level == RiskLevel.LOW:
        return confidence_score >= LOW_THRESHOLD

    if risk_level == RiskLevel.MEDIUM:
        return confidence_score >= MEDIUM_THRESHOLD

    return False
