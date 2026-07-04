export const DEFAULT_BACKEND_URL = 'http://localhost:8002';

export const APP_VERSION = 'v2.0.0';

export const APP_TITLE = 'API 测试看板';

export interface TabConfig {
  id: string;
  label: string;
  path: string;
}

export const ONLINE_TABS: TabConfig[] = [
  { id: 'run', label: '🚀 运行测试', path: '/run' },
  { id: 'history', label: '📊 测试历史', path: '/history' },
  { id: 'load', label: '📋 结果详情', path: '/load' },
];

export const OFFLINE_TABS: TabConfig[] = [
  { id: 'report', label: '📊 报告浏览', path: '/offline/report' },
  { id: 'detail', label: '📋 结果详情', path: '/offline/detail' },
];

export const CATEGORY_LABELS: Record<string, string> = {
  normal: '正常用例',
  boundary: '边界测试',
  error: '异常用例',
  security: '安全测试',
  'react-retry': 'ReAct 重试',
};

export const METHOD_COLORS: Record<string, string> = {
  GET: 'bg-green-100 text-green-700',
  POST: 'bg-blue-100 text-blue-700',
  PUT: 'bg-orange-100 text-orange-700',
  PATCH: 'bg-yellow-100 text-yellow-700',
  DELETE: 'bg-red-100 text-red-700',
};

export const QUICK_FILL_URLS = [
  { label: 'Petstore API', url: 'https://petstore3.swagger.io/api/v3/openapi.json' },
  { label: 'Localhost:8000', url: 'http://localhost:8000/openapi.json' },
  { label: 'Mock API:8001', url: 'http://localhost:8001/openapi.json' },
];
