'use client';

import { useQuery } from '@tanstack/react-query';
import { useRouter, useSearchParams } from 'next/navigation';
import { Suspense, useCallback, useEffect, useState } from 'react';
import {
  AlertCircle,
  ChevronLeft,
  ChevronRight,
  Loader2,
  RefreshCw,
  Search,
} from 'lucide-react';
import { getIncidents } from '@/lib/api';
import type { IncidentStatus } from '@/lib/types';

const STATUS_COLORS: Record<IncidentStatus, { bg: string; text: string; dot: string; border: string }> = {
  PENDING: { bg: 'bg-stone-100', text: 'text-stone-700', dot: 'bg-stone-400', border: 'border-stone-200' },
  ANALYZING: { bg: 'bg-sky-100', text: 'text-sky-700', dot: 'bg-sky-500', border: 'border-sky-200' },
  APPROVAL_REQUIRED: { bg: 'bg-amber-100', text: 'text-amber-700', dot: 'bg-amber-500', border: 'border-amber-200' },
  EXECUTING: { bg: 'bg-indigo-100', text: 'text-indigo-700', dot: 'bg-indigo-500', border: 'border-indigo-200' },
  RESOLVED: { bg: 'bg-emerald-100', text: 'text-emerald-700', dot: 'bg-emerald-500', border: 'border-emerald-200' },
  ESCALATED: { bg: 'bg-rose-100', text: 'text-rose-700', dot: 'bg-rose-500', border: 'border-rose-200' },
  FAILED: { bg: 'bg-rose-100', text: 'text-rose-700', dot: 'bg-rose-500', border: 'border-rose-200' },
  MONITOR_ONLY: { bg: 'bg-slate-100', text: 'text-slate-700', dot: 'bg-slate-500', border: 'border-slate-200' },
  WHITELIST_BLOCKED: { bg: 'bg-orange-100', text: 'text-orange-700', dot: 'bg-orange-500', border: 'border-orange-200' },
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

const ALERT_TYPE_LABELS: Record<string, string> = {
  CRASHLOOP: 'CrashLoop',
  OOMKILLED: 'OOMKilled',
  FAILED_DEPLOYMENT: 'Failed Deployment',
  PENDING_POD: 'Pending Pod',
  IMAGE_PULL_ERROR: 'Image Pull Error',
  UNKNOWN: 'Unknown',
};

const AUTO_REFRESH_INTERVAL = 10_000;

const STATUS_OPTIONS: { value: IncidentStatus | ''; label: string }[] = [
  { value: '', label: 'All Statuses' },
  { value: 'PENDING', label: 'Pending' },
  { value: 'ANALYZING', label: 'Analyzing' },
  { value: 'APPROVAL_REQUIRED', label: 'Approval Required' },
  { value: 'EXECUTING', label: 'Executing' },
  { value: 'RESOLVED', label: 'Resolved' },
  { value: 'ESCALATED', label: 'Escalated' },
  { value: 'FAILED', label: 'Failed' },
  { value: 'MONITOR_ONLY', label: 'Monitor Only' },
  { value: 'WHITELIST_BLOCKED', label: 'Whitelist Blocked' },
];

function formatDate(isoString: string): string {
  const date = new Date(isoString);
  return date.toLocaleString('en-US', {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  });
}

function StatusBadge({ status }: { status: IncidentStatus }) {
  const colors = STATUS_COLORS[status];
  return (
    <span
      className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] font-bold border tracking-tight ${colors.bg} ${colors.text} ${colors.border}`}
    >
      <span className={`w-1 h-1 rounded-full ${colors.dot}`} />
      {STATUS_LABELS[status].toUpperCase()}
    </span>
  );
}

function LoadingState() {
  return (
    <div className="flex flex-col items-center justify-center py-16 text-gray-400">
      <Loader2 className="w-8 h-8 animate-spin mb-3" />
      <span className="text-sm">Loading incidents…</span>
    </div>
  );
}

function ErrorState({ onRetry }: { onRetry: () => void }) {
  return (
    <div className="flex flex-col items-center justify-center py-16 text-red-500">
      <AlertCircle className="w-8 h-8 mb-3" />
      <p className="text-sm font-medium mb-3">Failed to load incidents</p>
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

function EmptyState() {
  return (
    <div className="flex flex-col items-center justify-center py-16 text-gray-400">
      <Search className="w-8 h-8 mb-3 opacity-50" />
      <p className="text-sm">No incidents found</p>
    </div>
  );
}

function IncidentsContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  
  const [page, setPage] = useState(() => Number(searchParams.get('page') ?? 1));
  const [statusFilter, setStatusFilter] = useState<IncidentStatus | ''>(() => {
    const s = searchParams.get('status');
    return (s as IncidentStatus) || '';
  });
  const [autoRefresh, setAutoRefresh] = useState(true);

  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ['incidents', { page, status: statusFilter || undefined }],
    queryFn: () =>
      getIncidents({
        page,
        limit: 20,
        ...(statusFilter ? { status: statusFilter } : {}),
      }),
    refetchInterval: autoRefresh ? AUTO_REFRESH_INTERVAL : false,
    staleTime: 5_000,
  });

  const totalPages = data ? Math.ceil(data.total / data.limit) : 0;

  const handleRowClick = useCallback(
    (incidentId: string) => {
      router.push(`/incidents/${incidentId}`);
    },
    [router],
  );

  const handleStatusChange = useCallback(
    (e: React.ChangeEvent<HTMLSelectElement>) => {
      const value = e.target.value as IncidentStatus | '';
      setStatusFilter(value);
      setPage(1);
    },
    [],
  );

  const handlePrevPage = useCallback(() => {
    setPage((p) => Math.max(1, p - 1));
  }, []);

  const handleNextPage = useCallback(() => {
    setPage((p) => Math.min(totalPages, p + 1));
  }, [totalPages]);

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'ArrowLeft') handlePrevPage();
      if (e.key === 'ArrowRight') handleNextPage();
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [handleNextPage, handlePrevPage]);

  return (
    <div className="max-w-6xl mx-auto space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold text-gray-900">Incidents</h1>
        <div className="flex items-center gap-3">
          <label className="inline-flex items-center gap-2 text-sm text-gray-500 cursor-pointer select-none">
            <input
              type="checkbox"
              checked={autoRefresh}
              onChange={(e) => setAutoRefresh(e.target.checked)}
              className="w-4 h-4 text-blue-600 rounded border-gray-300 focus:ring-blue-500"
            />
            Auto-refresh
          </label>
          <button
            onClick={() => refetch()}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 text-sm text-gray-600 hover:text-gray-900 hover:bg-gray-100 rounded-lg transition-colors"
            title="Refresh"
          >
            <RefreshCw className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* Filter Bar */}
      <div className="flex items-center gap-3 bg-white border border-gray-200 rounded-lg p-3">
        <label htmlFor="status-filter" className="text-sm text-gray-500 font-medium">
          Status
        </label>
        <select
          id="status-filter"
          value={statusFilter}
          onChange={handleStatusChange}
          className="text-sm border border-gray-200 rounded-lg px-3 py-1.5 bg-white text-gray-700 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent cursor-pointer"
        >
          {STATUS_OPTIONS.map((opt) => (
            <option key={opt.value} value={opt.value}>
              {opt.label}
            </option>
          ))}
        </select>

        {data && (
          <span className="ml-auto text-sm text-gray-400">
            {data.total} incident{data.total !== 1 ? 's' : ''} total
          </span>
        )}
      </div>

      {/* Table */}
      <div className="bg-white border border-gray-200 rounded-lg overflow-hidden">
        {isLoading ? (
          <LoadingState />
        ) : isError ? (
          <ErrorState onRetry={() => refetch()} />
        ) : !data?.incidents.length ? (
          <EmptyState />
        ) : (
          <>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-gray-100 bg-gray-50/50">
                    <th className="text-left font-medium text-gray-500 px-4 py-3 w-36">
                      Status
                    </th>
                    <th className="text-left font-medium text-gray-500 px-4 py-3 w-40">
                      Alert Type
                    </th>
                    <th className="text-left font-medium text-gray-500 px-4 py-3">
                      Cluster ID
                    </th>
                    <th className="text-left font-medium text-gray-500 px-4 py-3 w-36">
                      Created At
                    </th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100">
                  {data.incidents.map((incident) => (
                    <tr
                      key={incident.id}
                      onClick={() => handleRowClick(incident.id)}
                      className="hover:bg-gray-50/80 cursor-pointer transition-colors"
                    >
                      <td className="px-4 py-3">
                        <StatusBadge status={incident.status} />
                      </td>
                      <td className="px-4 py-3 text-gray-900 font-medium">
                        {ALERT_TYPE_LABELS[incident.alert_type] ?? incident.alert_type}
                      </td>
                      <td className="px-4 py-3 font-mono text-[11px] text-gray-500">
                        {incident.cluster_id}
                      </td>
                      <td className="px-4 py-4 text-gray-500 font-mono text-[11px]">
                        {formatDate(incident.created_at)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {/* Pagination */}
            {totalPages > 1 && (
              <div className="flex items-center justify-between px-4 py-3 border-t border-gray-100 bg-gray-50/50">
                <span className="text-xs text-gray-400">
                  Page {page} of {totalPages}
                </span>
                <div className="flex items-center gap-2">
                  <button
                    onClick={handlePrevPage}
                    disabled={page <= 1}
                    className="inline-flex items-center gap-1 px-3 py-1.5 text-sm border border-gray-200 rounded-lg hover:bg-white disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
                  >
                    <ChevronLeft className="w-4 h-4" />
                    Previous
                  </button>
                  <button
                    onClick={handleNextPage}
                    disabled={page >= totalPages}
                    className="inline-flex items-center gap-1 px-3 py-1.5 text-sm border border-gray-200 rounded-lg hover:bg-white disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
                  >
                    Next
                    <ChevronRight className="w-4 h-4" />
                  </button>
                </div>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}

export default function IncidentsPage() {
  return (
    <Suspense fallback={<LoadingState />}>
      <IncidentsContent />
    </Suspense>
  );
}
