'use client';

import { useState } from 'react';

export default function DashboardPage() {
  const [testMode] = useState(true);
  const [demoOutput, setDemoOutput] = useState<string | null>(null);

  const executeDemo = async () => {
    setDemoOutput('EXECUTING SCRIPT...');
    try {
      const res = await fetch('http://localhost:8000/api/v1/agent/analyze', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ incident_id: 'demo-' + Date.now(), context: { auto_remediate: true } })
      });
      const data = await res.json();
      setDemoOutput(res.ok ? 'SUCCESS: HTTP 200 OK — ' + (data.analysis?.summary || 'Analysis complete') : 'FAILED: ' + JSON.stringify(data));
    } catch (err: any) {
      setDemoOutput('ERROR: ' + err.message);
    }
  };

  return (
    <div className="min-h-screen bg-page text-text-main p-4 lg:p-8 font-sans">
      <div className="max-w-7xl mx-auto space-y-6">
        
        {/* Header Section */}
        <div className="flex flex-col md:flex-row items-start md:items-center justify-between gap-4 py-2 border-b border-border-line pb-6">
          <div>
            <h1 className="text-2xl font-semibold tracking-tight text-text-main">
              AutoSRE Console
            </h1>
            <p className="text-text-muted text-sm mt-1">
              Autonomous Infrastructure Intelligence & Remediation
            </p>
          </div>
          <div className="flex items-center gap-2 px-3 py-1 bg-card border border-border-line rounded text-resolved text-xs font-mono">
            <span>[SYS.STAT: ONLINE]</span>
          </div>
        </div>

        {/* Dashboard Grid */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          
          {/* Main Status Area */}
          <div className="lg:col-span-2 space-y-6">
            <div className="grid grid-cols-4 gap-4">
              <div className="p-4 bg-card border border-border-line rounded-md">
                <p className="text-xs text-text-muted uppercase tracking-wider mb-1">Active Incidents</p>
                <p className="text-xl font-mono text-resolved">0</p>
              </div>
              <div className="p-4 bg-card border border-border-line rounded-md">
                <p className="text-xs text-text-muted uppercase tracking-wider mb-1">AI Confidence</p>
                <p className="text-xl font-mono text-text-main">99.9%</p>
              </div>
              <div className="p-4 bg-card border border-border-line rounded-md">
                <p className="text-xs text-text-muted uppercase tracking-wider mb-1">Auto Responded</p>
                <p className="text-xl font-mono text-text-main">1204</p>
              </div>
              <div className="p-4 bg-card border border-border-line rounded-md">
                <p className="text-xs text-text-muted uppercase tracking-wider mb-1">MTTR</p>
                <p className="text-xl font-mono text-text-main">12ms</p>
              </div>
            </div>

            <div className="bg-card border border-border-line rounded-md">
              <div className="p-4 border-b border-border-line bg-[#0d1117] rounded-t-md">
                <h2 className="text-sm font-semibold text-text-main">Recent Activity Log</h2>
              </div>
              <div className="p-0 overflow-x-auto">
                <table className="w-full text-sm text-left">
                  <thead className="text-xs text-text-muted bg-[#161b22] border-b border-border-line">
                    <tr>
                      <th className="px-4 py-2 font-normal">TIMESTAMP</th>
                      <th className="px-4 py-2 font-normal">SOURCE</th>
                      <th className="px-4 py-2 font-normal">MESSAGE</th>
                      <th className="px-4 py-2 font-normal text-right">STATUS</th>
                    </tr>
                  </thead>
                  <tbody className="font-mono text-xs">
                    <tr className="border-b border-border-line hover:bg-[#1c2128] fade-in-row">
                      <td className="px-4 py-3 text-text-muted">2026-04-05T05:30:17Z</td>
                      <td className="px-4 py-3 text-info">KubeWatcher</td>
                      <td className="px-4 py-3 text-text-main">Anomalous spike detected on <span className="px-1 py-0.5 bg-[#21262d] border border-[#30363d] rounded text-critical">pod/api-prod-7f</span></td>
                      <td className="px-4 py-3 text-right text-warning">EVALUATING</td>
                    </tr>
                    <tr className="border-b border-border-line hover:bg-[#1c2128]">
                      <td className="px-4 py-3 text-text-muted">2026-04-05T05:28:44Z</td>
                      <td className="px-4 py-3 text-info">GeminiCore</td>
                      <td className="px-4 py-3 text-text-main">Applied fix: <span className="px-1 py-0.5 bg-[#21262d] border border-[#30363d] rounded text-text-main">kubectl scale deploy worker --replicas=5</span></td>
                      <td className="px-4 py-3 text-right text-resolved">RESOLVED</td>
                    </tr>
                    <tr className="hover:bg-[#1c2128]">
                      <td className="px-4 py-3 text-text-muted">2026-04-04T12:12:00Z</td>
                      <td className="px-4 py-3 text-info">InfraNet</td>
                      <td className="px-4 py-3 text-text-main">Initialized environment sync. SuperPlane configured successfully.</td>
                      <td className="px-4 py-3 text-right text-resolved">RESOLVED</td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </div>
          </div>

          <div className="space-y-6">
            <div className="bg-card border border-border-line rounded-md">
              <div className="p-4 border-b border-border-line bg-[#0d1117] rounded-t-md">
                <h3 className="text-sm font-semibold text-text-main">System Health</h3>
              </div>
              <div className="p-4 space-y-3">
                <div className="flex justify-between items-center text-sm border-b border-[#21262d] pb-2">
                  <span className="text-text-main">Gemini Pro API</span>
                  <span className="text-resolved font-mono text-xs px-2 py-0.5 bg-[#238636]/10 border border-[#238636] rounded">OK</span>
                </div>
                <div className="flex justify-between items-center text-sm border-b border-[#21262d] pb-2">
                  <span className="text-text-main">SuperPlane Hub</span>
                  <span className="text-resolved font-mono text-xs px-2 py-0.5 bg-[#238636]/10 border border-[#238636] rounded">SYNC</span>
                </div>
                <div className="flex justify-between items-center text-sm border-b border-[#21262d] pb-2">
                  <span className="text-text-main">K8s Cluster</span>
                  <span className="text-resolved font-mono text-xs px-2 py-0.5 bg-[#238636]/10 border border-[#238636] rounded">ACTIVE</span>
                </div>
                <div className="flex justify-between items-center text-sm">
                  <span className="text-text-main">JIRA API</span>
                  <span className="text-resolved font-mono text-xs px-2 py-0.5 bg-[#238636]/10 border border-[#238636] rounded">READY</span>
                </div>
              </div>
            </div>

            <div className="bg-card border border-border-line rounded-md">
              <div className="p-4 border-b border-border-line bg-[#0d1117] rounded-t-md">
                <h3 className="text-sm font-semibold text-text-main">Trigger Action</h3>
              </div>
              <div className="p-4 space-y-4">
                <p className="text-xs text-text-muted">
                  Launch a simulated incident payload to view autonomous root cause analysis and ticket creation flow via API <span className="font-mono text-text-main">:8001</span>.
                </p>
                <button 
                  onClick={executeDemo}
                  className="w-full px-4 py-2 bg-[#21262d] hover:bg-[#30363d] border border-border-line rounded-md text-text-main text-sm font-medium transition-none"
                >
                  Execute Demo Script
                </button>
                {demoOutput && (
                  <div className="mt-4 p-3 bg-[#11151c] border border-border-line rounded text-xs font-mono text-info break-words">
                    {demoOutput}
                  </div>
                )}
              </div>
            </div>
            
            {testMode && (
              <div className="p-3 border border-[#d29922]/50 bg-[#d29922]/10 text-warning text-xs rounded-md">
                <span className="font-mono block mb-1">MODE: DEMONSTRATION</span>
                Dashboard running in local context. External API calls are functionally mocked.
              </div>
            )}
          </div>
          
        </div>
      </div>
    </div>
  );
}