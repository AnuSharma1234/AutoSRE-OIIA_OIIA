import subprocess
import json
import os
import asyncio
from typing import Any

# KUBECONFIG env var (mounted from host: ~/.kube/config -> /root/.kube/config)
KUBECONFIG = os.getenv("KUBECONFIG", "/root/.kube/config")
CLUSTER_ID = os.getenv("CLUSTER_ID", "")
TIMEOUT_SECONDS = 30

def _run_kubectl(args: list[str]) -> tuple[str, str, int]:
    """Run kubectl command, return (stdout, stderr, returncode)."""
    env = os.environ.copy()
    env["KUBECONFIG"] = KUBECONFIG
    result = subprocess.run(
        ["kubectl"] + args,
        capture_output=True,
        text=True,
        timeout=TIMEOUT_SECONDS,
        env=env,
    )
    return result.stdout, result.stderr, result.returncode

def _run_kubectl_async(args: list[str]) -> tuple[str, str, int]:
    """Async version using asyncio subprocess."""
    env = os.environ.copy()
    env["KUBECONFIG"] = KUBECONFIG
    proc = yield asyncio.create_subprocess_exec(
        "kubectl", *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        env=env,
    )
    stdout, stderr = yield proc.communicate()
    return stdout.decode(), stderr.decode(), proc.returncode

def validate_cluster_context() -> bool:
    """Verify current-context matches CLUSTER_ID env var."""
    stdout, _, rc = _run_kubectl(["config", "current-context"])
    if rc != 0:
        raise RuntimeError(f"kubectl config current-context failed: {stdout}")
    current = stdout.strip()
    if CLUSTER_ID and current != CLUSTER_ID:
        raise RuntimeError(
            f"Cluster mismatch: current={current}, expected={CLUSTER_ID}. "
            f"Set CLUSTER_ID env var to match your kubeconfig context."
        )
    return True

def get_pod_logs(pod_name: str, namespace: str = "default") -> str:
    """Fetch pod logs, limited to last 200 lines."""
    stdout, stderr, rc = _run_kubectl(["logs", pod_name, "-n", namespace, "--tail=200"])
    if rc != 0:
        return f"Error fetching logs: {stderr}"
    return stdout

def get_deployment_config(deployment_name: str, namespace: str = "default") -> dict | None:
    """Get deployment YAML and parse to dict."""
    stdout, stderr, rc = _run_kubectl(
        ["get", "deployment", deployment_name, "-n", namespace, "-o", "json"]
    )
    if rc != 0:
        return None
    try:
        return json.loads(stdout)
    except json.JSONDecodeError:
        return None

def get_pod_events(pod_name: str, namespace: str = "default") -> list[dict]:
    """Get events related to a specific pod."""
    stdout, stderr, rc = _run_kubectl([
        "get", "events", "-n", namespace,
        "--field-selector", f"involvedObject.name={pod_name},involvedObject.kind=Pod",
        "--sort-by", ".lastTimestamp",
        "-o", "json",
    ])
    if rc != 0:
        return []
    try:
        data = json.loads(stdout)
        return data.get("items", [])
    except json.JSONDecodeError:
        return []

def get_container_status(pod_name: str, namespace: str = "default") -> dict | None:
    """Get container status for a pod."""
    stdout, stderr, rc = _run_kubectl([
        "get", "pod", pod_name, "-n", namespace, "-o", "json"
    ])
    if rc != 0:
        return None
    try:
        data = json.loads(stdout)
        return {
            "phase": data.get("status", {}).get("phase"),
            "conditions": data.get("status", {}).get("conditions", []),
            "container_statuses": data.get("status", {}).get("containerStatuses", []),
        }
    except json.JSONDecodeError:
        return None

def get_pods_in_namespace(namespace: str = "default") -> list[dict]:
    """List pods in namespace with status."""
    stdout, stderr, rc = _run_kubectl([
        "get", "pods", "-n", namespace, "-o", "json"
    ])
    if rc != 0:
        return []
    try:
        data = json.loads(stdout)
        return data.get("items", [])
    except json.JSONDecodeError:
        return []

def restart_pod(pod_name: str, namespace: str = "default") -> bool:
    """Delete pod to trigger restart. Returns True on success."""
    _, stderr, rc = _run_kubectl(["delete", "pod", pod_name, "-n", namespace])
    return rc == 0

def rollout_restart(deployment_name: str, namespace: str = "default") -> bool:
    """Execute kubectl rollout restart. Returns True on success."""
    _, stderr, rc = _run_kubectl([
        "rollout", "restart", f"deployment/{deployment_name}", "-n", namespace
    ])
    return rc == 0

def rollout_undo(deployment_name: str, namespace: str = "default") -> bool:
    """Execute kubectl rollout undo. Returns True on success."""
    _, stderr, rc = _run_kubectl([
        "rollout", "undo", f"deployment/{deployment_name}", "-n", namespace
    ])
    return rc == 0

def get_cluster_info() -> dict:
    """Get high-level cluster info: nodes, namespaces, pod summary."""
    # Get nodes
    stdout_n, _, rc_n = _run_kubectl(["get", "nodes", "-o", "json"])
    nodes = []
    if rc_n == 0:
        try:
            nodes_data = json.loads(stdout_n)
            for n in nodes_data.get("items", []):
                nodes.append({
                    "name": n.get("metadata", {}).get("name"),
                    "status": n.get("status", {}).get("phase"),
                    "roles": list(n.get("status", {}).get("nodeInfo", {}).keys()),
                })
        except json.JSONDecodeError:
            pass

    # Get namespaces
    stdout_ns, _, rc_ns = _run_kubectl(["get", "namespaces", "-o", "json"])
    namespaces = []
    if rc_ns == 0:
        try:
            ns_data = json.loads(stdout_ns)
            namespaces = [ns.get("metadata", {}).get("name") for ns in ns_data.get("items", [])]
        except json.JSONDecodeError:
            pass

    # Get pod counts across all namespaces
    total = running = pending = failed = 0
    for ns in namespaces[:10]:  # Check top 10 namespaces
        pods, _, _ = _run_kubectl(["get", "pods", "-n", ns, "--no-headers"])
        for line in pods.strip().split("\n"):
            if line:
                total += 1
                if "Running" in line:
                    running += 1
                elif "Pending" in line:
                    pending += 1
                elif "Failed" in line:
                    failed += 1

    return {
        "nodes": nodes,
        "namespaces": namespaces,
        "pod_summary": {"total": total, "running": running, "pending": pending, "failed": failed},
    }
