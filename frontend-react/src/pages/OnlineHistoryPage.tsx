import { useEffect } from 'react';
import { useHistoryStore } from '../stores/useHistoryStore';
import { SummaryCards } from '../components/common/SummaryCards';
import { PassRateTrendChart } from '../components/charts/PassRateTrendChart';
import { HistoryTable } from '../components/tables/HistoryTable';
import { ErrorAlert } from '../components/common/ErrorAlert';
import { LoadingSkeleton } from '../components/common/LoadingSkeleton';
import { EmptyState } from '../components/common/EmptyState';
import { RefreshCw } from 'lucide-react';
export function OnlineHistoryPage() {
  const runs = useHistoryStore((s) => s.runs);
  const totalRuns = useHistoryStore((s) => s.totalRuns);
  const isLoading = useHistoryStore((s) => s.isLoading);
  const error = useHistoryStore((s) => s.error);
  const fetchHistory = useHistoryStore((s) => s.fetchHistory);

  useEffect(() => {
    fetchHistory(50);
  }, [fetchHistory]);

  // Compute summary stats
  const completed = runs.filter((r) => r.status === 'completed').length;
  const running = runs.filter((r) => r.status === 'running').length;
  const avgPassRate =
    runs.length > 0
      ? runs.reduce((sum, r) => sum + (r.pass_rate || 0), 0) / runs.filter((r) => r.pass_rate != null).length || runs.length
      : 0;

  return (
    <div className="max-w-6xl mx-auto space-y-5">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold text-gray-800">测试历史</h2>
        <button
          onClick={() => fetchHistory(50)}
          disabled={isLoading}
          className="flex items-center gap-2 px-3 py-1.5 text-sm border border-gray-200 rounded-lg hover:bg-gray-50 transition-colors disabled:opacity-50"
        >
          <RefreshCw className={`w-4 h-4 ${isLoading ? 'animate-spin' : ''}`} />
          刷新
        </button>
      </div>

      {error && <ErrorAlert message={error} onRetry={() => fetchHistory(50)} />}

      {isLoading ? (
        <div className="space-y-4">
          <LoadingSkeleton type="card" />
          <LoadingSkeleton type="table" />
        </div>
      ) : runs.length === 0 ? (
        <EmptyState
          icon="📊"
          title="暂无测试记录"
          description="运行一次测试后，这里将显示测试历史数据和通过率趋势。"
        />
      ) : (
        <>
          {/* Summary */}
          <SummaryCards
            total={totalRuns}
            passed={completed}
            failed={running}
            errors={runs.filter((r) => r.status === 'error').length}
            passRate={avgPassRate / 100}
          />

          {/* Trend */}
          <PassRateTrendChart runs={runs} />

          {/* Table */}
          <HistoryTable runs={runs} />
        </>
      )}
    </div>
  );
}
