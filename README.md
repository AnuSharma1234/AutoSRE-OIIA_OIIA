# AutoSRE — Autonomous SRE Agent

> AI-powered Kubernetes incident detection, diagnosis, and remediation.

AutoSRE is a self-service platform that automatically handles Kubernetes cluster incidents using Claude AI for root-cause analysis and kubectl for safe, whitelisted remediation actions.

## Features

- **Prometheus Alertmanager webhook integration** — receives firing alerts, deduplicates within 5-minute windows
- **Claude AI-powered root cause analysis** — uses `claude-sonnet-4-20250514` to analyze alerts and recommend remediation commands
- **kubectl command execution with whitelist + risk gating** — only pre-approved commands are ever run; exec is always blocked
- **Auto-remediation for low-risk incidents** — auto-executes when risk level is LOW and AI confidence ≥ threshold
- **Manual approval workflow for medium/high-risk actions** — dashboard modal for human review before execution
- **Full audit logging** — every alert, analysis, and action is recorded with timestamps
- **Next.js dashboard** — incident list, detail view with AI analysis, cluster overview
- **Error Trigger Service (Event Poller)** — [Detailed Service Documentation](backend/TRIGGER_SERVICE.md)

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│  Prometheus + Alertmanager                              │
│  (Alertmanager → POST /api/v1/webhooks/prometheus)      │
└────────────────────┬────────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────────┐
│  FastAPI Backend (Python 3.11)  │  Port 8000            │
│  ├── Webhook receiver (dedup in Redis)                  │
│  ├── AI analysis engine (Claude AsyncAnthropic)         │
│  ├── Risk evaluation engine                             │
│  ├── kubectl executor (subprocess, whitelist)           │
│  ├── Background task queue (asyncio + Redis)            │
│  └── PostgreSQL (incidents, action_logs, ai_analysis)   │
└────────────────────┬────────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────────┐
│  Next.js Frontend  │  Port 3000                         │
│  ├── /incidents — paginated list with status filters    │
│  ├── /incidents/[id] — detail with AI analysis + approve │
│  └── /cluster — node/pod summary + recent incidents      │
└─────────────────────────────────────────────────────────┘
         │
         └── Redis (task queue, deduplication cache)
         └── PostgreSQL (persistent storage)
```

**Stack:** FastAPI · PostgreSQL 16 · Redis 7 · Next.js 14 · Tailwind CSS · Claude AI

---

## Prerequisites

- **Docker** and **Docker Compose** (v2+)
- **Kubernetes cluster** with `kubeconfig` at `~/.kube/config`
- **Anthropic API key** — get one at [console.anthropic.com](https://console.anthropic.com)

---

## Quick Start

```bash
# 1. Clone the repository
git clone <repo-url>
cd autosre

# 2. Configure environment
cp .env.example .env
# Edit .env with your ANTHROPIC_API_KEY, POSTGRES_PASSWORD, etc.

# 3. Mount your kubeconfig into the container path
# The backend expects ~/.kube/config to exist on the host and will be
# mounted read-only into containers. Ensure it exists:
mkdir -p ~/.kube
# (if you don't have one already, run: kubectl config view > ~/.kube/config)

# 4. Start the full stack
docker compose up -d

# 5. Verify services are healthy
curl http://localhost:8000/health
# Expected: {"status":"ok"}

curl http://localhost:3000
# Expected: Next.js frontend response (or redirect)

# 6. View logs
docker compose logs -f backend
docker compose logs -f frontend
```

---

## Configuration

All configuration is via environment variables (see `.env.example`):

| Variable | Required | Default | Description |
|---|---|---|---|
| `ANTHROPIC_API_KEY` | **Yes** | — | Anthropic API key for Claude AI. Get from [console.anthropic.com](https://console.anthropic.com) |
| `DATABASE_URL` | Yes | `postgresql+asyncpg://...` | Async PostgreSQL connection string |
| `POSTGRES_PASSWORD` | Yes | — | PostgreSQL password (used in `DATABASE_URL`) |
| `REDIS_URL` | Yes | `redis://redis:6379/0` | Redis connection URL for task queue and deduplication |
| `KUBECONFIG` | Yes | `/root/.kube/config` | Path inside containers where kubeconfig is mounted |
| `CLUSTER_ID` | Yes | `my-cluster` | Must match `kubectl config current-context`; used to validate cluster |
| `API_SECRET_KEY` | Yes | `change-me-in-prod` | Secret for API authentication; set a strong value in production |
| `AUTO_EXECUTE_LOW_THRESHOLD` | No | `0.9` | Auto-execute if risk=LOW and AI confidence ≥ this value |
| `AUTO_EXECUTE_MEDIUM_THRESHOLD` | No | `0.9` | Auto-execute if risk=MEDIUM and AI confidence ≥ this value (HIGH never auto-executes) |
| `ENVIRONMENT` | No | `development` | Set to `production` in production deployments |
| `NEXT_PUBLIC_API_URL` | No | `http://localhost:8000` | Backend URL used by the Next.js frontend |

---

## Prometheus Integration

AutoSRE receives alerts via Prometheus Alertmanager. Follow these steps to wire up your Prometheus instance:

### 1. Configure Alertmanager

Copy `prometheus/alertmanager.yml` to your Prometheus config directory and add it to your `alertmanager.yml`:

```yaml
# In your alertmanager.yml
route:
  receiver: 'autosre-webhook'
  # ... your existing route config

receivers:
  - name: 'autosre-webhook'
    webhook_configs:
      - url: 'http://<your-backend-host>:8000/api/v1/webhooks/prometheus'
        send_resolved: true
```

> **Docker Compose:** If running inside the same Compose stack, use `http://backend:8000/api/v1/webhooks/prometheus`

### 2. Add Alert Rules

Copy `prometheus/alerts.yml` to your Prometheus rules directory (e.g., `/etc/prometheus/rules/`). The included rules monitor:

| Alert | Condition | Severity |
|---|---|---|
| `KubePodCrashLoopBackOff` | Pod restarts > 3 over 5m | warning |
| `KubePodNotReady` | Pod in Pending phase for 2m | warning |
| `KubeDeploymentReplicasMismatch` | Deployment spec replicas ≠ available replicas | warning |
| `KubeImagePullBackOff` | Container in ImagePullBackOff for 1m | error |
| `KubeOOMKilled` | Pod OOMKilled with restarts > 2 | error |

Add to your `prometheus.yml`:
```yaml
rule_files:
  - '/etc/prometheus/rules/alerts.yml'
```

### 3. Restart Prometheus

```bash
# Reload Prometheus configuration
curl -X POST http://localhost:9090/-/reload

# Or restart the container
docker compose restart prometheus
```

### Alert Flow

```
Prometheus → Alertmanager → deduplication (5min window) → AutoSRE webhook
                                                              │
                                              ┌───────────────┴───────────────┐
                                              │  1. Create incident record     │
                                              │  2. Enqueue AI analysis task   │
                                              │  3. Background worker:          │
                                              │     - Claude AI root cause     │
                                              │     - Risk evaluation          │
                                              │     - Auto-execute or require   │
                                              │       manual approval          │
                                              └────────────────────────────────┘
```

---

## API Endpoints

Base URL: `http://localhost:8000` (or `http://backend:8000` inside Docker Compose)

### Health

| Method | Path | Description |
|---|---|---|
| `GET` | `/health` | Health check — returns `{"status":"ok"}` |

### Webhooks

| Method | Path | Description |
|---|---|---|
| `POST` | `/api/v1/webhooks/prometheus` | Prometheus Alertmanager webhook receiver |

### Incidents

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/v1/incidents` | List incidents. Query params: `page`, `limit`, `status`, `alert_type`, `cluster_id` |
| `GET` | `/api/v1/incidents/{id}` | Incident detail — includes `incident`, `analysis` (AI results), and `action_logs` |
| `GET` | `/api/v1/incidents/{id}/audit` | Full audit trail — merged AI analysis + action logs by timestamp |

### Remediation

| Method | Path | Description |
|---|---|---|
| `POST` | `/api/v1/execute` | Approve or reject a pending remediation. Body: `{incident_id, command, approved: bool}` |

### Cluster

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/v1/cluster/overview` | Cluster health summary: nodes, namespaces, pod counts, recent incidents |

### Authentication

All `/api/v1/*` endpoints require the `X-API-Key` header:
```bash
curl -H "X-API-Key: your-api-secret-key" http://localhost:8000/api/v1/incidents
```

---

## Dashboard

The Next.js frontend is served at `http://localhost:3000`.

### Pages

| Path | Description |
|---|---|
| `/incidents` | Paginated incident list with status filter (PENDING, ANALYZING, APPROVAL_REQUIRED, EXECUTING, RESOLVED, ESCALATED, FAILED), keyboard navigation (← →), and auto-refresh toggle |
| `/incidents/[id]` | Incident detail — AI analysis with confidence bar, risk badge, recommended kubectl command, and Approve/Reject buttons (medium/high risk) |
| `/cluster` | Cluster overview — pod summary cards, node status list, namespaces, and recent incidents |

---

## Security

AutoSRE is designed with defense in depth:

### kubectl Whitelist

Only these commands are permitted (regex-matched):

| Category | Allowed Patterns |
|---|---|
| **Read** | `kubectl get`, `kubectl describe`, `kubectl logs`, `kubectl top` |
| **Delete** | `kubectl delete pod` |
| **Rollout** | `kubectl rollout restart`, `kubectl rollout undo` |
| **Events** | `kubectl get events` |

### Always Blocked

- `kubectl exec` — **never** allowed
- Any command not matching the whitelist patterns
- Modifications to cluster-wide resources (deployments, services, configmaps)

### Risk Gating

| Risk Level | Condition | Action |
|---|---|---|
| `LOW` | confidence ≥ `AUTO_EXECUTE_LOW_THRESHOLD` (default 0.9) | Auto-executes |
| `MEDIUM` | confidence ≥ `AUTO_EXECUTE_MEDIUM_THRESHOLD` (default 0.9) | Auto-executes |
| `HIGH` | Any confidence | Requires manual approval |

If the AI analysis fails to parse, risk defaults to `HIGH` (manual approval required).

### API Authentication

All API endpoints (except `/health`) require `X-API-Key` matching `API_SECRET_KEY`.

---

## Development

### Backend

```bash
cd backend

# Install dependencies
pip install -r requirements.txt

# Run the development server (auto-reload enabled)
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Frontend

```bash
cd frontend

# Install dependencies
npm install

# Run the development server
npm run dev
```

### Running Tests

```bash
cd backend
pytest
```

---

## Project Structure

```
.
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI app entry point
│   │   ├── api/v1/              # API routes
│   │   │   ├── incidents.py      # Incident CRUD + audit
│   │   │   ├── webhooks.py       # Prometheus webhook receiver
│   │   │   ├── execute.py        # Remediation approval/rejection
│   │   │   └── cluster.py        # Cluster overview
│   │   ├── core/                # Core business logic
│   │   │   ├── claude_engine.py  # Claude AI integration
│   │   │   ├── risk_engine.py    # Risk evaluation
│   │   │   ├── kubectl_exec.py   # kubectl whitelist + executor
│   │   │   └── kubernetes.py     # K8s cluster queries
│   │   ├── tasks/
│   │   │   ├── queue.py          # Background task queue (asyncio)
│   │   │   └── executor.py       # Remediation execution
│   │   ├── models/              # SQLAlchemy models
│   │   └── schemas/             # Pydantic request/response schemas
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── app/
│   │   │   ├── incidents/page.tsx       # Incident list
│   │   │   ├── incidents/[id]/page.tsx  # Incident detail
│   │   │   └── cluster/page.tsx         # Cluster overview
│   │   ├── components/
│   │   │   ├── ApprovalModal.tsx        # Approve/reject modal
│   │   │   ├── StatusBadge.tsx
│   │   │   └── ...
│   │   └── lib/
│   │       ├── api.ts            # API client
│   │       └── types.ts          # TypeScript type definitions
│   ├── Dockerfile
│   └── package.json
├── prometheus/
│   ├── alertmanager.yml          # Alertmanager routing config
│   ├── alerts.yml                 # Kubernetes alert rules
│   └── prometheus.yml             # Prometheus scrape config
├── postgres/
│   └── init.sql                   # Database initialization
├── docker-compose.yml
└── .env.example
```

---

## Environment Variables Reference

For quick reference, here's the complete `.env.example`:

```env
# === AutoSRE Configuration ===

# Anthropic Claude API
ANTHROPIC_API_KEY=sk-ant-...        # Required. Get from console.anthropic.com

# === Database ===
DATABASE_URL=postgresql+asyncpg://autosre:changeme@postgres:5432/autosre

# === Redis ===
REDIS_URL=redis://redis:6379/0

# === Kubernetes ===
KUBECONFIG=/root/.kube/config        # Mount ~/.kube/config into container
CLUSTER_ID=my-cluster                # Must match kubectl config current-context

# === Security ===
API_SECRET_KEY=change-me-in-prod    # Secret key for API authentication

# === Risk Thresholds ===
AUTO_EXECUTE_LOW_THRESHOLD=0.9
AUTO_EXECUTE_MEDIUM_THRESHOLD=0.9

# === Frontend ===
NEXT_PUBLIC_API_URL=http://localhost:8000
```

---

## Troubleshooting

### Backend health check fails

```bash
# Check backend logs
docker compose logs backend

# Verify DATABASE_URL format is correct
# Should be: postgresql+asyncpg://user:pass@host:port/db
```

### Alerts not arriving

- Verify Alertmanager can reach the backend: `curl http://backend:8000/health`
- Check Alertmanager logs: `docker compose logs alertmanager`
- Ensure `alertmanager.yml` receiver URL uses the correct host (`backend:8000` in Docker Compose)

### kubectl commands fail

- Verify `~/.kube/config` is present on the host
- Check `kubectl config current-context` matches `CLUSTER_ID` in `.env`
- Test manually: `kubectl get pods` from a backend container

### AI analysis not running

- Verify `ANTHROPIC_API_KEY` is set correctly in `.env`
- Check backend logs for Claude API errors
- Ensure `anthropic` package is installed: `pip show anthropic`
