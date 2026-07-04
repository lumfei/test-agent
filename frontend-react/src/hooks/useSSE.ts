import { useEffect, useRef, useCallback, useState } from 'react';
import { createSSEConnection, type SSEEventHandler } from '../api/sse';
import { useAppStore } from '../stores/useAppStore';
import { useTestStore } from '../stores/useTestStore';
import type { ProgressEntry } from '../types';

export function useSSE(runId: string | null): { isConnected: boolean; reconnectCount: number } {
  const [isConnected, setIsConnected] = useState(false);
  const [reconnectCount, setReconnectCount] = useState(0);
  const closeRef = useRef<(() => void) | null>(null);

  const handleEvent: SSEEventHandler = useCallback((event) => {
    const store = useTestStore.getState();
    switch (event.type) {
      case 'progress': {
        const entry: ProgressEntry = {
          node: event.data.node,
          progress: event.data.progress,
          message: event.data.message,
          timestamp: Date.now(),
        };
        store.addProgress(entry);
        break;
      }
      case 'case_result':
        store.addCaseResult(event.data);
        break;
      case 'completed':
        store.setCompleted(event.data);
        break;
      case 'error':
        store.setError(event.data.message || '测试执行异常');
        break;
    }
  }, []);

  const handleConnectionChange = useCallback((connected: boolean) => {
    setIsConnected(connected);
    if (!connected) {
      setReconnectCount((c) => c + 1);
    }
  }, []);

  useEffect(() => {
    if (!runId) {
      setIsConnected(false);
      return;
    }

    setReconnectCount(0);
    const app = useAppStore.getState();
    const url = `${app.backendUrl}/api/test/stream/${runId}`;
    const conn = createSSEConnection(url, handleEvent, handleConnectionChange);
    closeRef.current = conn.close;

    return () => {
      conn.close();
      closeRef.current = null;
    };
  }, [runId, handleEvent, handleConnectionChange]);

  return { isConnected, reconnectCount };
}
