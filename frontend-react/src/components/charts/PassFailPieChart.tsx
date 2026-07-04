import { PieChart, Pie, Cell, ResponsiveContainer, Legend, Tooltip } from 'recharts';

interface PassFailPieChartProps {
  passed: number;
  failed: number;
  errors: number;
}

export function PassFailPieChart({ passed, failed, errors }: PassFailPieChartProps) {
  const data = [
    { name: '通过', value: passed, color: '#22c55e' },
    { name: '失败', value: failed, color: '#ef4444' },
    { name: '错误', value: errors, color: '#f97316' },
  ].filter((d) => d.value > 0);

  if (data.length === 0) {
    return (
      <div className="bg-white rounded-lg p-6 border border-gray-100">
        <h4 className="text-sm font-semibold text-gray-600 mb-4">结果分布</h4>
        <p className="text-sm text-gray-400 text-center py-8">暂无数据</p>
      </div>
    );
  }

  return (
    <div className="bg-white rounded-lg p-6 border border-gray-100">
      <h4 className="text-sm font-semibold text-gray-600 mb-4">结果分布</h4>
      <ResponsiveContainer width="100%" height={280}>
        <PieChart>
          <Pie
            data={data}
            cx="50%"
            cy="50%"
            innerRadius={55}
            outerRadius={100}
            paddingAngle={3}
            dataKey="value"
            label={({ name, value, percent }) =>
              `${name} ${value} (${((percent ?? 0) * 100).toFixed(0)}%)`
            }
          >
            {data.map((entry, index) => (
              <Cell key={index} fill={entry.color} />
            ))}
          </Pie>
          <Tooltip formatter={(value) => [`${value} 个`, '']} />
          <Legend />
        </PieChart>
      </ResponsiveContainer>
    </div>
  );
}
