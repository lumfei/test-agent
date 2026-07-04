import { create } from 'zustand';
import type { AuthType } from '../types';
import { DEFAULT_BACKEND_URL, ONLINE_TABS } from '../utils/constants';
import { apiClient } from '../api/client';

interface AppState {
  mode: 'online' | 'offline';
  activeTab: string;
  backendUrl: string;
  authType: AuthType;
  authToken: string;
  authUsername: string;
  authPassword: string;
  isHealthy: boolean | null;
  healthModel: string;

  setMode: (mode: 'online' | 'offline') => void;
  setActiveTab: (tab: string) => void;
  setBackendUrl: (url: string) => void;
  setAuthType: (type: AuthType) => void;
  setAuthToken: (token: string) => void;
  setAuthCredentials: (username: string, password: string) => void;
  checkHealth: () => Promise<void>;
}

export const useAppStore = create<AppState>((set, get) => ({
  mode: 'online',
  activeTab: ONLINE_TABS[0].id,
  backendUrl: DEFAULT_BACKEND_URL,
  authType: 'none',
  authToken: '',
  authUsername: '',
  authPassword: '',
  isHealthy: null,
  healthModel: '',

  setMode: (mode) => {
    set({ mode, isHealthy: null });
  },

  setActiveTab: (activeTab) => set({ activeTab }),

  setBackendUrl: (backendUrl) => set({ backendUrl, isHealthy: null }),

  setAuthType: (authType) => set({ authType }),

  setAuthToken: (authToken) => set({ authToken }),

  setAuthCredentials: (authUsername, authPassword) =>
    set({ authUsername, authPassword }),

  checkHealth: async () => {
    const { backendUrl } = get();
    try {
      const data = await apiClient<{ status: string; model: string }>(
        `${backendUrl}/api/health`,
        { timeout: 5000 },
      );
      set({ isHealthy: true, healthModel: data.model });
    } catch {
      set({ isHealthy: false, healthModel: '' });
    }
  },
}));
