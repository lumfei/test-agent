import { useAppStore } from '../../stores/useAppStore';
import { APP_VERSION } from '../../utils/constants';

export function Footer() {
  const mode = useAppStore((s) => s.mode);
  const modeLabel = mode === 'online' ? '在线模式' : '离线模式';

  return (
    <div className="border-t border-gray-200 px-4 py-3 text-center">
      <p className="text-xs text-gray-400">
        API Test Agent {APP_VERSION} &nbsp;|&nbsp; LangGraph + DeepSeek &nbsp;|&nbsp; {modeLabel}
        &nbsp;|&nbsp; {new Date().toLocaleString('zh-CN', { hour: '2-digit', minute: '2-digit' })}
      </p>
    </div>
  );
}
