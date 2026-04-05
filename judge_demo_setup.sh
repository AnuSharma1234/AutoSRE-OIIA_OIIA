#!/bin/bash

# Judge Demo Preparation Script
echo "🎪 Preparing AutoSRE Demo for Judges..."

# 1. Start backend server
echo "Starting AutoSRE backend with Gemini AI..."
cd /home/samarth/Hackathons/hackbyte_4.0/AutoSRE/backend || { echo "Failed to cd to backend"; exit 1; }
nix-shell ../shell.nix --run "uv run python api_server.py" &
SERVER_PID=$!

# 2. Wait for server initialization
echo "Waiting for server startup..."
sleep 10

# 3. Test all endpoints
echo "Testing all demo endpoints..."

# Test health
curl -s http://localhost:8000/health > /dev/null && echo "✅ Health endpoint OK" || echo "❌ Health endpoint failed"

# Test analysis endpoint
curl -s -X POST http://localhost:8000/webhook/superplane/analyze \
  -H "Content-Type: application/json" \
  -d '{"incident":"Test","service":"test","namespace":"test","severity":"low"}' \
  > /dev/null && echo "✅ Analysis endpoint OK" || echo "❌ Analysis endpoint failed"

# Test JIRA endpoint  
curl -s -X POST http://localhost:8000/webhook/superplane/jira \
  -H "Content-Type: application/json" \
  -d '{"summary":"Test","description":"Test","priority":"Low"}' \
  > /dev/null && echo "✅ JIRA endpoint OK" || echo "❌ JIRA endpoint failed"

echo ""
echo "🚀 DEMO ENVIRONMENT READY!"
echo "Server PID: $SERVER_PID"
echo "Backend: http://localhost:8000"
echo "API Docs: http://localhost:8000/docs"
echo "SuperPlane: https://app.superplane.com"
echo ""
echo "📋 Demo endpoints for SuperPlane Canvas:"
echo "  Analysis: http://localhost:8000/webhook/superplane/analyze"
echo "  JIRA: http://localhost:8000/webhook/superplane/jira"
echo ""
echo "Ready for judges! 🏆"

# Keep server running
echo "Press Ctrl+C to stop demo environment"
wait $SERVER_PID