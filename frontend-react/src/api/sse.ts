import type { SSEEvent, SSEProgressData, SSECaseResultData, SSECompletedData, SSEErrorData } from '../types';

export type SSEEventHandler = (event: SSEEvent) => void;

export interface SSEConnection {
  close: () => void;
  isConnected: () => boolean;
}

/**
 * Create an SSE connection to the given URL.
 * Parses server-sent events into typed SSEEvent objects.
 *
 * Events from the backend:
 *   event: progress    → { node, progress, message }
 *   event: case_result → { case_name, passed, method, path, status_code, elapsed_ms, category }
 *   event: completed   → { run_id, total, passed, failed, errors, pass_rate, api_name, report_path }
 *   event: error       → { message }
 */
export function createSSEConnection(
  url: string,
  onEvent: SSEEventHandler,
  onConnectionChange?: (connected: boolean) => void,
): SSEConnection {
  let eventSource: EventSource | null = null;
  let reconnectCount = 0;
  let reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  let closed = false;
  const MAX_RECONNECT = 3;

  function connect() {
    if (closed) return;

    eventSource = new EventSource(url);
    onConnectionChange?.(true);

    eventSource.onmessage = (e) => {
      try {
        const raw = JSON.parse(e.data);
        const eventType = raw.event as string;
        const data = raw.data;

        let typedEvent: SSEEvent;
        switch (eventType) {
          case 'progress':
            typedEvent = { type: 'progress', data: data as SSEProgressData };
            break;
          case 'case_result':
            typedEvent = { type: 'case_result', data: data as SSECaseResultData };
            break;
          case 'completed':
            typedEvent = { type: 'completed', data: data as SSECompletedData };
            // Auto-close on completed
            close();
            break;
          case 'error':
            typedEvent = { type: 'error', data: data as SSEErrorData };
            // Auto-close on error
            close();
            break;
          default:
            return; // Ignore unknown events
        }
        onEvent(typedEvent);
      } catch {
        // Ignore parse errors (heartbeats, comments, etc.)
      }
    };

    eventSource.onerror = () => {
      onConnectionChange?.(false);
      eventSource?.close();
      eventSource = null;

      if (closed) return;
      if (reconnectCount < MAX_RECONNECT) {
        reconnectCount++;
        const delay = Math.min(1000 * Math.pow(2, reconnectCount - 1), 4000);
        reconnectTimer = setTimeout(connect, delay);
      }
    };
  }

  function close() {
    closed = true;
    if (reconnectTimer) {
      clearTimeout(reconnectTimer);
      reconnectTimer = null;
    }
    if (eventSource) {
      eventSource.close();
      eventSource = null;
    }
    onConnectionChange?.(false);
  }

  function isConnected() {
    return eventSource !== null && eventSource.readyState === EventSource.OPEN;
  }

  connect();

  return { close, isConnected };
}
