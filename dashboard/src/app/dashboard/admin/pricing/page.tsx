"use client";

import { useState, useEffect } from "react";
import { useSession } from "next-auth/react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { CheckCircle, AlertCircle } from "lucide-react";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { getAdminPricing, updateTierPricing, TierConfig, TierConfigUpdate } from "@/lib/api";

interface TierState {
  original: TierConfig;
  edited: TierConfigUpdate;
  isSaving: boolean;
  saveStatus: 'idle' | 'success' | 'error';
  errorMessage?: string;
}

function getTierColor(tier: string): string {
  switch (tier?.toLowerCase()) {
    case 'free': return 'bg-secondary text-secondary-foreground border-border';
    case 'pro': return 'bg-indigo-100 text-indigo-800 border-indigo-200';
    case 'enterprise': return 'bg-purple-100 text-purple-800 border-purple-200';
    default: return 'bg-secondary text-secondary-foreground border-border';
  }
}

function formatDate(dateString: string): string {
  return new Date(dateString).toLocaleDateString('en-US', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit'
  });
}

function validateTierConfig(updates: TierConfigUpdate): { isValid: boolean; errors: string[] } {
  const errors: string[] = [];
  
  if (updates.hourly_limit !== undefined) {
    if (updates.hourly_limit < 1 || updates.hourly_limit > 10000) {
      errors.push('Hourly limit must be between 1 and 10,000');
    }
  }
  
  if (updates.monthly_limit !== undefined && updates.monthly_limit !== null) {
    if (updates.monthly_limit < 1 || updates.monthly_limit > 1000000) {
      errors.push('Monthly limit must be between 1 and 1,000,000');
    }
  }
  
  if (updates.cost_per_1k_tokens !== undefined) {
    if (updates.cost_per_1k_tokens < 0.001 || updates.cost_per_1k_tokens > 1.0) {
      errors.push('Cost per 1k tokens must be between 0.001 and 1.0');
    }
  }
  
  if (updates.max_expiry_days !== undefined) {
    if (![30, 90, 180].includes(updates.max_expiry_days)) {
      errors.push('Max expiry days must be 30, 90, or 180');
    }
  }
  
  return { isValid: errors.length === 0, errors };
}

export default function PricingPage() {
  const { data: session } = useSession();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  
  const [tiers, setTiers] = useState<{
    free: TierState;
    pro: TierState;
    enterprise: TierState;
  } | null>(null);

  type TierName = 'free' | 'pro' | 'enterprise';

  // Fetch pricing data on mount
  useEffect(() => {
    if (session?.user?.accessToken) {
      fetchPricing();
    }
  }, [session?.user?.accessToken]);

  const fetchPricing = async () => {
    if (!session?.user?.accessToken) return;
    
    try {
      setLoading(true);
      const response = await getAdminPricing(session.user.accessToken);
      
      const tierStates: typeof tiers = {
        free: {
          original: response.tiers.free,
          edited: {},
          isSaving: false,
          saveStatus: 'idle'
        },
        pro: {
          original: response.tiers.pro,
          edited: {},
          isSaving: false,
          saveStatus: 'idle'
        },
        enterprise: {
          original: response.tiers.enterprise,
          edited: {},
          isSaving: false,
          saveStatus: 'idle'
        }
      };
      
      setTiers(tierStates);
      setError("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to fetch pricing data");
    } finally {
      setLoading(false);
    }
  };

  const updateTierField = (tierName: TierName, field: keyof TierConfigUpdate, value: any) => {
    if (!tiers) return;
    
    setTiers(prev => {
      if (!prev) return prev;
      return {
        ...prev,
        [tierName]: {
          ...prev[tierName],
          edited: {
            ...prev[tierName].edited,
            [field]: value
          },
          saveStatus: 'idle'
        }
      };
    });
  };

  const hasChanges = (tierState: TierState): boolean => {
    const { original, edited } = tierState;
    
    for (const [key, value] of Object.entries(edited)) {
      if (value !== undefined && value !== original[key as keyof TierConfig]) {
        return true;
      }
    }
    
    return false;
  };

  const saveTier = async (tierName: TierName) => {
    if (!tiers || !session?.user?.accessToken) return;
    
    const tierState = tiers[tierName];
    const validation = validateTierConfig(tierState.edited);
    
    if (!validation.isValid) {
      setTiers(prev => {
        if (!prev) return prev;
        return {
          ...prev,
          [tierName]: {
            ...prev[tierName],
            saveStatus: 'error',
            errorMessage: validation.errors.join(', ')
          }
        };
      });
      return;
    }
    
    try {
      // Set saving state
      setTiers(prev => {
        if (!prev) return prev;
        return {
          ...prev,
          [tierName]: {
            ...prev[tierName],
            isSaving: true,
            saveStatus: 'idle',
            errorMessage: undefined
          }
        };
      });
      
      const response = await updateTierPricing(
        session.user.accessToken,
        tierName,
        tierState.edited
      );
      
      if (response.success) {
        // Update original values and clear edited
        setTiers(prev => {
          if (!prev) return prev;
          return {
            ...prev,
            [tierName]: {
              original: response.config,
              edited: {},
              isSaving: false,
              saveStatus: 'success'
            }
          };
        });
        
        // Clear success message after 3 seconds
        setTimeout(() => {
          setTiers(prev => {
            if (!prev) return prev;
            return {
              ...prev,
              [tierName]: {
                ...prev[tierName],
                saveStatus: 'idle'
              }
            };
          });
        }, 3000);
      } else {
        throw new Error('Failed to update tier');
      }
    } catch (err) {
      setTiers(prev => {
        if (!prev) return prev;
        return {
          ...prev,
          [tierName]: {
            ...prev[tierName],
            isSaving: false,
            saveStatus: 'error',
            errorMessage: err instanceof Error ? err.message : 'Failed to save changes'
          }
        };
      });
    }
  };

  if (loading) {
    return (
      <div className="space-y-6">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Pricing & Limits</h1>
          <p className="text-muted-foreground">Configure rate limits and pricing per tier</p>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {[1, 2, 3].map((i) => (
            <Card key={i}>
              <CardHeader>
                <div className="h-6 w-24 bg-zinc-200 rounded animate-pulse"></div>
                <div className="h-4 w-32 bg-zinc-200 rounded animate-pulse"></div>
              </CardHeader>
              <CardContent>
                <div className="space-y-4">
                  {[1, 2, 3, 4].map((j) => (
                    <div key={j}>
                      <div className="h-4 w-20 mb-2 bg-zinc-200 rounded animate-pulse"></div>
                      <div className="h-10 w-full bg-zinc-200 rounded animate-pulse"></div>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="space-y-6">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Pricing & Limits</h1>
          <p className="text-muted-foreground">Configure rate limits and pricing per tier</p>
        </div>
        <div className="p-4 border border-red-200 bg-red-50 rounded-lg">
          <p className="text-red-800">{error}</p>
        </div>
      </div>
    );
  }

  if (!tiers) {
    return null;
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">Pricing & Limits</h1>
        <p className="text-muted-foreground">Configure rate limits and pricing per tier</p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {(['free', 'pro', 'enterprise'] as TierName[]).map((tierName) => {
          const tierState = tiers[tierName];
          const hasUnsavedChanges = hasChanges(tierState);
          const isUnlimited = tierState.edited.monthly_limit === null || 
            (tierState.edited.monthly_limit === undefined && tierState.original.monthly_limit === null);
          
          return (
            <Card key={tierName}>
              <CardHeader>
                <div className="flex items-center justify-between">
                  <Badge className={getTierColor(tierName)}>
                    {tierName.charAt(0).toUpperCase() + tierName.slice(1)}
                  </Badge>
                  {tierState.saveStatus === 'success' && (
                    <div className="flex items-center text-green-600 text-sm">
                      <CheckCircle className="w-4 h-4 mr-1" />
                      Saved
                    </div>
                  )}
                </div>
                <CardDescription className="text-sm">
                  {tierState.original.updated_by_email ? (
                    <>Updated by {tierState.original.updated_by_email} on {formatDate(tierState.original.updated_at)}</>
                  ) : (
                    <>Never modified</>
                  )}
                </CardDescription>
              </CardHeader>
              <CardContent>
                <div className="space-y-4">
                  {/* Hourly Limit */}
                  <div className="space-y-2">
                    <Label htmlFor={`${tierName}-hourly`}>Hourly Limit</Label>
                    <Input
                      id={`${tierName}-hourly`}
                      type="number"
                      min="1"
                      max="10000"
                      value={tierState.edited.hourly_limit ?? tierState.original.hourly_limit}
                      onChange={(e) => updateTierField(tierName, 'hourly_limit', parseInt(e.target.value) || 0)}
                    />
                  </div>

                  {/* Monthly Limit */}
                  <div className="space-y-2">
                    <Label htmlFor={`${tierName}-monthly`}>Monthly Limit</Label>
                    <div className="space-y-2">
                      <div className="flex items-center space-x-2">
                        <input
                          type="checkbox"
                          id={`${tierName}-unlimited`}
                          checked={isUnlimited}
                          onChange={(e) => 
                            updateTierField(tierName, 'monthly_limit', e.target.checked ? null : 1000)
                          }
                          className="w-4 h-4 text-primary border-gray-300 rounded focus:ring-indigo-500"
                        />
                        <Label htmlFor={`${tierName}-unlimited`} className="text-sm">Unlimited</Label>
                      </div>
                      {!isUnlimited && (
                        <Input
                          id={`${tierName}-monthly`}
                          type="number"
                          min="1"
                          max="1000000"
                          value={tierState.edited.monthly_limit ?? tierState.original.monthly_limit ?? ''}
                          onChange={(e) => updateTierField(tierName, 'monthly_limit', parseInt(e.target.value) || null)}
                          placeholder="Enter limit"
                        />
                      )}
                    </div>
                  </div>

                  {/* Cost per 1k tokens */}
                  <div className="space-y-2">
                    <Label htmlFor={`${tierName}-cost`}>Cost per 1k tokens ($)</Label>
                    <Input
                      id={`${tierName}-cost`}
                      type="number"
                      min="0.001"
                      max="1.0"
                      step="0.001"
                      value={tierState.edited.cost_per_1k_tokens ?? tierState.original.cost_per_1k_tokens}
                      onChange={(e) => updateTierField(tierName, 'cost_per_1k_tokens', parseFloat(e.target.value) || 0)}
                    />
                  </div>

                  {/* Max Expiry Days */}
                  <div className="space-y-2">
                    <Label htmlFor={`${tierName}-expiry`}>Max Expiry Days</Label>
                    <Select
                      value={String(tierState.edited.max_expiry_days ?? tierState.original.max_expiry_days)}
                      onValueChange={(value) => updateTierField(tierName, 'max_expiry_days', parseInt(value))}
                    >
                      <SelectTrigger>
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="30">30 days</SelectItem>
                        <SelectItem value="90">90 days</SelectItem>
                        <SelectItem value="180">180 days</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>

                  {/* Error Message */}
                  {tierState.saveStatus === 'error' && tierState.errorMessage && (
                    <div className="flex items-center text-red-600 text-sm">
                      <AlertCircle className="w-4 h-4 mr-1" />
                      {tierState.errorMessage}
                    </div>
                  )}

                  {/* Save Button */}
                  <Button
                    onClick={() => saveTier(tierName)}
                    disabled={!hasUnsavedChanges || tierState.isSaving}
                    className="w-full bg-indigo-600 hover:bg-indigo-700"
                  >
                    {tierState.isSaving ? 'Saving...' : 'Save'}
                  </Button>
                </div>
              </CardContent>
            </Card>
          );
        })}
      </div>
    </div>
  );
}