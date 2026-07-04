import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend } from 'recharts';
import type { CategoryStat } from '../../types';
import { CATEGORY_LABELS } from '../../utils/constants';

interface CategoryBarChartProps {
  byCategory: Record<string, CategoryStat>;
}

export function CategoryBarChart({ byCategory }: CategoryBarChartProps) {
  const data = Object.entries(byCategory).map(([cat, stats]) => ({
    category: CATEGORY_LABELS[cat] || cat,
    通过: stats.passed,
    失败: stats.failed,
    错误: stats.errors,
  }));

  if (data.length === 0) {
    return (
      <div className="bg-white rounded-lg p-6 border border-gray-100">
        <h4 className="text-sm font-semibold text-gray-600 mb-4">按类别统计</h4>
        <p className="text-sm text-gray-400 text-center py-8">暂无数据</p>
      </div>
    );
  }

  return (
    <div className="bg-white rounded-lg p-6 border border-gray-100">
      <h4 className="text-sm font-semibold text-gray-600 mb-4">按类别统计</h4>
      <ResponsiveContainer width="100%" height={300}>
        <BarChart data={data} barGap={2}>
          <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
          <XAxis dataKey="category" tick={{ fontSize: 12 }} />
          <YAxis tick={{ fontSize: 12 }} />
          <Tooltip />
          <Legend />
          <Bar dataKey="通过" fill="#22c55e" radius={[4, 4, 0, 0]} />
          <Bar dataKey="失败" fill="#ef4444" radius={[4, 4, 0, 0]} />
          <Bar dataKey="错误" fill="#f97316" radius={[4, 4, 0, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
