"use client";

import { useState, useEffect } from "react";
import { useSession } from "next-auth/react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Activity, Zap, DollarSign, CheckCircle2, XCircle } from "lucide-react";
import { getUserUsage, getUserRequestLogs } from "@/lib/api";
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

function formatTokens(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`;
  return n.toString();
}

function formatCurrency(n: number): string {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    minimumFractionDigits: 2,
  }).format(n);
}

function formatTime(iso: string): string {
  return new Date(iso).toLocaleTimeString("en-US", {
    hour: "2-digit",
    minute: "2-digit",
  });
}

function buildBarData(tokenUsage: any[]): { name: string; requests: number }[] {
  const grouped: Record<string, number> = {};
  tokenUsage.forEach((u) => {
    const day = (u.date || "").substring(0, 10);
    grouped[day] = (grouped[day] || 0) + (u.request_count || 0);
  });
  const result = [];
  for (let i = 6; i >= 0; i--) {
    const d = new Date();
    d.setDate(d.getDate() - i);
    const key = d.toISOString().substring(0, 10);
    result.push({
      name: d.toLocaleDateString("en-US", { weekday: "short" }),
      requests: grouped[key] || 0,
    });
  }
  return result;
}

export default function OverviewPage() {
  const { data: session } = useSession();
  const [usageData, setUsageData] = useState<any>(null);
  const [activity, setActivity] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (session?.user?.accessToken && session?.user?.id) {
      load();
    }
  }, [session?.user?.accessToken, session?.user?.id]);

  async function load() {
    const [usageResult, logsResult] = await Promise.allSettled([
      getUserUsage(session!.user!.accessToken, session!.user!.id, 30),
      getUserRequestLogs(session!.user!.accessToken, {
        user_id: session!.user!.id,
        limit: 12,
      }),
    ]);
    if (usageResult.status === "fulfilled") setUsageData(usageResult.value);
    if (logsResult.status === "fulfilled")
      setActivity(logsResult.value.requests || []);
    setLoading(false);
  }

  const barData = usageData ? buildBarData(usageData.token_usage || []) : [];
  const donutData = (usageData?.tool_usage || []).map((t: any) => ({
    name: t.tool_name,
    value: t.call_count,
  }));

  if (loading) {
    return (
      <div className="p-6 space-y-6">
        <Skeleton className="h-8 w-40" />
        <div className="grid grid-cols-3 gap-4">
          {[0, 1, 2].map((i) => (
            <Card key={i}>
              <CardContent className="p-6">
                <Skeleton className="h-4 w-28 mb-3" />
                <Skeleton className="h-8 w-20" />
              </CardContent>
            </Card>
          ))}
        </div>
        <div className="grid grid-cols-2 gap-4">
          <Skeleton className="h-72" />
          <Skeleton className="h-72" />
        </div>
      </div>
    );
  }

  return (
    <div className="p-6 space-y-6">
      <div>
        <h1 className="text-3xl font-bold">Overview</h1>
        <p className="text-muted-foreground">Last 30 days</p>
      </div>

      {/* Stat cards */}
      <div className="grid grid-cols-3 gap-4">
        <Card>
          <CardContent className="p-6">
            <div className="flex items-center gap-2 text-sm text-muted-foreground mb-2">
              <Activity className="h-4 w-4" />
              Total Requests
            </div>
            <div className="text-3xl font-bold">
              {(usageData?.total_requests || 0).toLocaleString()}
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-6">
            <div className="flex items-center gap-2 text-sm text-muted-foreground mb-2">
              <Zap className="h-4 w-4" />
              Tokens Used
            </div>
            <div className="text-3xl font-bold">
              {formatTokens(usageData?.total_tokens || 0)}
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-6">
            <div className="flex items-center gap-2 text-sm text-muted-foreground mb-2">
              <DollarSign className="h-4 w-4" />
              Est. Cost
            </div>
            <div className="text-3xl font-bold">
              {formatCurrency(usageData?.total_cost || 0)}
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Charts + activity feed */}
      <div className="grid grid-cols-2 gap-4">
        {/* Left column: bar chart + donut */}
        <div className="space-y-4">
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium">
                Requests — last 7 days
              </CardTitle>
            </CardHeader>
            <CardContent>
              <ResponsiveContainer width="100%" height={180}>
                <BarChart data={barData} margin={{ top: 4, right: 4, bottom: 0, left: -20 }}>
                  <XAxis
                    dataKey="name"
                    tick={{ fontSize: 12 }}
                    tickLine={false}
                    axisLine={false}
                  />
                  <YAxis
                    tick={{ fontSize: 12 }}
                    tickLine={false}
                    axisLine={false}
                    allowDecimals={false}
                  />
                  <Tooltip
                    formatter={(v) => [v, "requests"]}
                    cursor={{ fill: "rgba(217,119,87,0.10)" }}
                  />
                  <Bar dataKey="requests" fill="#D97757" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium">Tool split</CardTitle>
            </CardHeader>
            <CardContent>
              {donutData.length > 0 ? (
                <ResponsiveContainer width="100%" height={170}>
                  <PieChart>
                    <Pie
                      data={donutData}
                      cx="50%"
                      cy="50%"
                      innerRadius={45}
                      outerRadius={68}
                      paddingAngle={3}
                      dataKey="value"
                    >
                      {donutData.map((_: any, i: number) => (
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
                <p className="text-center text-muted-foreground py-10 text-sm">
                  No tool usage yet
                </p>
              )}
            </CardContent>
          </Card>
        </div>

        {/* Right column: activity feed */}
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium">Recent activity</CardTitle>
          </CardHeader>
          <CardContent>
            {activity.length > 0 ? (
              <div className="space-y-3">
                {activity.map((req) => (
                  <div key={req.id} className="flex items-start gap-3 text-sm">
                    {req.success ? (
                      <CheckCircle2 className="h-4 w-4 text-green-500 mt-0.5 shrink-0" />
                    ) : (
                      <XCircle className="h-4 w-4 text-red-500 mt-0.5 shrink-0" />
                    )}
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center justify-between gap-2">
                        <span className="font-mono text-xs text-primary truncate">
                          {req.tool_name}
                        </span>
                        <span className="text-xs text-muted-foreground shrink-0">
                          {formatTime(req.created_at)}
                        </span>
                      </div>
                      <p className="text-xs text-muted-foreground truncate mt-0.5">
                        {req.input_summary || "—"}
                      </p>
                      <span className="text-xs text-muted-foreground">
                        {req.duration_ms}ms
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-center text-muted-foreground py-16 text-sm">
                No recent activity
              </p>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
