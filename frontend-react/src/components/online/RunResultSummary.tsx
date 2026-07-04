import { useTestStore } from '../../stores/useTestStore';
import { useReportDownload } from '../../hooks/useReportDownload';
import { SummaryCards } from '../common/SummaryCards';
import { DownloadButton } from '../common/DownloadButton';
import { CheckCircle2, AlertTriangle } from 'lucide-react';

export function RunResultSummary() {
  const summary = useTestStore((s) => s.summary);
  const runId = useTestStore((s) => s.runId);
  const error = useTestStore((s) => s.error);
  const caseResults = useTestStore((s) => s.caseResults);
  const reset = useTestStore((s) => s.reset);
  const { download, downloading } = useReportDownload();

  if (!summary) return null;

  const failures = caseResults.filter((r) => !r.passed);
  const passRate = summary.pass_rate / 100;

  return (
    <div className="space-y-4">
      {/* Success banner */}
      <div className="flex items-center gap-3 bg-green-50 border border-green-200 rounded-lg p-4">
        <CheckCircle2 className="w-6 h-6 text-green-600" />
        <div className="flex-1">
          <p className="text-sm font-semibold text-green-800">
            测试完成 — 通过率 {(summary.pass_rate).toFixed(1)}%
          </p>
          <p className="text-xs text-green-600">
            API: {summary.api_name} &nbsp;|&nbsp; Run ID: {runId?.slice(0, 8)}
          </p>
        </div>
        <button
          onClick={reset}
          className="px-3 py-1.5 text-xs font-medium text-green-700 bg-green-100 rounded-md hover:bg-green-200 transition-colors"
        >
          清除
        </button>
      </div>

      {/* Summary cards */}
      <SummaryCards
        total={summary.total}
        passed={summary.passed}
        failed={summary.failed}
        errors={summary.errors}
        passRate={passRate}
      />

      {/* Error message if any */}
      {error && (
        <div className="flex items-center gap-2 bg-orange-50 border border-orange-200 rounded-lg p-3">
          <AlertTriangle className="w-4 h-4 text-orange-500" />
          <p className="text-sm text-orange-700">{error}</p>
        </div>
      )}

      {/* Failure summary */}
      {failures.length > 0 && (
        <div className="bg-white border border-red-100 rounded-lg p-4">
          <h4 className="text-sm font-semibold text-red-700 mb-3">
            失败用例 ({failures.length})
          </h4>
          <div className="space-y-1 max-h-60 overflow-y-auto">
            {failures.slice(0, 20).map((f, i) => (
              <div key={i} className="flex items-center gap-3 text-sm py-1.5 border-b border-red-50">
                <span className="text-red-500 font-medium">{f.method}</span>
                <span className="text-gray-600 truncate flex-1">{f.path}</span>
                <span className="text-xs text-gray-400">{f.status_code}</span>
              </div>
            ))}
            {failures.length > 20 && (
              <p className="text-xs text-gray-400 text-center pt-2">
                还有 {failures.length - 20} 个失败用例，请查看完整报告
              </p>
            )}
          </div>
        </div>
      )}

      {/* All passed */}
      {failures.length === 0 && (
        <div className="bg-white border border-green-100 rounded-lg p-6 text-center">
          <span className="text-4xl">🎉</span>
          <p className="text-sm font-medium text-green-700 mt-2">所有测试用例全部通过！</p>
        </div>
      )}

      {/* Downloads */}
      {runId && (
        <div className="flex flex-wrap gap-2">
          <DownloadButton
            runId={runId}
            format="html"
            label="下载 HTML 报告"
            onDownload={download}
            isDownloading={downloading === `report_${runId}_html`}
          />
          <DownloadButton
            runId={runId}
            format="md"
            label="下载 Markdown 报告"
            onDownload={download}
            isDownloading={downloading === `report_${runId}_md`}
          />
          <DownloadButton
            runId={runId}
            format="json"
            label="下载 JSON 报告"
            onDownload={download}
            isDownloading={downloading === `report_${runId}_json`}
          />
        </div>
      )}
    </div>
  );
}
