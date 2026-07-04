import { create } from 'zustand';
import type { TestReport, TestResult, CategoryStat, EndpointStat, ResultsResponse } from '../types';
import { parseReport } from '../utils/formatters';
import { useAppStore } from './useAppStore';
import { apiClient } from '../api/client';

type ReportSource = 'file' | 'api' | null;
type ResultFilter = 'all' | 'passed' | 'failed';

interface ReportState {
  source: ReportSource;
  report: TestReport | null;
  isLoading: boolean;
  error: string | null;

  // Filters
  selectedCategories: string[];
  resultFilter: ResultFilter;

  // Actions
  loadFromFile: (file: File) => Promise<void>;
  loadFromRunId: (runId: string) => Promise<void>;
  loadFromApiResponse: (data: ResultsResponse) => void;
  setSelectedCategories: (categories: string[]) => void;
  setResultFilter: (filter: ResultFilter) => void;
  clear: () => void;

  // Selectors
  filteredResults: () => TestResult[];
  failureResults: () => TestResult[];
  uniqueCategories: () => string[];
}

export const useReportStore = create<ReportState>((set, get) => ({
  source: null,
  report: null,
  isLoading: false,
  error: null,
  selectedCategories: [],
  resultFilter: 'all',

  loadFromFile: async (file: File) => {
    set({ isLoading: true, error: null });
    try {
      const text = await file.text();
      const report = parseReport(text);
      set({
        report,
        source: 'file',
        isLoading: false,
        selectedCategories: [],
        resultFilter: 'all',
      });
    } catch (e) {
      const msg = e instanceof Error ? e.message : '文件读取失败';
      set({ error: msg, isLoading: false });
    }
  },

  loadFromRunId: async (runId: string) => {
    const app = useAppStore.getState();
    set({ isLoading: true, error: null });
    try {
      const data = await apiClient<ResultsResponse>(
        `${app.backendUrl}/api/test/results/${runId}`,
      );
      get().loadFromApiResponse(data);
    } catch (e) {
      const msg = e instanceof Error ? e.message : '加载结果失败';
      set({ error: msg, isLoading: false });
    }
  },

  loadFromApiResponse: (data: ResultsResponse) => {
    const results = (data.results || []).map((r, i) => ({
      name: (r.name as string) || `Case #${i}`,
      passed: Boolean(r.passed),
      method: (r.method as string) || 'GET',
      path: (r.path as string) || '/',
      status_code: Number(r.status_code ?? 0),
      elapsed_ms: Number(r.elapsed_ms ?? 0),
      expected_status: r.expected_status as number | number[] | undefined,
      category: (r.category as string) || 'unknown',
      checks: (r.checks as TestResult['checks']) || [],
      error: (r.error as string) ?? null,
      response_preview: (r.response_preview as string) || '',
      tags: (r.tags as string[]) || [],
    })) as TestResult[];

    const total = results.length;
    const passed = results.filter((r) => r.passed).length;
    const failed = results.filter((r) => !r.passed && !r.error).length;
    const errors = results.filter((r) => r.error).length;

    // Build category stats
    const byCategory: Record<string, CategoryStat> = {};
    const byEndpoint: Record<string, EndpointStat> = {};
    for (const r of results) {
      const cat = r.category || 'unknown';
      if (!byCategory[cat]) byCategory[cat] = { total: 0, passed: 0, failed: 0, errors: 0 };
      byCategory[cat].total++;
      if (r.passed) byCategory[cat].passed++;
      else if (r.error) byCategory[cat].errors++;
      else byCategory[cat].failed++;

      const ep = `${r.method} ${r.path}`;
      if (!byEndpoint[ep]) byEndpoint[ep] = { total: 0, passed: 0, failed: 0, errors: 0 };
      byEndpoint[ep].total++;
      if (r.passed) byEndpoint[ep].passed++;
      else if (r.error) byEndpoint[ep].errors++;
      else byEndpoint[ep].failed++;
    }

    const report: TestReport = {
      report_id: (data.run as Record<string, unknown>)?.run_id as string || '',
      api_name: (data.run as Record<string, unknown>)?.api_name as string || 'Unknown',
      base_url: (data.run as Record<string, unknown>)?.base_url as string || '',
      spec_url: (data.run as Record<string, unknown>)?.spec_url as string || null,
      generated_at: (data.run as Record<string, unknown>)?.started_at as string || '',
      duration_seconds: 0,
      summary: { total, passed, failed, errors, pass_rate: total > 0 ? passed / total : 0 },
      by_category: byCategory,
      by_endpoint: byEndpoint,
      results,
    };

    set({
      report,
      source: 'api',
      isLoading: false,
      selectedCategories: [],
      resultFilter: 'all',
    });
  },

  setSelectedCategories: (selectedCategories) => set({ selectedCategories }),
  setResultFilter: (resultFilter) => set({ resultFilter }),
  clear: () => set({
    source: null,
    report: null,
    isLoading: false,
    error: null,
    selectedCategories: [],
    resultFilter: 'all',
  }),

  filteredResults: () => {
    const { report, selectedCategories, resultFilter } = get();
    if (!report) return [];
    let results = report.results;
    if (selectedCategories.length > 0) {
      results = results.filter((r) => selectedCategories.includes(r.category));
    }
    if (resultFilter === 'passed') results = results.filter((r) => r.passed);
    if (resultFilter === 'failed') results = results.filter((r) => !r.passed);
    return results;
  },

  failureResults: () => {
    const { report } = get();
    if (!report) return [];
    return report.results.filter((r) => !r.passed);
  },

  uniqueCategories: () => {
    const { report } = get();
    if (!report) return [];
    return Object.keys(report.by_category);
  },
}));
