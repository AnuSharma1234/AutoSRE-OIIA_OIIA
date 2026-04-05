#!/bin/bash

# AutoSRE × SuperPlane Demo Script  
# Hackathon Demo Scenarios with Google Gemini AI Integration

echo "🚀 AutoSRE × SuperPlane Hackathon Demo (Powered by Gemini AI)"
echo "============================================================\n"

# Start backend server in background
echo "📡 Starting AutoSRE backend server..."
cd /home/samarth/Hackathons/hackbyte_4.0/AutoSRE/backend
nix-shell ../shell.nix --run "uv run python api_server.py" &
BACKEND_PID=$!
echo "Backend server started with PID: $BACKEND_PID"

# Wait for server to start
echo "⏳ Waiting for server to initialize..."
sleep 8

# Test health endpoint
echo "\n🔍 Testing server health..."
curl -s http://localhost:8000/health | jq '.'

echo "\n🎭 DEMO SCENARIOS FOR SUPERPLANE CANVAS"
echo "======================================\n"

# Scenario 1: Kubernetes OOM Kill
echo "📋 SCENARIO 1: Kubernetes OOMKilled Pod"
echo "---------------------------------------"
echo "Incident: Payment service experiencing memory issues"
echo "\n🤖 Testing AI Analysis..."

curl -s -X POST http://localhost:8000/webhook/superplane/analyze \
    -H "Content-Type: application/json" \
    -d '{
        "incident": "Kubernetes pod payment-service-7c8b5d9f4-x2k9m in production namespace is experiencing OOMKilled errors. Pod keeps restarting every 2-3 minutes. High CPU usage observed before crashes. Users reporting transaction failures.",
        "service": "payment-service", 
        "namespace": "production",
        "severity": "critical"
    }' | jq '.'

echo "\n🎫 Creating JIRA ticket..."
curl -s -X POST http://localhost:8000/webhook/superplane/jira \
    -H "Content-Type: application/json" \
    -d '{
        "summary": "CRITICAL: payment-service OOMKilled in production", 
        "description": "AutoSRE Analysis: Memory exhaustion detected in payment-service pods. Requires immediate memory limit increase and investigation of memory leak.",
        "priority": "Critical",
        "incident_id": "autosre-demo-001"
    }' | jq '.'

echo "\n" && sleep 3

# Scenario 2: Database Connection Issues  
echo "📋 SCENARIO 2: Database Connection Pool Exhaustion"
echo "-----------------------------------------------"
echo "Incident: API services unable to connect to database"

curl -s -X POST http://localhost:8000/webhook/superplane/analyze \
    -H "Content-Type: application/json" \
    -d '{
        "incident": "Multiple API services reporting database connection timeouts. Connection pool exhaustion detected. 503 errors increasing. Response times degraded from 200ms to 5000ms+.",
        "service": "user-api",
        "namespace": "production", 
        "severity": "high"
    }' | jq '.'

echo "\n" && sleep 2

# Scenario 3: Network Latency Issues
echo "📋 SCENARIO 3: Inter-service Network Latency"  
echo "------------------------------------------"
echo "Incident: Microservices experiencing communication delays"

curl -s -X POST http://localhost:8000/webhook/superplane/analyze \
    -H "Content-Type: application/json" \
    -d '{
        "incident": "Network latency between order-service and inventory-service increased from 5ms to 500ms. Timeout errors in logs. Service mesh metrics showing packet loss.",
        "service": "order-service",
        "namespace": "production",
        "severity": "medium" 
    }' | jq '.'

echo "\n📊 DEMO COMPLETE!"
echo "================\n"

echo "🎯 SuperPlane Canvas Configuration:"
echo "  1. Manual Trigger → AI Analysis → JIRA Creation → Results"
echo "  2. Use these endpoints in your Canvas:"
echo "     - Analysis: http://localhost:8000/webhook/superplane/analyze"
echo "     - JIRA: http://localhost:8000/webhook/superplane/jira"
echo ""
echo "🌐 Access SuperPlane at: https://app.superplane.com"
echo "📱 AutoSRE Dashboard: http://localhost:3000 (after starting frontend)"
echo "🔧 Backend API Docs: http://localhost:8000/docs"
echo ""
echo "🎪 HACKATHON DEMO READY!"
echo "Show judges the end-to-end automation:"
echo "  SuperPlane Canvas → AI Analysis → JIRA Ticket Creation"
echo ""

# Keep server running for demo
echo "💡 Backend server running on PID: $BACKEND_PID"
echo "   Kill with: kill $BACKEND_PID"
echo ""
echo "Press Ctrl+C to stop demo environment"

# Wait for user input to keep server alive
read -p "Press Enter to stop demo..."
kill $BACKEND_PID 2>/dev/null
echo "Demo environment stopped. ✅"