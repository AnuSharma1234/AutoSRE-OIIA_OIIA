'use client';

import {
  CheckCircle,
  Loader2,
  X,
  XCircle,
} from 'lucide-react';
import { useCallback, useEffect, useState } from 'react';
import { executeAction } from '@/lib/api';
import type { AIAnalysis, RiskLevel } from '@/lib/types';

interface ApprovalEventDetail {
  incidentId: string;
  command: string;
  analysis?: AIAnalysis | null;
  reason?: string;
}

interface ApprovalModalProps {
  onClose?: () => void;
}

const RISK_COLORS: Record<RiskLevel, { bg: string; text: string }> = {
  LOW: { bg: 'bg-green-100', text: 'text-green-700' },
  MEDIUM: { bg: 'bg-yellow-100', text: 'text-yellow-700' },
  HIGH: { bg: 'bg-red-100', text: 'text-red-700' },
};

function formatConfidence(score: number): number {
  return Math.round(score * 100);
}

function RiskBadge({ risk }: { risk: RiskLevel }) {
  const colors = RISK_COLORS[risk];
  return (
    <span
      className={`inline-flex items-center px-2.5 py-1 rounded-full text-xs font-medium ${colors.bg} ${colors.text}`}
    >
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

export default function ApprovalModal({ onClose }: ApprovalModalProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [mode, setMode] = useState<'approve' | 'reject' | null>(null);
  const [incidentId, setIncidentId] = useState<string | null>(null);
  const [command, setCommand] = useState<string>('');
  const [analysis, setAnalysis] = useState<AIAnalysis | null>(null);
  const [reason, setReason] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleClose = useCallback(() => {
    setIsOpen(false);
    setMode(null);
    setIncidentId(null);
    setCommand('');
    setAnalysis(null);
    setReason('');
    setError(null);
    onClose?.();
  }, [onClose]);

  useEffect(() => {
    const handleApprove = (e: Event) => {
      const detail = (e as CustomEvent<ApprovalEventDetail>).detail;
      setMode('approve');
      setIncidentId(detail.incidentId);
      setCommand(detail.command ?? '');
      setAnalysis(detail.analysis ?? null);
      setIsOpen(true);
    };

    const handleReject = (e: Event) => {
      const detail = (e as CustomEvent<ApprovalEventDetail>).detail;
      setMode('reject');
      setIncidentId(detail.incidentId);
      setCommand(detail.command ?? '');
      setAnalysis(detail.analysis ?? null);
      setReason('');
      setIsOpen(true);
    };

    window.addEventListener('incident:approve', handleApprove);
    window.addEventListener('incident:reject', handleReject);

    return () => {
      window.removeEventListener('incident:approve', handleApprove);
      window.removeEventListener('incident:reject', handleReject);
    };
  }, []);

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && isOpen) {
        handleClose();
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, handleClose]);

  const handleConfirm = useCallback(async () => {
    if (!incidentId || !command) return;

    setIsLoading(true);
    setError(null);

    try {
      const result = await executeAction(incidentId, command, mode === 'approve');

      if (result.result?.success === false || result.status === 'FAILED') {
        setError(result.result?.error ?? `Action ${mode === 'approve' ? 'approved' : 'rejected'} but failed on the server.`);
        setIsLoading(false);
        return;
      }

      window.alert(
        mode === 'approve'
          ? 'Remediation approved and executed successfully.'
          : 'Remediation rejected.',
      );
      handleClose();
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'An unexpected error occurred.';
      setError(msg);
      setIsLoading(false);
    }
  }, [incidentId, command, mode, handleClose]);

  if (!isOpen || mode === null) {
    return null;
  }

  const isApprove = mode === 'approve';
  const titleColor = isApprove ? 'text-green-700' : 'text-red-700';
  const titleBg = isApprove ? 'bg-green-50 border-green-100' : 'bg-red-50 border-red-100';
  const iconBg = isApprove ? 'text-green-600' : 'text-red-600';
  const confirmBtn = isApprove
    ? 'bg-green-600 hover:bg-green-700 text-white'
    : 'bg-red-600 hover:bg-red-700 text-white';

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4"
      role="dialog"
      aria-modal="true"
      aria-labelledby="approval-modal-title"
    >
      <div
        className="absolute inset-0 bg-black/40 backdrop-blur-sm"
        onClick={handleClose}
      />

      <div className="relative w-full max-w-lg bg-white rounded-2xl shadow-2xl overflow-hidden animate-in fade-in zoom-in-95 duration-200">
        <div
          className={`flex items-center justify-between px-6 py-4 border-b ${titleBg}`}
        >
          <div className="flex items-center gap-3">
            <div className={iconBg}>
              {isApprove ? (
                <CheckCircle className="w-6 h-6" />
              ) : (
                <XCircle className="w-6 h-6" />
              )}
            </div>
            <h2 id="approval-modal-title" className={`text-lg font-semibold ${titleColor}`}>
              {isApprove ? 'Approve Remediation' : 'Reject Remediation'}
            </h2>
          </div>
          <button
            onClick={handleClose}
            disabled={isLoading}
            className="p-1.5 rounded-lg text-gray-400 hover:text-gray-600 hover:bg-white/60 disabled:opacity-40 transition-colors"
            aria-label="Close"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="px-6 py-5 space-y-5">
          <div className="flex items-center gap-3">
            <span className="text-xs font-semibold text-gray-400 uppercase tracking-wide">
              Incident
            </span>
            <span className="font-mono text-sm text-gray-700">#{incidentId}</span>
          </div>

          {command && (
            <div>
              <span className="text-xs font-semibold text-gray-400 uppercase tracking-wide block mb-2">
                kubectl Command
              </span>
              <pre className="bg-slate-900 text-slate-100 rounded-lg p-4 font-mono text-sm overflow-x-auto">
                <code>{command}</code>
              </pre>
            </div>
          )}

          {isApprove && analysis && (
            <>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <span className="text-xs font-semibold text-gray-400 uppercase tracking-wide block mb-1.5">
                    Confidence
                  </span>
                  <ConfidenceBar score={analysis.confidence_score} />
                </div>

                <div>
                  <span className="text-xs font-semibold text-gray-400 uppercase tracking-wide block mb-1.5">
                    Risk Level
                  </span>
                  <RiskBadge risk={analysis.risk_level} />
                </div>
              </div>

              <div>
                <span className="text-xs font-semibold text-gray-400 uppercase tracking-wide block mb-1.5">
                  Root Cause
                </span>
                <div className="bg-blue-50 border border-blue-100 rounded-lg px-4 py-3 text-sm text-blue-900">
                  {analysis.root_cause}
                </div>
              </div>
            </>
          )}

          {!isApprove && (
            <div>
              <span className="text-xs font-semibold text-gray-400 uppercase tracking-wide block mb-1.5">
                Reason <span className="font-normal text-gray-400">(optional)</span>
              </span>
              <textarea
                value={reason}
                onChange={(e) => setReason(e.target.value)}
                disabled={isLoading}
                placeholder="Provide a reason for rejection…"
                rows={3}
                className="w-full px-3 py-2 text-sm border border-gray-200 rounded-lg resize-none focus:outline-none focus:ring-2 focus:ring-red-300 focus:border-transparent placeholder-gray-300 disabled:opacity-50 disabled:bg-gray-50"
              />
            </div>
          )}

          {error && (
            <div className="bg-red-50 border border-red-200 rounded-lg px-4 py-3 text-sm text-red-700">
              {error}
            </div>
          )}
        </div>

        <div className="flex items-center justify-end gap-3 px-6 py-4 border-t border-gray-100 bg-gray-50/50">
          <button
            onClick={handleClose}
            disabled={isLoading}
            className="inline-flex items-center gap-2 px-4 py-2 text-sm font-medium text-gray-600 bg-white border border-gray-200 hover:bg-gray-50 rounded-lg transition-colors disabled:opacity-40"
          >
            Cancel
          </button>
          <button
            onClick={handleConfirm}
            disabled={isLoading || !command}
            className={`inline-flex items-center gap-2 px-5 py-2 text-sm font-medium rounded-lg transition-colors disabled:opacity-40 disabled:cursor-not-allowed ${confirmBtn}`}
          >
            {isLoading ? (
              <>
                <Loader2 className="w-4 h-4 animate-spin" />
                Processing…
              </>
            ) : isApprove ? (
              <>
                <CheckCircle className="w-4 h-4" />
                Approve & Execute
              </>
            ) : (
              <>
                <XCircle className="w-4 h-4" />
                Reject
              </>
            )}
          </button>
        </div>
      </div>
    </div>
  );
}
