import { create } from 'zustand';
import type { ProgressEntry, SSECompletedData, SSECaseResultData, RunResult, StartTestRequest } from '../types';
import { useAppStore } from './useAppStore';
import { apiClient } from '../api/client';

type TestStatus = 'idle' | 'starting' | 'running' | 'completed' | 'error';

interface TestState {
  specUrl: string;
  runId: string | null;
  status: TestStatus;
  progressLog: ProgressEntry[];
  caseResults: SSECaseResultData[];
  summary: SSECompletedData | null;
  error: string | null;
  runMeta: RunResult | null;

  setSpecUrl: (url: string) => void;
  startTest: () => Promise<string | null>;
  addProgress: (entry: ProgressEntry) => void;
  addCaseResult: (result: SSECaseResultData) => void;
  setCompleted: (summary: SSECompletedData) => void;
  setError: (error: string) => void;
  setRunMeta: (meta: RunResult) => void;
  reset: () => void;
}

export const useTestStore = create<TestState>((set, get) => ({
  specUrl: '',
  runId: null,
  status: 'idle',
  progressLog: [],
  caseResults: [],
  summary: null,
  error: null,
  runMeta: null,

  setSpecUrl: (specUrl) => set({ specUrl }),

  startTest: async () => {
    const { specUrl } = get();
    if (!specUrl.trim()) {
      set({ error: '请输入 API 文档 URL', status: 'error' });
      return null;
    }

    const app = useAppStore.getState();
    set({ status: 'starting', error: null, progressLog: [], caseResults: [], summary: null });

    try {
      const body: StartTestRequest = { spec_url: specUrl.trim() };
      if (app.authType !== 'none') {
        body.auth_type = app.authType;
        if (app.authType === 'bearer') body.auth_token = app.authToken;
        if (app.authType === 'api_key') body.auth_token = app.authToken;
        if (app.authType === 'basic') {
          body.auth_username = app.authUsername;
          body.auth_password = app.authPassword;
        }
      }

      const data = await apiClient<{ run_id: string; status: string; started_at: string }>(
        `${app.backendUrl}/api/test/run`,
        {
          method: 'POST',
          body: JSON.stringify(body),
          headers: { 'Content-Type': 'application/json' },
        },
      );

      set({ runId: data.run_id, status: 'running' });
      return data.run_id;
    } catch (e) {
      const msg = e instanceof Error ? e.message : '启动测试失败';
      set({ error: msg, status: 'error' });
      return null;
    }
  },

  addProgress: (entry) =>
    set((s) => ({ progressLog: [...s.progressLog, entry] })),

  addCaseResult: (result) =>
    set((s) => ({ caseResults: [...s.caseResults, result] })),

  setCompleted: (summary) =>
    set({ summary, status: 'completed' }),

  setError: (error) =>
    set({ error, status: 'error' }),

  setRunMeta: (runMeta) => set({ runMeta }),

  reset: () =>
    set({
      status: 'idle',
      runId: null,
      progressLog: [],
      caseResults: [],
      summary: null,
      error: null,
      runMeta: null,
    }),
}));
