"use client";

import { useState, useEffect } from "react";
import { useSession } from "next-auth/react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Badge } from "@/components/ui/badge";
import { Users, Activity, Zap, DollarSign } from "lucide-react";
import { getAdminSummary, getToolStats, getAdminKeys, DashboardSummary, ToolStat, ApiKey } from "@/lib/api";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  Cell,
} from "recharts";

const TOOL_COLORS = ["#D97757", "#C8B286", "#8EA898", "#B291AD", "#D4B88E"];

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

function getSuccessRateColor(rate: number): string {
  if (rate >= 95) return 'bg-green-100 text-green-800 border-green-200';
  if (rate >= 80) return 'bg-yellow-100 text-yellow-800 border-yellow-200';
  return 'bg-red-100 text-red-800 border-red-200';
}

export default function AdminOverview() {
  const { data: session } = useSession();
  const [summary, setSummary] = useState<DashboardSummary | null>(null);
  const [toolStats, setToolStats] = useState<ToolStat[]>([]);
  const [keys, setKeys] = useState<ApiKey[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    if (session?.user?.accessToken) {
      fetchData();
    }
  }, [session]);

  const fetchData = async () => {
    if (!session?.user?.accessToken) return;

    try {
      setLoading(true);
      
      const [summaryData, toolsData, keysData] = await Promise.all([
        getAdminSummary(session.user.accessToken),
        getToolStats(session.user.accessToken),
        getAdminKeys(session.user.accessToken)
      ]);

      setSummary(summaryData.summary);
      setToolStats(toolsData.tool_stats);
      // Handle different response structures for keys
      let allKeys: ApiKey[] = [];
      if (Array.isArray(keysData)) {
        allKeys = keysData;
      } else if (keysData && typeof keysData === 'object' && 'keys' in keysData) {
        allKeys = (keysData as { keys: ApiKey[] }).keys;
      }
      setKeys(allKeys);
      setError("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to fetch admin data");
    } finally {
      setLoading(false);
    }
  };

  const getKeysWithOverrides = (): number => {
    // This would need to be determined from the API response
    // For now, we'll count keys that have override data
    // This is a placeholder - the actual implementation would check for override fields
    return 0; // Placeholder - will be updated when API provides override data
  };

  if (loading) {
    return (
      <div className="space-y-6">
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
          {[1, 2, 3, 4].map((i) => (
            <Card key={i}>
              <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <Skeleton className="h-4 w-6" />
                <Skeleton className="h-4 w-4" />
              </CardHeader>
              <CardContent>
                <Skeleton className="h-8 w-16 mb-1" />
                <Skeleton className="h-3 w-20" />
              </CardContent>
            </Card>
          ))}
        </div>
        
        <Card>
          <CardHeader>
            <Skeleton className="h-6 w-32" />
            <Skeleton className="h-4 w-48" />
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              {[1, 2, 3, 4, 5].map((i) => (
                <div key={i} className="flex items-center space-x-4">
                  <Skeleton className="h-4 w-24" />
                  <Skeleton className="h-4 w-16" />
                  <Skeleton className="h-4 w-20" />
                  <Skeleton className="h-4 w-16" />
                  <Skeleton className="h-4 w-16" />
                  <Skeleton className="h-4 w-16" />
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
      <div className="text-center py-12">
        <p className="text-red-600">{error}</p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Summary Cards */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Total Users</CardTitle>
            <Users className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{summary?.total_users || 0}</div>
            <p className="text-xs text-muted-foreground">
              {summary?.active_users_today || 0} active today
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Requests Today</CardTitle>
            <Activity className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{summary?.total_requests_today || 0}</div>
            <p className="text-xs text-muted-foreground">
              Avg: {formatDuration(summary?.avg_duration_today || 0)}
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Tokens Today</CardTitle>
            <Zap className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {(summary?.total_tokens_today || 0).toLocaleString()}
            </div>
            <p className="text-xs text-muted-foreground">
              Total tokens processed
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Cost Today</CardTitle>
            <DollarSign className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {formatCurrency(summary?.total_cost_today || 0)}
            </div>
            <p className="text-xs text-muted-foreground">
              Total API costs
            </p>
          </CardContent>
        </Card>
      </div>

      {/* Tool call volume chart */}
      {toolStats.length > 0 && (
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium">Tool Call Volume</CardTitle>
          </CardHeader>
          <CardContent>
            <ResponsiveContainer width="100%" height={180}>
              <BarChart
                data={toolStats.map((t) => ({
                  name: t.tool_name,
                  calls: t.total_calls,
                }))}
                layout="vertical"
                margin={{ top: 4, right: 16, bottom: 4, left: 80 }}
              >
                <XAxis
                  type="number"
                  tick={{ fontSize: 11 }}
                  tickLine={false}
                  axisLine={false}
                  allowDecimals={false}
                />
                <YAxis
                  type="category"
                  dataKey="name"
                  tick={{ fontSize: 11 }}
                  tickLine={false}
                  axisLine={false}
                  width={76}
                />
                <Tooltip
                  formatter={(v) => [v, "calls"]}
                  cursor={{ fill: "rgba(217,119,87,0.10)" }}
                />
                <Bar dataKey="calls" radius={[0, 4, 4, 0]}>
                  {toolStats.map((_t, i) => (
                    <Cell key={i} fill={TOOL_COLORS[i % TOOL_COLORS.length]} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>
      )}

      {/* Tool Stats Table */}
      <Card>
        <CardHeader>
          <CardTitle>Tool Statistics</CardTitle>
          <CardDescription>
            Performance metrics for all tools
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            {toolStats.length === 0 ? (
              <p className="text-muted-foreground text-center py-8">
                No tool statistics available
              </p>
            ) : (
              <div className="space-y-2">
                <div className="grid grid-cols-7 gap-4 text-sm font-medium text-muted-foreground pb-2 border-b">
                  <div>Tool</div>
                  <div className="text-right">Calls</div>
                  <div className="text-right">Avg Duration</div>
                  <div className="text-right">Success Rate</div>
                  <div className="text-right">Unique Users</div>
                  <div className="text-right">Tokens</div>
                  <div className="text-right">Cost</div>
                </div>
                
                {toolStats.map((tool) => (
                  <div key={tool.tool_name} className="grid grid-cols-7 gap-4 items-center text-sm py-2 border-b">
                    <div className="font-medium">{tool.tool_name}</div>
                    <div className="text-right">{tool.total_calls.toLocaleString()}</div>
                    <div className="text-right">{formatDuration(tool.avg_duration_ms)}</div>
                    <div className="text-right">
                      <Badge className={getSuccessRateColor(tool.success_rate)}>
                        {tool.success_rate.toFixed(1)}%
                      </Badge>
                    </div>
                    <div className="text-right">{tool.unique_users}</div>
                    <div className="text-right">{tool.total_tokens.toLocaleString()}</div>
                    <div className="text-right">{formatCurrency(tool.total_cost_usd)}</div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
