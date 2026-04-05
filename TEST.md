# AutoSRE v2.0 Testing Guide 🧪

> **Complete testing checklist to verify all systems are operational**

## 🎯 **Testing Overview**

This guide provides step-by-step verification procedures for all AutoSRE v2.0 components. Follow this checklist before demos, deployments, or troubleshooting to ensure everything is working properly.

**Testing Time:** 15-20 minutes  
**Required Access:** Local development environment, SuperPlane account, JIRA access  
**Dependencies:** Nix shell, Docker (optional), curl, Python 3.13+

---

## 📋 **Pre-Test Setup**

### **1. Environment Verification**

```bash
# Navigate to project directory
cd /home/samarth/Hackathons/hackbyte_4.0/AutoSRE

# Verify Nix environment
nix-shell shell.nix --run "echo 'Nix environment ready'"

# Check project structure
ls -la
# Expected: backend/, frontend/, shell.nix, README.md, etc.
```

### **2. Configuration Check**

```bash
# Verify environment file exists
test -f .env && echo "✅ .env file found" || echo "❌ .env file missing"

# Check required environment variables
grep -q "GEMINI_API_KEY" .env && echo "✅ Gemini API key configured" || echo "❌ Gemini API key missing"
grep -q "SUPERPLANE_ENABLED=true" .env && echo "✅ SuperPlane enabled" || echo "❌ SuperPlane disabled"
grep -q "JIRA_ENABLED=true" .env && echo "✅ JIRA enabled" || echo "❌ JIRA disabled"
```

---

## 🔧 **Component Testing**

### **Test 1: Backend API Server** ⭐ *Critical*

#### **1.1 Start Backend Server**

```bash
# Terminal 1: Start backend
cd backend
nix-shell ../shell.nix --run "uv run python api_server.py"

# Expected output:
# ✅ "Starting Oncall Agent API Server"
# ✅ "SuperPlane integration: enabled"  
# ✅ "JIRA integration: enabled"
# ✅ "Application startup complete."
```

**❌ If server fails to start:**
```bash
# Check dependencies
uv sync

# Check Python imports
python -c "
import sys
sys.path.append('.')
from src.oncall_agent.config import get_config
print('✅ Imports working')
"

# Check port availability  
lsof -i :8000
```

#### **1.2 Health Check**

```bash
# Terminal 2: Test health endpoint
curl -s http://localhost:8000/health | jq

# Expected response:
{
  "status": "healthy",
  "checks": {
    "api": "ok",
    "config": "ok", 
    "superplane_enabled": true,
    "jira_enabled": true
  }
}
```

#### **1.3 API Routes Verification**

```bash
# List all routes
curl -s http://localhost:8000/routes | jq '.routes[].path' | head -10

# Test key endpoints
curl -s http://localhost:8000/ | jq
curl -s http://localhost:8000/api/v1/agent/config | jq '.ai_providers'
```

**✅ Success Criteria:**
- Server starts without errors
- Health endpoint returns "healthy" status
- All integrations show as enabled
- Routes endpoint lists available paths

---

### **Test 2: Google Gemini AI Integration** ⭐ *Critical*

#### **2.1 API Key Validation**

```bash
# Test Gemini API directly
python test_gemini.py

# Expected output:
# ✅ Google Gemini AI Test
# ✅ API Key: Valid 
# ✅ Model Response: [AI analysis text]
```

#### **2.2 AI Analysis Endpoint**

```bash
# Test AI analysis via API
curl -X POST http://localhost:8000/webhook/superplane/analyze \
  -H "Content-Type: application/json" \
  -d '{
    "incident_type": "test", 
    "description": "Test incident for AI analysis",
    "severity": "low"
  }' | jq

# Expected response:
{
  "success": true,
  "analysis": {
    "root_cause": "...",
    "immediate_actions": ["..."],
    "long_term_recommendations": ["..."],
    "confidence_score": 0.85
  },
  "jira_ticket": {
    "key": "ASRE-XXXX",
    "url": "https://auto-sre.atlassian.net/browse/ASRE-XXXX"
  }
}
```

**❌ If Gemini AI fails:**
```bash
# Check API key
echo $GEMINI_API_KEY | cut -c1-10
# Should show: AIzaSyDIAK...

# Test fallback system
curl -X POST http://localhost:8000/webhook/superplane/analyze \
  -H "Content-Type: application/json" \
  -H "X-Force-Fallback: true" \
  -d '{"incident_type": "test", "description": "Fallback test"}'
```

**✅ Success Criteria:**
- Gemini API responds with intelligent analysis
- Fallback system works when AI is unavailable
- Response includes structured recommendations
- JIRA ticket creation is triggered

---

### **Test 3: Frontend Dashboard** ⭐ *Important*

#### **3.1 Start Frontend**

```bash
# Terminal 3: Start frontend
cd frontend
nix-shell ../shell.nix --run "npm run dev"

# Expected output:
# ✅ Next.js development server started
# ✅ Local: http://localhost:3000
# ✅ Ready in [time]
```

#### **3.2 UI Component Testing**

```bash
# Test frontend accessibility
curl -s http://localhost:3000 | grep -q "AutoSRE" && echo "✅ Frontend loading" || echo "❌ Frontend issue"

# Open browser and verify:
# - AutoSRE branding visible
# - Gruvbox color scheme applied
# - Navigation components working
# - Dashboard data loading
```

#### **3.3 API Integration**

Open browser developer tools and verify:

```javascript
// Console test for API connectivity
fetch('/api/v1/agent/config')
  .then(r => r.json())
  .then(d => console.log('✅ API connected:', d.ai_providers))
  .catch(e => console.error('❌ API error:', e));

// Test real-time updates
fetch('/api/v1/insights/analysis')
  .then(r => r.json()) 
  .then(d => console.log('✅ Insights loaded:', d.data.total_incidents))
  .catch(e => console.error('❌ Insights error:', e));
```

**✅ Success Criteria:**
- Frontend loads without errors
- AutoSRE branding and Gruvbox theme visible  
- API calls return data successfully
- Dashboard shows mock/real incident data

---

### **Test 4: SuperPlane Integration** ⭐ *Critical*

#### **4.1 Webhook Endpoints**

```bash
# Test SuperPlane analyze endpoint
curl -X POST http://localhost:8000/webhook/superplane/analyze \
  -H "Content-Type: application/json" \
  -d '{
    "incident_id": "test-001",
    "title": "Test SuperPlane Integration", 
    "description": "Testing webhook connectivity",
    "severity": "medium",
    "source": "superplane_test"
  }' | jq '.success'

# Expected: true

# Test JIRA endpoint  
curl -X POST http://localhost:8000/webhook/superplane/jira \
  -H "Content-Type: application/json" \
  -d '{
    "analysis": {
      "root_cause": "Test analysis",
      "recommendations": ["Test recommendation"]
    },
    "incident": {
      "id": "test-001",
      "title": "Test Incident"
    }
  }' | jq '.jira_ticket'
```

#### **4.2 SuperPlane Canvas (Optional)**

If SuperPlane access is available:

1. **Open SuperPlane:** https://app.superplane.com
2. **Configure Webhook:** Point to your ngrok/public URL
3. **Test Canvas:** Trigger a test workflow
4. **Verify Logs:** Check AutoSRE backend logs for incoming webhooks

```bash
# Monitor webhook traffic
tail -f backend/logs/api_server.log | grep "SuperPlane"
```

**✅ Success Criteria:**
- Webhook endpoints respond correctly
- JIRA ticket creation works
- SuperPlane Canvas can trigger AutoSRE (if available)
- Logs show proper webhook processing

---

### **Test 5: JIRA Integration** ⭐ *Important*

#### **5.1 JIRA Configuration**

```bash
# Test JIRA settings
curl -s http://localhost:8000/api/v1/agent/config | jq '.jira'

# Expected response:
{
  "jira_enabled": true,
  "jira_url": "https://auto-sre.atlassian.net",
  "jira_project_key": "ASRE"
}
```

#### **5.2 Ticket Creation Test**

```bash
# Trigger incident that should create JIRA ticket
curl -X POST http://localhost:8000/webhook/superplane/analyze \
  -H "Content-Type: application/json" \
  -d '{
    "incident_type": "kubernetes_pod_crash",
    "service": "test-service",
    "description": "Pod test-pod-12345 crashed with OOM error",
    "severity": "high", 
    "details": {
      "pod_name": "test-pod-12345",
      "namespace": "testing",
      "exit_code": "137"
    }
  }' | jq '.jira_ticket'

# Expected response:
{
  "key": "ASRE-####",
  "url": "https://auto-sre.atlassian.net/browse/ASRE-####",
  "status": "created"
}
```

**✅ Success Criteria:**
- JIRA configuration is properly loaded
- Tickets are created with structured content
- AI analysis is included in ticket description
- Ticket URLs are accessible

---

### **Test 6: Insights & Analytics** 

#### **6.1 Dashboard Analytics**

```bash
# Test insights endpoints
curl -s http://localhost:8000/api/v1/insights/analysis | jq '.data.total_incidents'
curl -s http://localhost:8000/api/v1/insights/recommendations | jq '.recommendations | length'
curl -s http://localhost:8000/api/v1/insights/trends | jq '.trends | length'

# Test chaos analysis
curl -X POST http://localhost:8000/api/v1/insights/analyze-chaos | jq '.data.chaos_incidents_created'
```

#### **6.2 Report Generation**

```bash
# Test markdown report generation
curl -s http://localhost:8000/api/v1/insights/report | jq '.report' | head -10
```

**✅ Success Criteria:**
- All insights endpoints return data
- Mock analytics show reasonable numbers
- Report generation produces markdown content
- Chaos analysis simulates incident data

---

## 🔄 **End-to-End Integration Tests**

### **Integration Test 1: Complete Incident Flow** ⭐ *Most Important*

```bash
#!/bin/bash
echo "🧪 Testing complete incident response flow..."

# Step 1: Trigger incident
RESPONSE=$(curl -s -X POST http://localhost:8000/webhook/superplane/analyze \
  -H "Content-Type: application/json" \
  -d '{
    "incident_type": "database_connection_failure",
    "service": "payment-service", 
    "description": "Connection pool exhausted - 503 errors rising",
    "severity": "critical"
  }')

# Step 2: Verify AI analysis
echo "Step 1: AI Analysis"
echo $RESPONSE | jq '.analysis.root_cause' | grep -q "connection" && echo "✅ AI identified connection issue" || echo "❌ AI analysis failed"

# Step 3: Verify JIRA ticket
echo "Step 2: JIRA Integration"  
TICKET_URL=$(echo $RESPONSE | jq -r '.jira_ticket.url')
echo $TICKET_URL | grep -q "auto-sre.atlassian.net" && echo "✅ JIRA ticket created" || echo "❌ JIRA integration failed"

# Step 4: Check dashboard update
echo "Step 3: Dashboard Update"
sleep 2
curl -s http://localhost:8000/api/v1/insights/analysis | jq '.data.total_incidents' | grep -q "[0-9]" && echo "✅ Dashboard updated" || echo "❌ Dashboard not updated"

echo "🎉 Integration test complete!"
```

### **Integration Test 2: Failure Recovery**

```bash
# Test system behavior under various failure conditions

echo "🧪 Testing failure recovery..."

# Test 1: Invalid JSON
curl -X POST http://localhost:8000/webhook/superplane/analyze \
  -H "Content-Type: application/json" \
  -d '{"invalid": json}' \
  && echo "❌ Should have rejected invalid JSON" \
  || echo "✅ Properly rejected invalid JSON"

# Test 2: Missing required fields
curl -X POST http://localhost:8000/webhook/superplane/analyze \
  -H "Content-Type: application/json" \
  -d '{}' \
  | jq '.error' | grep -q "required" \
  && echo "✅ Validation working" \
  || echo "❌ Validation not working"

# Test 3: Rate limiting (if implemented)
for i in {1..10}; do
  curl -s -X POST http://localhost:8000/webhook/superplane/analyze \
    -H "Content-Type: application/json" \
    -d '{"test": "rate_limit"}' > /dev/null &
done
wait
echo "✅ Rate limiting test complete"
```

---

## 📊 **Performance Tests**

### **Load Testing** (Optional)

```bash
# Simple load test with curl
echo "🚀 Performance testing..."

# Test concurrent requests
time (
  for i in {1..5}; do
    curl -s -X POST http://localhost:8000/webhook/superplane/analyze \
      -H "Content-Type: application/json" \
      -d '{"incident_type": "load_test", "description": "Load test '$i'"}' &
  done
  wait
)

echo "✅ Load test complete - check response times"
```

### **Memory Usage**

```bash
# Monitor memory usage during operation
ps aux | grep "python api_server.py" | awk '{print "Memory: " $6/1024 " MB"}'

# Check for memory leaks (run multiple requests and monitor)
for i in {1..20}; do
  curl -s http://localhost:8000/health > /dev/null
  ps aux | grep "python api_server.py" | awk '{print "Request '$i': " $6/1024 " MB"}'
  sleep 1
done
```

---

## 🔍 **Debugging & Troubleshooting**

### **Common Issues & Solutions**

#### **Backend Won't Start**
```bash
# Check Python environment
python --version  # Should be 3.13+
which python

# Check dependencies
cd backend && uv sync
uv pip list | grep -E "(anthropic|google|fastapi)"

# Check port conflicts
lsof -i :8000
```

#### **Gemini AI Not Working**
```bash
# Verify API key
echo "API Key length: ${#GEMINI_API_KEY} characters"
python -c "
import google.generativeai as genai
genai.configure(api_key='$GEMINI_API_KEY')
print('✅ Gemini configured successfully')
"
```

#### **Frontend Not Loading**
```bash
# Check Node.js version
node --version  # Should be 20+
npm --version

# Clear cache and reinstall
cd frontend
rm -rf node_modules package-lock.json .next
npm install
npm run build
```

#### **Database Connection Issues**
```bash
# Check PostgreSQL URL (if using database)
echo $DATABASE_URL
psql $DATABASE_URL -c "SELECT 1;" 2>/dev/null && echo "✅ DB connected" || echo "❌ DB connection failed"
```

---

## ✅ **Test Results Checklist**

### **Critical Components** (Must Pass)
- [ ] Backend API server starts successfully
- [ ] Health endpoint returns "healthy" status  
- [ ] Google Gemini AI responds to test requests
- [ ] SuperPlane webhooks accept and process requests
- [ ] JIRA integration creates tickets with AI analysis
- [ ] Frontend loads with AutoSRE branding and Gruvbox theme

### **Important Components** (Should Pass)  
- [ ] All API routes are accessible
- [ ] Insights endpoints return mock data
- [ ] Frontend dashboard shows analytics
- [ ] Error handling works for invalid requests
- [ ] Fallback system activates when AI unavailable

### **Optional Components** (Nice to Have)
- [ ] SuperPlane Canvas integration working
- [ ] Real-time dashboard updates
- [ ] Performance under load acceptable
- [ ] Memory usage stable over time
- [ ] All historical data/trends showing

---

## 🚨 **Emergency Testing (Pre-Demo)**

**5-Minute Quick Test Before Important Demos:**

```bash
#!/bin/bash
echo "🚨 Emergency pre-demo test..."

# 1. Quick backend test
curl -s http://localhost:8000/health | jq -r '.status' | grep -q "healthy" && echo "✅ Backend OK" || echo "❌ Backend FAIL"

# 2. Quick AI test  
curl -s -X POST http://localhost:8000/webhook/superplane/analyze \
  -H "Content-Type: application/json" \
  -d '{"incident_type": "test", "description": "Quick test"}' \
  | jq -r '.success' | grep -q "true" && echo "✅ AI OK" || echo "❌ AI FAIL"

# 3. Quick frontend test
curl -s http://localhost:3000 | grep -q "AutoSRE" && echo "✅ Frontend OK" || echo "❌ Frontend FAIL"

echo "🚨 Emergency test complete!"
```

---

## 📈 **Success Metrics**

After completing all tests, you should have:

- **🟢 Backend:** API server running stable, all endpoints responding
- **🟢 AI Integration:** Gemini providing intelligent analysis with >80% relevance  
- **🟢 SuperPlane:** Webhooks processing incidents and triggering workflows
- **🟢 JIRA:** Tickets created automatically with structured AI insights
- **🟢 Frontend:** Dashboard loading with proper branding and functionality
- **🟢 Reliability:** System handles errors gracefully with fallback mechanisms

**If all critical tests pass:** ✅ **System is demo-ready!**  
**If any critical tests fail:** ❌ **Fix issues before proceeding to demo**

---

**🎯 Built for HackByte 4.0 - Ensuring AutoSRE v2.0 delivers reliable, intelligent infrastructure automation!**