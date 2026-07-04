import { useNavigate } from 'react-router-dom';
import type { HistoryRun } from '../../types';
import { formatTime } from '../../utils/formatters';

interface HistoryTableProps {
  runs: HistoryRun[];
}

export function HistoryTable({ runs }: HistoryTableProps) {
  const navigate = useNavigate();

  if (runs.length === 0) {
    return <p className="text-sm text-gray-400 text-center py-8">暂无历史记录</p>;
  }

  return (
    <div className="bg-white rounded-lg border border-gray-100 overflow-hidden">
      <div className="max-h-[500px] overflow-y-auto">
        <table className="w-full text-sm">
          <thead className="bg-gray-50 sticky top-0">
            <tr>
              <th className="px-3 py-2 text-xs font-medium text-gray-500 text-left">Run ID</th>
              <th className="px-3 py-2 text-xs font-medium text-gray-500 text-left">API</th>
              <th className="px-3 py-2 text-xs font-medium text-gray-500 text-left">时间</th>
              <th className="px-3 py-2 text-xs font-medium text-gray-500 text-center">状态</th>
              <th className="px-3 py-2 text-xs font-medium text-gray-500 text-right">通过率</th>
              <th className="px-3 py-2 text-xs font-medium text-gray-500 text-center">操作</th>
            </tr>
          </thead>
          <tbody>
            {runs.map((r) => {
              const passRate = r.pass_rate != null ? r.pass_rate : null;
              const rateColor =
                passRate === null ? 'text-gray-400'
                : passRate >= 90 ? 'text-green-600'
                : passRate >= 70 ? 'text-yellow-600'
                : 'text-red-600';

              return (
                <tr key={r.run_id} className="border-b border-gray-50 hover:bg-gray-50">
                  <td className="px-3 py-2.5 text-xs font-mono text-gray-600">{r.run_id?.slice(0, 8) || 'N/A'}</td>
                  <td className="px-3 py-2.5 text-xs text-gray-700 truncate max-w-40">{r.api_name || 'N/A'}</td>
                  <td className="px-3 py-2.5 text-xs text-gray-400">{r.started_at ? formatTime(r.started_at) : 'N/A'}</td>
                  <td className="px-3 py-2.5 text-center">
                    <span
                      className={`inline-flex px-2 py-0.5 text-xs font-medium rounded-full ${
                        r.status === 'completed' ? 'bg-green-100 text-green-700'
                        : r.status === 'running' ? 'bg-blue-100 text-blue-700'
                        : r.status === 'error' ? 'bg-red-100 text-red-700'
                        : 'bg-gray-100 text-gray-600'
                      }`}
                    >
                      {r.status === 'completed' ? '完成'
                        : r.status === 'running' ? '运行中'
                        : r.status === 'error' ? '错误'
                        : r.status || '未知'}
                    </span>
                  </td>
                  <td className={`px-3 py-2.5 text-xs font-semibold text-right ${rateColor}`}>
                    {passRate != null ? `${passRate.toFixed(1)}%` : 'N/A'}
                  </td>
                  <td className="px-3 py-2.5 text-center">
                    <button
                      onClick={() => navigate(`/load/${r.run_id}`)}
                      className="px-2 py-1 text-xs text-indigo-600 hover:bg-indigo-50 rounded transition-colors"
                    >
                      查看详情
                    </button>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
