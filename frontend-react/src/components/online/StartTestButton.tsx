import { Loader2, Play } from 'lucide-react';

interface StartTestButtonProps {
  status: 'idle' | 'starting' | 'running' | 'completed' | 'error';
  onClick: () => void;
  disabled?: boolean;
}

export function StartTestButton({ status, onClick, disabled }: StartTestButtonProps) {
  const isActive = status === 'starting' || status === 'running';

  return (
    <button
      onClick={onClick}
      disabled={disabled || isActive}
      className="w-full flex items-center justify-center gap-2 px-6 py-3 text-base font-medium text-white bg-indigo-600 rounded-lg hover:bg-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
    >
      {isActive ? (
        <>
          <Loader2 className="w-5 h-5 animate-spin" />
          {status === 'starting' ? '正在启动...' : '测试运行中...'}
        </>
      ) : (
        <>
          <Play className="w-5 h-5" />
          开始测试
        </>
      )}
    </button>
  );
}
