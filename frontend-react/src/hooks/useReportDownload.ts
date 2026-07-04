import { useState, useCallback } from 'react';
import { useAppStore } from '../stores/useAppStore';
import { ApiError } from '../api/client';

type ReportFormat = 'md' | 'html' | 'json';

export function useReportDownload() {
  const [downloading, setDownloading] = useState<string | null>(null);

  const download = useCallback(async (runId: string, format: ReportFormat, filename?: string) => {
    const app = useAppStore.getState();
    const key = `report_${runId}_${format}`;
    setDownloading(key);

    try {
      const url = `${app.backendUrl}/api/test/report/${runId}?format=${format}`;
      const response = await fetch(url);
      if (!response.ok) {
        throw new ApiError(`下载失败 (${response.status})`, response.status);
      }
      const blob = await response.blob();
      const objectUrl = URL.createObjectURL(blob);

      const a = document.createElement('a');
      a.href = objectUrl;
      a.download = filename || `report_${runId}.${format}`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(objectUrl);
    } catch (e) {
      const msg = e instanceof Error ? e.message : '下载失败';
      throw new Error(msg);
    } finally {
      setDownloading(null);
    }
  }, []);

  return { download, downloading };
}
