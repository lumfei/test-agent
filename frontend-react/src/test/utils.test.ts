import { describe, it, expect } from 'vitest';
import { formatPercent, formatDuration, formatTime, truncate, validateReport, parseReport } from '../utils/formatters';

// ===== formatPercent =====
describe('formatPercent', () => {
  it('formats 0.5 as "50.0%"', () => {
    expect(formatPercent(0.5)).toBe('50.0%');
  });

  it('formats 1 as "100.0%"', () => {
    expect(formatPercent(1)).toBe('100.0%');
  });

  it('formats 0 as "0.0%"', () => {
    expect(formatPercent(0)).toBe('0.0%');
  });

  it('handles 2 decimal places', () => {
    expect(formatPercent(0.1234, 2)).toBe('12.34%');
  });

  it('handles 0 decimal places', () => {
    expect(formatPercent(0.567, 0)).toBe('57%');
  });
});

// ===== formatDuration =====
describe('formatDuration', () => {
  it('formats milliseconds < 1000', () => {
    expect(formatDuration(500)).toBe('500ms');
  });

  it('formats seconds < 60000', () => {
    expect(formatDuration(3500)).toBe('3.5s');
  });

  it('formats minutes >= 60000', () => {
    expect(formatDuration(125000)).toMatch(/^\d+m \d+s$/);
  });

  it('handles 0', () => {
    expect(formatDuration(0)).toBe('0ms');
  });
});

// ===== formatTime =====
describe('formatTime', () => {
  it('formats ISO 8601 string', () => {
    const result = formatTime('2026-07-01T13:44:14.479417+00:00');
    expect(result).toContain('07/01');
  });

  it('returns original on invalid input', () => {
    expect(formatTime('not-a-date')).toBe('not-a-date');
  });
});

// ===== truncate =====
describe('truncate', () => {
  it('returns string as-is if shorter than max', () => {
    expect(truncate('hello', 10)).toBe('hello');
  });

  it('truncates and appends ...', () => {
    expect(truncate('hello world this is long', 10)).toBe('hello w...');
  });

  it('defaults to 60 chars', () => {
    const s = 'a'.repeat(100);
    expect(truncate(s).length).toBe(60);
  });
});

// ===== validateReport =====
describe('validateReport', () => {
  it('rejects null', () => {
    expect(validateReport(null).valid).toBe(false);
  });

  it('rejects non-object', () => {
    expect(validateReport('string').valid).toBe(false);
  });

  it('rejects missing report_id', () => {
    expect(validateReport({ summary: {}, results: [] }).valid).toBe(false);
  });

  it('rejects missing summary', () => {
    expect(validateReport({ report_id: 'x', results: [] }).valid).toBe(false);
  });

  it('rejects non-array results', () => {
    expect(validateReport({ report_id: 'x', summary: {}, results: 'nope' }).valid).toBe(false);
  });

  it('accepts valid report', () => {
    expect(validateReport({ report_id: 'test-1', summary: { total: 1 }, results: [] }).valid).toBe(true);
  });
});

// ===== parseReport =====
describe('parseReport', () => {
  it('parses valid JSON report', () => {
    const json = JSON.stringify({
      report_id: 'r1',
      api_name: 'Test API',
      base_url: 'http://localhost',
      summary: { total: 2, passed: 1, failed: 1, errors: 0, pass_rate: 0.5 },
      results: [
        { name: 'test1', passed: true, method: 'GET', path: '/a', status_code: 200, elapsed_ms: 100 },
        { name: 'test2', passed: false, method: 'POST', path: '/b', status_code: 500, elapsed_ms: 200 },
      ],
    });
    const report = parseReport(json);
    expect(report.report_id).toBe('r1');
    expect(report.results).toHaveLength(2);
    expect(report.summary.pass_rate).toBe(0.5);
  });

  it('normalizes missing fields in results', () => {
    const json = JSON.stringify({
      report_id: 'r2',
      summary: { total: 1, passed: 0, failed: 1, errors: 0, pass_rate: 0 },
      results: [{}],
    });
    const report = parseReport(json);
    expect(report.results[0].name).toBe('Case #0');
    expect(report.results[0].method).toBe('GET');
    expect(report.results[0].path).toBe('/');
    expect(report.results[0].category).toBe('unknown');
    expect(report.results[0].checks).toEqual([]);
  });

  it('throws on invalid JSON', () => {
    expect(() => parseReport('not json')).toThrow();
  });

  it('throws on invalid report structure', () => {
    expect(() => parseReport('{}')).toThrow('缺少必填字段: report_id');
  });
});
