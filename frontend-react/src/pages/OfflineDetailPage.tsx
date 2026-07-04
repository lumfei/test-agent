import { useReportStore } from '../stores/useReportStore';
import { FileDropZone } from '../components/common/FileDropZone';
import { SummaryCards } from '../components/common/SummaryCards';
import { ResultsTable } from '../components/tables/ResultsTable';
import { FailureTable } from '../components/tables/FailureTable';
import { ErrorAlert } from '../components/common/ErrorAlert';
import { LoadingSkeleton } from '../components/common/LoadingSkeleton';
import { EmptyState } from '../components/common/EmptyState';
import { formatTime, formatDuration } from '../utils/formatters';

export function OfflineDetailPage() {
  const report = useReportStore((s) => s.report);
  const isLoading = useReportStore((s) => s.isLoading);
  const error = useReportStore((s) => s.error);
  const loadFromFile = useReportStore((s) => s.loadFromFile);
  const selectedCategories = useReportStore((s) => s.selectedCategories);
  const setSelectedCategories = useReportStore((s) => s.setSelectedCategories);
  const resultFilter = useReportStore((s) => s.resultFilter);
  const setResultFilter = useReportStore((s) => s.setResultFilter);
  const clear = useReportStore((s) => s.clear);

  const categories = report ? Object.keys(report.by_category) : [];

  if (!report && !isLoading) {
    return (
      <div className="max-w-2xl mx-auto space-y-4">
        {error && <ErrorAlert message={error} onDismiss={clear} />}
        <FileDropZone onFile={loadFromFile} isLoading={isLoading} />
        <EmptyState icon="📋" title="选择 JSON 报告文件查看详细结果" />
      </div>
    );
  }

  if (isLoading || !report) {
    return (
      <div className="max-w-6xl mx-auto space-y-4">
        <LoadingSkeleton type="card" />
        <LoadingSkeleton type="table" />
      </div>
    );
  }

  const failures = report.results.filter((r) => !r.passed);

  return (
    <div className="max-w-6xl mx-auto space-y-5">
      {error && <ErrorAlert message={error} onDismiss={clear} />}

      <FileDropZone onFile={loadFromFile} isLoading={isLoading} />

      {/* Metadata */}
      <div className="bg-white rounded-lg border border-gray-100 p-5">
        <h3 className="text-sm font-semibold text-gray-700 mb-3">报告信息</h3>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <MetaItem label="API 名称" value={report.api_name} />
          <MetaItem label="Base URL" value={report.base_url || 'N/A'} />
          <MetaItem label="报告 ID" value={report.report_id} />
          <MetaItem label="生成时间" value={report.generated_at ? formatTime(report.generated_at) : 'N/A'} />
          {report.spec_url && <MetaItem label="Spec URL" value={report.spec_url} />}
          <MetaItem label="耗时" value={report.duration_seconds ? formatDuration(report.duration_seconds * 1000) : 'N/A'} />
        </div>
      </div>

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
    </div>
  );
}

function MetaItem({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <p className="text-xs text-gray-400 mb-0.5">{label}</p>
      <p className="text-sm text-gray-700 font-medium truncate">{value}</p>
    </div>
  );
}
