// Typed HTTP client with retry logic, timeout, and request tracing
import { ApiResponse, ApiError, RequestOptions } from "./types";

const DEFAULT_TIMEOUT_MS = 10_000;
const DEFAULT_RETRIES = 3;

export class HttpError extends Error {
  constructor(
    public readonly status: number,
    public readonly apiError: ApiError
  ) {
    super(apiError.message);
    this.name = "HttpError";
  }
}

export class HttpClient {
  private readonly baseUrl: string;
  private readonly defaultHeaders: Record<string, string>;

  constructor(baseUrl: string, defaultHeaders: Record<string, string> = {}) {
    this.baseUrl = baseUrl.replace(/\/$/, "");
    this.defaultHeaders = {
      "Content-Type": "application/json",
      ...defaultHeaders,
    };
  }

  async get<T>(path: string, options: RequestOptions = {}): Promise<ApiResponse<T>> {
    return this.request<T>("GET", path, undefined, options);
  }

  async post<T>(path: string, body: unknown, options: RequestOptions = {}): Promise<ApiResponse<T>> {
    return this.request<T>("POST", path, body, options);
  }

  async put<T>(path: string, body: unknown, options: RequestOptions = {}): Promise<ApiResponse<T>> {
    return this.request<T>("PUT", path, body, options);
  }

  async delete<T>(path: string, options: RequestOptions = {}): Promise<ApiResponse<T>> {
    return this.request<T>("DELETE", path, undefined, options);
  }

  private async request<T>(
    method: string,
    path: string,
    body: unknown,
    options: RequestOptions
  ): Promise<ApiResponse<T>> {
    const url = `${this.baseUrl}${path}`;
    const timeout = options.timeout ?? DEFAULT_TIMEOUT_MS;
    const maxRetries = options.retries ?? DEFAULT_RETRIES;

    const headers = { ...this.defaultHeaders, ...(options.headers ?? {}) };

    for (let attempt = 0; attempt <= maxRetries; attempt++) {
      const controller = new AbortController();
      const timerId = setTimeout(() => controller.abort(), timeout);

      try {
        const response = await fetch(url, {
          method,
          headers,
          body: body !== undefined ? JSON.stringify(body) : undefined,
          signal: options.signal ?? controller.signal,
        });

        clearTimeout(timerId);

        if (!response.ok) {
          const error: ApiError = await response.json().catch(() => ({
            code: "UNKNOWN",
            message: response.statusText,
          }));
          throw new HttpError(response.status, error);
        }

        return response.json() as Promise<ApiResponse<T>>;
      } catch (err) {
        clearTimeout(timerId);
        const isLastAttempt = attempt === maxRetries;
        const isRetryable = !(err instanceof HttpError) || err.status >= 500;

        if (isLastAttempt || !isRetryable) throw err;

        // Exponential backoff: 100ms, 200ms, 400ms...
        await sleep(100 * Math.pow(2, attempt));
      }
    }

    throw new Error("Request failed after max retries");
  }

  withAuthHeader(token: string): HttpClient {
    return new HttpClient(this.baseUrl, {
      ...this.defaultHeaders,
      Authorization: `Bearer ${token}`,
    });
  }
}

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}
