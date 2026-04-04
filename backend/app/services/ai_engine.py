import os
import json
import asyncio
import google.generativeai as genai
from app.schemas.analysis import AIAnalysisResponse, RiskLevel
from app.schemas.incident import AlertType, K8sContext

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY") or os.getenv("GEMENI_API_KEY")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-1.5-pro")
TIMEOUT_SECONDS = 60
MAX_RETRIES = 3

SYSTEM_PROMPT = """You are AutoSRE, an expert Site Reliability Engineer. Analyze the Kubernetes incident and respond with ONLY a valid JSON object. No markdown, no explanation, just the JSON.

Required JSON fields:
- "root_cause" (string): Brief explanation of the root cause
- "suggested_action" (string): Recommended remediation action
- "kubectl_command" (string or null): Safe kubectl command to execute, or null if no remediation needed
- "confidence_score" (float 0.0-1.0): Your confidence in this analysis
- "risk_level" (string): LOW, MEDIUM, or HIGH risk of the suggested action

Rules:
- Only suggest kubectl commands that are in the whitelist (delete pod, rollout restart, rollout undo)
- NEVER suggest exec, scale to 0, or cluster-destructive commands
- If unsure, set confidence to 0.5 or lower and risk to HIGH
- kubectl_command must be null if no safe remediation exists
"""

if not GEMINI_API_KEY:
    raise RuntimeError("GEMINI_API_KEY environment variable is not set")

genai.configure(api_key=GEMINI_API_KEY)

def _build_prompt(alert_type: str, cluster_id: str, metadata: dict, context: K8sContext) -> str:
    """Build the user prompt for Gemini."""
    pod_logs = context.pod_logs[:2000] if context.pod_logs else "No logs available"
    events = "\n".join([
        f"- {e.get('type', 'Unknown')}: {e.get('reason', '')}: {e.get('message', '')}"
        for e in (context.events or [])[:10]
    ])
    if not events:
        events = "No events available"

    container_info = json.dumps(context.container_status, indent=2) if context.container_status else "No container status"
    deployment_info = json.dumps(context.deployment_config, indent=2) if context.deployment_config else "No deployment info"

    return f"""Analyze this Kubernetes incident:

Alert Type: {alert_type}
Cluster ID: {cluster_id}
Metadata: {json.dumps(metadata)}

Kubernetes Context:
Pod Logs (last 200 lines):
{pod_logs}

Recent Events:
{events}

Container Status:
{container_info}

Deployment Config:
{deployment_info}

Respond with ONLY JSON."""


async def analyze_incident(
    incident_data: dict,
    k8s_context: K8sContext,
) -> AIAnalysisResponse:
    """
    Send incident data to Gemini for root cause analysis.
    Returns AIAnalysisResponse with root_cause, suggested_action, kubectl_command, confidence_score, risk_level.
    Falls back to safe defaults on error.
    """
    alert_type = incident_data.get("alert_type", "UNKNOWN")
    cluster_id = incident_data.get("cluster_id", "unknown")
    metadata = incident_data.get("metadata", {})
    user_prompt = _build_prompt(alert_type, cluster_id, metadata, k8s_context)

    model = genai.GenerativeModel(
        model_name=GEMINI_MODEL,
        system_instruction=SYSTEM_PROMPT,
    )

    for attempt in range(MAX_RETRIES):
        try:
            response = await asyncio.wait_for(
                model.generate_content_async(
                    user_prompt,
                    generation_config=genai.types.GenerationConfig(
                        temperature=0.0,
                    )
                ),
                timeout=TIMEOUT_SECONDS,
            )

            raw_text = response.text.strip()
            # Strip markdown code blocks if present
            if raw_text.startswith("```"):
                raw_text = "\n".join(raw_text.split("\n")[1:-1])

            data = json.loads(raw_text)

            return AIAnalysisResponse(
                root_cause=data.get("root_cause", "Analysis failed"),
                suggested_action=data.get("suggested_action", "Monitor and escalate"),
                kubectl_command=data.get("kubectl_command"),
                confidence_score=float(data.get("confidence_score", 0.0)),
                risk_level=RiskLevel(data.get("risk_level", "HIGH")),
            )

        except (json.JSONDecodeError, asyncio.TimeoutError, Exception) as e:
            if attempt == MAX_RETRIES - 1:
                # Fallback on final failure
                return AIAnalysisResponse(
                    root_cause="Gemini analysis failed after all retries",
                    suggested_action="Manual investigation required",
                    kubectl_command=None,
                    confidence_score=0.0,
                    risk_level=RiskLevel.HIGH,
                )
            await asyncio.sleep(2 ** attempt)  # Exponential backoff

    # Should not reach here, but fallback
    return AIAnalysisResponse(
        root_cause="Analysis unavailable",
        suggested_action="Manual investigation required",
        kubectl_command=None,
        confidence_score=0.0,
        risk_level=RiskLevel.HIGH,
    )
