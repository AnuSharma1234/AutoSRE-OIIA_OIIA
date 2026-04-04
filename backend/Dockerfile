FROM python:3.11-slim

# --- System deps ---
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && curl -LO "https://dl.k8s.io/release/$(curl -L -s https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl" \
    && install -o root -g root -m 0755 kubectl /usr/local/bin/kubectl \
    && rm kubectl

# --- Non-root user ---
RUN groupadd -r autosre && useradd -r -g autosre -d /app -s /sbin/nologin autosre

WORKDIR /app

# --- Python deps (cached layer) ---
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# --- Application code ---
COPY . .

RUN chown -R autosre:autosre /app
USER autosre

# Default ports: 8000 (main API), 8001 (trigger/event service)
EXPOSE 8000
EXPOSE ${SERVICE_PORT:-8001}

# Env defaults for the event poller
ENV K8S_IN_CLUSTER="false" \
    K8S_NAMESPACE="default" \
    SERVICE_PORT="8001" \
    LOG_LEVEL="info"

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
