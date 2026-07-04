// ===== SSE Events =====
export interface SSEProgressData {
  node: string;
  progress: number;
  message: string;
}

export interface SSECaseResultData {
  case_name: string;
  passed: boolean;
  method: string;
  path: string;
  status_code: number;
  elapsed_ms: number;
  category: string;
}

export interface SSECompletedData {
  run_id: string;
  total: number;
  passed: number;
  failed: number;
  errors: number;
  pass_rate: number;
  api_name: string;
  report_path: string;
}

export interface SSEErrorData {
  message: string;
}

export type SSEEvent =
  | { type: 'progress'; data: SSEProgressData }
  | { type: 'case_result'; data: SSECaseResultData }
  | { type: 'completed'; data: SSECompletedData }
  | { type: 'error'; data: SSEErrorData };

// ===== Test Result =====
export interface TestCheck {
  check_name: string;
  passed: boolean;
  detail: string;
}

export interface TestResult {
  name: string;
  passed: boolean;
  method: string;
  path: string;
  status_code: number;
  elapsed_ms: number;
  expected_status?: number | number[];
  category: string;
  checks: TestCheck[];
  error?: string | null;
  response_preview?: string;
  tags?: string[];
}

export interface TestCase {
  name: string;
  description: string;
  method: string;
  path: string;
  params?: Record<string, unknown> | null;
  body?: Record<string, unknown> | null;
  headers?: Record<string, string> | null;
  expected_status: number | number[];
  expected_schema?: Record<string, unknown> | null;
  priority: string;
  category: string;
  tags: string[];
}

// ===== Report =====
export interface CategoryStat {
  total: number;
  passed: number;
  failed: number;
  errors: number;
}

export interface EndpointStat {
  total: number;
  passed: number;
  failed: number;
  errors: number;
}

export interface ReportSummary {
  total: number;
  passed: number;
  failed: number;
  errors: number;
  pass_rate: number;
}

export interface TestReport {
  report_id: string;
  api_name: string;
  base_url: string;
  spec_url?: string | null;
  generated_at: string;
  duration_seconds: number;
  summary: ReportSummary;
  by_category: Record<string, CategoryStat>;
  by_endpoint: Record<string, EndpointStat>;
  results: TestResult[];
}

// ===== API Types =====
export interface StartTestRequest {
  spec_url: string;
  auth_type?: string | null;
  auth_token?: string | null;
  auth_username?: string | null;
  auth_password?: string | null;
}

export interface StartTestResponse {
  run_id: string;
  status: string;
  started_at: string;
  check_status_url: string;
}

export interface RunResult {
  run_id: string;
  api_name: string;
  base_url: string;
  spec_url: string;
  started_at: string;
  completed_at?: string;
  status: string;
  total_cases: number;
  passed: number;
  failed: number;
  errors: number;
  pass_rate: number;
  report_path?: string;
}

export interface ResultsResponse {
  run: Record<string, unknown>;
  results: TestResult[];
  categories: { category: string; total: number; passed: number; failed: number; errors: number }[];
}

export interface HistoryRun {
  run_id: string;
  api_name: string;
  base_url: string;
  spec_url: string;
  started_at: string;
  completed_at?: string;
  duration_seconds?: number;
  total_cases?: number;
  passed?: number;
  failed?: number;
  errors?: number;
  pass_rate?: number;
  status: string;
}

export interface HistoryResponse {
  total: number;
  runs: HistoryRun[];
}

export interface HealthResponse {
  status: string;
  model: string;
}

// ===== Auth =====
export type AuthType = 'none' | 'bearer' | 'api_key' | 'basic';

export interface AuthConfig {
  type: AuthType;
  token?: string;
  key?: string;
  username?: string;
  password?: string;
}

// ===== Progress =====
export interface ProgressEntry {
  node: string;
  progress: number;
  message: string;
  timestamp: number;
}
