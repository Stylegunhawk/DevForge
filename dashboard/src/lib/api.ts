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
  expires_at: string | null;
  expiry_duration: string | null;
  is_expired: boolean;
  days_remaining: number | null;
}

export interface CreateKeyRequest {
  name: string;
  integration_name: string;
  tenant_id: string;
  tier?: string;
  scopes?: string[];
  expiry_duration?: "30d" | "90d" | "180d" | null;
}

// Admin Types
export interface DashboardSummary {
  total_users: number
  total_requests_today: number
  total_tokens_today: number
  total_cost_today: number
  active_users_today: number
  avg_duration_today: number
}

export interface TierConfig {
  tier: string
  hourly_limit: number
  monthly_limit: number | null
  cost_per_1k_tokens: number
  max_expiry_days: number
  is_active: boolean
  updated_at: string
  updated_by_email: string | null
}

export interface TierConfigUpdate {
  hourly_limit?: number
  monthly_limit?: number | null
  cost_per_1k_tokens?: number
  max_expiry_days?: number
}

export interface AdminPricingResponse {
  tiers: {
    free: TierConfig
    pro: TierConfig
    enterprise: TierConfig
  }
}

export interface KeyOverride {
  api_key_id: string
  tier: string
  name: string
  tier_defaults: { hourly_limit: number, monthly_limit: number | null }
  overrides: { hourly_limit_override: number | null, monthly_limit_override: number | null }
  effective_limits: { hourly: number, monthly: number | null }
}

export interface KeyOverrideUpdate {
  hourly_limit_override: number | null
  monthly_limit_override: number | null
}

export interface ToolStat {
  tool_name: string
  total_calls: number
  avg_duration_ms: number
  success_count: number
  error_count: number
  success_rate: number
  unique_users: number
  total_tokens: number
  total_cost_usd: number
}

export interface RequestLog {
  id: string
  user_id: string | null
  user_email: string
  user_name: string
  tenant_id: string
  integration_name: string
  tool_name: string
  input_summary: string
  success: boolean
  duration_ms: number
  created_at: string
}

export interface RequestDetail {
  id: string
  user_id: string | null
  user_email: string
  user_name: string
  tenant_id: string
  integration_name: string
  tool_name: string
  input_summary: string
  success: boolean
  duration_ms: number
  created_at: string
}

export interface AdminUser {
  id: string
  email: string
  name: string
  is_admin: boolean
  is_active: boolean
  created_at: string
}

export interface RequestLogFilters {
  tool_name?: string;
  success?: boolean;
  page?: number;
  limit?: number;
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

// Admin API functions
export async function getAdminSummary(accessToken: string): Promise<{summary: DashboardSummary, top_tools: ToolStat[]}> {
  return apiFetch<{summary: DashboardSummary, top_tools: ToolStat[]}>("/api/admin/dashboard/summary", {
    accessToken,
  });
}

export async function getToolStats(accessToken: string, days?: number): Promise<{tool_stats: ToolStat[], summary: any}> {
  const params = days ? `?days=${days}` : '';
  return apiFetch<{tool_stats: ToolStat[], summary: any}>(`/api/admin/tools/stats${params}`, {
    accessToken,
  });
}

export async function getRequestLogs(accessToken: string, filters?: RequestLogFilters): Promise<{requests: RequestLog[], pagination: any}> {
  const params = new URLSearchParams();
  if (filters?.tool_name) params.append('tool_name', filters.tool_name);
  if (filters?.success !== undefined) params.append('success', filters.success.toString());
  if (filters?.page) params.append('page', filters.page.toString());
  if (filters?.limit) params.append('limit', filters.limit.toString());
  
  const queryString = params.toString();
  return apiFetch<{requests: RequestLog[], pagination: any}>(`/api/admin/requests${queryString ? '?' + queryString : ''}`, {
    accessToken,
  });
}

export async function getAdminUsers(accessToken: string): Promise<{users: AdminUser[]}> {
  return apiFetch<{users: AdminUser[]}>("/api/admin/users", {
    accessToken,
  });
}

export async function updateUser(accessToken: string, userId: string, data: {is_admin?: boolean, is_active?: boolean}): Promise<any> {
  const params = new URLSearchParams();
  if (data.is_admin !== undefined) params.append('is_admin', data.is_admin.toString());
  if (data.is_active !== undefined) params.append('is_active', data.is_active.toString());
  
  return apiFetch<any>(`/api/admin/users/${userId}?${params.toString()}`, {
    method: "PATCH",
    accessToken,
  });
}

export async function getUserUsage(accessToken: string, userId: string, days?: number): Promise<{
  success: boolean;
  user: any;
  total_requests: number;
  total_tokens: number;
  total_cost: number;
  tool_usage: any[];
  token_usage: any[];
  period_days: number;
}> {
  const params = days ? `?days=${days}` : '';
  return apiFetch<{
    success: boolean;
    user: any;
    total_requests: number;
    total_tokens: number;
    total_cost: number;
    tool_usage: any[];
    token_usage: any[];
    period_days: number;
  }>(`/api/admin/users/${userId}/usage${params}`, {
    accessToken,
  });
}

export async function getUserRequestLogs(accessToken: string, filters?: {user_id?: string, limit?: number}): Promise<{requests: RequestLog[]}> {
  const params = new URLSearchParams();
  if (filters?.user_id) params.append('user_id', filters.user_id);
  if (filters?.limit) params.append('limit', filters.limit.toString());
  
  const queryString = params.toString();
  return apiFetch<{requests: RequestLog[]}>(`/api/admin/requests${queryString ? '?' + queryString : ''}`, {
    accessToken,
  });
}

export async function getCurrentUser(accessToken: string): Promise<any> {
  return apiFetch<any>('/api/auth/me', {
    accessToken,
  });
}

export async function updateProfile(accessToken: string, data: {name: string}): Promise<any> {
  return apiFetch<any>('/api/users/profile', {
    method: 'PATCH',
    body: JSON.stringify(data),
    accessToken,
  });
}

export async function getAdminPricing(accessToken: string): Promise<AdminPricingResponse> {
  return apiFetch<AdminPricingResponse>('/api/admin/pricing', {
    accessToken,
  });
}

export async function updateTierPricing(
  accessToken: string,
  tier: "free" | "pro" | "enterprise",
  updates: TierConfigUpdate
): Promise<{success: boolean, tier: string, config: TierConfig}> {
  return apiFetch<{success: boolean, tier: string, config: TierConfig}>(`/api/admin/pricing/${tier}`, {
    method: 'PATCH',
    body: JSON.stringify(updates),
    accessToken,
  });
}

export async function getKeyOverrides(
  accessToken: string, 
  keyId: string
): Promise<KeyOverride> {
  return apiFetch<KeyOverride>(`/api/admin/keys/${keyId}/overrides`, {
    accessToken,
  });
}

export async function updateKeyOverrides(
  accessToken: string,
  keyId: string,
  data: KeyOverrideUpdate
): Promise<{ success: boolean, effective_limits: any }> {
  return apiFetch<{ success: boolean, effective_limits: any }>(`/api/admin/keys/${keyId}/overrides`, {
    method: 'PATCH',
    body: JSON.stringify(data),
    accessToken,
  });
}

export async function getAdminKeys(accessToken: string): Promise<ApiKey[]> {
  return apiFetch<ApiKey[]>("/api/admin/keys", {
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
  patch: <T>(endpoint: string, data?: any, accessToken?: string) =>
    apiFetch<T>(endpoint, {
      method: "PATCH",
      body: data ? JSON.stringify(data) : undefined,
      accessToken,
    }),
};
