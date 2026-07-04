const DEFAULT_TIMEOUT = 30000;

export class ApiError extends Error {
  status: number;
  body: unknown;

  constructor(message: string, status: number, body?: unknown) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.body = body;
  }
}

interface RequestOptions extends RequestInit {
  timeout?: number;
  params?: Record<string, string>;
}

export async function apiClient<T>(url: string, options: RequestOptions = {}): Promise<T> {
  const { timeout = DEFAULT_TIMEOUT, params, ...fetchOptions } = options;

  // Append query params
  let finalUrl = url;
  if (params) {
    const qs = new URLSearchParams(params).toString();
    finalUrl += (url.includes('?') ? '&' : '?') + qs;
  }

  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeout);

  try {
    const response = await fetch(finalUrl, {
      ...fetchOptions,
      signal: controller.signal,
      headers: {
        Accept: 'application/json',
        ...fetchOptions.headers,
      },
    });

    if (!response.ok) {
      let body: unknown;
      try {
        body = await response.json();
      } catch {
        body = await response.text();
      }
      const statusMessages: Record<number, string> = {
        404: '资源未找到',
        500: '服务器内部错误',
        502: '网关错误',
        503: '服务不可用',
      };
      throw new ApiError(
        statusMessages[response.status] || `请求失败 (${response.status})`,
        response.status,
        body,
      );
    }

    // Handle empty responses (204, etc.)
    const contentType = response.headers.get('content-type') || '';
    if (contentType.includes('application/json')) {
      return (await response.json()) as T;
    }
    return (await response.text()) as unknown as T;
  } catch (e) {
    if (e instanceof ApiError) throw e;
    if (e instanceof DOMException && e.name === 'AbortError') {
      throw new ApiError('请求超时', 408);
    }
    if (e instanceof TypeError && e.message.includes('fetch')) {
      throw new ApiError('无法连接到后端服务，请检查服务是否启动', 0);
    }
    throw e;
  } finally {
    clearTimeout(timer);
  }
}
