# SuperPlane Canvas Configuration: AutoSRE Incident Analysis

## Canvas Name: AutoSRE Incident Response Automation

### Components:

#### 1. Manual Trigger (Form Input)
- **Component**: Form Input
- **Fields**:
  - `incident`: Text area - "Describe the incident"
  - `service`: Text - "Service name (e.g. payment-service)"
  - `namespace`: Text - "Kubernetes namespace (e.g. production)"
  - `severity`: Dropdown - ["critical", "high", "medium", "low"]

#### 2. AI Analysis Webhook
- **Component**: HTTP Webhook
- **Method**: POST
- **URL**: `http://YOUR_TUNNEL_URL/webhook/superplane/analyze`
- **Headers**: 
  - `Content-Type: application/json`
- **Body**: 
```json
{
  "incident": "{{form.incident}}",
  "service": "{{form.service}}", 
  "namespace": "{{form.namespace}}",
  "severity": "{{form.severity}}"
}
```

#### 3. JIRA Ticket Creation
- **Component**: HTTP Webhook  
- **Method**: POST
- **URL**: `http://YOUR_TUNNEL_URL/webhook/superplane/jira`
- **Headers**:
  - `Content-Type: application/json`
- **Body**:
```json
{
  "summary": "{{analysis.service}} - {{form.severity}} incident",
  "description": "AutoSRE Analysis:\n{{analysis.analysis}}\n\nRoot Cause: {{analysis.root_cause}}\n\nRecommendations:\n{{analysis.recommendations}}",
  "priority": "{{analysis.severity_assessment.priority}}",
  "incident_id": "{{analysis.incident_id}}"
}
```

#### 4. Results Display
- **Component**: Display/Results
- **Show**:
  - Analysis Results: `{{analysis.analysis}}`
  - Root Cause: `{{analysis.root_cause}}`
  - Recommendations: `{{analysis.recommendations}}`
  - JIRA Ticket: `{{jira.ticket_url}}`
  - Incident ID: `{{analysis.incident_id}}`

### Canvas Flow:
```
Form Input → AI Analysis → JIRA Creation → Display Results
```

### Demo Data:
- **Incident**: "Kubernetes pod payment-service experiencing OOMKilled errors with high CPU usage"
- **Service**: "payment-service"
- **Namespace**: "production"
- **Severity**: "high"

### Expected Output:
- AI analysis with root cause identification
- JIRA ticket automatically created
- Actionable recommendations for SRE team
- Complete incident timeline