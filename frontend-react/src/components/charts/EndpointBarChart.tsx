import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend } from 'recharts';
import type { EndpointStat } from '../../types';
import { useMemo } from 'react';

interface EndpointBarChartProps {
  byEndpoint: Record<string, EndpointStat>;
}

export function EndpointBarChart({ byEndpoint }: EndpointBarChartProps) {
  const data = useMemo(() => {
    return Object.entries(byEndpoint)
      .sort((a, b) => b[1].total - a[1].total)
      .slice(0, 15)
      .map(([ep, stats]) => ({
        endpoint: ep.length > 40 ? ep.slice(0, 38) + '...' : ep,
        fullEndpoint: ep,
        total: stats.total,
        passed: stats.passed,
        failed: stats.failed,
        errors: stats.errors,
      }));
  }, [byEndpoint]);

  if (data.length === 0) {
    return (
      <div className="bg-white rounded-lg p-6 border border-gray-100">
        <h4 className="text-sm font-semibold text-gray-600 mb-4">按接口统计 (Top 15)</h4>
        <p className="text-sm text-gray-400 text-center py-8">暂无数据</p>
      </div>
    );
  }

  return (
    <div className="bg-white rounded-lg p-6 border border-gray-100">
      <h4 className="text-sm font-semibold text-gray-600 mb-4">按接口统计 (Top 15)</h4>
      <ResponsiveContainer width="100%" height={Math.max(300, data.length * 28)}>
        <BarChart data={data} layout="vertical" barSize={16}>
          <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
          <XAxis type="number" tick={{ fontSize: 12 }} />
          <YAxis
            type="category"
            dataKey="endpoint"
            width={200}
            tick={{ fontSize: 11 }}
          />
          <Tooltip
            formatter={(value, name) => [`${value}`, name]}
            labelFormatter={(label) => {
              const idx = data.findIndex(d => d.endpoint === label);
              return idx >= 0 ? data[idx].fullEndpoint : String(label);
            }}
          />
          <Legend />
          <Bar dataKey="passed" name="通过" fill="#22c55e" radius={[0, 2, 2, 0]} stackId="stack" />
          <Bar dataKey="failed" name="失败" fill="#ef4444" stackId="stack" />
          <Bar dataKey="errors" name="错误" fill="#f97316" stackId="stack" />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
