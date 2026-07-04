import { Loader2, Download } from 'lucide-react';
import { clsx } from 'clsx';

interface DownloadButtonProps {
  runId: string;
  format: 'md' | 'html' | 'json';
  label: string;
  onDownload: (runId: string, format: 'md' | 'html' | 'json') => Promise<void>;
  isDownloading: boolean;
}

export function DownloadButton({ runId, format, label, onDownload, isDownloading }: DownloadButtonProps) {
  const colors: Record<string, string> = {
    html: 'bg-orange-50 text-orange-700 border-orange-200 hover:bg-orange-100',
    md: 'bg-blue-50 text-blue-700 border-blue-200 hover:bg-blue-100',
    json: 'bg-gray-50 text-gray-700 border-gray-200 hover:bg-gray-100',
  };

  return (
    <button
      onClick={() => onDownload(runId, format)}
      disabled={isDownloading}
      className={clsx(
        'inline-flex items-center gap-2 px-4 py-2 text-sm font-medium border rounded-lg transition-colors disabled:opacity-50',
        colors[format] || colors.json,
      )}
    >
      {isDownloading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Download className="w-4 h-4" />}
      {label}
    </button>
  );
}
