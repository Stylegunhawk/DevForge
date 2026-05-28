"use client";

import { useState, useEffect } from "react";
import { useSession } from "next-auth/react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { RefreshCw, ChevronLeft, ChevronRight } from "lucide-react";
import { getRequestLogs, RequestLog, RequestLogFilters } from "@/lib/api";

function formatRelativeTime(timestamp: string): string {
  const now = new Date();
  const time = new Date(timestamp);
  const diffMs = now.getTime() - time.getTime();
  const diffMinutes = Math.floor(diffMs / (1000 * 60));
  const diffHours = Math.floor(diffMs / (1000 * 60 * 60));
  const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));

  if (diffMinutes < 1) return "just now";
  if (diffMinutes < 60) return `${diffMinutes}m ago`;
  if (diffHours < 24) return `${diffHours}h ago`;
  return `${diffDays}d ago`;
}

function formatAbsoluteTime(timestamp: string): string {
  return new Date(timestamp).toLocaleString("en-US", {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function formatDuration(ms: number): string {
  if (ms < 1000) return `${ms}ms`;
  return `${(ms / 1000).toFixed(1)}s`;
}

function durationColor(ms: number): string {
  if (ms > 3000) return "text-[rgb(var(--danger))]";
  if (ms > 1000) return "text-yellow-600";
  return "";
}

interface Pagination {
  page: number;
  pages: number;
  total: number;
  limit: number;
}

// Fixed widths for structured columns; Input gets all remaining space
const COL_TEMPLATE =
  "90px minmax(0,130px) minmax(0,160px) minmax(0,110px) 75px 65px minmax(0,1fr)";

export default function AdminRequests() {
  const { data: session } = useSession();
  const [logs, setLogs] = useState<RequestLog[]>([]);
  const [tools, setTools] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [filters, setFilters] = useState<RequestLogFilters>({ page: 1, limit: 20 });
  const [pagination, setPagination] = useState<Pagination | null>(null);
  const [refreshing, setRefreshing] = useState(false);

  useEffect(() => {
    if (session?.user?.accessToken) {
      fetchLogs();
    }
  }, [session, filters]);

  const fetchLogs = async () => {
    if (!session?.user?.accessToken) return;

    try {
      setLoading(true);
      const response = await getRequestLogs(session.user.accessToken, filters);
      setLogs(response.requests);
      setPagination(response.pagination);

      // Accumulate unique tool names across page changes so the dropdown stays populated
      const incoming = response.requests.map((l) => l.tool_name);
      setTools((prev) => [...new Set([...prev, ...incoming])]);

      setError("");
    } catch (err) {
      setLogs([]);
      setError(err instanceof Error ? err.message : "Failed to fetch request logs");
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  const handleRefresh = () => {
    setRefreshing(true);
    fetchLogs();
  };

  const currentPage = pagination?.page ?? 1;
  const totalPages = pagination?.pages ?? 1;
  const totalCount = pagination?.total ?? logs.length;
  const pageSize = filters.limit ?? 20;
  const rangeStart = (currentPage - 1) * pageSize + 1;
  const rangeEnd = Math.min(currentPage * pageSize, totalCount);

  if (loading && !refreshing) {
    return (
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <div className="flex space-x-3">
            <Skeleton className="h-10 w-40" />
            <Skeleton className="h-10 w-32" />
          </div>
          <Skeleton className="h-9 w-9" />
        </div>

        <Card>
          <CardHeader>
            <Skeleton className="h-6 w-32" />
            <Skeleton className="h-4 w-48" />
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              {[1, 2, 3, 4, 5, 6, 7, 8].map((i) => (
                <div key={i} className="grid gap-4 items-center py-2.5" style={{ gridTemplateColumns: COL_TEMPLATE }}>
                  <Skeleton className="h-4 w-14" />
                  <Skeleton className="h-5 w-20 rounded-full" />
                  <Skeleton className="h-4 w-28" />
                  <Skeleton className="h-4 w-24" />
                  <Skeleton className="h-4 w-12" />
                  <Skeleton className="h-5 w-10 rounded-full" />
                  <Skeleton className="h-4 w-32" />
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {error && (
        <div className="bg-[rgb(var(--danger)/0.08)] border border-[rgb(var(--danger)/0.3)] text-[rgb(var(--danger))] px-4 py-3 rounded text-sm">
          {error}
        </div>
      )}

      {/* Filter Bar */}
      <div className="flex items-center justify-between">
        <div className="flex space-x-3">
          <Select
            value={filters.tool_name || "all"}
            onValueChange={(value) =>
              setFilters((prev) => ({
                ...prev,
                tool_name: value === "all" ? undefined : value,
                page: 1,
              }))
            }
          >
            <SelectTrigger className="w-40">
              <SelectValue placeholder="All Tools" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All Tools</SelectItem>
              {tools.map((tool) => (
                <SelectItem key={tool} value={tool}>
                  {tool}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>

          <Select
            value={filters.success === undefined ? "all" : filters.success.toString()}
            onValueChange={(value) =>
              setFilters((prev) => ({
                ...prev,
                success: value === "all" ? undefined : value === "true",
                page: 1,
              }))
            }
          >
            <SelectTrigger className="w-32">
              <SelectValue placeholder="Status" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All</SelectItem>
              <SelectItem value="true">Success</SelectItem>
              <SelectItem value="false">Failed</SelectItem>
            </SelectContent>
          </Select>
        </div>

        <div className="flex items-center gap-3">
          {pagination && (
            <span className="text-xs text-[rgb(var(--text-muted))]">
              {totalCount.toLocaleString()} total
            </span>
          )}
          <Button
            variant="outline"
            size="sm"
            onClick={handleRefresh}
            disabled={refreshing}
          >
            <RefreshCw className={`h-4 w-4 ${refreshing ? "animate-spin" : ""}`} />
          </Button>
        </div>
      </div>

      {/* Request Logs Table */}
      <Card>
        <CardHeader>
          <CardTitle>Request Logs</CardTitle>
          <CardDescription>
            {pagination
              ? `${totalCount.toLocaleString()} API calls across all users`
              : "Recent API requests and their status"}
          </CardDescription>
        </CardHeader>
        <CardContent>
          {logs.length === 0 ? (
            <p className="text-[rgb(var(--text-muted))] text-center py-8 text-sm">
              No request logs found
            </p>
          ) : (
            <div className="space-y-3">
              {/* Header */}
              <div className="grid gap-4 text-xs text-[rgb(var(--text-muted))] uppercase tracking-wide pb-2 border-b" style={{ gridTemplateColumns: COL_TEMPLATE }}>
                <div>Time</div>
                <div>Tool</div>
                <div>User</div>
                <div>Integration</div>
                <div>Duration</div>
                <div>Status</div>
                <div>Input</div>
              </div>

              {/* Rows */}
              <div className="divide-y">
                {logs.map((log) => (
                  <div
                    key={log.id}
                    className="grid gap-4 items-center text-sm py-2.5 hover:bg-[rgb(var(--muted)/0.4)] transition-colors rounded"
                    style={{ gridTemplateColumns: COL_TEMPLATE }}
                  >
                    <div
                      className="text-[rgb(var(--text-muted))] text-xs"
                      title={formatAbsoluteTime(log.created_at)}
                    >
                      {formatRelativeTime(log.created_at)}
                    </div>

                    <div>
                      <Badge variant="outline" className="text-xs font-mono">
                        {log.tool_name}
                      </Badge>
                    </div>

                    <div className="min-w-0">
                      {log.user_email === "Anonymous" ? (
                        <span className="italic text-[rgb(var(--text-muted))] text-xs">
                          Anonymous
                        </span>
                      ) : (
                        <div title={`${log.user_name} <${log.user_email}>`}>
                          <div className="font-medium text-xs truncate">{log.user_name}</div>
                          <div className="text-[rgb(var(--text-muted))] text-xs truncate">
                            {log.user_email}
                          </div>
                        </div>
                      )}
                    </div>

                    <div
                      className="text-[rgb(var(--text-muted))] text-xs truncate"
                      title={log.integration_name}
                    >
                      {log.integration_name}
                    </div>

                    <div className={`text-xs font-mono ${durationColor(log.duration_ms)}`}>
                      {formatDuration(log.duration_ms)}
                    </div>

                    <div>
                      <Badge
                        variant={log.success ? "default" : "destructive"}
                        className="text-xs"
                      >
                        {log.success ? "ok" : "error"}
                      </Badge>
                    </div>

                    <div
                      className="text-[rgb(var(--text-muted))] text-xs truncate"
                      title={log.input_summary}
                    >
                      {log.input_summary}
                    </div>
                  </div>
                ))}
              </div>

              {/* Pagination */}
              {pagination && totalPages > 1 && (
                <div className="flex items-center justify-between pt-4 border-t">
                  <p className="text-xs text-[rgb(var(--text-muted))]">
                    Showing {rangeStart}–{rangeEnd} of {totalCount.toLocaleString()}
                  </p>
                  <div className="flex items-center gap-2">
                    <Button
                      variant="outline"
                      size="sm"
                      disabled={currentPage <= 1}
                      onClick={() =>
                        setFilters((prev) => ({ ...prev, page: currentPage - 1 }))
                      }
                    >
                      <ChevronLeft className="h-4 w-4 mr-1" />
                      Previous
                    </Button>
                    <span className="text-xs text-[rgb(var(--text-muted))] min-w-[80px] text-center">
                      Page {currentPage} of {totalPages}
                    </span>
                    <Button
                      variant="outline"
                      size="sm"
                      disabled={currentPage >= totalPages}
                      onClick={() =>
                        setFilters((prev) => ({ ...prev, page: currentPage + 1 }))
                      }
                    >
                      Next
                      <ChevronRight className="h-4 w-4 ml-1" />
                    </Button>
                  </div>
                </div>
              )}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
