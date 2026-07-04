import { clsx } from 'clsx';

interface StatusBadgeProps {
  passed: boolean;
  error?: boolean;
  className?: string;
}

export function StatusBadge({ passed, error, className }: StatusBadgeProps) {
  const label = error ? '错误' : passed ? '通过' : '失败';
  const style = error
    ? 'bg-orange-100 text-orange-700'
    : passed
    ? 'bg-green-100 text-green-700'
    : 'bg-red-100 text-red-700';

  return (
    <span className={clsx('inline-flex items-center px-2 py-0.5 text-xs font-medium rounded-full', style, className)}>
      {label}
    </span>
  );
}
