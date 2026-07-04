import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, ReferenceLine } from 'recharts';
import type { HistoryRun } from '../../types';
import { useMemo } from 'react';
import { formatTime } from '../../utils/formatters';

interface PassRateTrendChartProps {
  runs: HistoryRun[];
}

export function PassRateTrendChart({ runs }: PassRateTrendChartProps) {
  const data = useMemo(() => {
    return runs
      .filter((r) => r.pass_rate !== undefined && r.pass_rate !== null)
      .slice(-20)
      .reverse()
      .map((r) => ({
        time: r.started_at ? formatTime(r.started_at) : 'N/A',
        passRate: Number(r.pass_rate),
        passed: r.passed || 0,
        total: r.total_cases || 0,
      }));
  }, [runs]);

  if (data.length === 0) {
    return (
      <div className="bg-white rounded-lg p-6 border border-gray-100">
        <h4 className="text-sm font-semibold text-gray-600 mb-4">通过率趋势</h4>
        <p className="text-sm text-gray-400 text-center py-8">暂无历史数据</p>
      </div>
    );
  }

  return (
    <div className="bg-white rounded-lg p-6 border border-gray-100">
      <h4 className="text-sm font-semibold text-gray-600 mb-4">通过率趋势</h4>
      <ResponsiveContainer width="100%" height={250}>
        <LineChart data={data}>
          <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
          <XAxis dataKey="time" tick={{ fontSize: 11 }} />
          <YAxis domain={[0, 100]} tick={{ fontSize: 12 }} unit="%" />
          <Tooltip
            formatter={(value) => [`${Number(value).toFixed(1)}%`, '通过率']}
            labelFormatter={(label) => {
              const idx = data.findIndex(d => d.time === label);
              const d = idx >= 0 ? data[idx] : null;
              return d ? `${d.time} (${d.passed}/${d.total})` : String(label);
            }}
          />
          <ReferenceLine y={90} stroke="#22c55e" strokeDasharray="4 4" label={{ value: '90%', fontSize: 11 }} />
          <Line
            type="monotone"
            dataKey="passRate"
            name="通过率"
            stroke="#6366f1"
            strokeWidth={2}
            dot={{ r: 3, fill: '#6366f1' }}
            activeDot={{ r: 5 }}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
