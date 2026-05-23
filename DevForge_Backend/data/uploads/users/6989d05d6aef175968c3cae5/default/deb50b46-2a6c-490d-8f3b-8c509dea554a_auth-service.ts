// Authentication service: login, token refresh, session management
import { AuthToken, TokenString, UserId, SessionId, AuditEvent } from "./types";
import { HttpClient } from "./http-client";
import { UserSessionCache } from "./cache";

interface LoginRequest {
  email: string;
  password: string;
  tenantId: string;
}

interface RefreshRequest {
  refreshToken: TokenString;
}

export class AuthService {
  private readonly sessionCache: UserSessionCache;
  private readonly tokenStore = new Map<UserId, AuthToken>();
  private readonly auditLog: AuditEvent[] = [];

  constructor(
    private readonly client: HttpClient,
    private readonly tenantId: string
  ) {
    this.sessionCache = new UserSessionCache();
  }

  async login(email: string, password: string): Promise<AuthToken> {
    const body: LoginRequest = { email, password, tenantId: this.tenantId };
    const response = await this.client.post<AuthToken>("/api/auth/login", body);
    const token = response.data;

    this.tokenStore.set(token.userId, token);
    this.sessionCache.setSession(this.generateSessionId(), token.userId);

    this.recordAuditEvent({
      type: "user.login",
      userId: token.userId,
      sessionId: this.generateSessionId(),
      metadata: { email, tenantId: this.tenantId },
      timestamp: new Date(),
    });

    return token;
  }

  async refreshToken(userId: UserId): Promise<AuthToken> {
    const current = this.tokenStore.get(userId);
    if (!current) throw new Error(`No token found for user ${userId}`);

    if (!this.isTokenExpiringSoon(current)) return current;

    const body: RefreshRequest = { refreshToken: current.refreshToken };
    const response = await this.client.post<AuthToken>("/api/auth/refresh", body);
    const newToken = response.data;

    this.tokenStore.set(userId, newToken);
    this.recordAuditEvent({
      type: "token.refreshed",
      userId,
      sessionId: this.generateSessionId(),
      metadata: { tenantId: this.tenantId },
      timestamp: new Date(),
    });

    return newToken;
  }

  async logout(userId: UserId): Promise<void> {
    const token = this.tokenStore.get(userId);
    if (token) {
      await this.client.post("/api/auth/logout", { userId }).catch(() => {});
      this.tokenStore.delete(userId);
      this.sessionCache.invalidateUser(userId);

      this.recordAuditEvent({
        type: "user.logout",
        userId,
        sessionId: this.generateSessionId(),
        metadata: {},
        timestamp: new Date(),
      });
    }
  }

  getValidToken(userId: UserId): AuthToken | null {
    const token = this.tokenStore.get(userId);
    if (!token) return null;
    if (new Date() >= token.expiresAt) {
      this.tokenStore.delete(userId);
      return null;
    }
    return token;
  }

  resolveSession(sessionId: SessionId): UserId | null {
    return this.sessionCache.getSession(sessionId);
  }

  getAuditLog(): readonly AuditEvent[] {
    return this.auditLog;
  }

  private isTokenExpiringSoon(token: AuthToken, bufferMs = 60_000): boolean {
    return token.expiresAt.getTime() - Date.now() < bufferMs;
  }

  private generateSessionId(): SessionId {
    return `sess_${Date.now()}_${Math.random().toString(36).slice(2)}`;
  }

  private recordAuditEvent(event: AuditEvent): void {
    this.auditLog.push(event);
    if (this.auditLog.length > 10_000) {
      this.auditLog.splice(0, 1000); // trim oldest 1000
    }
  }
}
