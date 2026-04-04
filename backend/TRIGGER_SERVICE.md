# 🚨 Error Trigger Service (Event Poller)

This service is the entry point for the AutoSRE incident remediation pipeline. It watches for infrastructure and application failures, normalizes them into a standard format, and pushes them to **SpacetimeDB** and **Superplane**.

## How It Works

The service is a stateless Python (FastAPI) microservice that listens to two primary event sources:

| Source | Method | Description |
| :--- | :--- | :--- |
| **Prometheus AlertManager** | Webhook (HTTP POST) | Receives firing alerts from AlertManager (e.g., `KubePodCrashLooping`). |
| **Kubernetes Events API** | Background Watcher | Streams cluster-level events (e.g., `BackOff`, `OOMKilling`) in real-time. |

### 🛠️ Processing Logic
1.  **Normalization**: All events are mapped to a strict `IncidentEvent` schema.
2.  **Deduplication**: If an identical event (same pod + same alert type) is detected within **60 seconds**, it is dropped to prevent alert storms.
3.  **SpacetimeDB Push**: The normalized incident is written to SpacetimeDB by calling the `create_incident` reducer.
4.  **Superplane Trigger**: A workflow run for `autosre-incident-pipeline` is initiated via the Superplane API to begin AI-driven remediation.

---

## 🚀 Setup Guide

### 1. Environment Variables
Copy `.env.example` to `.env` and configure the following:

```env
# SpacetimeDB
SPACETIMEDB_URL=ws://localhost:3000
SPACETIMEDB_MODULE=autosre
SPACETIMEDB_TOKEN=your-token

# Kubernetes
K8S_NAMESPACE=default
K8S_IN_CLUSTER=false  # Set 'true' only when running inside the cluster

# Prometheus / AlertManager
ALERTMANAGER_WEBHOOK_SECRET=my-shared-secret  # Used for 'X-Webhook-Secret' validation

# Superplane
SUPERPLANE_WEBHOOK_URL=https://api.superplane.dev/v1/runs
SUPERPLANE_API_KEY=your-api-key
```

### 2. AlertManager Configuration
To route alerts into the system, add this receiver to your `alertmanager.yaml`:

```yaml
receivers:
- name: 'autosre-trigger'
  webhook_configs:
  - url: 'http://autosre-trigger-service:8001/webhook/alertmanager'
    http_config:
      bearer_token_file: /etc/alertmanager/webhook-secret # Or use X-Webhook-Secret header
```

### 3. Local Installation
1.  **Enable Kubernetes**: Ensure "Kubernetes" is enabled in your Docker Desktop settings.
2.  **Install Dependencies**:
    ```bash
    pip install -r backend/requirements.txt
    ```
3.  **Run Locally**:
    ```bash
    cd backend
    uvicorn app.main:app --host 0.0.0.0 --port 8001 --reload
    ```

---

## 🧪 Testing

### Automated Tests
Run the comprehensive suite covering normalization, deduplication, and integration mocking:
```bash
cd backend
python -m pytest tests/test_event_poller.py -v
```

### Manual Alert Simulation
You can simulate an AlertManager webhook using `curl`:
```bash
curl -X POST http://localhost:8001/webhook/alertmanager \
  -H "X-Webhook-Secret: your-secret" \
  -H "Content-Type: application/json" \
  -d '{
    "alerts": [{
      "status": "firing",
      "labels": {
        "alertname": "KubePodCrashLooping",
        "pod": "my-test-pod",
        "severity": "critical"
      }
    }]
  }'
```

---

## 📊 Observability
- **Health**: `GET /health` shows if the K8s watcher is running.
- **Metrics**: `GET /metrics` provides Prometheus-format counters:
    - `autosre_events_received_total`
    - `autosre_events_emitted_total`
    - `autosre_spacetimedb_write_failures_total`
    - `autosre_duplicates_dropped_total`
