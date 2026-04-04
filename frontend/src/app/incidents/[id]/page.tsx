'use client';

import { useQuery } from '@tanstack/react-query';
import {
  AlertCircle,
  ArrowLeft,
  CheckCircle2,
  ClipboardCopy,
  Loader2,
  RefreshCw,
  Terminal,
  XCircle,
} from 'lucide-react';
import { useParams, useRouter } from 'next/navigation';
import { useCallback, useState } from 'react';
import ApprovalModal from '@/components/ApprovalModal';
import { getIncident } from '@/lib/api';
import type {
  ActionLog,
  ActionStatus,
  AlertType,
  IncidentDetailResponse,
  IncidentStatus,
  RiskLevel,
} from '@/lib/types';

const AUTO_REFRESH_INTERVAL = 5_000;

const STATUS_COLORS: Record<IncidentStatus, { bg: string; text: string; dot: string }> = {
  PENDING: { bg: 'bg-gray-100', text: 'text-gray-700', dot: 'bg-gray-500' },
  ANALYZING: { bg: 'bg-blue-100', text: 'text-blue-700', dot: 'bg-blue-500' },
  APPROVAL_REQUIRED: { bg: 'bg-yellow-100', text: 'text-yellow-700', dot: 'bg-yellow-500' },
  EXECUTING: { bg: 'bg-purple-100', text: 'text-purple-700', dot: 'bg-purple-500' },
  RESOLVED: { bg: 'bg-green-100', text: 'text-green-700', dot: 'bg-green-500' },
  ESCALATED: { bg: 'bg-red-100', text: 'text-red-700', dot: 'bg-red-500' },
  FAILED: { bg: 'bg-red-100', text: 'text-red-700', dot: 'bg-red-500' },
  MONITOR_ONLY: { bg: 'bg-slate-100', text: 'text-slate-700', dot: 'bg-slate-500' },
  WHITELIST_BLOCKED: { bg: 'bg-orange-100', text: 'text-orange-700', dot: 'bg-orange-500' },
};

const STATUS_LABELS: Record<IncidentStatus, string> = {
  PENDING: 'Pending',
  ANALYZING: 'Analyzing',
  APPROVAL_REQUIRED: 'Approval Required',
  EXECUTING: 'Executing',
  RESOLVED: 'Resolved',
  ESCALATED: 'Escalated',
  FAILED: 'Failed',
  MONITOR_ONLY: 'Monitor Only',
  WHITELIST_BLOCKED: 'Whitelist Blocked',
};

const ALERT_TYPE_LABELS: Record<AlertType, string> = {
  CRASHLOOP: 'CrashLoop',
  OOMKILLED: 'OOMKilled',
  FAILED_DEPLOYMENT: 'Failed Deployment',
  PENDING_POD: 'Pending Pod',
  IMAGE_PULL_ERROR: 'Image Pull Error',
  UNKNOWN: 'Unknown',
};

const RISK_COLORS: Record<RiskLevel, { bg: string; text: string }> = {
  LOW: { bg: 'bg-green-100', text: 'text-green-700' },
  MEDIUM: { bg: 'bg-yellow-100', text: 'text-yellow-700' },
  HIGH: { bg: 'bg-red-100', text: 'text-red-700' },
};

const ACTION_STATUS_COLORS: Record<ActionStatus, { bg: string; text: string; icon: React.ElementType }> = {
  PENDING: { bg: 'bg-gray-100', text: 'text-gray-600', icon: Loader2 },
  SUCCESS: { bg: 'bg-green-100', text: 'text-green-700', icon: CheckCircle2 },
  FAILED: { bg: 'bg-red-100', text: 'text-red-700', icon: XCircle },
  REJECTED: { bg: 'bg-red-100', text: 'text-red-700', icon: XCircle },
};

function formatDate(isoString: string): string {
  const date = new Date(isoString);
  return date.toLocaleString('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false,
  });
}

function formatConfidence(score: number): number {
  return Math.round(score * 100);
}

function StatusBadge({ status }: { status: IncidentStatus }) {
  const colors = STATUS_COLORS[status];
  return (
    <span
      className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium ${colors.bg} ${colors.text}`}
    >
      <span className={`w-1.5 h-1.5 rounded-full ${colors.dot}`} />
      {STATUS_LABELS[status]}
    </span>
  );
}

function AlertTypeBadge({ alertType }: { alertType: AlertType }) {
  return (
    <span className="inline-flex items-center px-2.5 py-1 rounded-full text-xs font-medium bg-slate-100 text-slate-700">
      {ALERT_TYPE_LABELS[alertType] ?? alertType}
    </span>
  );
}

function RiskBadge({ risk }: { risk: RiskLevel }) {
  const colors = RISK_COLORS[risk];
  return (
    <span className={`inline-flex items-center px-2.5 py-1 rounded-full text-xs font-medium ${colors.bg} ${colors.text}`}>
      {risk}
    </span>
  );
}

function ConfidenceBar({ score }: { score: number }) {
  const pct = formatConfidence(score);
  const color = pct >= 80 ? 'bg-green-500' : pct >= 50 ? 'bg-yellow-500' : 'bg-red-500';
  return (
    <div className="flex items-center gap-3">
      <div className="flex-1 h-2 bg-gray-100 rounded-full overflow-hidden">
        <div
          className={`h-full rounded-full transition-all duration-500 ${color}`}
          style={{ width: `${pct}%` }}
        />
      </div>
      <span className="text-sm font-medium text-gray-700 w-10 text-right">{pct}%</span>
    </div>
  );
}

function CodeBlock({ command }: { command: string }) {
  const [copied, setCopied] = useState(false);

  const handleCopy = useCallback(async () => {
    await navigator.clipboard.writeText(command);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }, [command]);

  return (
    <div className="relative group">
      <pre className="bg-slate-900 text-slate-100 rounded-lg p-4 font-mono text-sm overflow-x-auto">
        <code>{command}</code>
      </pre>
      <button
        onClick={handleCopy}
        className="absolute top-2 right-2 p-2 rounded-md bg-slate-700 hover:bg-slate-600 text-slate-300 opacity-0 group-hover:opacity-100 transition-opacity"
        title="Copy command"
      >
        {copied ? (
          <CheckCircle2 className="w-4 h-4 text-green-400" />
        ) : (
          <ClipboardCopy className="w-4 h-4" />
        )}
      </button>
    </div>
  );
}

function ActionLogItem({ log }: { log: ActionLog }) {
  const colors = ACTION_STATUS_COLORS[log.status];
  const Icon = colors.icon;

  return (
    <div className="flex gap-4 py-4 border-b border-gray-100 last:border-0">
      <div className="flex-shrink-0 mt-0.5">
        <div className={`w-8 h-8 rounded-full flex items-center justify-center ${colors.bg}`}>
          <Icon className={`w-4 h-4 ${colors.text} ${log.status === 'PENDING' ? 'animate-spin' : ''}`} />
        </div>
      </div>
      <div className="flex-1 min-w-0">
        <div className="flex items-center justify-between gap-2 mb-1">
          <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${colors.bg} ${colors.text}`}>
            {log.status}
          </span>
          <span className="text-xs text-gray-400 flex-shrink-0">
            {formatDate(log.timestamp)}
          </span>
        </div>
        <pre className="font-mono text-xs text-gray-700 bg-gray-50 rounded p-2 mb-1 overflow-x-auto whitespace-pre-wrap break-all">
          {log.command}
        </pre>
        {log.result && (
          <p className="text-xs text-gray-500 mt-1 whitespace-pre-wrap">{log.result}</p>
        )}
        {log.confidence_score != null && (
          <div className="mt-2 flex items-center gap-2">
            <span className="text-xs text-gray-400">Confidence:</span>
            <ConfidenceBar score={log.confidence_score} />
          </div>
        )}
      </div>

      <ApprovalModal />
    </div>
  );
}

function LoadingState() {
  return (
    <div className="flex flex-col items-center justify-center py-20 text-gray-400">
      <Loader2 className="w-10 h-10 animate-spin mb-4" />
      <span className="text-sm">Loading incident…</span>
    </div>
  );
}

function ErrorState({ message, onRetry }: { message: string; onRetry: () => void }) {
  return (
    <div className="flex flex-col items-center justify-center py-20">
      <AlertCircle className="w-10 h-10 text-red-400 mb-4" />
      <p className="text-sm font-medium text-red-600 mb-1">Failed to load incident</p>
      <p className="text-xs text-gray-400 mb-4">{message}</p>
      <div className="flex gap-3">
        <button
          onClick={onRetry}
          className="inline-flex items-center gap-2 px-4 py-2 bg-gray-100 hover:bg-gray-200 text-gray-700 rounded-lg text-sm font-medium transition-colors"
        >
          <RefreshCw className="w-4 h-4" />
          Retry
        </button>
        <button
          onClick={() => window.history.back()}
          className="inline-flex items-center gap-2 px-4 py-2 bg-gray-100 hover:bg-gray-200 text-gray-700 rounded-lg text-sm font-medium transition-colors"
        >
          <ArrowLeft className="w-4 h-4" />
          Back
        </button>
      </div>
    </div>
  );
}

export default function IncidentDetailPage() {
  const params = useParams();
  const router = useRouter();
  const id = params.id as string;

  const { data, isLoading, isError, error, refetch } = useQuery<IncidentDetailResponse, Error>({
    queryKey: ['incident', id],
    queryFn: () => getIncident(id),
    refetchInterval: AUTO_REFRESH_INTERVAL,
    staleTime: 3_000,
    retry: 1,
  });

  const handleBack = useCallback(() => {
    router.push('/incidents');
  }, [router]);

  const handleExecute = useCallback(() => {
    window.dispatchEvent(
      new CustomEvent('incident:approve', {
        detail: {
          incidentId: id,
          command: data?.analysis?.[0]?.kubectl_command ?? '',
          analysis: data?.analysis?.[0] ?? null,
        },
      }),
    );
  }, [id, data]);

  const handleReject = useCallback(() => {
    window.dispatchEvent(
      new CustomEvent('incident:reject', {
        detail: {
          incidentId: id,
          command: data?.analysis?.[0]?.kubectl_command ?? '',
          analysis: data?.analysis?.[0] ?? null,
        },
      }),
    );
  }, [id, data]);

  if (isLoading) return <LoadingState />;

  if (isError) {
    return <ErrorState message={error?.message ?? 'Unknown error'} onRetry={() => refetch()} />;
  }

  const { incident, analysis, action_logs } = data!;
  const primaryAnalysis = analysis?.[0] ?? null;

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      <div className="flex items-center gap-4">
        <button
          onClick={handleBack}
          className="inline-flex items-center gap-1.5 px-3 py-1.5 text-sm text-gray-600 hover:text-gray-900 hover:bg-gray-100 rounded-lg transition-colors"
        >
          <ArrowLeft className="w-4 h-4" />
          Back
        </button>
        <div className="flex-1 flex items-center gap-3 flex-wrap">
          <span className="font-mono text-sm text-gray-500">#{incident.id}</span>
          <AlertTypeBadge alertType={incident.alert_type} />
          <StatusBadge status={incident.status} />
          <span className="font-mono text-xs text-gray-400">{incident.cluster_id}</span>
        </div>
        <span className="text-xs text-gray-400">
          {formatDate(incident.created_at)}
        </span>
      </div>

      {/* AI Analysis */}
      {primaryAnalysis && (
        <section className="bg-white border border-gray-200 rounded-xl overflow-hidden">
          <div className="px-5 py-4 border-b border-gray-100 flex items-center gap-2">
            <Terminal className="w-4 h-4 text-blue-500" />
            <h2 className="text-base font-semibold text-gray-900">AI Analysis</h2>
          </div>
          <div className="p-5 space-y-5">
            <div>
              <h3 className="text-xs font-semibold text-gray-400 uppercase tracking-wide mb-2">
                Root Cause
              </h3>
              <div className="bg-blue-50 border border-blue-100 rounded-lg px-4 py-3 text-sm text-blue-900">
                {primaryAnalysis.root_cause}
              </div>
            </div>

            <div>
              <h3 className="text-xs font-semibold text-gray-400 uppercase tracking-wide mb-2">
                Suggested Action
              </h3>
              <p className="text-sm text-gray-700">{primaryAnalysis.suggested_action}</p>
            </div>

            {primaryAnalysis.kubectl_command && (
              <div>
                <h3 className="text-xs font-semibold text-gray-400 uppercase tracking-wide mb-2">
                  kubectl Command
                </h3>
                <CodeBlock command={primaryAnalysis.kubectl_command} />
              </div>
            )}

            <div className="flex flex-col sm:flex-row gap-4 sm:items-center">
              <div className="flex-1">
                <div className="flex items-center justify-between mb-1.5">
                  <span className="text-xs font-semibold text-gray-400 uppercase tracking-wide">
                    Confidence
                  </span>
                </div>
                <ConfidenceBar score={primaryAnalysis.confidence_score} />
              </div>
              <div className="flex-shrink-0">
                <span className="text-xs font-semibold text-gray-400 uppercase tracking-wide block mb-1.5">
                  Risk Level
                </span>
                <RiskBadge risk={primaryAnalysis.risk_level} />
              </div>
            </div>
          </div>
        </section>
      )}

      {/* Action Logs */}
      <section className="bg-white border border-gray-200 rounded-xl overflow-hidden">
        <div className="px-5 py-4 border-b border-gray-100 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Terminal className="w-4 h-4 text-purple-500" />
            <h2 className="text-base font-semibold text-gray-900">Action Logs</h2>
          </div>
          {action_logs.length > 0 && (
            <span className="text-xs text-gray-400">{action_logs.length} log{action_logs.length !== 1 ? 's' : ''}</span>
          )}
        </div>
        <div className="p-5">
          {action_logs.length === 0 ? (
            <p className="text-sm text-gray-400 text-center py-6">No action logs yet.</p>
          ) : (
            <div>
              {action_logs.map((log) => (
                <ActionLogItem key={log.id} log={log} />
              ))}
            </div>
          )}
        </div>
      </section>

      {incident.status === 'APPROVAL_REQUIRED' && (
        <div className="flex items-center gap-3">
          <button
            onClick={handleExecute}
            className="inline-flex items-center gap-2 px-5 py-2.5 bg-green-600 hover:bg-green-700 text-white rounded-lg text-sm font-medium transition-colors shadow-sm"
          >
            <CheckCircle2 className="w-4 h-4" />
            Execute Action
          </button>
          <button
            onClick={handleReject}
            className="inline-flex items-center gap-2 px-5 py-2.5 bg-white hover:bg-red-50 text-red-600 border border-red-200 rounded-lg text-sm font-medium transition-colors"
          >
            <XCircle className="w-4 h-4" />
            Reject
          </button>
        </div>
      )}
    </div>
  );
}
