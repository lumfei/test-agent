import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

// Common components
import { SummaryCards } from '../components/common/SummaryCards';
import { StatusBadge } from '../components/common/StatusBadge';
import { EmptyState } from '../components/common/EmptyState';
import { ErrorAlert } from '../components/common/ErrorAlert';
import { LoadingSkeleton } from '../components/common/LoadingSkeleton';
import { DownloadButton } from '../components/common/DownloadButton';
import { FileDropZone } from '../components/common/FileDropZone';

// Online components
import { SpecUrlInput } from '../components/online/SpecUrlInput';
import { StartTestButton } from '../components/online/StartTestButton';
import { ProgressNode } from '../components/online/ProgressNode';
import { CaseResultRow } from '../components/online/CaseResultRow';

// Chart components (need wrapper for responsive container)
import { PassFailPieChart } from '../components/charts/PassFailPieChart';

// Table components
import { FailureTable } from '../components/tables/FailureTable';
import type { TestResult } from '../types';

// ==================== Common Components ====================

describe('SummaryCards', () => {
  it('renders all 5 stat cards with correct values', () => {
    render(<SummaryCards total={10} passed={8} failed={1} errors={1} passRate={0.8} />);
    expect(screen.getByText('总用例')).toBeInTheDocument();
    expect(screen.getByText('10')).toBeInTheDocument();
    expect(screen.getByText('8')).toBeInTheDocument();
    expect(screen.getByText('80.0%')).toBeInTheDocument();
  });

  it('renders duration in seconds when < 60s', () => {
    render(<SummaryCards total={5} passed={5} failed={0} errors={0} passRate={1} durationSeconds={30} />);
    expect(screen.getByText('30.0s')).toBeInTheDocument();
  });

  it('renders duration in minutes when >= 60s', () => {
    render(<SummaryCards total={5} passed={5} failed={0} errors={0} passRate={1} durationSeconds={125} />);
    expect(screen.getByText('2m 5s')).toBeInTheDocument();
  });

  it('does not render duration when not provided', () => {
    render(<SummaryCards total={5} passed={5} failed={0} errors={0} passRate={1} />);
    expect(screen.queryByText('⏱️')).not.toBeInTheDocument();
  });
});

describe('StatusBadge', () => {
  it('renders "通过" for passed=true', () => {
    render(<StatusBadge passed={true} />);
    expect(screen.getByText('通过')).toBeInTheDocument();
  });

  it('renders "失败" for passed=false', () => {
    render(<StatusBadge passed={false} />);
    expect(screen.getByText('失败')).toBeInTheDocument();
  });

  it('renders "错误" when error flag is true', () => {
    render(<StatusBadge passed={false} error={true} />);
    expect(screen.getByText('错误')).toBeInTheDocument();
  });
});

describe('EmptyState', () => {
  it('renders title and description', () => {
    render(<EmptyState title="No data" description="Nothing to show" />);
    expect(screen.getByText('No data')).toBeInTheDocument();
    expect(screen.getByText('Nothing to show')).toBeInTheDocument();
  });

  it('renders action when provided', () => {
    render(<EmptyState title="Empty" action={<button>Retry</button>} />);
    expect(screen.getByText('Retry')).toBeInTheDocument();
  });
});

describe('ErrorAlert', () => {
  it('renders error message', () => {
    render(<ErrorAlert message="Something went wrong" />);
    expect(screen.getByText('Something went wrong')).toBeInTheDocument();
  });

  it('calls onDismiss when close clicked', async () => {
    const onDismiss = vi.fn();
    render(<ErrorAlert message="Error" onDismiss={onDismiss} />);
    await userEvent.click(screen.getByTitle('关闭'));
    expect(onDismiss).toHaveBeenCalledOnce();
  });

  it('calls onRetry when retry clicked', async () => {
    const onRetry = vi.fn();
    render(<ErrorAlert message="Error" onRetry={onRetry} />);
    await userEvent.click(screen.getByTitle('重试'));
    expect(onRetry).toHaveBeenCalledOnce();
  });

  it('hides dismiss when onDismiss not provided', () => {
    render(<ErrorAlert message="Error" />);
    expect(screen.queryByTitle('关闭')).not.toBeInTheDocument();
  });
});

describe('LoadingSkeleton', () => {
  it('renders card skeleton with 5 placeholder cards', () => {
    const { container } = render(<LoadingSkeleton type="card" />);
    expect(container.querySelector('.animate-pulse')).toBeInTheDocument();
  });

  it('renders table skeleton with correct row count', () => {
    render(<LoadingSkeleton type="table" rows={3} />);
    const allRows = document.querySelectorAll('.animate-pulse .border-b');
    expect(allRows.length).toBeGreaterThanOrEqual(2);
  });

  it('renders chart skeleton', () => {
    render(<LoadingSkeleton type="chart" />);
    // Should have a tall placeholder box
    const chartBox = document.querySelector('.h-64');
    expect(chartBox).toBeInTheDocument();
  });
});

describe('DownloadButton', () => {
  it('renders label and triggers download on click', async () => {
    const onDownload = vi.fn().mockResolvedValue(undefined);
    render(
      <DownloadButton runId="r1" format="json" label="Download JSON" onDownload={onDownload} isDownloading={false} />,
    );
    await userEvent.click(screen.getByText('Download JSON'));
    expect(onDownload).toHaveBeenCalledWith('r1', 'json');
  });

  it('is disabled while downloading', () => {
    const onDownload = vi.fn();
    render(
      <DownloadButton runId="r1" format="html" label="Download" onDownload={onDownload} isDownloading={true} />,
    );
    expect(screen.getByRole('button')).toBeDisabled();
  });
});

describe('FileDropZone', () => {
  it('renders upload prompt', () => {
    render(<FileDropZone onFile={vi.fn()} />);
    expect(screen.getByText(/点击或拖拽/)).toBeInTheDocument();
    expect(screen.getByText(/report_\*\.json/)).toBeInTheDocument();
  });

  it('shows loading spinner when isLoading', () => {
    render(<FileDropZone onFile={vi.fn()} isLoading={true} />);
    expect(screen.getByText('正在解析文件...')).toBeInTheDocument();
  });

  it('shows error for non-JSON file', () => {
    const onFile = vi.fn();
    render(<FileDropZone onFile={onFile} />);
    const input = document.querySelector('input[type="file"]')! as HTMLInputElement;
    const file = new File(['text'], 'test.txt', { type: 'text/plain' });

    // jsdom: mock files property with a FileList-like object
    Object.defineProperty(input, 'files', {
      value: { 0: file, length: 1, item: () => file },
      writable: false,
    });
    fireEvent.change(input);

    expect(screen.getByText('请选择 JSON 格式的报告文件')).toBeInTheDocument();
    expect(onFile).not.toHaveBeenCalled();
  });

  it('calls onFile for valid JSON file', () => {
    const onFile = vi.fn();
    render(<FileDropZone onFile={onFile} />);
    const input = document.querySelector('input[type="file"]')! as HTMLInputElement;
    const file = new File(['{}'], 'report.json', { type: 'application/json' });

    Object.defineProperty(input, 'files', {
      value: { 0: file, length: 1, item: () => file },
      writable: false,
    });
    fireEvent.change(input);

    expect(onFile).toHaveBeenCalledWith(file);
  });

  it('rejects files > 50MB by showing error', () => {
    const onFile = vi.fn();
    render(<FileDropZone onFile={onFile} />);
    const input = document.querySelector('input[type="file"]')! as HTMLInputElement;
    const largeFile = new File(['x'.repeat(100)], 'large.json', { type: 'application/json' });
    Object.defineProperty(largeFile, 'size', { value: 51 * 1024 * 1024 });

    Object.defineProperty(input, 'files', {
      value: { 0: largeFile, length: 1, item: () => largeFile },
      writable: false,
    });
    fireEvent.change(input);

    expect(screen.getByText('文件大小不能超过 50MB')).toBeInTheDocument();
    expect(onFile).not.toHaveBeenCalled();
  });
});

// ==================== Online Components ====================

describe('SpecUrlInput', () => {
  it('renders input with correct placeholder', () => {
    render(<SpecUrlInput value="" onChange={vi.fn()} />);
    expect(screen.getByPlaceholderText(/OpenAPI/)).toBeInTheDocument();
  });

  it('displays current value', () => {
    render(<SpecUrlInput value="https://example.com" onChange={vi.fn()} />);
    expect(screen.getByDisplayValue('https://example.com')).toBeInTheDocument();
  });

  it('is disabled when disabled prop is true', () => {
    render(<SpecUrlInput value="" onChange={vi.fn()} disabled={true} />);
    expect(screen.getByRole('textbox')).toBeDisabled();
  });
});

describe('StartTestButton', () => {
  it('shows "开始测试" when idle', () => {
    render(<StartTestButton status="idle" onClick={vi.fn()} />);
    expect(screen.getByText('开始测试')).toBeInTheDocument();
  });

  it('shows "正在启动..." when starting', () => {
    render(<StartTestButton status="starting" onClick={vi.fn()} />);
    expect(screen.getByText('正在启动...')).toBeInTheDocument();
  });

  it('shows "测试运行中..." when running', () => {
    render(<StartTestButton status="running" onClick={vi.fn()} />);
    expect(screen.getByText('测试运行中...')).toBeInTheDocument();
  });

  it('is disabled when running', () => {
    render(<StartTestButton status="running" onClick={vi.fn()} />);
    expect(screen.getByRole('button')).toBeDisabled();
  });

  it('is disabled when starting', () => {
    render(<StartTestButton status="starting" onClick={vi.fn()} />);
    expect(screen.getByRole('button')).toBeDisabled();
  });

  it('calls onClick when clicked in idle state', async () => {
    const onClick = vi.fn();
    render(<StartTestButton status="idle" onClick={onClick} />);
    await userEvent.click(screen.getByRole('button'));
    expect(onClick).toHaveBeenCalledOnce();
  });
});

describe('ProgressNode', () => {
  it('renders label, progress bar, and percentage', () => {
    const entry = { node: 'parse', progress: 0.75, message: 'almost done', timestamp: Date.now() };
    render(<ProgressNode entry={entry} />);
    expect(screen.getByText('解析文档')).toBeInTheDocument();
    expect(screen.getByText('75%')).toBeInTheDocument();
    expect(screen.getByText('almost done')).toBeInTheDocument();
  });

  it('shows unknown node label as-is', () => {
    const entry = { node: 'custom_step', progress: 0.5, message: '', timestamp: Date.now() };
    render(<ProgressNode entry={entry} />);
    expect(screen.getByText('custom_step')).toBeInTheDocument();
  });

  it('renders 0% correctly', () => {
    const entry = { node: 'analyze', progress: 0, message: '', timestamp: Date.now() };
    render(<ProgressNode entry={entry} />);
    expect(screen.getByText('分析 API')).toBeInTheDocument();
    expect(screen.getByText('0%')).toBeInTheDocument();
  });
});

describe('CaseResultRow', () => {
  it('renders passed case with all fields', () => {
    const result = {
      case_name: 'Test Case',
      passed: true,
      method: 'GET',
      path: '/users',
      status_code: 200,
      elapsed_ms: 45,
      category: 'normal',
    };
    render(<CaseResultRow result={result} />);
    expect(screen.getByText('GET')).toBeInTheDocument();
    expect(screen.getByText('/users')).toBeInTheDocument();
    expect(screen.getByText('200')).toBeInTheDocument();
    expect(screen.getByText('45ms')).toBeInTheDocument();
  });

  it('renders failed case with 0 elapsed as ---', () => {
    const result = {
      case_name: 'Fail',
      passed: false,
      method: 'POST',
      path: '/bad',
      status_code: 500,
      elapsed_ms: 0,
      category: 'error',
    };
    render(<CaseResultRow result={result} />);
    expect(screen.getByText('POST')).toBeInTheDocument();
    // elapsed_ms=0 should show empty string
    expect(screen.queryByText('0ms')).not.toBeInTheDocument();
  });
});

// ==================== Chart Components ====================

describe('PassFailPieChart', () => {
  it('renders empty state when all values are 0', () => {
    render(<PassFailPieChart passed={0} failed={0} errors={0} />);
    expect(screen.getByText('暂无数据')).toBeInTheDocument();
  });

  it('renders chart when data exists', () => {
    const { container } = render(<PassFailPieChart passed={5} failed={2} errors={1} />);
    expect(screen.getByText('结果分布')).toBeInTheDocument();
    // Recharts ResponsiveContainer needs explicit dimensions in jsdom
    // Check that the chart wrapper is rendered
    expect(container.querySelector('.recharts-responsive-container')).toBeInTheDocument();
  });
});

// ==================== Table Components ====================

describe('FailureTable', () => {
  const makeResult = (overrides: Partial<TestResult> = {}): TestResult => ({
    name: 'Test',
    passed: false,
    method: 'GET',
    path: '/test',
    status_code: 400,
    elapsed_ms: 100,
    category: 'error',
    checks: [],
    error: null,
    ...overrides,
  });

  it('returns null when no failures', () => {
    const { container } = render(<FailureTable failures={[]} />);
    expect(container.innerHTML).toBe('');
  });

  it('renders failure table with count', () => {
    const failures = [
      makeResult({ name: 'Fail 1', method: 'GET', path: '/a' }),
      makeResult({ name: 'Fail 2', method: 'POST', path: '/b' }),
    ];
    render(<FailureTable failures={failures} />);
    expect(screen.getByText('失败用例 (2)')).toBeInTheDocument();
    expect(screen.getByText('Fail 1')).toBeInTheDocument();
    expect(screen.getByText('Fail 2')).toBeInTheDocument();
  });

  it('shows error as failure reason', () => {
    const failures = [makeResult({ name: 'Err', error: 'Connection refused' })];
    render(<FailureTable failures={failures} />);
    expect(screen.getByText('Connection refused')).toBeInTheDocument();
  });

  it('shows check detail as failure reason when no error', () => {
    const failures = [
      makeResult({
        name: 'Check Fail',
        error: null,
        checks: [{ check_name: 'status', passed: false, detail: 'expected 200 got 500' }],
      }),
    ];
    render(<FailureTable failures={failures} />);
    expect(screen.getByText('expected 200 got 500')).toBeInTheDocument();
  });

  it('expands row on click to show details', async () => {
    const failures = [
      makeResult({
        name: 'Expandable',
        checks: [
          { check_name: 'status_code', passed: false, detail: 'expected 200' },
          { check_name: 'body', passed: true, detail: 'OK' },
        ],
      }),
    ];
    render(<FailureTable failures={failures} />);
    // Click row to expand
    await userEvent.click(screen.getByText('Expandable'));
    expect(screen.getByText('status_code')).toBeInTheDocument();
    expect(screen.getByText('expected 200')).toBeInTheDocument();
  });
});
