"use client";

import { useState, useEffect } from "react";
import { useSession } from "next-auth/react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { RefreshCw, CheckCircle, XCircle, Clock } from "lucide-react";
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

function formatDuration(ms: number): string {
  if (ms < 1000) return `${ms}ms`;
  return `${(ms / 1000).toFixed(1)}s`;
}

function truncateText(text: string, maxLength: number): string {
  if (text.length <= maxLength) return text;
  return text.substring(0, maxLength) + "...";
}

export default function AdminRequests() {
  const { data: session } = useSession();
  const [logs, setLogs] = useState<RequestLog[]>([]);
  const [tools, setTools] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [filters, setFilters] = useState<RequestLogFilters>({
    page: 1,
    limit: 20,
  });
  const [pagination, setPagination] = useState<any>(null);
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
      
      // Extract unique tool names for filter dropdown
      const uniqueTools = [...new Set(response.requests.map(log => log.tool_name))];
      setTools(uniqueTools);
      
      setError("");
    } catch (err) {
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

  const handlePageChange = (newPage: number) => {
    setFilters(prev => ({ ...prev, page: newPage }));
  };

  if (loading && !refreshing) {
    return (
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <div className="flex space-x-4">
            <Skeleton className="h-10 w-40" />
            <Skeleton className="h-10 w-32" />
            <Skeleton className="h-10 w-24" />
          </div>
          <Skeleton className="h-10 w-10" />
        </div>
        
        <Card>
          <CardHeader>
            <Skeleton className="h-6 w-32" />
            <Skeleton className="h-4 w-48" />
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              {[1, 2, 3, 4, 5, 6, 7, 8].map((i) => (
                <div key={i} className="flex items-center space-x-4 p-4 border rounded">
                  <Skeleton className="h-4 w-16" />
                  <Skeleton className="h-4 w-20" />
                  <Skeleton className="h-4 w-32" />
                  <Skeleton className="h-4 w-24" />
                  <Skeleton className="h-4 w-16" />
                  <Skeleton className="h-4 w-12" />
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
        <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded">
          {error}
        </div>
      )}

      {/* Filter Bar */}
      <div className="flex items-center justify-between">
        <div className="flex space-x-4">
          <Select
            value={filters.tool_name || "all"}
            onValueChange={(value) => setFilters(prev => ({ 
              ...prev, 
              tool_name: value === "all" ? undefined : value,
              page: 1 
            }))}
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
            onValueChange={(value) => setFilters(prev => ({ 
              ...prev, 
              success: value === "all" ? undefined : value === "true",
              page: 1 
            }))}
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

        <Button
          variant="outline"
          size="sm"
          onClick={handleRefresh}
          disabled={refreshing}
        >
          <RefreshCw className={`h-4 w-4 ${refreshing ? 'animate-spin' : ''}`} />
        </Button>
      </div>

      {/* Request Logs Table */}
      <Card>
        <CardHeader>
          <CardTitle>Request Logs</CardTitle>
          <CardDescription>
            Recent API requests and their status
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            {logs.length === 0 ? (
              <p className="text-muted-foreground text-center py-8">
                No request logs found
              </p>
            ) : (
              <>
                <div className="space-y-2">
                  <div className="grid grid-cols-7 gap-4 text-sm font-medium text-muted-foreground pb-2 border-b">
                    <div>Time</div>
                    <div>Tool</div>
                    <div>User</div>
                    <div>Tenant ID</div>
                    <div>Duration</div>
                    <div>Status</div>
                    <div>Input Summary</div>
                  </div>
                  
                  {logs.map((log) => (
                    <div key={log.id} className="grid grid-cols-7 gap-4 items-center text-sm py-2 border-b">
                      <div className="text-muted-foreground">
                        {formatRelativeTime(log.created_at)}
                      </div>
                      <div>
                        <Badge variant="outline">{log.tool_name}</Badge>
                      </div>
                      <div className="text-muted-foreground">
                        {log.user_email === "Anonymous" ? (
                          <span className="italic text-zinc-400">Anonymous</span>
                        ) : (
                          <span 
                            className="truncate max-w-[120px]" 
                            title={log.user_email}
                          >
                            {log.user_email.length > 20 ? `${log.user_email.substring(0, 20)}...` : log.user_email}
                          </span>
                        )}
                      </div>
                      <div className="text-muted-foreground font-mono text-xs">
                        {log.tenant_id.substring(0, 8)}...
                      </div>
                      <div className="text-muted-foreground">
                        {formatDuration(log.duration_ms)}
                      </div>
                      <div>
                        {log.success ? (
                          <CheckCircle className="h-4 w-4 text-green-600" />
                        ) : (
                          <XCircle className="h-4 w-4 text-red-600" />
                        )}
                      </div>
                      <div className="text-muted-foreground" title={log.input_summary}>
                        {truncateText(log.input_summary, 60)}
                      </div>
                    </div>
                  ))}
                </div>

                {/* Pagination */}
                {pagination && pagination.total_pages > 1 && (
                  <div className="flex items-center justify-between pt-4 border-t">
                    <div className="text-sm text-muted-foreground">
                      Page {pagination.current_page} of {pagination.total_pages}
                    </div>
                    <div className="flex space-x-2">
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => handlePageChange(pagination.current_page - 1)}
                        disabled={pagination.current_page <= 1}
                      >
                        Previous
                      </Button>
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => handlePageChange(pagination.current_page + 1)}
                        disabled={pagination.current_page >= pagination.total_pages}
                      >
                        Next
                      </Button>
                    </div>
                  </div>
                )}
              </>
            )}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
