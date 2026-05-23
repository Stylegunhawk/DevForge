// User repository: CRUD operations with caching, auth, and pagination
import { User, UserId, UserFilter, PaginatedResponse, ApiResponse } from "./types";
import { HttpClient } from "./http-client";
import { AuthService } from "./auth-service";
import { CacheStore } from "./cache";

const USER_CACHE_TTL_MS = 2 * 60 * 1000; // 2 minutes

export class UserRepository {
  private readonly userCache: CacheStore<User>;

  constructor(
    private readonly client: HttpClient,
    private readonly auth: AuthService,
    private readonly currentUserId: UserId
  ) {
    this.userCache = new CacheStore<User>({
      maxSize: 256,
      defaultTtlMs: USER_CACHE_TTL_MS,
    });
  }

  async findById(id: UserId): Promise<User | null> {
    const cached = this.userCache.get(`user:${id}`);
    if (cached) return cached;

    const authedClient = await this.getAuthedClient();
    const response = await authedClient
      .get<User>(`/api/v1/users/${id}`)
      .catch(() => null);

    if (!response) return null;
    this.userCache.set(`user:${id}`, response.data);
    return response.data;
  }

  async list(filter: UserFilter = {}): Promise<PaginatedResponse<User>> {
    const authedClient = await this.getAuthedClient();
    const params = new URLSearchParams();

    if (filter.role) params.set("role", filter.role);
    if (filter.email) params.set("email", filter.email);
    if (filter.limit !== undefined) params.set("limit", String(filter.limit));
    if (filter.offset !== undefined) params.set("offset", String(filter.offset));

    const path = `/api/v1/users?${params.toString()}`;
    const response = await authedClient.get<PaginatedResponse<User>>(path);
    return response.data;
  }

  async create(data: Omit<User, "id" | "createdAt" | "lastLoginAt">): Promise<User> {
    const authedClient = await this.getAuthedClient();
    const response = await authedClient.post<User>("/api/v1/users", data);
    const user = response.data;
    this.userCache.set(`user:${user.id}`, user);
    return user;
  }

  async update(id: UserId, patch: Partial<Pick<User, "displayName" | "role">>): Promise<User> {
    const authedClient = await this.getAuthedClient();
    const response = await authedClient.put<User>(`/api/v1/users/${id}`, patch);
    const updated = response.data;
    this.userCache.set(`user:${id}`, updated);
    return updated;
  }

  async delete(id: UserId): Promise<void> {
    const authedClient = await this.getAuthedClient();
    await authedClient.delete(`/api/v1/users/${id}`);
    this.userCache.delete(`user:${id}`);
  }

  async bulkFetch(ids: UserId[]): Promise<Map<UserId, User>> {
    const result = new Map<UserId, User>();
    const missing: UserId[] = [];

    for (const id of ids) {
      const cached = this.userCache.get(`user:${id}`);
      if (cached) result.set(id, cached);
      else missing.push(id);
    }

    if (missing.length > 0) {
      const authedClient = await this.getAuthedClient();
      const response = await authedClient.post<User[]>("/api/v1/users/bulk", { ids: missing });
      for (const user of response.data) {
        result.set(user.id, user);
        this.userCache.set(`user:${user.id}`, user);
      }
    }

    return result;
  }

  invalidateCache(userId?: UserId): void {
    if (userId) {
      this.userCache.delete(`user:${userId}`);
    } else {
      this.userCache.clear();
    }
  }

  private async getAuthedClient(): Promise<HttpClient> {
    const token = await this.auth.refreshToken(this.currentUserId);
    return this.client.withAuthHeader(token.accessToken);
  }
}
