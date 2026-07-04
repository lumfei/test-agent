import { useReportStore } from '../stores/useReportStore';
import { FileDropZone } from '../components/common/FileDropZone';
import { SummaryCards } from '../components/common/SummaryCards';
import { PassFailPieChart } from '../components/charts/PassFailPieChart';
import { CategoryBarChart } from '../components/charts/CategoryBarChart';
import { EndpointBarChart } from '../components/charts/EndpointBarChart';
import { ResultsTable } from '../components/tables/ResultsTable';
import { FailureTable } from '../components/tables/FailureTable';
import { ErrorAlert } from '../components/common/ErrorAlert';
import { LoadingSkeleton } from '../components/common/LoadingSkeleton';
import { EmptyState } from '../components/common/EmptyState';
import { Download } from 'lucide-react';

export function OfflineReportPage() {
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

  const handleExportJson = () => {
    if (!report) return;
    const json = JSON.stringify(report, null, 2);
    const blob = new Blob([json], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `report_${report.report_id || 'export'}.json`;
    a.click();
    URL.revokeObjectURL(url);
  };

  // No report loaded
  if (!report && !isLoading) {
    return (
      <div className="max-w-2xl mx-auto space-y-4">
        {error && <ErrorAlert message={error} onDismiss={clear} />}
        <FileDropZone onFile={loadFromFile} isLoading={isLoading} />
        <EmptyState
          icon="📁"
          title="选择或拖拽 JSON 报告文件"
          description="支持从 reports/ 目录导出的 report_*.json 文件，加载后可查看图表、筛选结果、浏览失败详情。"
        />
      </div>
    );
  }

  // Loading
  if (isLoading || !report) {
    return (
      <div className="max-w-6xl mx-auto space-y-4">
        <LoadingSkeleton type="card" />
        <LoadingSkeleton type="chart" />
        <LoadingSkeleton type="table" />
      </div>
    );
  }

  const failures = report.results.filter((r) => !r.passed);

  return (
    <div className="max-w-6xl mx-auto space-y-5">
      {error && <ErrorAlert message={error} onDismiss={clear} />}

      {/* File loader + Export */}
      <div className="flex items-start gap-4">
        <div className="flex-1">
          <FileDropZone onFile={loadFromFile} isLoading={isLoading} />
        </div>
        <button
          onClick={handleExportJson}
          className="flex items-center gap-2 px-4 py-2.5 text-sm border border-gray-200 rounded-lg hover:bg-gray-50 transition-colors"
        >
          <Download className="w-4 h-4" /> 导出 JSON
        </button>
      </div>

      {/* Summary */}
      <SummaryCards
        total={report.summary.total}
        passed={report.summary.passed}
        failed={report.summary.failed}
        errors={report.summary.errors}
        passRate={report.summary.pass_rate}
        durationSeconds={report.duration_seconds}
      />

      {/* Charts */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <PassFailPieChart
          passed={report.summary.passed}
          failed={report.summary.failed}
          errors={report.summary.errors}
        />
        <CategoryBarChart byCategory={report.by_category} />
      </div>

      <EndpointBarChart byEndpoint={report.by_endpoint} />

      {/* Failure details */}
      {failures.length > 0 && <FailureTable failures={failures} />}

      {/* Full results table */}
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
