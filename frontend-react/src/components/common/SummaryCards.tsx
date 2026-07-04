interface SummaryCardsProps {
  total: number;
  passed: number;
  failed: number;
  errors: number;
  passRate: number;
  durationSeconds?: number;
}

export function SummaryCards({ total, passed, failed, errors, passRate, durationSeconds }: SummaryCardsProps) {
  const cards = [
    { label: '总用例', value: total, color: 'text-blue-600', bg: 'bg-blue-50', icon: '📋' },
    { label: '通过', value: passed, color: 'text-green-600', bg: 'bg-green-50', icon: '✅' },
    { label: '失败', value: failed, color: 'text-red-600', bg: 'bg-red-50', icon: '❌' },
    { label: '错误', value: errors, color: 'text-orange-600', bg: 'bg-orange-50', icon: '⚠️' },
    { label: '通过率', value: `${(passRate * 100).toFixed(1)}%`, color: 'text-purple-600', bg: 'bg-purple-50', icon: '📊' },
  ];

  if (durationSeconds !== undefined) {
    cards.push({
      label: '耗时', value: durationSeconds < 60 ? `${durationSeconds.toFixed(1)}s` : `${Math.floor(durationSeconds / 60)}m ${Math.round(durationSeconds % 60)}s`,
      color: 'text-gray-600', bg: 'bg-gray-50', icon: '⏱️',
    });
  }

  return (
    <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
      {cards.map((card) => (
        <div key={card.label} className={`${card.bg} rounded-lg p-4 border border-gray-100`}>
          <div className="flex items-center gap-2 mb-2">
            <span className="text-lg">{card.icon}</span>
            <span className="text-xs font-medium text-gray-500">{card.label}</span>
          </div>
          <p className={`text-2xl font-bold ${card.color}`}>{card.value}</p>
        </div>
      ))}
    </div>
  );
}
