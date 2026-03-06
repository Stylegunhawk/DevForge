"use client";

import { useState, useEffect } from "react";
import { useSession } from "next-auth/react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Activity, Zap, DollarSign, ArrowRight } from "lucide-react";
import { getUserUsage, getUserKeys } from "@/lib/api";
import { useRouter } from "next/navigation";

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

interface ApiKey {
  id: string;
  name: string;
  integration_name: string;
  tier: string;
  last_used: string;
  is_active: boolean;
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
  if (successRate >= 95) return 'text-green-600';
  if (successRate >= 80) return 'text-yellow-600';
  return 'text-red-600';
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
    total_tokens: number;
    total_cost: number;
    total_requests: number;
  } | null>(null);
  const [apiKeys, setApiKeys] = useState<ApiKey[]>([]);

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
          <p className="text-zinc-500">Last 30 days</p>
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
                <div key={i} className="grid grid-cols-7 gap-4">
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
          <p className="text-zinc-500">Last 30 days</p>
        </div>

        <Card>
          <CardContent className="p-6">
            <div className="text-center text-red-600">
              <p className="font-medium">{error}</p>
              <p className="text-sm">Please try again later.</p>
            </div>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold">Usage</h1>
        <p className="text-zinc-500">Last 30 days</p>
      </div>

      {/* Stats Row */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <Card>
          <CardContent className="p-6">
            <div className="flex items-center space-x-2">
              <Activity className="h-4 w-4 text-muted-foreground" />
              <span className="text-sm font-medium">Total Requests</span>
            </div>
            <div className="text-2xl font-bold">{usageData?.total_requests || 0}</div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="p-6">
            <div className="flex items-center space-x-2">
              <Zap className="h-4 w-4 text-muted-foreground" />
              <span className="text-sm font-medium">Total Tokens</span>
            </div>
            <div className="text-2xl font-bold">{(usageData?.total_tokens || 0).toLocaleString()}</div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="p-6">
            <div className="flex items-center space-x-2">
              <DollarSign className="h-4 w-4 text-muted-foreground" />
              <span className="text-sm font-medium">Total Cost</span>
            </div>
            <div className="text-2xl font-bold">{formatCurrency(usageData?.total_cost || 0)}</div>
          </CardContent>
        </Card>
      </div>

      {/* Token Usage by Model */}
      <Card>
        <CardHeader>
          <CardTitle>Token Breakdown</CardTitle>
        </CardHeader>
        <CardContent>
          {usageData?.token_usage?.length > 0 ? (
            <div className="space-y-4">
              <div className="grid grid-cols-7 gap-4 text-xs text-zinc-500 uppercase tracking-wide">
                <div>Date</div>
                <div>Model</div>
                <div>Task</div>
                <div>Prompt Tokens</div>
                <div>Completion Tokens</div>
                <div>Total</div>
                <div>Cost</div>
              </div>
              {usageData.token_usage.map((usage, index) => (
                <div key={index} className="grid grid-cols-7 gap-4 text-sm">
                  <div>{formatDate(usage.date)}</div>
                  <div className="font-mono text-xs">{usage.model_name}</div>
                  <div>{usage.task_type}</div>
                  <div>{usage.total_prompt_tokens.toLocaleString()}</div>
                  <div>{usage.total_completion_tokens.toLocaleString()}</div>
                  <div>{usage.total_tokens.toLocaleString()}</div>
                  <div>{formatCurrency(usage.total_cost_usd)}</div>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-center text-muted-foreground py-8">
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
          {usageData?.tool_usage?.length > 0 ? (
            <div className="space-y-4">
              <div className="grid grid-cols-4 gap-4 text-xs text-zinc-500 uppercase tracking-wide">
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
            <p className="text-center text-muted-foreground py-8">
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
              <div className="grid grid-cols-5 gap-4 text-xs text-zinc-500 uppercase tracking-wide">
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
                  <div>{key.last_used ? formatDate(key.last_used) : 'Never'}</div>
                  <div>
                    <Badge variant={key.is_active ? 'default' : 'secondary'}>
                      {key.is_active ? 'Active' : 'Inactive'}
                    </Badge>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-center text-muted-foreground py-8">
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
