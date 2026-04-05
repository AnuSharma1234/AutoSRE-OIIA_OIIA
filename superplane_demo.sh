#!/bin/bash

# SuperPlane Canvas Demo Setup Script
echo "🚀 Starting AutoSRE × SuperPlane Demo Setup"

# Check if backend is running
if ! curl -s http://localhost:8000/health > /dev/null; then
    echo "Starting AutoSRE backend..."
    cd /home/samarth/Hackathons/hackbyte_4.0/AutoSRE/backend
    nix-shell ../shell.nix --run "uv run python api_server.py" &
    BACKEND_PID=$!
    echo "Backend started with PID: $BACKEND_PID"
    sleep 5
    
    # Test the new SuperPlane endpoints
    echo "Testing SuperPlane integration endpoints..."
    
    # Test analysis endpoint
    curl -X POST http://localhost:8000/webhook/superplane/analyze \
        -H "Content-Type: application/json" \
        -d '{
            "incident": "Kubernetes pod payment-service experiencing OOMKilled errors in production namespace",
            "service": "payment-service",
            "namespace": "production", 
            "severity": "high"
        }' | jq .
        
    # Test JIRA endpoint
    curl -X POST http://localhost:8000/webhook/superplane/jira \
        -H "Content-Type: application/json" \
        -d '{
            "summary": "Production payment-service OOMKilled",
            "description": "AutoSRE Analysis: Memory exhaustion detected in payment-service pods",
            "priority": "High",
            "incident_id": "autosre-20241205-032800"
        }' | jq .
else
    echo "AutoSRE backend already running on port 8000"
fi

echo "✅ Demo setup complete!"
echo "🌐 SuperPlane Canvas can now call:"
echo "   - http://localhost:8000/webhook/superplane/analyze"
echo "   - http://localhost:8000/webhook/superplane/jira"
echo ""
echo "📋 Next steps:"
echo "1. Open https://app.superplane.com"
echo "2. Create new Canvas with HTTP webhook components"
echo "3. Configure webhooks to call the AutoSRE endpoints above"