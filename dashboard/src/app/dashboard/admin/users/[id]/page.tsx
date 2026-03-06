"use client";

import { useState, useEffect } from "react";
import { useSession } from "next-auth/react";
import { useParams, useRouter } from "next/navigation";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { ArrowLeft, BarChart3, DollarSign, Zap, Clock, CheckCircle, XCircle, Settings2, X } from "lucide-react";
import { getUserUsage, getUserRequestLogs, RequestDetail, getAdminKeys, getKeyOverrides, updateKeyOverrides, ApiKey, KeyOverride, KeyOverrideUpdate } from "@/lib/api";

interface ToolUsage {
  tool_name: string;
  call_count: number;
  avg_duration_ms: number;
  success_count: number;
  error_count: number;
  success_rate: number;
  total_tokens?: number;
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

function formatRelativeTime(timestamp: string): string {
  const now = new Date();
  const time = new Date(timestamp);
  const diffMs = now.getTime() - time.getTime();
  const diffSeconds = Math.floor(diffMs / 1000);
  const diffMinutes = Math.floor(diffSeconds / 60);
  const diffHours = Math.floor(diffMinutes / 60);
  const diffDays = Math.floor(diffHours / 24);

  if (diffSeconds < 60) return "just now";
  if (diffMinutes < 60) return `${diffMinutes}m ago`;
  if (diffHours < 24) return `${diffHours}h ago`;
  return `${diffDays}d ago`;
}

export default function UserDetailPage() {
  const { data: session } = useSession();
  const params = useParams();
  const router = useRouter();
  const userId = params.id as string;

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [userUsage, setUserUsage] = useState<{
  success: boolean;
  user: any;
  total_requests: number;
  total_tokens: number;
  total_cost: number;
  tool_usage: ToolUsage[];
  token_usage: any[];
  period_days: number;
} | null>(null);
  const [userRequests, setUserRequests] = useState<RequestDetail[]>([]);
  const [userKeys, setUserKeys] = useState<ApiKey[]>([]);
  const [keyEffectiveLimits, setKeyEffectiveLimits] = useState<Record<string, { hourly: number; monthly: number | null }>>({});
  const [overrideDialogOpen, setOverrideDialogOpen] = useState(false);
  const [selectedKey, setSelectedKey] = useState<ApiKey | null>(null);
  const [keyOverride, setKeyOverride] = useState<KeyOverride | null>(null);
  const [overrideLoading, setOverrideLoading] = useState(false);
  const [overrideSaving, setOverrideSaving] = useState(false);
  const [overrideForm, setOverrideForm] = useState<KeyOverrideUpdate>({
    hourly_limit_override: null,
    monthly_limit_override: null
  });
  const [overrideSuccess, setOverrideSuccess] = useState(false);

  useEffect(() => {
    if (session?.user?.accessToken && userId) {
      fetchData();
    }
  }, [session?.user?.accessToken, userId]);

  const fetchData = async () => {
    if (!session?.user?.accessToken) return;

    try {
      setLoading(true);
      
      const [usageData, requestsData, keysData] = await Promise.all([
        getUserUsage(session.user.accessToken, userId, 30),
        getUserRequestLogs(session.user.accessToken, { user_id: userId, limit: 50 }),
        getAdminKeys(session.user.accessToken)
      ]);

      console.log('Usage data:', JSON.stringify(usageData, null, 2));
      console.log('Requests data:', JSON.stringify(requestsData, null, 2));
      console.log('Keys data:', JSON.stringify(keysData, null, 2));
      
      setUserUsage(usageData);
      setUserRequests(requestsData.requests);
      // Filter keys by user_id - handle different response structures
      console.log('Keys data structure:', typeof keysData, Array.isArray(keysData), keysData);
      let userKeys: ApiKey[] = [];
      
      if (Array.isArray(keysData)) {
        userKeys = keysData.filter((key: ApiKey) => key.user_id === userId);
      } else if (keysData && typeof keysData === 'object' && 'keys' in keysData) {
        userKeys = (keysData as { keys: ApiKey[] }).keys.filter((key: ApiKey) => key.user_id === userId);
      }
      
      setUserKeys(userKeys);
      
      // Fetch override data for all user keys
      const effectiveLimitsMap: Record<string, { hourly: number; monthly: number | null }> = {};
      await Promise.all(
        userKeys.map(async (key) => {
          try {
            const overrideData = await getKeyOverrides(session.user.accessToken, key.id);
            effectiveLimitsMap[key.id] = overrideData.effective_limits;
          } catch (err) {
            console.error(`Failed to fetch overrides for key ${key.id}:`, err);
            // Use tier defaults as fallback
            effectiveLimitsMap[key.id] = { hourly: 50, monthly: 500 }; // Free tier defaults
          }
        })
      );
      setKeyEffectiveLimits(effectiveLimitsMap);
      
      setError("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to fetch user details");
    } finally {
      setLoading(false);
    }
  };

  const openOverrideDialog = async (key: ApiKey) => {
    setSelectedKey(key);
    setOverrideDialogOpen(true);
    setOverrideLoading(true);
    setOverrideSuccess(false);
    
    try {
      if (!session?.user?.accessToken) return;
      
      const overrideData = await getKeyOverrides(session.user.accessToken, key.id);
      setKeyOverride(overrideData);
      setOverrideForm({
        hourly_limit_override: overrideData.overrides.hourly_limit_override,
        monthly_limit_override: overrideData.overrides.monthly_limit_override
      });
    } catch (err) {
      console.error('Failed to fetch key overrides:', err);
      // Set default values if API fails
      setOverrideForm({
        hourly_limit_override: null,
        monthly_limit_override: null
      });
    } finally {
      setOverrideLoading(false);
    }
  };

  const closeOverrideDialog = () => {
    setOverrideDialogOpen(false);
    setSelectedKey(null);
    setKeyOverride(null);
    setOverrideForm({
      hourly_limit_override: null,
      monthly_limit_override: null
    });
    setOverrideSuccess(false);
  };

  const saveOverride = async () => {
    if (!selectedKey || !session?.user?.accessToken) return;
    
    try {
      setOverrideSaving(true);
      
      // Validate inputs
      const updates: KeyOverrideUpdate = {
        hourly_limit_override: overrideForm.hourly_limit_override,
        monthly_limit_override: overrideForm.monthly_limit_override
      };
      
      const result = await updateKeyOverrides(session.user.accessToken, selectedKey.id, updates);
      
      if (result.success) {
        setOverrideSuccess(true);
        
        // Update the keyOverride with the new effective limits from the response
        if (result.effective_limits && selectedKey) {
          setKeyOverride(prev => prev ? {
            ...prev,
            effective_limits: result.effective_limits
          } : null);
          
          // Update the effective limits in the state
          setKeyEffectiveLimits(prev => ({
            ...prev,
            [selectedKey.id]: result.effective_limits
          }));
        }
        
        // Refresh keys data to get updated state
        await fetchData();
        
        // Close dialog after 1.5 seconds
        setTimeout(() => {
          closeOverrideDialog();
        }, 1500);
      }
    } catch (err) {
      console.error('Failed to save override:', err);
    } finally {
      setOverrideSaving(false);
    }
  };

  const formatLimits = (hourly: number, monthly: number | null): string => {
    return `${hourly}/hr • ${monthly || '∞'}/mo`;
  };

  const getKeyEffectiveLimits = (key: ApiKey): { hourly: number; monthly: number | null } => {
    // Return the effective limits from state if available, otherwise return tier defaults
    return keyEffectiveLimits[key.id] || { hourly: 50, monthly: 500 }; // Free tier defaults
  };

  const hasOverride = (key: ApiKey): boolean => {
    // Check if the key has any override data by comparing effective limits with tier defaults
    const effective = getKeyEffectiveLimits(key);
    const defaults = { hourly: 50, monthly: 500 }; // Free tier defaults
    
    return effective.hourly !== defaults.hourly || effective.monthly !== defaults.monthly;
  };

  if (loading) {
    return (
      <div className="space-y-6">
        <div className="flex items-center space-x-4">
          <Button variant="outline" onClick={() => router.back()}>
            <ArrowLeft className="h-4 w-4 mr-2" />
            ← Back to Users
          </Button>
        </div>

        <Card>
          <CardHeader>
            <CardTitle>User Details</CardTitle>
            <CardDescription>Loading user information...</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              <Skeleton className="h-4 w-32" />
              <Skeleton className="h-4 w-48" />
              <Skeleton className="h-4 w-64" />
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Recent Activity</CardTitle>
            <CardDescription>Loading user requests...</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              {[1, 2, 3, 4, 5].map((i) => (
                <div key={i} className="flex items-center space-x-4 p-4 border rounded">
                  <Skeleton className="h-4 w-4" />
                  <Skeleton className="h-4 w-24" />
                  <Skeleton className="h-4 w-16" />
                  <Skeleton className="h-4 w-16" />
                  <Skeleton className="h-4 w-20" />
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
        <div className="flex items-center space-x-4">
          <Button variant="outline" onClick={() => router.back()}>
            <ArrowLeft className="h-4 w-4 mr-2" />
            ← Back to Users
          </Button>
        </div>

        <Card>
          <CardContent className="p-6">
            <div className="text-center text-red-600">
              <p className="font-medium">{error}</p>
              <p className="text-sm">Please try again later.</p>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Usage Statistics</CardTitle>
            <CardDescription>Loading user information...</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              {!userUsage ? (
                <div className="space-y-4">
                  <Skeleton className="h-4 w-32" />
                  <Skeleton className="h-4 w-48" />
                  <Skeleton className="h-4 w-64" />
                </div>
              ) : (
                <>
                  <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
                    <div className="space-y-2">
                      <div className="flex items-center space-x-2">
                        <BarChart3 className="h-4 w-4 text-muted-foreground" />
                        <span className="text-sm font-medium">Total Requests</span>
                      </div>
                      <div className="text-2xl font-bold">{userUsage?.total_requests || 0}</div>
                    </div>
                    
                    <div className="space-y-2">
                      <div className="flex items-center space-x-2">
                        <Zap className="h-4 w-4 text-muted-foreground" />
                        <span className="text-sm font-medium">Total Tokens</span>
                      </div>
                      <div className="text-2xl font-bold">{(userUsage?.total_tokens || 0).toLocaleString()}</div>
                    </div>
                    
                    <div className="space-y-2">
                      <div className="flex items-center space-x-2">
                        <DollarSign className="h-4 w-4 text-muted-foreground" />
                        <span className="text-sm font-medium">Total Cost</span>
                      </div>
                      <div className="text-2xl font-bold">{formatCurrency(userUsage?.total_cost || 0)}</div>
                    </div>
                  </div>

                  <div className="mt-8">
                    <h3 className="text-lg font-semibold mb-4">Tool Breakdown</h3>
                    <div className="space-y-2">
                      {userUsage?.tool_usage?.map((tool: ToolUsage) => (
                        <div key={tool.tool_name} className="flex items-center justify-between p-3 border rounded">
                          <div className="flex items-center space-x-3">
                            <Badge variant="outline">{tool.tool_name}</Badge>
                            <span className="text-sm text-muted-foreground">
                              {tool.call_count} calls • {formatDuration(tool.avg_duration_ms)} avg • {tool.total_tokens ? tool.total_tokens.toLocaleString() : '0'} tokens • {tool.success_rate.toFixed(1)}% success
                            </span>
                          </div>
                          <div className="text-right">
                            <div className="text-sm text-muted-foreground">
                              {tool.success_rate.toFixed(1)}% success rate
                            </div>
                          </div>
                        </div>
                      )) || (
                        <p className="text-muted-foreground text-center py-8">
                          No tool usage data available
                        </p>
                      )}
                    </div>
                  </div>
                </>
              )}
            </div>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center space-x-4">
        <Button variant="outline" onClick={() => router.back()}>
          <ArrowLeft className="h-4 w-4 mr-2" />
          ← Back to Users
        </Button>
      </div>

      {userUsage?.user && (
        <Card>
          <CardContent className="p-6">
            <div className="flex items-center justify-between">
              <div>
                <h1 className="text-2xl font-bold">{userUsage.user.name}</h1>
                <p className="text-zinc-500">{userUsage.user.email}</p>
                <p className="text-sm text-muted-foreground">
                  Member since {new Date(userUsage.user.member_since).toLocaleDateString()}
                </p>
              </div>
              {userUsage.user.is_admin && (
                <Badge variant="default">Admin</Badge>
              )}
            </div>
          </CardContent>
        </Card>
      )}

      {userUsage && (
        <Card>
          <CardHeader>
            <CardTitle>Usage Statistics</CardTitle>
            <CardDescription>Token usage and activity for the last 30 days</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
              <div className="space-y-2">
                <div className="flex items-center space-x-2">
                  <BarChart3 className="h-4 w-4 text-muted-foreground" />
                  <span className="text-sm font-medium">Total Requests</span>
                </div>
                <div className="text-2xl font-bold">{userUsage?.total_requests || 0}</div>
              </div>
              
              <div className="space-y-2">
                <div className="flex items-center space-x-2">
                  <Zap className="h-4 w-4 text-muted-foreground" />
                  <span className="text-sm font-medium">Total Tokens</span>
                </div>
                <div className="text-2xl font-bold">{(userUsage?.total_tokens || 0).toLocaleString()}</div>
              </div>
              
              <div className="space-y-2">
                <div className="flex items-center space-x-2">
                  <DollarSign className="h-4 w-4 text-muted-foreground" />
                  <span className="text-sm font-medium">Total Cost</span>
                </div>
                <div className="text-2xl font-bold">{formatCurrency(userUsage?.total_cost || 0)}</div>
              </div>
            </div>

            <div className="mt-8">
              <h3 className="text-lg font-semibold mb-4">Tool Breakdown</h3>
              <div className="space-y-2">
                {userUsage?.tool_usage?.map((tool: ToolUsage) => (
                  <div key={tool.tool_name} className="flex items-center justify-between p-3 border rounded">
                    <div className="flex items-center space-x-3">
                      <Badge variant="outline">{tool.tool_name}</Badge>
                      <span className="text-sm text-muted-foreground">
                        {tool.call_count} calls • {formatDuration(tool.avg_duration_ms)} avg
                      </span>
                    </div>
                    <div className="text-right">
                      <div className="text-sm text-muted-foreground">
                        {tool.success_rate.toFixed(1)}% success rate
                      </div>
                      <div className="text-sm font-medium">
                        {tool.total_tokens ? tool.total_tokens.toLocaleString() : 'N/A'} tokens
                      </div>
                    </div>
                  </div>
                )) || (
                  <p className="text-muted-foreground text-center py-8">
                    No tool usage data available
                  </p>
                )}
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {userKeys.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle>API Keys & Limits</CardTitle>
            <CardDescription>Manage rate limit overrides for this user's API keys</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              <div className="grid grid-cols-5 gap-4 items-center text-xs text-zinc-500 uppercase tracking-wide py-2 border-b">
                <div>Key Name</div>
                <div>Integration</div>
                <div>Tier</div>
                <div>Effective Limits</div>
                <div>Override Status</div>
                <div>Actions</div>
              </div>
              <div className="space-y-2">
                {userKeys.map((key) => {
                  const effectiveLimits = getKeyEffectiveLimits(key);
                  const hasKeyOverride = hasOverride(key);
                  
                  return (
                    <div key={key.id} className="grid grid-cols-5 gap-4 items-center text-sm py-2 border-b">
                      <div className="font-medium">{key.name}</div>
                      <div className="text-muted-foreground">{key.integration_name}</div>
                      <div>
                        <Badge variant="outline" className={key.tier === 'free' ? 'border-zinc-300' : key.tier === 'pro' ? 'border-indigo-300' : 'border-purple-300'}>
                          {key.tier}
                        </Badge>
                      </div>
                      <div className={hasKeyOverride ? 'text-indigo-600 font-medium' : 'text-muted-foreground'}>
                        {formatLimits(effectiveLimits.hourly, effectiveLimits.monthly)}
                      </div>
                      <div>
                        {hasKeyOverride ? (
                          <Badge className="bg-indigo-100 text-indigo-800 border-indigo-200">
                            Custom Limits
                          </Badge>
                        ) : (
                          <Badge className="bg-zinc-100 text-zinc-800 border-zinc-200">
                            Tier Default
                          </Badge>
                        )}
                      </div>
                      <div>
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => openOverrideDialog(key)}
                          className="h-8 w-8 p-0"
                        >
                          <Settings2 className="h-4 w-4" />
                        </Button>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      <Card>
        <CardHeader>
          <CardTitle>Request History</CardTitle>
          <CardDescription>All API requests from this user</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            {userRequests?.length > 0 ? (
              <>
                <div className="grid grid-cols-6 gap-4 items-center text-xs text-zinc-500 uppercase tracking-wide py-2 border-b">
                  <div>Time</div>
                  <div>Tool</div>
                  <div>Tenant ID</div>
                  <div>Duration</div>
                  <div>Status</div>
                  <div>Input Summary</div>
                </div>
                <div className="space-y-2">
                  {userRequests.map((request) => (
                    <div key={request.id} className="grid grid-cols-6 gap-4 items-center text-sm py-2 border-b">
                      <div className="text-muted-foreground">
                        {formatRelativeTime(request.created_at)}
                      </div>
                      <div>
                        <Badge variant="outline">{request.tool_name}</Badge>
                      </div>
                      <div className="text-muted-foreground font-mono text-xs">
                        {request.tenant_id?.substring(0, 8)}...
                      </div>
                      <div className="text-muted-foreground">
                        {formatDuration(request.duration_ms)}
                      </div>
                      <div>
                        {request.success ? (
                          <CheckCircle className="h-4 w-4 text-green-600" />
                        ) : (
                          <XCircle className="h-4 w-4 text-red-600" />
                        )}
                      </div>
                      <div className="text-muted-foreground truncate max-w-[200px]" title={request.input_summary}>
                        {request.input_summary?.substring(0, 60)}{request.input_summary?.length > 60 ? '...' : ''}
                      </div>
                    </div>
                  ))}
                </div>
                {userRequests.length > 10 && (
                  <div className="flex items-center justify-between pt-4 border-t">
                    <p className="text-sm text-muted-foreground">
                      Showing 1-{Math.min(10, userRequests.length)} of {userRequests.length} requests
                    </p>
                    <div className="flex space-x-2">
                      <Button variant="outline" size="sm" disabled>
                        Previous
                      </Button>
                      <Button variant="outline" size="sm" disabled>
                        Next
                      </Button>
                    </div>
                  </div>
                )}
              </>
            ) : (
              <p className="text-center text-muted-foreground py-8">
                No requests yet
              </p>
            )}
          </div>
        </CardContent>
      </Card>

      {/* Override Dialog */}
      <Dialog open={overrideDialogOpen} onOpenChange={setOverrideDialogOpen}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>Limits for {selectedKey?.name}</DialogTitle>
            <DialogDescription>
              Tier: {selectedKey?.tier} • Defaults: {keyOverride ? formatLimits(keyOverride.tier_defaults.hourly_limit, keyOverride.tier_defaults.monthly_limit) : 'Loading...'}
            </DialogDescription>
          </DialogHeader>
          
          {overrideLoading ? (
            <div className="flex items-center justify-center py-8">
              <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-indigo-600"></div>
            </div>
          ) : (
            <div className="space-y-4">
              {overrideSuccess && (
                <div className="p-3 bg-green-50 border border-green-200 rounded-lg">
                  <p className="text-green-800 text-sm">Limits updated</p>
                </div>
              )}
              
              <div className="space-y-2">
                <Label htmlFor="hourly-override">Hourly Limit Override</Label>
                <div className="relative">
                  <Input
                    id="hourly-override"
                    type="number"
                    min="1"
                    max="10000"
                    placeholder={`Leave empty for tier default (${keyOverride?.tier_defaults.hourly_limit}/hr)`}
                    value={overrideForm.hourly_limit_override || ''}
                    onChange={(e) => setOverrideForm(prev => ({
                      ...prev,
                      hourly_limit_override: e.target.value ? parseInt(e.target.value) : null
                    }))}
                  />
                  {overrideForm.hourly_limit_override && (
                    <Button
                      variant="ghost"
                      size="sm"
                      className="absolute right-2 top-1/2 transform -translate-y-1/2 h-6 w-6 p-0"
                      onClick={() => setOverrideForm(prev => ({ ...prev, hourly_limit_override: null }))}
                    >
                      <X className="h-4 w-4" />
                    </Button>
                  )}
                </div>
              </div>
              
              <div className="space-y-2">
                <Label htmlFor="monthly-override">Monthly Limit Override</Label>
                <div className="relative">
                  <Input
                    id="monthly-override"
                    type="number"
                    min="1"
                    max="1000000"
                    placeholder={`Leave empty for tier default (${keyOverride?.tier_defaults.monthly_limit || '∞'}/mo)`}
                    value={overrideForm.monthly_limit_override || ''}
                    onChange={(e) => setOverrideForm(prev => ({
                      ...prev,
                      monthly_limit_override: e.target.value ? parseInt(e.target.value) : null
                    }))}
                  />
                  {overrideForm.monthly_limit_override && (
                    <Button
                      variant="ghost"
                      size="sm"
                      className="absolute right-2 top-1/2 transform -translate-y-1/2 h-6 w-6 p-0"
                      onClick={() => setOverrideForm(prev => ({ ...prev, monthly_limit_override: null }))}
                    >
                      <X className="h-4 w-4" />
                    </Button>
                  )}
                </div>
              </div>
              
              <div className="p-3 bg-zinc-50 border border-zinc-200 rounded-lg">
                <p className="text-zinc-700 text-sm">
                  Leaving a field empty will use the tier default.
                  Free tier defaults: 50/hr • 500/mo
                </p>
              </div>
              
              <div className="flex justify-end space-x-2">
                <Button variant="outline" onClick={closeOverrideDialog} disabled={overrideSaving}>
                  Cancel
                </Button>
                <Button 
                  onClick={saveOverride} 
                  disabled={overrideSaving}
                  className="bg-indigo-600 hover:bg-indigo-700"
                >
                  {overrideSaving ? 'Saving...' : 'Save Override'}
                </Button>
              </div>
            </div>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}
