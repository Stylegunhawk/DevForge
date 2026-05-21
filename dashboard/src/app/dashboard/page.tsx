"use client";

import { useState, useEffect } from "react";
import { useSession } from "next-auth/react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Badge } from "@/components/ui/badge";
import { Activity, Zap, DollarSign, CheckCircle2, XCircle, TrendingUp } from "lucide-react";
import { getUserUsage, getUserRequestLogs } from "@/lib/api";
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer,
  PieChart, Pie, Cell, Legend,
} from "recharts";

const CHART_COLORS = [
  "rgb(var(--chart-violet))",
  "rgb(var(--chart-cyan))",
  "rgb(var(--chart-emerald))",
  "rgb(var(--chart-rose))",
  "rgb(var(--chart-amber))",
];

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
  return new Date(iso).toLocaleTimeString("en-US", { hour: "2-digit", minute: "2-digit" });
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

function StatCard({
  icon: Icon,
  label,
  value,
  loading,
}: {
  icon: React.ElementType;
  label: string;
  value: string;
  loading: boolean;
}) {
  return (
    <Card>
      <CardContent className="p-5">
        <div className="flex items-center gap-2 text-[rgb(var(--text-muted))] mb-3">
          <Icon className="h-4 w-4" />
          <span className="text-xs font-medium uppercase tracking-wider">{label}</span>
        </div>
        {loading ? (
          <Skeleton className="h-8 w-24" />
        ) : (
          <div className="text-2xl font-bold text-[rgb(var(--text))]">{value}</div>
        )}
      </CardContent>
    </Card>
  );
}

const tooltipStyle = {
  backgroundColor: "rgb(var(--surface-2))",
  border: "1px solid rgb(var(--border))",
  borderRadius: "8px",
  color: "rgb(var(--text))",
  fontSize: "12px",
};

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
      getUserRequestLogs(session!.user!.accessToken, { user_id: session!.user!.id, limit: 12 }),
    ]);
    if (usageResult.status === "fulfilled") setUsageData(usageResult.value);
    if (logsResult.status === "fulfilled") setActivity(logsResult.value.requests || []);
    setLoading(false);
  }

  const barData = usageData ? buildBarData(usageData.token_usage || []) : [];
  const donutData = (usageData?.tool_usage || []).map((t: any) => ({
    name: t.tool_name,
    value: t.call_count,
  }));

  return (
    <div className="p-6 max-w-6xl mx-auto space-y-6">
      {/* Page header */}
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-bold text-[rgb(var(--text))]">Overview</h1>
          <p className="text-sm text-[rgb(var(--text-muted))] mt-0.5">Last 30 days</p>
        </div>
        {!loading && (
          <Badge variant="secondary" className="gap-1.5 text-xs">
            <TrendingUp className="h-3 w-3" />
            Live
          </Badge>
        )}
      </div>

      {/* Stat cards */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <StatCard
          icon={Activity}
          label="Total Requests"
          value={(usageData?.total_requests || 0).toLocaleString()}
          loading={loading}
        />
        <StatCard
          icon={Zap}
          label="Tokens Used"
          value={formatTokens(usageData?.total_tokens || 0)}
          loading={loading}
        />
        <StatCard
          icon={DollarSign}
          label="Est. Cost"
          value={formatCurrency(usageData?.total_cost || 0)}
          loading={loading}
        />
      </div>

      {/* Charts + activity */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Left: charts */}
        <div className="space-y-4">
          {/* Bar chart */}
          <Card>
            <CardHeader>
              <CardTitle>Requests — last 7 days</CardTitle>
            </CardHeader>
            <CardContent>
              {loading ? (
                <Skeleton className="h-44 w-full" />
              ) : (
                <ResponsiveContainer width="100%" height={176}>
                  <BarChart data={barData} margin={{ top: 4, right: 4, bottom: 0, left: -22 }}>
                    <XAxis
                      dataKey="name"
                      tick={{ fontSize: 11, fill: "rgb(var(--text-muted))" }}
                      tickLine={false}
                      axisLine={false}
                    />
                    <YAxis
                      tick={{ fontSize: 11, fill: "rgb(var(--text-muted))" }}
                      tickLine={false}
                      axisLine={false}
                      allowDecimals={false}
                    />
                    <Tooltip
                      contentStyle={tooltipStyle}
                      cursor={{ fill: "rgb(var(--accent)/0.08)" }}
                      formatter={(v) => [v, "requests"]}
                    />
                    <Bar dataKey="requests" fill="rgb(var(--chart-violet))" radius={[4, 4, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              )}
            </CardContent>
          </Card>

          {/* Tool split donut */}
          <Card>
            <CardHeader>
              <CardTitle>Tool usage split</CardTitle>
            </CardHeader>
            <CardContent>
              {loading ? (
                <Skeleton className="h-40 w-full" />
              ) : donutData.length > 0 ? (
                <ResponsiveContainer width="100%" height={160}>
                  <PieChart>
                    <Pie
                      data={donutData}
                      cx="50%"
                      cy="50%"
                      innerRadius={42}
                      outerRadius={62}
                      paddingAngle={3}
                      dataKey="value"
                    >
                      {donutData.map((_: any, i: number) => (
                        <Cell key={i} fill={CHART_COLORS[i % CHART_COLORS.length]} />
                      ))}
                    </Pie>
                    <Legend
                      iconType="circle"
                      iconSize={8}
                      wrapperStyle={{ fontSize: "12px", color: "rgb(var(--text-muted))" }}
                    />
                    <Tooltip contentStyle={tooltipStyle} />
                  </PieChart>
                </ResponsiveContainer>
              ) : (
                <p className="text-center text-sm text-[rgb(var(--text-muted))] py-10">
                  No tool usage yet
                </p>
              )}
            </CardContent>
          </Card>
        </div>

        {/* Right: activity feed */}
        <Card>
          <CardHeader>
            <CardTitle>Recent activity</CardTitle>
          </CardHeader>
          <CardContent>
            {loading ? (
              <div className="space-y-3">
                {Array.from({ length: 6 }).map((_, i) => (
                  <Skeleton key={i} className="h-10 w-full" />
                ))}
              </div>
            ) : activity.length > 0 ? (
              <div className="space-y-0.5">
                {activity.map((req) => (
                  <div
                    key={req.id}
                    className="flex items-start gap-3 px-2 py-2.5 rounded-lg hover:bg-[rgb(var(--surface-2))] transition-colors duration-100"
                  >
                    {req.success ? (
                      <CheckCircle2 className="h-4 w-4 text-[rgb(var(--success))] mt-0.5 shrink-0" />
                    ) : (
                      <XCircle className="h-4 w-4 text-[rgb(var(--danger))] mt-0.5 shrink-0" />
                    )}
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center justify-between gap-2">
                        <span className="font-mono text-xs text-[rgb(var(--accent-2))] truncate">
                          {req.tool_name}
                        </span>
                        <span className="text-[10px] text-[rgb(var(--text-muted))] shrink-0 tabular-nums">
                          {formatTime(req.created_at)}
                        </span>
                      </div>
                      <p className="text-xs text-[rgb(var(--text-muted))] truncate mt-0.5">
                        {req.input_summary || "—"}
                      </p>
                      <span className="text-[10px] text-[rgb(var(--text-muted))]">
                        {req.duration_ms}ms
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="flex flex-col items-center justify-center py-16 text-center">
                <Activity className="h-8 w-8 text-[rgb(var(--border-2))] mb-3" />
                <p className="text-sm text-[rgb(var(--text-muted))]">No recent activity</p>
                <p className="text-xs text-[rgb(var(--text-muted))] mt-1">
                  Make your first API call to see logs here
                </p>
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
