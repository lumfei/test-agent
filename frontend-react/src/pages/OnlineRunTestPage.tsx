import { useTestStore } from '../stores/useTestStore';
import { SpecUrlInput } from '../components/online/SpecUrlInput';
import { StartTestButton } from '../components/online/StartTestButton';
import { ProgressPanel } from '../components/online/ProgressPanel';
import { RunResultSummary } from '../components/online/RunResultSummary';
import { ErrorAlert } from '../components/common/ErrorAlert';
import { EmptyState } from '../components/common/EmptyState';
import { QUICK_FILL_URLS } from '../utils/constants';

export function OnlineRunTestPage() {
  const specUrl = useTestStore((s) => s.specUrl);
  const setSpecUrl = useTestStore((s) => s.setSpecUrl);
  const status = useTestStore((s) => s.status);
  const error = useTestStore((s) => s.error);
  const summary = useTestStore((s) => s.summary);
  const startTest = useTestStore((s) => s.startTest);
  const setError = useTestStore((s) => s.setError);

  const handleQuickFill = (url: string) => {
    setSpecUrl(url);
  };

  const handleStart = () => {
    startTest();
  };

  return (
    <div className="max-w-4xl mx-auto space-y-5">
      {/* Input Section - hidden when running or completed */}
      {status !== 'running' && !summary && (
        <div className="space-y-4">
          {/* Spec URL */}
          <SpecUrlInput
            value={specUrl}
            onChange={setSpecUrl}
            disabled={status === 'starting'}
          />

          {/* Quick fill */}
          <div className="flex items-center gap-2">
            <span className="text-xs text-gray-400">快速填入:</span>
            {QUICK_FILL_URLS.map((item) => (
              <button
                key={item.url}
                onClick={() => handleQuickFill(item.url)}
                className="px-3 py-1 text-xs border border-gray-200 rounded-md text-gray-600 hover:bg-gray-50 hover:border-gray-300 transition-colors"
              >
                {item.label}
              </button>
            ))}
          </div>

          {/* Start button */}
          <StartTestButton status={status} onClick={handleStart} />

          {/* Idle state hint */}
          {status === 'idle' && (
            <EmptyState
              icon="🚀"
              title="输入 API 文档 URL 并点击「开始测试」"
              description="支持 OpenAPI 3.0 / Swagger 2.0 规范，也支持抓取 Swagger UI 页面。测试过程可实时查看进度。"
            />
          )}
        </div>
      )}

      {/* Error */}
      {error && status !== 'running' && (
        <ErrorAlert message={error} onDismiss={() => setError('')} />
      )}

      {/* Progress Panel - during test */}
      <ProgressPanel />

      {/* Results Summary - after completion */}
      {summary && <RunResultSummary />}
    </div>
  );
}
