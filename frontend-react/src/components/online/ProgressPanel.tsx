import { useEffect, useRef } from 'react';
import { useTestStore } from '../../stores/useTestStore';
import { useSSE } from '../../hooks/useSSE';
import { ProgressNode } from './ProgressNode';
import { CaseResultRow } from './CaseResultRow';
import { Wifi, WifiOff } from 'lucide-react';

export function ProgressPanel() {
  const runId = useTestStore((s) => s.runId);
  const status = useTestStore((s) => s.status);
  const progressLog = useTestStore((s) => s.progressLog);
  const caseResults = useTestStore((s) => s.caseResults);
  const { isConnected, reconnectCount } = useSSE(runId);

  const bottomRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [progressLog.length, caseResults.length]);

  if (status !== 'running') return null;

  return (
    <div className="bg-white rounded-lg border border-gray-200">
      {/* Header */}
      <div className="px-5 py-3 border-b border-gray-100 flex items-center justify-between">
        <h3 className="text-sm font-semibold text-gray-700">
          测试运行中
          <span className="ml-2 text-xs font-normal text-gray-400">Run ID: {runId?.slice(0, 8)}</span>
        </h3>
        <div className="flex items-center gap-2">
          {isConnected ? (
            <span className="flex items-center gap-1 text-xs text-green-600">
              <Wifi className="w-3 h-3" /> 已连接
            </span>
          ) : (
            <span className="flex items-center gap-1 text-xs text-orange-500">
              <WifiOff className="w-3 h-3" /> 重连中({reconnectCount})
            </span>
          )}
        </div>
      </div>

      {/* Progress Nodes */}
      <div className="px-5 py-3 space-y-1 max-h-80 overflow-y-auto">
        {progressLog.length === 0 && (
          <p className="text-sm text-gray-400 text-center py-4">等待测试进度...</p>
        )}
        {progressLog.map((entry, i) => (
          <ProgressNode key={i} entry={entry} />
        ))}
        <div ref={bottomRef} />
      </div>

      {/* Case Results Stream */}
      {caseResults.length > 0 && (
        <div className="border-t border-gray-100">
          <div className="px-5 py-2 bg-gray-50 border-b border-gray-100">
            <span className="text-xs font-medium text-gray-500">
              实时结果 ({caseResults.length})
            </span>
          </div>
          <div className="max-h-60 overflow-y-auto">
            {caseResults.map((cr, i) => (
              <CaseResultRow key={i} result={cr} />
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
