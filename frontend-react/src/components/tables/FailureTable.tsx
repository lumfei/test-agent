import type { TestResult } from '../../types';
import { METHOD_COLORS, CATEGORY_LABELS } from '../../utils/constants';
import { useState, Fragment } from 'react';

interface FailureTableProps {
  failures: TestResult[];
}

export function FailureTable({ failures }: FailureTableProps) {
  const [expandedIdx, setExpandedIdx] = useState<number | null>(null);

  if (failures.length === 0) return null;

  return (
    <div className="bg-white rounded-lg border border-red-100 overflow-hidden">
      <div className="px-4 py-2 border-b border-red-100 bg-red-50">
        <span className="text-sm font-semibold text-red-700">失败用例 ({failures.length})</span>
      </div>
      <div className="max-h-80 overflow-y-auto">
        <table className="w-full text-sm">
          <thead className="bg-gray-50 sticky top-0">
            <tr>
              <th className="px-3 py-2 text-xs font-medium text-gray-500 text-left">用例</th>
              <th className="px-3 py-2 text-xs font-medium text-gray-500 text-left">方法</th>
              <th className="px-3 py-2 text-xs font-medium text-gray-500 text-left">路径</th>
              <th className="px-3 py-2 text-xs font-medium text-gray-500 text-center">状态码</th>
              <th className="px-3 py-2 text-xs font-medium text-gray-500 text-left">类别</th>
              <th className="px-3 py-2 text-xs font-medium text-gray-500 text-left">失败原因</th>
            </tr>
          </thead>
          <tbody>
            {failures.map((r, i) => {
              const methodColor = METHOD_COLORS[r.method] || 'bg-gray-100 text-gray-600';
              const failReason = r.error
                ? r.error
                : r.checks.find((c) => !c.passed)?.detail || '验证失败';
              return (
                <Fragment key={i}>
                  <tr
                    key={i}
                    onClick={() => setExpandedIdx(expandedIdx === i ? null : i)}
                    className="border-b border-gray-50 hover:bg-gray-50 cursor-pointer"
                  >
                    <td className="px-3 py-2 text-xs truncate max-w-36">{r.name}</td>
                    <td className="px-3 py-2">
                      <span className={`inline-flex px-1.5 py-0.5 text-xs font-medium rounded ${methodColor}`}>
                        {r.method}
                      </span>
                    </td>
                    <td className="px-3 py-2 text-xs font-mono text-gray-600 truncate max-w-48">{r.path}</td>
                    <td className="px-3 py-2 text-xs font-mono text-center">{r.status_code || '-'}</td>
                    <td className="px-3 py-2 text-xs text-gray-500">{CATEGORY_LABELS[r.category] || r.category}</td>
                    <td className="px-3 py-2 text-xs text-red-600 truncate max-w-80">{failReason}</td>
                  </tr>
                  {expandedIdx === i && (
                    <tr>
                      <td colSpan={6} className="bg-gray-50 px-6 py-3 border-b border-gray-100">
                        <div className="space-y-2">
                          {r.error && (
                            <div className="bg-red-50 border border-red-100 rounded p-2">
                              <span className="text-xs font-medium text-red-700">错误:</span>
                              <pre className="text-xs text-red-600 mt-1 whitespace-pre-wrap">{r.error}</pre>
                            </div>
                          )}
                          {r.checks.map((c, ci) => (
                            <div key={ci} className="flex items-start gap-2 text-xs">
                              <span className={c.passed ? 'text-green-500 mt-0.5' : 'text-red-500 mt-0.5'}>
                                {c.passed ? '✓' : '✗'}
                              </span>
                              <div>
                                <span className="text-gray-600">{c.check_name}</span>
                                {!c.passed && <span className="text-gray-400 ml-2">— {c.detail}</span>}
                              </div>
                            </div>
                          ))}
                          {r.response_preview && (
                            <pre className="text-xs text-gray-500 bg-gray-100 rounded p-2 overflow-x-auto max-h-24">
                              {r.response_preview.slice(0, 300)}
                            </pre>
                          )}
                        </div>
                      </td>
                    </tr>
                  )}
                </Fragment>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
