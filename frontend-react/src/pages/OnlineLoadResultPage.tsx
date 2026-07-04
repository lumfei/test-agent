import { useState, useEffect } from 'react';
import { useParams } from 'react-router-dom';
import { useReportStore } from '../stores/useReportStore';
import { useTestStore } from '../stores/useTestStore';
import { useReportDownload } from '../hooks/useReportDownload';
import { SummaryCards } from '../components/common/SummaryCards';
import { ResultsTable } from '../components/tables/ResultsTable';
import { FailureTable } from '../components/tables/FailureTable';
import { DownloadButton } from '../components/common/DownloadButton';
import { ErrorAlert } from '../components/common/ErrorAlert';
import { LoadingSkeleton } from '../components/common/LoadingSkeleton';
import { EmptyState } from '../components/common/EmptyState';
import { Search } from 'lucide-react';

export function OnlineLoadResultPage() {
  const { runId: paramRunId } = useParams<{ runId: string }>();
  const lastRunId = useTestStore((s) => s.runId);
  const [runIdInput, setRunIdInput] = useState(paramRunId || lastRunId || '');

  const report = useReportStore((s) => s.report);
  const isLoading = useReportStore((s) => s.isLoading);
  const error = useReportStore((s) => s.error);
  const loadFromRunId = useReportStore((s) => s.loadFromRunId);
  const clear = useReportStore((s) => s.clear);
  const selectedCategories = useReportStore((s) => s.selectedCategories);
  const setSelectedCategories = useReportStore((s) => s.setSelectedCategories);
  const resultFilter = useReportStore((s) => s.resultFilter);
  const setResultFilter = useReportStore((s) => s.setResultFilter);

  const { download, downloading } = useReportDownload();

  // Auto-load if navigated from history
  useEffect(() => {
    if (paramRunId && paramRunId !== report?.report_id) {
      setRunIdInput(paramRunId);
      loadFromRunId(paramRunId);
    }
  }, [paramRunId]); // eslint-disable-line react-hooks/exhaustive-deps

  const handleLoad = () => {
    if (runIdInput.trim()) {
      loadFromRunId(runIdInput.trim());
    }
  };

  const categories = report ? Object.keys(report.by_category) : [];
  const runId = report?.report_id || runIdInput;
  const failures = report ? report.results.filter((r) => !r.passed) : [];

  return (
    <div className="max-w-6xl mx-auto space-y-5">
      {/* Input */}
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1.5">Run ID</label>
        <div className="flex gap-2">
          <input
            type="text"
            value={runIdInput}
            onChange={(e) => setRunIdInput(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleLoad()}
            placeholder="输入 Run ID..."
            className="flex-1 px-4 py-2.5 text-sm border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-400 focus:border-transparent"
          />
          <button
            onClick={handleLoad}
            disabled={isLoading || !runIdInput.trim()}
            className="flex items-center gap-2 px-5 py-2.5 text-sm font-medium text-white bg-indigo-600 rounded-lg hover:bg-indigo-700 disabled:opacity-50 transition-colors"
          >
            <Search className="w-4 h-4" />
            加载结果
          </button>
        </div>
      </div>

      {error && <ErrorAlert message={error} onDismiss={clear} onRetry={handleLoad} />}

      {/* Loading */}
      {isLoading && (
        <div className="space-y-4">
          <LoadingSkeleton type="card" />
          <LoadingSkeleton type="table" />
        </div>
      )}

      {/* Empty state */}
      {!isLoading && !report && !error && (
        <EmptyState
          icon="🔍"
          title="输入 Run ID 以加载测试结果"
          description="Run ID 可在「运行测试」页面完成后获取，或在「测试历史」中查看。也支持 URL 参数跳转。"
        />
      )}

      {/* Results */}
      {report && (
        <>
          <SummaryCards
            total={report.summary.total}
            passed={report.summary.passed}
            failed={report.summary.failed}
            errors={report.summary.errors}
            passRate={report.summary.pass_rate}
            durationSeconds={report.duration_seconds}
          />

          {failures.length > 0 && <FailureTable failures={failures} />}

          <ResultsTable
            results={report.results}
            categories={categories}
            selectedCategories={selectedCategories}
            onCategoryChange={setSelectedCategories}
            resultFilter={resultFilter}
            onResultFilterChange={setResultFilter}
          />

          {/* Downloads */}
          {runId && (
            <div className="flex flex-wrap gap-2">
              <DownloadButton runId={runId} format="html" label="下载 HTML 报告" onDownload={download} isDownloading={downloading === `report_${runId}_html`} />
              <DownloadButton runId={runId} format="md" label="下载 Markdown 报告" onDownload={download} isDownloading={downloading === `report_${runId}_md`} />
              <DownloadButton runId={runId} format="json" label="下载 JSON 报告" onDownload={download} isDownloading={downloading === `report_${runId}_json`} />
            </div>
          )}
        </>
      )}
    </div>
  );
}
