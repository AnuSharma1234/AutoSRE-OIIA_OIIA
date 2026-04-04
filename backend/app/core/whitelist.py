import re
import shlex

# Allowed kubectl command templates
ALLOWED_PATTERNS = [
    re.compile(r"^kubectl\s+delete\s+pod\s+\S+\s+-n\s+\S+(\s+--grace-period=\d+)?$"),
    re.compile(r"^kubectl\s+rollout\s+restart\s+deployment/\S+\s+-n\s+\S+$"),
    re.compile(r"^kubectl\s+rollout\s+undo\s+deployment/\S+\s+-n\s+\S+$"),
    re.compile(r"^kubectl\s+get\s+pods\s+-n\s+\S+\s+-o\s+json$"),
    re.compile(r"^kubectl\s+get\s+pods\s+-n\s+\S+\s+--no-headers$"),
    re.compile(r"^kubectl\s+get\s+events\s+-n\s+\S+\s+--sort-by=.lastTimestamp$"),
    re.compile(r"^kubectl\s+get\s+events\s+-n\s+\S+\s+--sort-by=.lastTimestamp\s+-o\s+json$"),
    re.compile(r"^kubectl\s+get\s+pod\s+\S+\s+-n\s+\S+\s+-o\s+json$"),
]

# Forbidden patterns (always blocked regardless of whitelist)
FORBIDDEN_PATTERNS = [
    "kubectl exec",
    "kubectl attach",
    "kubectl run --rm",
    "kubectl cp",
    "kubectl top",
    "kubectl drain",
    "kubectl taint",
    "kubectl label",
    "kubectl annotate",
    "kubectl api-resources",
    "kubectl debug",
    "kubectl proxy",
    "kubectl port-forward",
    "rm -rf",
    "&&",
    "|",
    ";",
    "$(",
    "`",
]


def sanitize_command(command: str) -> str:
    """Normalize and strip command string."""
    return " ".join(command.split())


def is_command_allowed(command: str) -> bool:
    """
    Validate kubectl command against whitelist.
    Returns True if command is allowed, False otherwise.
    """
    if not command or not command.strip():
        return False

    cmd = sanitize_command(command)

    # Block forbidden patterns first (security critical)
    for pattern in FORBIDDEN_PATTERNS:
        if pattern in cmd:
            return False

    # Block commands that delete beyond pod level
    if re.search(r"kubectl\s+delete\s+(namespace|node|deployment|statefulset|daemonset|ingress|service|configmap|secret)", cmd):
        return False

    # Block kubectl delete all
    if re.search(r"kubectl\s+delete\s+all", cmd):
        return False

    # Check against allowed patterns
    for pattern in ALLOWED_PATTERNS:
        if pattern.match(cmd):
            return True

    return False
