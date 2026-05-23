// Generic in-memory cache with TTL and LRU eviction
import { CacheEntry } from "./types";

export class CacheStore<T> {
  private store = new Map<string, CacheEntry<T>>();
  private readonly maxSize: number;
  private readonly defaultTtlMs: number;

  constructor(options: { maxSize?: number; defaultTtlMs?: number } = {}) {
    this.maxSize = options.maxSize ?? 512;
    this.defaultTtlMs = options.defaultTtlMs ?? 5 * 60 * 1000; // 5 minutes
  }

  set(key: string, value: T, ttlMs?: number): void {
    if (this.store.size >= this.maxSize) {
      this.evictOldest();
    }
    const expiresAt = Date.now() + (ttlMs ?? this.defaultTtlMs);
    this.store.set(key, { key, value, expiresAt });
  }

  get(key: string): T | null {
    const entry = this.store.get(key);
    if (!entry) return null;
    if (Date.now() > entry.expiresAt) {
      this.store.delete(key);
      return null;
    }
    // LRU: re-insert to move to end of iteration order
    this.store.delete(key);
    this.store.set(key, entry);
    return entry.value;
  }

  delete(key: string): boolean {
    return this.store.delete(key);
  }

  invalidateByPrefix(prefix: string): number {
    let count = 0;
    for (const key of this.store.keys()) {
      if (key.startsWith(prefix)) {
        this.store.delete(key);
        count++;
      }
    }
    return count;
  }

  purgeExpired(): number {
    const now = Date.now();
    let count = 0;
    for (const [key, entry] of this.store.entries()) {
      if (now > entry.expiresAt) {
        this.store.delete(key);
        count++;
      }
    }
    return count;
  }

  size(): number {
    return this.store.size;
  }

  clear(): void {
    this.store.clear();
  }

  private evictOldest(): void {
    const oldestKey = this.store.keys().next().value;
    if (oldestKey) this.store.delete(oldestKey);
  }
}

export class UserSessionCache extends CacheStore<string> {
  constructor() {
    super({ maxSize: 1000, defaultTtlMs: 30 * 60 * 1000 }); // 30 min session TTL
  }

  setSession(sessionId: string, userId: string): void {
    this.set(`session:${sessionId}`, userId);
  }

  getSession(sessionId: string): string | null {
    return this.get(`session:${sessionId}`);
  }

  invalidateUser(userId: string): number {
    return this.invalidateByPrefix(`session:user:${userId}`);
  }
}
