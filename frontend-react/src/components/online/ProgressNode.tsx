import type { ProgressEntry } from '../../types';

interface ProgressNodeProps {
  entry: ProgressEntry;
}

const NODE_LABELS: Record<string, string> = {
  parse: '解析文档',
  analyze: '分析 API',
  generate: '生成用例',
  execute: '执行测试',
  validate: '验证 & 报告',
  reflect: 'ReAct 反思',
  error: '错误',
};

export function ProgressNode({ entry }: ProgressNodeProps) {
  const label = NODE_LABELS[entry.node] || entry.node;
  const pct = Math.round(entry.progress * 100);

  return (
    <div className="flex items-center gap-3 py-1.5">
      <span className="text-xs font-medium text-gray-600 w-20 flex-shrink-0">{label}</span>
      <div className="flex-1 h-2 bg-gray-100 rounded-full overflow-hidden">
        <div
          className="h-full bg-indigo-500 rounded-full progress-stripe transition-all duration-300"
          style={{ width: `${pct}%` }}
        />
      </div>
      <span className="text-xs text-gray-400 w-10 text-right flex-shrink-0">{pct}%</span>
      {entry.message && (
        <span className="text-xs text-gray-500 truncate max-w-48 flex-shrink-0 hidden sm:block">
          {entry.message}
        </span>
      )}
    </div>
  );
}
