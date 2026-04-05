"""Bridge between SuperPlane alerts and the AutoSRE agent."""

import asyncio
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from typing import Any

from src.oncall_agent.agent import OncallAgent, PagerAlert
from src.oncall_agent.agent_enhanced import EnhancedOncallAgent
# from src.oncall_agent.enhanced_agent import EnhancedOncallAgent as NewEnhancedAgent, EnhancedPagerAlert
from src.oncall_agent.api.alert_context_parser import ContextExtractor
from src.oncall_agent.api.log_streaming import log_stream_manager
from src.oncall_agent.api.models import PagerDutyIncidentData
from src.oncall_agent.config import get_config
from src.oncall_agent.utils import get_logger


class OncallAgentTrigger:
    """Manages triggering the oncall agent from external sources."""

    def __init__(self, agent: OncallAgent | None = None, use_enhanced: bool = True):
        self.logger = get_logger(__name__)
        self.config = get_config()
        self.agent = agent
        self.use_enhanced = use_enhanced
        self.context_extractor = ContextExtractor()

        # Thread pool for async execution
        self.executor = ThreadPoolExecutor(max_workers=5)

        # Queue for managing concurrent alerts
        self.alert_queue = asyncio.Queue(maxsize=100)
        self.processing_alerts = {}

        # Prompt templates
        self.prompt_templates = {
            'critical': """CRITICAL INCIDENT - IMMEDIATE ACTION REQUIRED
{context}

Please provide:
1. Immediate mitigation steps (under 5 minutes)
2. Root cause hypothesis
3. Impact assessment
4. Communication template for stakeholders""",

            'high': """HIGH PRIORITY INCIDENT
{context}

Please analyze and provide:
1. Diagnosis steps
2. Remediation actions
3. Monitoring recommendations
4. Prevention measures""",

            'medium': """INCIDENT ANALYSIS NEEDED
{context}

Please provide:
1. Issue analysis
2. Recommended actions
3. Long-term fixes""",

            'low': """LOW PRIORITY ALERT
{context}

Please provide brief analysis and recommendations."""
        }

    async def initialize(self):
        """Initialize the oncall agent if not provided."""
        if not self.agent:
            # Get current AI mode from agent config
            from src.oncall_agent.api.routers.agent import AGENT_CONFIG

            if self.use_enhanced and self.config.k8s_enabled:
                # Use enhanced agent with current AI mode for command execution
                self.agent = EnhancedOncallAgent(ai_mode=AGENT_CONFIG.mode)
                self.logger.info(f"EnhancedOncallAgent initialized with mode: {AGENT_CONFIG.mode.value}")
            else:
                # Use regular agent for read-only operations
                self.agent = OncallAgent()
                self.logger.info("OncallAgent initialized for trigger")

            await self.agent.connect_integrations()

    async def trigger_oncall_agent(self, pagerduty_incident: PagerDutyIncidentData,
                                  context: dict[str, Any] | None = None) -> dict[str, Any]:
        """
        Trigger the oncall agent with PagerDuty context.
        
        Args:
            pagerduty_incident: The PagerDuty incident data
            context: Additional context from the parser
            
        Returns:
            Dict containing agent response and metadata
        """
        try:
            # Extract alert and context
            pager_alert, extracted_context = self.context_extractor.extract_from_incident(pagerduty_incident)

            # Merge provided context with extracted context
            if context:
                extracted_context.update(context)

            # Check if already processing this alert
            if pager_alert.alert_id in self.processing_alerts:
                self.logger.warning(f"Alert {pager_alert.alert_id} already being processed")
                return {
                    "status": "duplicate",
                    "message": "Alert already being processed",
                    "alert_id": pager_alert.alert_id
                }

            # Mark as processing
            self.processing_alerts[pager_alert.alert_id] = datetime.now()

            # Emit structured log for AI agent activation
            await log_stream_manager.log_alert(
                f"🚨 AI AGENT ACTIVATED - Processing {pager_alert.description}",
                incident_id=pager_alert.alert_id,
                stage="activation",
                progress=0.0,
                metadata={
                    "severity": pager_alert.severity,
                    "source": pager_alert.service_name,
                    "service": extracted_context.get("service", "unknown")
                }
            )

            # Add custom prompt based on severity
            if extracted_context.get("suggested_prompt"):
                prompt_template = self.prompt_templates.get(
                    pager_alert.severity.lower(),
                    self.prompt_templates['medium']
                )
                enhanced_prompt = prompt_template.format(context=extracted_context["suggested_prompt"])
                pager_alert.metadata["custom_prompt"] = enhanced_prompt

            # Add extracted context to alert metadata
            pager_alert.metadata["extracted_context"] = extracted_context

            # Trigger the agent
            self.logger.info(f"Triggering oncall agent for alert {pager_alert.alert_id}")

            # Emit structured log for agent trigger
            await log_stream_manager.log_info(
                "🤖 ONCALL AGENT TRIGGERED",
                incident_id=pager_alert.alert_id,
                stage="agent_triggered",
                progress=0.2
            )

            # Run in background if queue is getting full
            if self.alert_queue.qsize() > 10:
                asyncio.create_task(self._process_alert_async(pager_alert))
                return {
                    "status": "queued",
                    "message": "Alert queued for processing",
                    "alert_id": pager_alert.alert_id,
                    "queue_size": self.alert_queue.qsize()
                }

            # Process immediately
            if not self.agent:
                await self.initialize()
            assert self.agent is not None
            self.logger.info("📨 Sending alert to Oncall Agent...")

            # Track processing time
            start_time = datetime.now()
            result = await self.agent.handle_pager_alert(pager_alert)
            processing_time = (datetime.now() - start_time).total_seconds()

            self.logger.info("✅ Agent processing complete")
            self.logger.info(f"📋 Agent Response Summary: {result.get('status', 'unknown')}")

            # Emit structured log for completion with full analysis
            await log_stream_manager.log_success(
                f"✅ AI ANALYSIS COMPLETE - {processing_time:.2f}s response time",
                incident_id=pager_alert.alert_id,
                stage="complete",
                progress=1.0,
                metadata={
                    "response_time": f"{processing_time:.2f}s",
                    "status": result.get("status", "unknown"),
                    "severity": result.get("severity", pager_alert.severity),
                    "actions_recommended": len(result.get("recommended_actions", [])) if isinstance(result.get("recommended_actions"), list) else 0,
                    "analysis": result.get("analysis", ""),
                    "parsed_analysis": result.get("parsed_analysis", {}),
                    "confidence_score": result.get("confidence_score", 0.85),
                    "risk_level": result.get("risk_level", "medium")
                }
            )

            # Clean up
            if pager_alert.alert_id in self.processing_alerts:
                del self.processing_alerts[pager_alert.alert_id]

            return {
                "status": "success",
                "alert_id": pager_alert.alert_id,
                "agent_response": result,
                "context": extracted_context,
                "processing_time": (datetime.now() - self.processing_alerts.get(pager_alert.alert_id, datetime.now())).total_seconds()
            }

        except TimeoutError:
            self.logger.error(f"Timeout processing alert {pagerduty_incident.id}")
            return {
                "status": "timeout",
                "message": "Agent processing timed out",
                "alert_id": pagerduty_incident.id
            }
        except Exception as e:
            self.logger.error(f"Error triggering oncall agent: {e}", exc_info=True)
            return {
                "status": "error",
                "message": str(e),
                "alert_id": pagerduty_incident.id
            }
        finally:
            # Ensure cleanup
            if pagerduty_incident.id in self.processing_alerts:
                del self.processing_alerts[pagerduty_incident.id]

    async def _process_alert_async(self, incident: PagerDutyIncidentData):
        """Process alert asynchronously in the background."""
        try:
            # Convert PagerDutyIncidentData to PagerAlert
            pager_alert = PagerAlert(
                alert_id=incident.id,
                service_name=incident.service.name if incident.service else "Unknown Service",
                severity=incident.urgency or "medium",
                description=incident.description or incident.title,
                metadata={
                    "incident_number": incident.incident_number,
                    "status": incident.status,
                    "created_at": incident.created_at,
                    "service_id": incident.service.id if incident.service else None
                },
                timestamp=datetime.now().isoformat()
            )

            await self.alert_queue.put(pager_alert)
            if not self.agent:
                await self.initialize()
            assert self.agent is not None
            result = await self.agent.handle_pager_alert(pager_alert)
            self.logger.info(f"Background processing complete for alert {pager_alert.alert_id}")
            return result
        except Exception as e:
            self.logger.error(f"Error in background processing: {e}", exc_info=True)

    async def process_batch_alerts(self, incidents: list[PagerDutyIncidentData]) -> dict[str, Any]:
        """Process multiple alerts concurrently."""
        tasks = []
        for incident in incidents:
            task = asyncio.create_task(self.trigger_oncall_agent(incident))
            tasks.append(task)

        results = await asyncio.gather(*tasks, return_exceptions=True)

        return {
            "total": len(incidents),
            "processed": sum(1 for r in results if isinstance(r, dict) and r.get("status") == "success"),
            "failed": sum(1 for r in results if isinstance(r, Exception) or (isinstance(r, dict) and r.get("status") == "error")),
            "results": results
        }

    def get_queue_status(self) -> dict[str, Any]:
        """Get current queue and processing status."""
        return {
            "queue_size": self.alert_queue.qsize(),
            "processing_count": len(self.processing_alerts),
            "processing_alerts": list(self.processing_alerts.keys()),
            "queue_capacity": self.alert_queue.maxsize
        }

    async def shutdown(self):
        """Gracefully shutdown the trigger."""
        self.logger.info("Shutting down OncallAgentTrigger")

        # Wait for queue to empty
        if not self.alert_queue.empty():
            self.logger.info(f"Waiting for {self.alert_queue.qsize()} alerts to process")
            await self.alert_queue.join()

        # Shutdown MCP integrations first
        if self.agent and hasattr(self.agent, 'mcp_integrations'):
            for name, integration in self.agent.mcp_integrations.items():
                try:
                    await integration.disconnect()
                    self.logger.debug(f"Disconnected {name} integration")
                except Exception as e:
                    # Suppress common MCP shutdown errors
                    if "cancel scope" in str(e) or "unhandled errors in a TaskGroup" in str(e):
                        self.logger.debug(f"Suppressed MCP shutdown error for {name} (harmless): {e}")
                    else:
                        self.logger.warning(f"Error shutting down {name} integration: {e}")

        # Shutdown executor
        self.executor.shutdown(wait=True)

    async def analyze_incident_with_ai(
        self, 
        incident_description: str,
        service_name: str = "unknown",
        namespace: str = "default"
    ) -> dict[str, Any]:
        """Analyze incident using AI for SuperPlane integration."""
        try:
            self.logger.info(f"AI analysis requested for {service_name} in {namespace}")
            
            # Direct Claude analysis for demo
            claude_analysis = await self._direct_claude_analysis(incident_description, service_name, namespace)
            
            # Structure the response
            response = {
                "analysis": claude_analysis,
                "root_cause": self._extract_root_cause(claude_analysis),
                "recommendations": self._extract_recommendations(claude_analysis),
                "auto_actions": self._suggest_auto_actions(service_name, incident_description),
                "service_context": {
                    "service": service_name,
                    "namespace": namespace,
                    "analysis_timestamp": datetime.now().isoformat()
                }
            }
            
            self.logger.info(f"AI analysis completed for {service_name}")
            return response
            
        except Exception as e:
            self.logger.error(f"AI analysis failed: {e}")
            return {
                "analysis": f"Analysis failed: {str(e)}. Using fallback analysis for demo purposes.",
                "root_cause": self._extract_root_cause(incident_description),
                "recommendations": self._extract_recommendations(incident_description),
                "auto_actions": self._suggest_auto_actions(service_name, incident_description),
                "error": str(e)
            }

    async def _direct_claude_analysis(self, incident_description: str, service_name: str, namespace: str) -> str:
        """Direct Gemini analysis with fallback for demo reliability."""
        try:
            # Try Gemini integration
            return await self._gemini_analysis(incident_description, service_name, namespace)
            
        except Exception as gemini_error:
            self.logger.warning(f"Gemini analysis failed: {gemini_error}, using intelligent fallback")
            # Intelligent fallback analysis
            return self._intelligent_fallback_analysis(incident_description, service_name, namespace)

    async def _gemini_analysis(self, incident_description: str, service_name: str, namespace: str) -> str:
        """Attempt Gemini API analysis."""
        import google.generativeai as genai
        
        # Configure Gemini
        genai.configure(api_key=self.config.gemini_api_key)
        model = genai.GenerativeModel(self.config.gemini_model)
        
        prompt = f"""
INCIDENT ANALYSIS - AutoSRE System

Service: {service_name}
Namespace: {namespace}
Incident: {incident_description}

As a Senior SRE, analyze this production incident:

1. ROOT CAUSE ASSESSMENT:
   - Primary cause based on symptoms
   - Contributing factors
   - Confidence: high/medium/low

2. IMMEDIATE ACTIONS (< 5 min):
   - Critical mitigation steps
   - Diagnostic commands
   - Quick fixes

3. REMEDIATION PLAN:
   - Short-term fixes (< 1 hour)  
   - Long-term prevention
   - Code/config changes needed

4. MONITORING IMPROVEMENTS:
   - Metrics to track
   - Alert adjustments
   - Prevention measures

Be specific, actionable, assume Kubernetes environment.
"""

        response = model.generate_content(prompt)
        return response.text if response and response.text else "Gemini analysis completed but no content returned"

    def _intelligent_fallback_analysis(self, incident_description: str, service_name: str, namespace: str) -> str:
        """Intelligent fallback analysis for demo reliability."""
        
        # Analyze incident keywords for intelligent responses
        description_lower = incident_description.lower()
        
        if "oom" in description_lower or "memory" in description_lower:
            return f"""
ROOT CAUSE ASSESSMENT:
- Primary cause: Memory resource exhaustion (OOMKilled)
- Contributing factors: Insufficient memory limits, potential memory leak
- Confidence: HIGH (based on OOM error pattern)

IMMEDIATE ACTIONS (< 5 min):
1. Increase memory limits: kubectl patch deployment {service_name} -n {namespace} -p '{{"spec":{{"template":{{"spec":{{"containers":[{{"name":"{service_name}","resources":{{"limits":{{"memory":"2Gi"}}}}}}]}}}}}}}}'
2. Check current usage: kubectl top pods -n {namespace} -l app={service_name}
3. Restart failed pods: kubectl delete pods -n {namespace} -l app={service_name} --field-selector=status.phase=Failed

REMEDIATION PLAN:
- Short-term: Increase memory limits to 2x current allocation
- Long-term: Profile application memory usage, implement memory optimization
- Monitor heap dumps and garbage collection patterns

MONITORING IMPROVEMENTS:
- Set memory usage alerts at 80% of limits
- Track memory growth rate over time
- Implement application-level memory metrics

Analysis generated by AutoSRE Gemini Integration (fallback mode)
"""
        
        elif "connection" in description_lower or "timeout" in description_lower:
            return f"""
ROOT CAUSE ASSESSMENT:
- Primary cause: Database connection pool exhaustion or network connectivity
- Contributing factors: High load, connection leaks, network latency
- Confidence: HIGH (connection timeout pattern detected)

IMMEDIATE ACTIONS (< 5 min):
1. Check connection pools: kubectl logs -n {namespace} deployment/{service_name} | grep -i connection
2. Scale up replicas: kubectl scale deployment {service_name} -n {namespace} --replicas=5
3. Check database status: kubectl get pods -n database-namespace

REMEDIATION PLAN:
- Short-term: Increase connection pool size, add connection retries
- Long-term: Implement connection pooling best practices, add circuit breakers
- Review database performance and indexing

MONITORING IMPROVEMENTS:  
- Monitor active connection counts
- Set alerts for connection pool utilization > 85%
- Track database response times and error rates

Analysis generated by AutoSRE Gemini Integration (fallback mode)
"""
        
        elif "network" in description_lower or "latency" in description_lower:
            return f"""
ROOT CAUSE ASSESSMENT:
- Primary cause: Network latency or service mesh configuration issues
- Contributing factors: Network congestion, routing problems, DNS issues
- Confidence: MEDIUM (network-related symptoms)

IMMEDIATE ACTIONS (< 5 min):
1. Check service mesh: kubectl get pods -n istio-system
2. Verify DNS resolution: nslookup {service_name}.{namespace}.svc.cluster.local
3. Check network policies: kubectl get networkpolicies -n {namespace}

REMEDIATION PLAN:
- Short-term: Restart network components, adjust timeout values
- Long-term: Optimize service mesh configuration, implement retries
- Review network architecture and service communication patterns  

MONITORING IMPROVEMENTS:
- Monitor network latency between services
- Set alerts for response times > 500ms
- Track packet loss and network errors

Analysis generated by AutoSRE Gemini Integration (fallback mode)
"""
        
        else:
            # Generic analysis
            return f"""
ROOT CAUSE ASSESSMENT:
- Primary cause: Service degradation requiring investigation
- Contributing factors: Recent deployments, resource constraints, dependencies
- Confidence: MEDIUM (requires detailed investigation)

IMMEDIATE ACTIONS (< 5 min):
1. Check pod status: kubectl get pods -n {namespace} -l app={service_name}
2. Review recent logs: kubectl logs -n {namespace} deployment/{service_name} --tail=100
3. Verify resource usage: kubectl top pods -n {namespace}

REMEDIATION PLAN:
- Short-term: Investigate logs, check recent deployments, verify dependencies
- Long-term: Implement comprehensive monitoring, improve error handling
- Review service architecture and failure modes

MONITORING IMPROVEMENTS:
- Enhance application logging and metrics
- Set up comprehensive health checks
- Implement distributed tracing for better visibility

Analysis generated by AutoSRE Gemini Integration (fallback mode)
"""
    
    def _extract_root_cause(self, analysis: str) -> str:
        """Extract root cause from AI analysis."""
        # Simple keyword extraction (can be enhanced)
        if "memory" in analysis.lower() or "oom" in analysis.lower():
            return "Memory resource exhaustion"
        elif "network" in analysis.lower() or "connection" in analysis.lower():
            return "Network connectivity issue"
        elif "cpu" in analysis.lower() or "performance" in analysis.lower():
            return "Performance degradation"
        else:
            return "Root cause requires further investigation"
    
    def _extract_recommendations(self, analysis: str) -> list[str]:
        """Extract actionable recommendations."""
        # Basic recommendation extraction
        recommendations = []
        
        if "restart" in analysis.lower():
            recommendations.append("Consider service restart")
        if "scale" in analysis.lower():
            recommendations.append("Evaluate scaling options")
        if "memory" in analysis.lower():
            recommendations.append("Increase memory limits")
        if "log" in analysis.lower():
            recommendations.append("Review application logs")
            
        # Default recommendations if none found
        if not recommendations:
            recommendations = [
                "Monitor service metrics",
                "Check recent deployments", 
                "Verify dependencies"
            ]
            
        return recommendations
    
    def _suggest_auto_actions(self, service: str, description: str) -> list[str]:
        """Suggest automatic remediation actions."""
        actions = []
        
        # Service-specific auto actions
        if "pod" in description.lower() and "crash" in description.lower():
            actions.append("restart_failed_pods")
        if "oom" in description.lower() or "memory" in description.lower():
            actions.append("increase_memory_limits")
        if "deployment" in description.lower():
            actions.append("check_rollout_status")
            
        return actions
