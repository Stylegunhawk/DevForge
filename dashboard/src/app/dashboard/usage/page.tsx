"use client";

import { useState, useEffect } from "react";
import { useSession } from "next-auth/react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Activity, Zap, DollarSign, ArrowRight, ChevronLeft, ChevronRight } from "lucide-react";
import { getUserUsage, getUserKeys, type ApiKey } from "@/lib/api";
import { useRouter } from "next/navigation";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell,
  Legend,
} from "recharts";

const TOOL_COLORS = ["#D97757", "#C8B286", "#8EA898", "#B291AD", "#D4B88E"];
const CALL_HISTORY_PAGE_SIZE = 10;
const TOKEN_BREAKDOWN_PAGE_SIZE = 10;

// Fixed widths for numeric columns; Model + Task share remaining space
const TOKEN_COL_TEMPLATE =
  "100px minmax(0,150px) minmax(0,1fr) 100px 130px 80px 70px";

interface DailyRequest {
  date: string;
  request_count: number;
}

function buildDailyData(
  dailyRequests: DailyRequest[]
): { name: string; requests: number }[] {
  const grouped: Record<string, number> = {};
  dailyRequests.forEach((d) => {
    const day = (d.date || "").substring(0, 10);
    grouped[day] = d.request_count;
  });
  const result = [];
  for (let i = 29; i >= 0; i--) {
    const d = new Date();
    d.setDate(d.getDate() - i);
    const key = d.toISOString().substring(0, 10);
    result.push({
      name: i % 7 === 0 ? d.toLocaleDateString("en-US", { month: "short", day: "numeric" }) : "",
      requests: grouped[key] || 0,
    });
  }
  return result;
}

interface TokenUsage {
  model_name: string;
  task_type: string;
  total_prompt_tokens: number;
  total_completion_tokens: number;
  total_tokens: number;
  total_cost_usd: number;
  request_count: number;
  date: string;
}

interface ToolUsage {
  tool_name: string;
  call_count: number;
  avg_duration_ms: number;
  success_count: number;
  error_count: number;
  success_rate: number;
}

interface RecentRequest {
  tool_name: string;
  success: boolean;
  duration_ms: number;
  created_at: string;
  input_summary: string | null;
}

function formatCurrency(amount: number): string {
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
  }).format(amount);
}

function formatDuration(ms: number): string {
  if (ms < 1000) return `${ms}ms`;
  return `${(ms / 1000).toFixed(1)}s`;
}

function formatDate(dateString: string): string {
  const date = new Date(dateString);
  return date.toLocaleDateString('en-US', { 
    month: 'short', 
    day: 'numeric', 
    year: 'numeric' 
  });
}

function getSuccessRateColor(successRate: number): string {
  if (successRate >= 95) return 'text-[rgb(var(--success))]';
  if (successRate >= 80) return 'text-yellow-600';
  return 'text-[rgb(var(--danger))]';
}

export default function UsagePage() {
  const { data: session } = useSession();
  const router = useRouter();

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [usageData, setUsageData] = useState<{
    user: any;
    period_days: number;
    token_usage: TokenUsage[];
    tool_usage: ToolUsage[];
    recent_requests: RecentRequest[];
    daily_requests: DailyRequest[];
    total_tokens: number;
    total_cost: number;
    total_requests: number;
  } | null>(null);
  const [apiKeys, setApiKeys] = useState<ApiKey[]>([]);
  const [callHistoryPage, setCallHistoryPage] = useState(1);
  const [tokenBreakdownPage, setTokenBreakdownPage] = useState(1);

  useEffect(() => {
    if (session?.user?.accessToken && session?.user?.id) {
      fetchData();
    }
  }, [session?.user?.accessToken, session?.user?.id]);

  const fetchData = async () => {
    if (!session?.user?.accessToken || !session?.user?.id) return;

    try {
      setLoading(true);
      
      const [usageResponse, keysResponse] = await Promise.all([
        getUserUsage(session.user.accessToken, session.user.id, 30),
        getUserKeys(session.user.accessToken)
      ]);

      setUsageData(usageResponse);
      setApiKeys(keysResponse);
      setCallHistoryPage(1);
      setTokenBreakdownPage(1);
      setError("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to fetch usage data");
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="space-y-6">
        <div>
          <h1 className="text-3xl font-bold">Usage</h1>
          <p className="text-[rgb(var(--text-muted))]">Last 30 days</p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {[1, 2, 3].map((i) => (
            <Card key={i}>
              <CardContent className="p-6">
                <Skeleton className="h-4 w-32 mb-2" />
                <Skeleton className="h-8 w-24" />
              </CardContent>
            </Card>
          ))}
        </div>

        <Card>
          <CardHeader>
            <Skeleton className="h-6 w-32" />
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              {[1, 2, 3].map((i) => (
                <div key={i} className="grid gap-4" style={{ gridTemplateColumns: "100px minmax(0,150px) minmax(0,1fr) 100px 130px 80px 70px" }}>
                  <Skeleton className="h-4 w-20" />
                  <Skeleton className="h-4 w-24" />
                  <Skeleton className="h-4 w-16" />
                  <Skeleton className="h-4 w-20" />
                  <Skeleton className="h-4 w-24" />
                  <Skeleton className="h-4 w-16" />
                  <Skeleton className="h-4 w-12" />
                </div>
              ))}
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <Skeleton className="h-6 w-32" />
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              {[1, 2, 3].map((i) => (
                <div key={i} className="grid grid-cols-4 gap-4">
                  <Skeleton className="h-4 w-24" />
                  <Skeleton className="h-4 w-16" />
                  <Skeleton className="h-4 w-20" />
                  <Skeleton className="h-4 w-16" />
                </div>
              ))}
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <Skeleton className="h-6 w-32" />
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              {[1, 2, 3].map((i) => (
                <div key={i} className="grid grid-cols-5 gap-4">
                  <Skeleton className="h-4 w-24" />
                  <Skeleton className="h-4 w-20" />
                  <Skeleton className="h-4 w-16" />
                  <Skeleton className="h-4 w-20" />
                  <Skeleton className="h-4 w-12" />
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      </div>
    );
  }

  if (error) {
    return (
      <div className="space-y-6">
        <div>
          <h1 className="text-3xl font-bold">Usage</h1>
          <p className="text-[rgb(var(--text-muted))]">Last 30 days</p>
        </div>

        <Card>
          <CardContent className="p-6">
            <div className="text-center text-[rgb(var(--danger))]">
              <p className="font-medium">{error}</p>
              <p className="text-sm">Please try again later.</p>
            </div>
          </CardContent>
        </Card>
      </div>
    );
  }

  // Call History — client-side pagination over recent_requests (backend caps the slice at ~100)
  const recentRequests = usageData?.recent_requests ?? [];
  const totalCallPages = Math.max(1, Math.ceil(recentRequests.length / CALL_HISTORY_PAGE_SIZE));
  const currentCallPage = Math.min(callHistoryPage, totalCallPages);
  const callRangeStart = (currentCallPage - 1) * CALL_HISTORY_PAGE_SIZE;
  const callRangeEnd = Math.min(callRangeStart + CALL_HISTORY_PAGE_SIZE, recentRequests.length);
  const pagedRecentRequests = recentRequests.slice(callRangeStart, callRangeEnd);

  // Token Breakdown — client-side pagination
  const tokenUsage = usageData?.token_usage ?? [];
  const totalTokenPages = Math.max(1, Math.ceil(tokenUsage.length / TOKEN_BREAKDOWN_PAGE_SIZE));
  const currentTokenPage = Math.min(tokenBreakdownPage, totalTokenPages);
  const tokenRangeStart = (currentTokenPage - 1) * TOKEN_BREAKDOWN_PAGE_SIZE;
  const tokenRangeEnd = Math.min(tokenRangeStart + TOKEN_BREAKDOWN_PAGE_SIZE, tokenUsage.length);
  const pagedTokenUsage = tokenUsage.slice(tokenRangeStart, tokenRangeEnd);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold">Usage</h1>
        <p className="text-[rgb(var(--text-muted))]">Last 30 days</p>
      </div>

      {/* Stats Row */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <Card>
          <CardContent className="p-6">
            <div className="flex items-center space-x-2">
              <Activity className="h-4 w-4 text-[rgb(var(--text-muted))]" />
              <span className="text-sm font-medium">Total Requests</span>
            </div>
            <div className="text-2xl font-bold">{usageData?.total_requests || 0}</div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="p-6">
            <div className="flex items-center space-x-2">
              <Zap className="h-4 w-4 text-[rgb(var(--text-muted))]" />
              <span className="text-sm font-medium">Total Tokens</span>
            </div>
            <div className="text-2xl font-bold">{(usageData?.total_tokens || 0).toLocaleString()}</div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="p-6">
            <div className="flex items-center space-x-2">
              <DollarSign className="h-4 w-4 text-[rgb(var(--text-muted))]" />
              <span className="text-sm font-medium">Total Cost</span>
            </div>
            <div className="text-2xl font-bold">{formatCurrency(usageData?.total_cost || 0)}</div>
          </CardContent>
        </Card>
      </div>

      {/* Charts */}
      {usageData && (
        <div className="grid grid-cols-2 gap-6">
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium">Daily Requests (30 days)</CardTitle>
            </CardHeader>
            <CardContent>
              <ResponsiveContainer width="100%" height={200}>
                <BarChart
                  data={buildDailyData(usageData.daily_requests || [])}
                  margin={{ top: 4, right: 4, bottom: 0, left: -20 }}
                >
                  <XAxis
                    dataKey="name"
                    tick={{ fontSize: 11 }}
                    tickLine={false}
                    axisLine={false}
                  />
                  <YAxis
                    tick={{ fontSize: 11 }}
                    tickLine={false}
                    axisLine={false}
                    allowDecimals={false}
                  />
                  <Tooltip
                    formatter={(v) => [v, "requests"]}
                    cursor={{ fill: "rgba(217,119,87,0.10)" }}
                  />
                  <Bar dataKey="requests" fill="#D97757" radius={[3, 3, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium">Tool Split</CardTitle>
            </CardHeader>
            <CardContent>
              {usageData.tool_usage?.length > 0 ? (
                <ResponsiveContainer width="100%" height={200}>
                  <PieChart>
                    <Pie
                      data={usageData.tool_usage.map((t: ToolUsage) => ({
                        name: t.tool_name,
                        value: t.call_count,
                      }))}
                      cx="50%"
                      cy="50%"
                      innerRadius={50}
                      outerRadius={75}
                      paddingAngle={3}
                      dataKey="value"
                    >
                      {usageData.tool_usage.map((_: ToolUsage, i: number) => (
                        <Cell
                          key={i}
                          fill={TOOL_COLORS[i % TOOL_COLORS.length]}
                        />
                      ))}
                    </Pie>
                    <Legend iconType="circle" iconSize={8} />
                    <Tooltip />
                  </PieChart>
                </ResponsiveContainer>
              ) : (
                <p className="text-center text-[rgb(var(--text-muted))] py-14 text-sm">
                  No tool usage yet
                </p>
              )}
            </CardContent>
          </Card>
        </div>
      )}

      {/* Call History — all tool calls from request_logs */}
      <Card>
        <CardHeader>
          <CardTitle>Call History</CardTitle>
          <CardDescription>Every API call in the last 30 days, newest first</CardDescription>
        </CardHeader>
        <CardContent>
          {recentRequests.length > 0 ? (
            <div className="space-y-3">
              <div className="grid grid-cols-4 gap-4 text-xs text-[rgb(var(--text-muted))] uppercase tracking-wide">
                <div>Time</div>
                <div>Tool</div>
                <div>Duration</div>
                <div>Status</div>
              </div>
              {pagedRecentRequests.map((req, i) => (
                <div key={callRangeStart + i} className="grid grid-cols-4 gap-4 text-sm items-center">
                  <div className="text-[rgb(var(--text-muted))] text-xs">
                    {new Date(req.created_at).toLocaleString("en-US", {
                      month: "short",
                      day: "numeric",
                      hour: "2-digit",
                      minute: "2-digit",
                    })}
                  </div>
                  <div className="font-medium">{req.tool_name}</div>
                  <div>{formatDuration(req.duration_ms)}</div>
                  <div>
                    <Badge variant={req.success ? "default" : "destructive"}>
                      {req.success ? "ok" : "error"}
                    </Badge>
                  </div>
                </div>
              ))}
              {recentRequests.length > CALL_HISTORY_PAGE_SIZE && (
                <div className="flex items-center justify-between pt-4 border-t">
                  <p className="text-xs text-[rgb(var(--text-muted))]">
                    Showing {callRangeStart + 1}–{callRangeEnd} of {recentRequests.length}
                  </p>
                  <div className="flex items-center gap-2">
                    <Button
                      variant="outline"
                      size="sm"
                      disabled={currentCallPage === 1}
                      onClick={() => setCallHistoryPage(currentCallPage - 1)}
                    >
                      <ChevronLeft className="h-4 w-4 mr-1" />
                      Previous
                    </Button>
                    <span className="text-xs text-[rgb(var(--text-muted))] min-w-[80px] text-center">
                      Page {currentCallPage} of {totalCallPages}
                    </span>
                    <Button
                      variant="outline"
                      size="sm"
                      disabled={currentCallPage === totalCallPages}
                      onClick={() => setCallHistoryPage(currentCallPage + 1)}
                    >
                      Next
                      <ChevronRight className="h-4 w-4 ml-1" />
                    </Button>
                  </div>
                </div>
              )}
            </div>
          ) : (
            <p className="text-center text-[rgb(var(--text-muted))] py-8">
              No calls in the last 30 days
            </p>
          )}
        </CardContent>
      </Card>

      {/* Token Usage by Model */}
      <Card>
        <CardHeader>
          <CardTitle>Token Breakdown</CardTitle>
        </CardHeader>
        <CardContent>
          {tokenUsage.length > 0 ? (
            <div className="space-y-3">
              <div className="grid gap-4 text-xs text-[rgb(var(--text-muted))] uppercase tracking-wide pb-2 border-b" style={{ gridTemplateColumns: TOKEN_COL_TEMPLATE }}>
                <div>Date</div>
                <div>Model</div>
                <div>Task</div>
                <div>Prompt Tokens</div>
                <div>Completion Tokens</div>
                <div>Total</div>
                <div>Cost</div>
              </div>
              {pagedTokenUsage.map((usage, index) => (
                <div key={tokenRangeStart + index} className="grid gap-4 text-sm items-center py-2 hover:bg-[rgb(var(--muted)/0.4)] transition-colors rounded" style={{ gridTemplateColumns: TOKEN_COL_TEMPLATE }}>
                  <div className="text-xs text-[rgb(var(--text-muted))]">{formatDate(usage.date)}</div>
                  <div className="font-mono text-xs truncate" title={usage.model_name}>{usage.model_name}</div>
                  <div className="text-xs truncate" title={usage.task_type}>{usage.task_type}</div>
                  <div className="text-xs">{usage.total_prompt_tokens.toLocaleString()}</div>
                  <div className="text-xs">{usage.total_completion_tokens.toLocaleString()}</div>
                  <div className="text-xs">{usage.total_tokens.toLocaleString()}</div>
                  <div className="text-xs">{formatCurrency(usage.total_cost_usd)}</div>
                </div>
              ))}
              {tokenUsage.length > TOKEN_BREAKDOWN_PAGE_SIZE && (
                <div className="flex items-center justify-between pt-4 border-t">
                  <p className="text-xs text-[rgb(var(--text-muted))]">
                    Showing {tokenRangeStart + 1}–{tokenRangeEnd} of {tokenUsage.length}
                  </p>
                  <div className="flex items-center gap-2">
                    <Button
                      variant="outline"
                      size="sm"
                      disabled={currentTokenPage === 1}
                      onClick={() => setTokenBreakdownPage(currentTokenPage - 1)}
                    >
                      <ChevronLeft className="h-4 w-4 mr-1" />
                      Previous
                    </Button>
                    <span className="text-xs text-[rgb(var(--text-muted))] min-w-[80px] text-center">
                      Page {currentTokenPage} of {totalTokenPages}
                    </span>
                    <Button
                      variant="outline"
                      size="sm"
                      disabled={currentTokenPage === totalTokenPages}
                      onClick={() => setTokenBreakdownPage(currentTokenPage + 1)}
                    >
                      Next
                      <ChevronRight className="h-4 w-4 ml-1" />
                    </Button>
                  </div>
                </div>
              )}
            </div>
          ) : (
            <p className="text-center text-[rgb(var(--text-muted))] py-8">
              No token usage in the last 30 days
            </p>
          )}
        </CardContent>
      </Card>

      {/* Tool Usage */}
      <Card>
        <CardHeader>
          <CardTitle>Tool Activity</CardTitle>
        </CardHeader>
        <CardContent>
          {usageData?.tool_usage && usageData.tool_usage.length > 0 ? (
            <div className="space-y-4">
              <div className="grid grid-cols-4 gap-4 text-xs text-[rgb(var(--text-muted))] uppercase tracking-wide">
                <div>Tool</div>
                <div>Calls</div>
                <div>Avg Duration</div>
                <div>Success Rate</div>
              </div>
              {usageData.tool_usage.map((tool) => (
                <div key={tool.tool_name} className="grid grid-cols-4 gap-4 text-sm">
                  <div className="font-medium">{tool.tool_name}</div>
                  <div>{tool.call_count}</div>
                  <div>{formatDuration(tool.avg_duration_ms)}</div>
                  <div className={getSuccessRateColor(tool.success_rate)}>
                    {tool.success_rate.toFixed(1)}%
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-center text-[rgb(var(--text-muted))] py-8">
              No tool usage in the last 30 days
            </p>
          )}
        </CardContent>
      </Card>

      {/* API Keys Section */}
      <Card>
        <CardHeader>
          <CardTitle>Your API Keys</CardTitle>
        </CardHeader>
        <CardContent>
          {apiKeys?.length > 0 ? (
            <div className="space-y-4">
              <div className="grid grid-cols-5 gap-4 text-xs text-[rgb(var(--text-muted))] uppercase tracking-wide">
                <div>Name</div>
                <div>Integration</div>
                <div>Tier</div>
                <div>Last Used</div>
                <div>Status</div>
              </div>
              {apiKeys.map((key) => (
                <div key={key.id} className="grid grid-cols-5 gap-4 text-sm">
                  <div className="font-medium">{key.name}</div>
                  <div>{key.integration_name}</div>
                  <div>{key.tier}</div>
                  <div>{key.last_used_at ? formatDate(key.last_used_at) : 'Never'}</div>
                  <div>
                    <Badge variant={key.is_active ? 'default' : 'secondary'}>
                      {key.is_active ? 'Active' : 'Inactive'}
                    </Badge>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-center text-[rgb(var(--text-muted))] py-8">
              No API keys found
            </p>
          )}
          <div className="mt-6 pt-4 border-t">
            <Button 
              variant="outline" 
              onClick={() => router.push('/dashboard/keys')}
              className="w-full"
            >
              Manage keys
              <ArrowRight className="h-4 w-4 ml-2" />
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
