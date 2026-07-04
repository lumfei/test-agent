import { AlertTriangle, X, RefreshCw } from 'lucide-react';

interface ErrorAlertProps {
  message: string;
  onDismiss?: () => void;
  onRetry?: () => void;
}

export function ErrorAlert({ message, onDismiss, onRetry }: ErrorAlertProps) {
  return (
    <div className="flex items-start gap-3 bg-red-50 border border-red-200 rounded-lg p-4">
      <AlertTriangle className="w-5 h-5 text-red-500 flex-shrink-0 mt-0.5" />
      <div className="flex-1 min-w-0">
        <p className="text-sm font-medium text-red-800">出错了</p>
        <p className="text-sm text-red-600 mt-0.5">{message}</p>
      </div>
      <div className="flex items-center gap-1 flex-shrink-0">
        {onRetry && (
          <button
            onClick={onRetry}
            className="p-1.5 text-red-500 hover:bg-red-100 rounded-md transition-colors"
            title="重试"
          >
            <RefreshCw className="w-4 h-4" />
          </button>
        )}
        {onDismiss && (
          <button
            onClick={onDismiss}
            className="p-1.5 text-red-400 hover:bg-red-100 rounded-md transition-colors"
            title="关闭"
          >
            <X className="w-4 h-4" />
          </button>
        )}
      </div>
    </div>
  );
}
