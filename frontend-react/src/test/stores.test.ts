import { describe, it, expect, beforeEach, vi } from 'vitest';
import { useAppStore } from '../stores/useAppStore';
import { useTestStore } from '../stores/useTestStore';
import { useReportStore } from '../stores/useReportStore';
import { useHistoryStore } from '../stores/useHistoryStore';

// Mock the API client
vi.mock('../api/client', () => ({
  apiClient: vi.fn(),
  ApiError: class ApiError extends Error {
    status: number;
    constructor(message: string, status: number) {
      super(message);
      this.name = 'ApiError';
      this.status = status;
    }
  },
}));

import { apiClient } from '../api/client';
const mockApiClient = vi.mocked(apiClient);

beforeEach(() => {
  vi.clearAllMocks();
  useAppStore.setState({
    mode: 'online',
    backendUrl: 'http://localhost:8002',
    authType: 'none',
    authToken: '',
    authUsername: '',
    authPassword: '',
    isHealthy: null,
    healthModel: '',
  });
  useTestStore.setState({
    specUrl: '',
    runId: null,
    status: 'idle',
    progressLog: [],
    caseResults: [],
    summary: null,
    error: null,
    runMeta: null,
  });
  useReportStore.setState({
    source: null,
    report: null,
    isLoading: false,
    error: null,
    selectedCategories: [],
    resultFilter: 'all',
  });
  useHistoryStore.setState({
    runs: [],
    totalRuns: 0,
    isLoading: false,
    error: null,
  });
});

// ===== useAppStore =====
describe('useAppStore', () => {
  it('has correct initial state', () => {
    const state = useAppStore.getState();
    expect(state.mode).toBe('online');
    expect(state.backendUrl).toBe('http://localhost:8002');
    expect(state.isHealthy).toBeNull();
    expect(state.authType).toBe('none');
  });

  it('setMode switches mode and resets health', () => {
    useAppStore.getState().setMode('offline');
    const state = useAppStore.getState();
    expect(state.mode).toBe('offline');
    expect(state.isHealthy).toBeNull();
  });

  it('setBackendUrl resets health', () => {
    useAppStore.setState({ isHealthy: true, healthModel: 'test' });
    useAppStore.getState().setBackendUrl('http://new:9999');
    const state = useAppStore.getState();
    expect(state.backendUrl).toBe('http://new:9999');
    expect(state.isHealthy).toBeNull();
  });

  it('checkHealth sets isHealthy=true on success', async () => {
    mockApiClient.mockResolvedValueOnce({ status: 'ok', model: 'deepseek-chat' });
    await useAppStore.getState().checkHealth();
    const state = useAppStore.getState();
    expect(state.isHealthy).toBe(true);
    expect(state.healthModel).toBe('deepseek-chat');
  });

  it('checkHealth sets isHealthy=false on failure', async () => {
    mockApiClient.mockRejectedValueOnce(new Error('fail'));
    await useAppStore.getState().checkHealth();
    const state = useAppStore.getState();
    expect(state.isHealthy).toBe(false);
    expect(state.healthModel).toBe('');
  });

  it('setAuthType changes auth type', () => {
    useAppStore.getState().setAuthType('bearer');
    expect(useAppStore.getState().authType).toBe('bearer');
  });

  it('setAuthToken sets token', () => {
    useAppStore.getState().setAuthToken('secret123');
    expect(useAppStore.getState().authToken).toBe('secret123');
  });

  it('setAuthCredentials sets both fields', () => {
    useAppStore.getState().setAuthCredentials('user', 'pass');
    const s = useAppStore.getState();
    expect(s.authUsername).toBe('user');
    expect(s.authPassword).toBe('pass');
  });
});

// ===== useTestStore =====
describe('useTestStore', () => {
  it('has correct initial state', () => {
    const s = useTestStore.getState();
    expect(s.status).toBe('idle');
    expect(s.runId).toBeNull();
    expect(s.progressLog).toEqual([]);
    expect(s.caseResults).toEqual([]);
    expect(s.summary).toBeNull();
  });

  it('setSpecUrl updates specUrl', () => {
    useTestStore.getState().setSpecUrl('https://example.com/openapi.json');
    expect(useTestStore.getState().specUrl).toBe('https://example.com/openapi.json');
  });

  it('startTest fails with empty URL', async () => {
    const runId = await useTestStore.getState().startTest();
    expect(runId).toBeNull();
    expect(useTestStore.getState().status).toBe('error');
    expect(useTestStore.getState().error).toBe('请输入 API 文档 URL');
  });

  it('startTest with URL makes API call', async () => {
    useTestStore.getState().setSpecUrl('https://example.com/openapi.json');
    mockApiClient.mockResolvedValueOnce({
      run_id: 'test-run-123',
      status: 'started',
      started_at: '2026-07-01T00:00:00Z',
    });
    const runId = await useTestStore.getState().startTest();
    expect(runId).toBe('test-run-123');
    expect(useTestStore.getState().status).toBe('running');
    expect(useTestStore.getState().runId).toBe('test-run-123');
  });

  it('startTest handles API error', async () => {
    useTestStore.getState().setSpecUrl('https://example.com/openapi.json');
    mockApiClient.mockRejectedValueOnce(new Error('Network error'));
    const runId = await useTestStore.getState().startTest();
    expect(runId).toBeNull();
    expect(useTestStore.getState().status).toBe('error');
  });

  it('addProgress appends to progress log', () => {
    const entry = { node: 'parse', progress: 0.5, message: 'parsing', timestamp: Date.now() };
    useTestStore.getState().addProgress(entry);
    expect(useTestStore.getState().progressLog).toHaveLength(1);
    expect(useTestStore.getState().progressLog[0].node).toBe('parse');
  });

  it('addCaseResult appends case result', () => {
    const result = { case_name: 'test', passed: true, method: 'GET', path: '/', status_code: 200, elapsed_ms: 100, category: 'normal' };
    useTestStore.getState().addCaseResult(result);
    expect(useTestStore.getState().caseResults).toHaveLength(1);
  });

  it('setCompleted sets summary and status', () => {
    const summary = {
      run_id: 'r1', total: 10, passed: 9, failed: 1, errors: 0,
      pass_rate: 90, api_name: 'Test', report_path: '/path',
    };
    useTestStore.getState().setCompleted(summary);
    const s = useTestStore.getState();
    expect(s.summary).toEqual(summary);
    expect(s.status).toBe('completed');
  });

  it('setError sets error message', () => {
    useTestStore.getState().setError('Something broke');
    const s = useTestStore.getState();
    expect(s.error).toBe('Something broke');
    expect(s.status).toBe('error');
  });

  it('reset clears all state', () => {
    useTestStore.setState({
      status: 'completed', runId: 'r1', progressLog: [{ node: 'x', progress: 1, message: 'done', timestamp: 0 }],
      caseResults: [{ case_name: 't', passed: true, method: 'GET', path: '/', status_code: 200, elapsed_ms: 10, category: 'n' }],
      summary: { run_id: 'r1', total: 1, passed: 1, failed: 0, errors: 0, pass_rate: 100, api_name: 'A', report_path: '/p' },
      error: 'x',
    });
    useTestStore.getState().reset();
    const s = useTestStore.getState();
    expect(s.status).toBe('idle');
    expect(s.runId).toBeNull();
    expect(s.progressLog).toEqual([]);
    expect(s.caseResults).toEqual([]);
    expect(s.summary).toBeNull();
    expect(s.error).toBeNull();
  });
});

// ===== useReportStore =====
describe('useReportStore', () => {
  const sampleResultsResponse = {
    run: { run_id: 'test-run', api_name: 'Test API', base_url: 'http://localhost', spec_url: null, started_at: '2026-01-01T00:00:00Z' },
    results: [
      { name: 'Case 1', passed: true, method: 'GET', path: '/a', status_code: 200, elapsed_ms: 50, category: 'normal', checks: [], error: null },
      { name: 'Case 2', passed: false, method: 'POST', path: '/b', status_code: 400, elapsed_ms: 100, category: 'error', checks: [{ check_name: 'status', passed: false, detail: 'expected 200 got 400' }], error: null },
    ],
    categories: [],
  };

  it('loadFromApiResponse builds correct report structure', () => {
    useReportStore.getState().loadFromApiResponse(sampleResultsResponse);
    const report = useReportStore.getState().report;
    expect(report).not.toBeNull();
    expect(report!.report_id).toBe('test-run');
    expect(report!.summary.total).toBe(2);
    expect(report!.summary.passed).toBe(1);
    expect(report!.summary.failed).toBe(1);
    expect(report!.summary.errors).toBe(0);
    expect(report!.by_category['normal'].total).toBe(1);
    expect(report!.by_category['error'].total).toBe(1);
    expect(report!.by_endpoint['GET /a'].total).toBe(1);
    expect(report!.by_endpoint['POST /b'].total).toBe(1);
  });

  it('loadFromApiResponse handles empty results', () => {
    useReportStore.getState().loadFromApiResponse({ run: {}, results: [], categories: [] });
    const report = useReportStore.getState().report;
    expect(report!.summary.total).toBe(0);
    expect(report!.results).toEqual([]);
  });

  it('filteredResults filters by category', () => {
    useReportStore.getState().loadFromApiResponse(sampleResultsResponse);
    useReportStore.getState().setSelectedCategories(['normal']);
    const filtered = useReportStore.getState().filteredResults();
    expect(filtered).toHaveLength(1);
    expect(filtered[0].category).toBe('normal');
  });

  it('filteredResults filters by pass/fail', () => {
    useReportStore.getState().loadFromApiResponse(sampleResultsResponse);
    useReportStore.getState().setResultFilter('passed');
    const filtered = useReportStore.getState().filteredResults();
    expect(filtered).toHaveLength(1);
    expect(filtered[0].passed).toBe(true);
  });

  it('filteredResults returns empty when no report', () => {
    const filtered = useReportStore.getState().filteredResults();
    expect(filtered).toEqual([]);
  });

  it('failureResults returns only failures', () => {
    useReportStore.getState().loadFromApiResponse(sampleResultsResponse);
    const failures = useReportStore.getState().failureResults();
    expect(failures).toHaveLength(1);
    expect(failures[0].passed).toBe(false);
  });

  it('uniqueCategories returns all category keys', () => {
    useReportStore.getState().loadFromApiResponse(sampleResultsResponse);
    const cats = useReportStore.getState().uniqueCategories();
    expect(cats).toContain('normal');
    expect(cats).toContain('error');
  });

  it('clear resets all state', () => {
    useReportStore.getState().loadFromApiResponse(sampleResultsResponse);
    useReportStore.getState().clear();
    expect(useReportStore.getState().report).toBeNull();
    expect(useReportStore.getState().source).toBeNull();
  });

  it('loadFromFile parses JSON and sets report', async () => {
    const file = new File(
      [JSON.stringify({
        report_id: 'f1',
        summary: { total: 1, passed: 1, failed: 0, errors: 0, pass_rate: 1 },
        results: [{ name: 't', passed: true, method: 'GET', path: '/' }],
      })],
      'report.json',
      { type: 'application/json' },
    );
    await useReportStore.getState().loadFromFile(file);
    expect(useReportStore.getState().report?.report_id).toBe('f1');
    expect(useReportStore.getState().source).toBe('file');
  });

  it('loadFromFile handles errors', async () => {
    const file = new File(['not json'], 'bad.json', { type: 'application/json' });
    await useReportStore.getState().loadFromFile(file);
    expect(useReportStore.getState().error).toBeTruthy();
    expect(useReportStore.getState().isLoading).toBe(false);
  });
});

// ===== useHistoryStore =====
describe('useHistoryStore', () => {
  it('fetchHistory populates runs', async () => {
    mockApiClient.mockResolvedValueOnce({
      total: 2,
      runs: [
        { run_id: 'r1', api_name: 'API 1', status: 'completed', pass_rate: 95, started_at: '2026-01-01T00:00:00Z' },
        { run_id: 'r2', api_name: 'API 2', status: 'completed', pass_rate: 80, started_at: '2026-01-02T00:00:00Z' },
      ],
    });
    await useHistoryStore.getState().fetchHistory(10);
    const s = useHistoryStore.getState();
    expect(s.runs).toHaveLength(2);
    expect(s.totalRuns).toBe(2);
    expect(s.isLoading).toBe(false);
  });

  it('fetchHistory handles empty response', async () => {
    mockApiClient.mockResolvedValueOnce({ total: 0, runs: [] });
    await useHistoryStore.getState().fetchHistory();
    expect(useHistoryStore.getState().totalRuns).toBe(0);
  });

  it('fetchHistory handles errors', async () => {
    mockApiClient.mockRejectedValueOnce(new Error('fail'));
    await useHistoryStore.getState().fetchHistory();
    expect(useHistoryStore.getState().error).toBeTruthy();
    expect(useHistoryStore.getState().isLoading).toBe(false);
  });
});
