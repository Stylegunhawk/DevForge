const BASE_URL = process.env.NODE_ENV === 'production' ? 'http://localhost:8001' : '';

// Types
export interface ApiKey {
  id: string;
  name: string;
  integration_name: string;
  tenant_id: string;
  tier: string;
  scopes: string[];
  is_active: boolean;
  last_used_at: string | null;
  created_at: string;
  user_id: string | null;
}

export interface CreateKeyRequest {
  name: string;
  integration_name: string;
  tenant_id: string;
  tier?: string;
  scopes?: string[];
}

export function getAuthHeaders(accessToken?: string): Record<string, string> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
  };

  if (accessToken) {
    headers.Authorization = `Bearer ${accessToken}`;
  }

  return headers;
}

export async function apiFetch<T>(
  endpoint: string,
  options?: RequestInit & { accessToken?: string }
): Promise<T> {
  // Map backend endpoints to proxy routes
  let proxyUrl = endpoint;
  if (endpoint.startsWith('/api/')) {
    proxyUrl = `/api/proxy${endpoint.substring(4)}`; // Replace /api with /api/proxy
  }

  const url = BASE_URL ? `${BASE_URL}${endpoint}` : proxyUrl;
  const headers = getAuthHeaders(options?.accessToken);

  const response = await fetch(url, {
    ...options,
    headers: {
      ...headers,
      ...options?.headers,
    },
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(error.message || `HTTP error! status: ${response.status}`);
  }

  return response.json();
}

// API Key functions
export async function getUserKeys(accessToken: string): Promise<ApiKey[]> {
  return apiFetch<ApiKey[]>("/api/users/keys", {
    accessToken,
  });
}

export async function createUserKey(
  accessToken: string,
  data: CreateKeyRequest
): Promise<{ key: string; message: string }> {
  return apiFetch<{ key: string; message: string }>("/api/users/keys", {
    method: "POST",
    body: JSON.stringify(data),
    accessToken,
  });
}

export async function revokeUserKey(
  accessToken: string,
  keyId: string
): Promise<{ success: boolean }> {
  return apiFetch<{ success: boolean }>(`/api/users/keys/${keyId}`, {
    method: "DELETE",
    accessToken,
  });
}

export const api = {
  get: <T>(endpoint: string, accessToken?: string) => 
    apiFetch<T>(endpoint, { accessToken }),
  post: <T>(endpoint: string, data?: any, accessToken?: string) =>
    apiFetch<T>(endpoint, {
      method: "POST",
      body: data ? JSON.stringify(data) : undefined,
      accessToken,
    }),
  put: <T>(endpoint: string, data?: any, accessToken?: string) =>
    apiFetch<T>(endpoint, {
      method: "PUT",
      body: data ? JSON.stringify(data) : undefined,
      accessToken,
    }),
  delete: <T>(endpoint: string, accessToken?: string) =>
    apiFetch<T>(endpoint, {
      method: "DELETE",
      accessToken,
    }),
};
