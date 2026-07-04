import type { SSECaseResultData } from '../../types';
import { METHOD_COLORS } from '../../utils/constants';
import { CheckCircle, XCircle } from 'lucide-react';

interface CaseResultRowProps {
  result: SSECaseResultData;
}

export function CaseResultRow({ result }: CaseResultRowProps) {
  const methodColor = METHOD_COLORS[result.method] || 'bg-gray-100 text-gray-600';

  return (
    <div className="flex items-center gap-3 px-5 py-2 border-b border-gray-50 text-sm hover:bg-gray-50">
      {/* Pass/Fail icon */}
      {result.passed ? (
        <CheckCircle className="w-4 h-4 text-green-500 flex-shrink-0" />
      ) : (
        <XCircle className="w-4 h-4 text-red-500 flex-shrink-0" />
      )}

      {/* Method badge */}
      <span className={`inline-flex px-1.5 py-0.5 text-xs font-medium rounded ${methodColor} flex-shrink-0`}>
        {result.method}
      </span>

      {/* Path */}
      <span className="text-gray-700 truncate flex-1 min-w-0">{result.path}</span>

      {/* Status code */}
      <span className={`text-xs font-mono flex-shrink-0 ${result.status_code >= 400 ? 'text-red-500' : 'text-gray-500'}`}>
        {result.status_code || '---'}
      </span>

      {/* Elapsed */}
      <span className="text-xs text-gray-400 flex-shrink-0 w-16 text-right">
        {result.elapsed_ms > 0 ? `${Math.round(result.elapsed_ms)}ms` : ''}
      </span>
    </div>
  );
}
