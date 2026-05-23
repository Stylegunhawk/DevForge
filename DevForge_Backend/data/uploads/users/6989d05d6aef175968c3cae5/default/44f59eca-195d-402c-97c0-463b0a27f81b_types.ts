// Core domain types for the RAG test codebase

export type UserId = string;
export type SessionId = string;
export type TokenString = string;

export interface User {
  id: UserId;
  email: string;
  displayName: string;
  role: "admin" | "member" | "viewer";
  createdAt: Date;
  lastLoginAt: Date | null;
}

export interface AuthToken {
  accessToken: TokenString;
  refreshToken: TokenString;
  expiresAt: Date;
  tenantId: string;
  userId: UserId;
}

export interface ApiResponse<T> {
  data: T;
  status: number;
  message: string;
  requestId: string;
  timestamp: Date;
}

export interface PaginatedResponse<T> extends ApiResponse<T[]> {
  page: number;
  pageSize: number;
  totalCount: number;
  hasNextPage: boolean;
}

export interface ApiError {
  code: string;
  message: string;
  details?: Record<string, unknown>;
  requestId?: string;
}

export interface CacheEntry<T> {
  value: T;
  expiresAt: number;
  key: string;
}

export interface RequestOptions {
  headers?: Record<string, string>;
  timeout?: number;
  retries?: number;
  signal?: AbortSignal;
}

export interface UserFilter {
  role?: User["role"];
  email?: string;
  createdAfter?: Date;
  limit?: number;
  offset?: number;
}

export type EventType =
  | "user.login"
  | "user.logout"
  | "user.created"
  | "token.refreshed"
  | "token.revoked";

export interface AuditEvent {
  type: EventType;
  userId: UserId;
  sessionId: SessionId;
  metadata: Record<string, unknown>;
  timestamp: Date;
}
