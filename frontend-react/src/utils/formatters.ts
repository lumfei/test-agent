import type { TestReport } from '../types';

/** Format a decimal (0-1) as a percentage string */
export function formatPercent(rate: number, decimals = 1): string {
  return `${(rate * 100).toFixed(decimals)}%`;
}

/** Format milliseconds to a human-readable string */
export function formatDuration(ms: number): string {
  if (ms < 1000) return `${Math.round(ms)}ms`;
  if (ms < 60000) return `${(ms / 1000).toFixed(1)}s`;
  const mins = Math.floor(ms / 60000);
  const secs = Math.round((ms % 60000) / 1000);
  return `${mins}m ${secs}s`;
}

/** Format ISO 8601 timestamp to a short local string */
export function formatTime(iso: string): string {
  try {
    const d = new Date(iso);
    if (isNaN(d.getTime())) return iso;
    return d.toLocaleString('zh-CN', {
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
    });
  } catch {
    return iso;
  }
}

/** Truncate a string to maxLen, appending "..." */
export function truncate(s: string, maxLen = 60): string {
  if (s.length <= maxLen) return s;
  return s.slice(0, maxLen - 3) + '...';
}

/** Validate a TestReport JSON structure, returns error message or null */
export function validateReport(data: unknown): { valid: boolean; error?: string } {
  if (!data || typeof data !== 'object') {
    return { valid: false, error: '数据格式错误：不是有效的 JSON 对象' };
  }
  const r = data as Record<string, unknown>;
  if (!r.report_id || typeof r.report_id !== 'string') {
    return { valid: false, error: '缺少必填字段: report_id' };
  }
  if (!r.summary || typeof r.summary !== 'object') {
    return { valid: false, error: '缺少必填字段: summary' };
  }
  if (!Array.isArray(r.results)) {
    return { valid: false, error: '缺少必填字段: results (应为数组)' };
  }
  return { valid: true };
}

/** Parse a JSON report file and return typed TestReport */
export function parseReport(json: string): TestReport {
  const data = JSON.parse(json);
  const validation = validateReport(data);
  if (!validation.valid) {
    throw new Error(validation.error ?? '报告格式无效');
  }
  // Normalize: ensure results have expected shape
  const results = (data.results as unknown[]).map((r: unknown, i: number) => {
    const item = r as Record<string, unknown>;
    return {
      name: (item.name as string) || (item.case_name as string) || `Case #${i}`,
      passed: Boolean(item.passed),
      method: (item.method as string) || 'GET',
      path: (item.path as string) || '/',
      status_code: Number(item.status_code ?? 0),
      elapsed_ms: Number(item.elapsed_ms ?? 0),
      expected_status: item.expected_status as number | number[] | undefined,
      category: (item.category as string) || 'unknown',
      checks: Array.isArray(item.checks) ? (item.checks as TestReport['results'][0]['checks']) : [],
      error: (item.error as string) ?? null,
      response_preview: (item.response_preview as string) || '',
      tags: Array.isArray(item.tags) ? (item.tags as string[]) : [],
    };
  });
  return {
    report_id: data.report_id as string,
    api_name: (data.api_name as string) || 'Unknown API',
    base_url: (data.base_url as string) || '',
    spec_url: (data.spec_url as string) ?? null,
    generated_at: (data.generated_at as string) || new Date().toISOString(),
    duration_seconds: Number(data.duration_seconds ?? 0),
    summary: {
      total: Number(data.summary?.total ?? 0),
      passed: Number(data.summary?.passed ?? 0),
      failed: Number(data.summary?.failed ?? 0),
      errors: Number(data.summary?.errors ?? 0),
      pass_rate: Number(data.summary?.pass_rate ?? 0),
    },
    by_category: (data.by_category as TestReport['by_category']) || {},
    by_endpoint: (data.by_endpoint as TestReport['by_endpoint']) || {},
    results,
  } as TestReport;
}
