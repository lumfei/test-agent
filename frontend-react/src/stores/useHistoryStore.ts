import { create } from 'zustand';
import type { HistoryRun, HistoryResponse } from '../types';
import { useAppStore } from './useAppStore';
import { apiClient } from '../api/client';

interface HistoryStore {
  runs: HistoryRun[];
  totalRuns: number;
  isLoading: boolean;
  error: string | null;

  fetchHistory: (limit?: number) => Promise<void>;
}

export const useHistoryStore = create<HistoryStore>((set) => ({
  runs: [],
  totalRuns: 0,
  isLoading: false,
  error: null,

  fetchHistory: async (limit = 50) => {
    const app = useAppStore.getState();
    set({ isLoading: true, error: null });
    try {
      const data = await apiClient<HistoryResponse>(
        `${app.backendUrl}/api/test/history?limit=${limit}`,
      );
      set({
        runs: data.runs || [],
        totalRuns: data.total || 0,
        isLoading: false,
      });
    } catch (e) {
      const msg = e instanceof Error ? e.message : '获取历史记录失败';
      set({ error: msg, isLoading: false });
    }
  },
}));
