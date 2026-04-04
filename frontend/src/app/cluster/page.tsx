'use client';

import { useQuery } from '@tanstack/react-query';
import { useRouter } from 'next/navigation';
import {
  AlertCircle,
  AlertTriangle,
  CheckCircle,
  Clock,
  RefreshCw,
  Server,
} from 'lucide-react';
import { getClusterOverview } from '@/lib/api';
import type { IncidentStatus } from '@/lib/types';
import type { AlertType } from '@/lib/types';

const AUTO_REFRESH_INTERVAL = 10_000;

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

function timeAgo(isoString: string | null): string {
  if (!isoString) return '—';
  const diff = Date.now() - new Date(isoString).getTime();
  const mins = Math.floor(diff / 60_000);
  if (mins < 1) return 'just now';
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours}h ago`;
  return `${Math.floor(hours / 24)}d ago`;
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

function PodCard({
  label,
  value,
  icon: Icon,
  iconColor,
  cardBg,
}: {
  label: string;
  value: number;
  icon: React.ComponentType<{ className?: string }>;
  iconColor: string;
  cardBg: string;
}) {
  return (
    <div className="bg-white border border-gray-200 rounded-lg p-5 flex items-center gap-4">
      <div className={`p-3 rounded-xl ${cardBg}`}>
        <Icon className={`w-6 h-6 ${iconColor}`} />
      </div>
      <div>
        <p className="text-sm text-gray-500 font-medium">{label}</p>
        <p className="text-3xl font-bold text-gray-900 leading-none mt-1">{value}</p>
      </div>
    </div>
  );
}

function NodeStatusDot({ status }: { status: string }) {
  const isReady = status === 'Ready';
  return (
    <span className={`inline-flex items-center gap-1.5 text-xs font-medium ${isReady ? 'text-green-700' : 'text-red-700'}`}>
      <span className={`w-1.5 h-1.5 rounded-full ${isReady ? 'bg-green-500' : 'bg-red-500'}`} />
      {status}
    </span>
  );
}

function LoadingState() {
  return (
    <div className="flex flex-col items-center justify-center py-20 text-gray-400">
      <RefreshCw className="w-8 h-8 animate-spin mb-3" />
      <span className="text-sm">Loading cluster overview…</span>
    </div>
  );
}

function ErrorState({ onRetry }: { onRetry: () => void }) {
  return (
    <div className="flex flex-col items-center justify-center py-20 text-red-500">
      <AlertCircle className="w-8 h-8 mb-3" />
      <p className="text-sm font-medium mb-3">Failed to load cluster overview</p>
      <button
        onClick={onRetry}
        className="inline-flex items-center gap-2 px-4 py-2 bg-red-50 hover:bg-red-100 text-red-600 rounded-lg text-sm font-medium transition-colors"
      >
        <RefreshCw className="w-4 h-4" />
        Retry
      </button>
    </div>
  );
}

export default function ClusterPage() {
  const router = useRouter();

  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ['cluster-overview'],
    queryFn: getClusterOverview,
    refetchInterval: AUTO_REFRESH_INTERVAL,
    staleTime: 5_000,
  });

  return (
    <div className="max-w-6xl mx-auto space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold text-gray-900">Cluster Overview</h1>
        <button
          onClick={() => refetch()}
          className="inline-flex items-center gap-1.5 px-3 py-1.5 text-sm text-gray-600 hover:text-gray-900 hover:bg-gray-100 rounded-lg transition-colors"
          title="Refresh"
        >
          <RefreshCw className="w-4 h-4" />
          Refresh
        </button>
      </div>

      {isLoading ? (
        <LoadingState />
      ) : isError ? (
        <ErrorState onRetry={() => refetch()} />
      ) : data ? (
        <>
          <section>
            <h2 className="text-sm font-medium text-gray-500 mb-3">Pod Summary</h2>
            <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
              <PodCard
                label="Total Pods"
                value={data.pod_summary.total}
                icon={Server}
                iconColor="text-gray-500"
                cardBg="bg-gray-50"
              />
              <PodCard
                label="Running"
                value={data.pod_summary.running}
                icon={CheckCircle}
                iconColor="text-green-600"
                cardBg="bg-green-50"
              />
              <PodCard
                label="Pending"
                value={data.pod_summary.pending}
                icon={Clock}
                iconColor="text-yellow-600"
                cardBg="bg-yellow-50"
              />
              <PodCard
                label="Failed"
                value={data.pod_summary.failed}
                icon={AlertTriangle}
                iconColor="text-red-600"
                cardBg="bg-red-50"
              />
            </div>
          </section>

          <div className="grid grid-cols-1 lg:grid-cols-5 gap-6">
            <section className="lg:col-span-3">
              <h2 className="text-sm font-medium text-gray-500 mb-3">Nodes</h2>
              <div className="bg-white border border-gray-200 rounded-lg overflow-hidden">
                {data.nodes.length === 0 ? (
                  <div className="flex flex-col items-center justify-center py-12 text-gray-400">
                    <Server className="w-8 h-8 mb-3 opacity-50" />
                    <p className="text-sm">No nodes found</p>
                  </div>
                ) : (
                  <div className="overflow-x-auto">
                    <table className="w-full text-sm">
                      <thead>
                        <tr className="border-b border-gray-100 bg-gray-50/50">
                          <th className="text-left font-medium text-gray-500 px-4 py-3">
                            Name
                          </th>
                          <th className="text-left font-medium text-gray-500 px-4 py-3 w-36">
                            Status
                          </th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-gray-50">
                        {data.nodes.map((node) => (
                          <tr key={node.name} className="hover:bg-gray-50 transition-colors">
                            <td className="px-4 py-3 font-mono text-xs text-gray-800">
                              {node.name}
                            </td>
                            <td className="px-4 py-3">
                              <NodeStatusDot status={node.status} />
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>
            </section>

            <section className="lg:col-span-2">
              <div className="flex items-center justify-between mb-3">
                <h2 className="text-sm font-medium text-gray-500">Recent Incidents</h2>
                <button
                  onClick={() => router.push('/incidents')}
                  className="text-xs text-blue-600 hover:text-blue-700 hover:underline transition-colors"
                >
                  View all
                </button>
              </div>
              <div className="bg-white border border-gray-200 rounded-lg overflow-hidden">
                {data.recent_incidents.length === 0 ? (
                  <div className="flex flex-col items-center justify-center py-12 text-gray-400">
                    <CheckCircle className="w-8 h-8 mb-3 opacity-50" />
                    <p className="text-sm">No recent incidents</p>
                  </div>
                ) : (
                  <ul className="divide-y divide-gray-50">
                    {data.recent_incidents.slice(0, 5).map((incident) => (
                      <li
                        key={incident.id}
                        onClick={() => router.push(`/incidents/${incident.id}`)}
                        className="px-4 py-3 hover:bg-blue-50/50 cursor-pointer transition-colors"
                      >
                        <div className="flex items-start justify-between gap-2">
                          <div className="min-w-0">
                            <p className="font-mono text-xs text-gray-800 font-medium truncate">
                              {incident.id}
                            </p>
                            <p className="text-xs text-gray-500 mt-0.5">
                              {ALERT_TYPE_LABELS[incident.alert_type] ?? incident.alert_type}
                            </p>
                          </div>
                          <div className="flex flex-col items-end gap-1 shrink-0">
                            <StatusBadge status={incident.status} />
                            <span className="text-xs text-gray-400">
                              {timeAgo(incident.created_at)}
                            </span>
                          </div>
                        </div>
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            </section>
          </div>

          {data.namespaces.length > 0 && (
            <section>
              <h2 className="text-sm font-medium text-gray-500 mb-3">Namespaces</h2>
              <div className="flex flex-wrap gap-2">
                {data.namespaces.map((ns) => (
                  <span
                    key={ns}
                    className="px-3 py-1.5 bg-white border border-gray-200 rounded-full text-xs font-mono text-gray-700"
                  >
                    {ns}
                  </span>
                ))}
              </div>
            </section>
          )}
        </>
      ) : null}
    </div>
  );
}
