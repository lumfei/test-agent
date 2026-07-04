import { useAppStore } from '../../stores/useAppStore';
import { DEFAULT_BACKEND_URL } from '../../utils/constants';
import { Wifi, WifiOff } from 'lucide-react';

export function Sidebar() {
  const mode = useAppStore((s) => s.mode);
  const setMode = useAppStore((s) => s.setMode);
  const backendUrl = useAppStore((s) => s.backendUrl);
  const setBackendUrl = useAppStore((s) => s.setBackendUrl);
  const isHealthy = useAppStore((s) => s.isHealthy);
  const healthModel = useAppStore((s) => s.healthModel);
  const checkHealth = useAppStore((s) => s.checkHealth);
  const authType = useAppStore((s) => s.authType);
  const setAuthType = useAppStore((s) => s.setAuthType);
  const authToken = useAppStore((s) => s.authToken);
  const setAuthToken = useAppStore((s) => s.setAuthToken);
  const authUsername = useAppStore((s) => s.authUsername);
  const authPassword = useAppStore((s) => s.authPassword);
  const setAuthCredentials = useAppStore((s) => s.setAuthCredentials);

  const healthColor = isHealthy === null ? 'bg-gray-300' : isHealthy ? 'bg-green-500' : 'bg-red-500';
  const healthText = isHealthy === null ? '未检查' : isHealthy ? `已连接 - ${healthModel}` : '连接失败';

  return (
    <aside className="w-72 bg-white border-r border-gray-200 flex flex-col h-full">
      {/* Header */}
      <div className="px-5 py-4 border-b border-gray-100">
        <h1 className="text-lg font-bold text-gray-800 flex items-center gap-2">
          <span className="text-xl">🧪</span>
          API 测试看板
        </h1>
        <p className="text-xs text-gray-400 mt-0.5">LangGraph + DeepSeek</p>
      </div>

      {/* Mode Toggle */}
      <div className="px-4 py-3 border-b border-gray-100">
        <div className="flex rounded-lg bg-gray-100 p-0.5">
          <button
            onClick={() => setMode('online')}
            className={`flex-1 py-1.5 text-sm rounded-md font-medium transition-colors ${
              mode === 'online'
                ? 'bg-white text-gray-800 shadow-sm'
                : 'text-gray-500 hover:text-gray-700'
            }`}
          >
            🌐 在线模式
          </button>
          <button
            onClick={() => setMode('offline')}
            className={`flex-1 py-1.5 text-sm rounded-md font-medium transition-colors ${
              mode === 'offline'
                ? 'bg-white text-gray-800 shadow-sm'
                : 'text-gray-500 hover:text-gray-700'
            }`}
          >
            📁 离线模式
          </button>
        </div>
      </div>

      {/* Online mode config */}
      {mode === 'online' && (
        <div className="flex-1 overflow-y-auto">
          <div className="px-4 py-3 space-y-3">
            {/* Backend URL */}
            <div>
              <label className="block text-xs font-medium text-gray-500 mb-1">后端地址</label>
              <input
                type="text"
                value={backendUrl}
                onChange={(e) => setBackendUrl(e.target.value)}
                className="w-full px-3 py-1.5 text-sm border border-gray-200 rounded-md focus:outline-none focus:ring-2 focus:ring-indigo-400 focus:border-transparent"
                placeholder={DEFAULT_BACKEND_URL}
              />
            </div>

            {/* Health check */}
            <div>
              <button
                onClick={checkHealth}
                className="w-full flex items-center justify-center gap-2 px-3 py-1.5 text-sm border border-gray-200 rounded-md hover:bg-gray-50 transition-colors"
              >
                <span className={`w-2 h-2 rounded-full ${healthColor}`} />
                <span>检查连接</span>
              </button>
              {isHealthy !== null && (
                <p className={`text-xs mt-1 px-1 ${isHealthy ? 'text-green-600' : 'text-red-500'}`}>
                  {isHealthy ? <Wifi className="inline w-3 h-3 mr-1" /> : <WifiOff className="inline w-3 h-3 mr-1" />}
                  {healthText}
                </p>
              )}
            </div>
          </div>

          {/* Auth Config */}
          <div className="px-4 py-3 border-t border-gray-100">
            <label className="block text-xs font-medium text-gray-500 mb-2">认证配置</label>
            <select
              value={authType}
              onChange={(e) => setAuthType(e.target.value as typeof authType)}
              className="w-full px-3 py-1.5 text-sm border border-gray-200 rounded-md focus:outline-none focus:ring-2 focus:ring-indigo-400"
            >
              <option value="none">无认证</option>
              <option value="bearer">Bearer Token</option>
              <option value="api_key">API Key</option>
              <option value="basic">Basic Auth</option>
            </select>

            {(authType === 'bearer' || authType === 'api_key') && (
              <div className="mt-2">
                <label className="block text-xs text-gray-400 mb-1">令牌</label>
                <input
                  type="password"
                  value={authToken}
                  onChange={(e) => setAuthToken(e.target.value)}
                  className="w-full px-3 py-1.5 text-sm border border-gray-200 rounded-md focus:outline-none focus:ring-2 focus:ring-indigo-400"
                  placeholder="输入令牌..."
                />
              </div>
            )}

            {authType === 'basic' && (
              <div className="mt-2 space-y-2">
                <div>
                  <label className="block text-xs text-gray-400 mb-1">用户名</label>
                  <input
                    type="text"
                    value={authUsername}
                    onChange={(e) => setAuthCredentials(e.target.value, authPassword)}
                    className="w-full px-3 py-1.5 text-sm border border-gray-200 rounded-md focus:outline-none focus:ring-2 focus:ring-indigo-400"
                    placeholder="用户名"
                  />
                </div>
                <div>
                  <label className="block text-xs text-gray-400 mb-1">密码</label>
                  <input
                    type="password"
                    value={authPassword}
                    onChange={(e) => setAuthCredentials(authUsername, e.target.value)}
                    className="w-full px-3 py-1.5 text-sm border border-gray-200 rounded-md focus:outline-none focus:ring-2 focus:ring-indigo-400"
                    placeholder="密码"
                  />
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Offline mode hint */}
      {mode === 'offline' && (
        <div className="flex-1 px-4 py-4">
          <div className="bg-indigo-50 border border-indigo-100 rounded-lg p-3">
            <p className="text-xs text-indigo-700 font-medium mb-1">📁 离线模式</p>
            <p className="text-xs text-indigo-500">
              拖拽或选择本地的 JSON 报告文件来查看测试结果，无需后端运行。
            </p>
          </div>
        </div>
      )}
    </aside>
  );
}
