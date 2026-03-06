"use client";

import { useState, useEffect } from "react";
import { useSession } from "next-auth/react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle, AlertDialogTrigger } from "@/components/ui/alert-dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { ApiKey, CreateKeyRequest, getUserKeys, createUserKey, revokeUserKey } from "@/lib/api";
import { Key, Plus, Copy, Trash2, CheckCircle, XCircle } from "lucide-react";

// Time formatting helper
function formatRelativeTime(timestamp: string | null): string {
  if (!timestamp) return "Never used";
  
  const now = new Date();
  const time = new Date(timestamp);
  const diffMs = now.getTime() - time.getTime();
  const diffSeconds = Math.floor(diffMs / 1000);
  const diffMinutes = Math.floor(diffSeconds / 60);
  const diffHours = Math.floor(diffMinutes / 60);
  const diffDays = Math.floor(diffHours / 24);

  if (diffSeconds < 60) return "just now";
  if (diffMinutes < 60) return `${diffMinutes} minute${diffMinutes > 1 ? 's' : ''} ago`;
  if (diffHours < 24) return `${diffHours} hour${diffHours > 1 ? 's' : ''} ago`;
  return `${diffDays} day${diffDays > 1 ? 's' : ''} ago`;
}

function getTierColor(tier: string): string {
  switch (tier?.toLowerCase()) {
    case 'free': return 'bg-zinc-100 text-zinc-800 border-zinc-200';
    case 'pro': return 'bg-indigo-100 text-indigo-800 border-indigo-200';
    case 'enterprise': return 'bg-purple-100 text-purple-800 border-purple-200';
    default: return 'bg-zinc-100 text-zinc-800 border-zinc-200';
  }
}

function getExpiryBadge(key: ApiKey): { text: string; className: string } | null {
  if (key.days_remaining === null) {
    return null; // No expiry
  }
  
  if (key.is_expired) {
    return {
      text: "Expired",
      className: "bg-red-100 text-red-800 border-red-200"
    };
  }
  
  const days = key.days_remaining;
  let className = "";
  
  if (days > 30) {
    className = "bg-zinc-100 text-zinc-800 border-zinc-200";
  } else if (days <= 30 && days > 7) {
    className = "bg-yellow-100 text-yellow-800 border-yellow-200";
  } else if (days <= 7 && days > 0) {
    className = "bg-orange-100 text-orange-800 border-orange-200";
  }
  
  return {
    text: `Expires in ${days} day${days !== 1 ? 's' : ''}`,
    className
  };
}

export default function KeysPage() {
  const { data: session } = useSession();
  const [keys, setKeys] = useState<ApiKey[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [isCreateDialogOpen, setIsCreateDialogOpen] = useState(false);
  const [createdKey, setCreatedKey] = useState<{ key: string; message: string } | null>(null);
  const [copied, setCopied] = useState(false);
  const [revokingKeyId, setRevokingKeyId] = useState<string | null>(null);
  
  // Form state
  const [formData, setFormData] = useState<CreateKeyRequest>({
    name: "",
    integration_name: "",
    tenant_id: "",
    tier: "free",
    scopes: [],
    expiry_duration: null
  });
  const [isCreating, setIsCreating] = useState(false);

  // Fetch keys on mount
  useEffect(() => {
    if (session?.user?.accessToken) {
      fetchKeys();
    }
  }, [session?.user?.accessToken]); // Only depend on the token

  const fetchKeys = async () => {
    if (!session?.user?.accessToken) {
      return;
    }
    
    try {
      setLoading(true);
      const userKeys = await getUserKeys(session.user.accessToken);
      setKeys(userKeys);
      setError("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to fetch API keys");
    } finally {
      setLoading(false);
    }
  };

  const handleCreateKey = async () => {
    if (!session?.user?.accessToken || !formData.name || !formData.integration_name || !formData.tenant_id) {
      return;
    }

    try {
      setIsCreating(true);
      const result = await createUserKey(session.user.accessToken, formData);
      setCreatedKey(result);
      setIsCreateDialogOpen(false);
      setFormData({ name: "", integration_name: "", tenant_id: "", tier: "free", scopes: [], expiry_duration: null });
      await fetchKeys(); // Refresh the list
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create API key");
    } finally {
      setIsCreating(false);
    }
  };

  const handleRevokeKey = async (keyId: string) => {
    if (!session?.user?.accessToken) return;

    try {
      setRevokingKeyId(keyId);
      await revokeUserKey(session.user.accessToken, keyId);
      // Optimistic update: remove key from list immediately
      setKeys(prev => prev.filter(key => key.id !== keyId));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to revoke API key");
      // Refresh list on error to restore state
      await fetchKeys();
    } finally {
      setRevokingKeyId(null);
    }
  };

  const copyToClipboard = async (text: string) => {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (err) {
      console.error("Failed to copy:", err);
    }
  };

  if (loading) {
    return (
      <div className="p-6">
        <div className="mb-6">
          <h1 className="text-3xl font-bold">API Keys</h1>
          <p className="text-muted-foreground">Manage your API keys and tokens</p>
        </div>
        
        <div className="space-y-4">
          {[1, 2, 3].map((i) => (
            <Card key={i}>
              <CardHeader>
                <Skeleton className="h-6 w-48" />
                <Skeleton className="h-4 w-32" />
              </CardHeader>
              <CardContent>
                <Skeleton className="h-20 w-full" />
              </CardContent>
            </Card>
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="p-6">
      {/* Header */}
      <div className="mb-6 flex justify-between items-center">
        <div>
          <h1 className="text-3xl font-bold">API Keys</h1>
          <p className="text-muted-foreground">Manage your API keys and tokens</p>
        </div>
        <Dialog open={isCreateDialogOpen} onOpenChange={setIsCreateDialogOpen}>
          <DialogTrigger asChild>
            <Button className="bg-indigo-600 hover:bg-indigo-700">
              <Plus className="w-4 h-4 mr-2" />
              Create new key
            </Button>
          </DialogTrigger>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Create API Key</DialogTitle>
              <DialogDescription>
                Generate a new API key for your integrations.
              </DialogDescription>
            </DialogHeader>
            <div className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="name">Key name</Label>
                <Input
                  id="name"
                  placeholder="e.g., My Cursor IDE"
                  value={formData.name}
                  onChange={(e) => setFormData(prev => ({ ...prev, name: e.target.value }))}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="integration">Integration name</Label>
                <Input
                  id="integration"
                  placeholder="e.g., cursor-ide"
                  value={formData.integration_name}
                  onChange={(e) => setFormData(prev => ({ ...prev, integration_name: e.target.value }))}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="tenant">Tenant ID</Label>
                <Input
                  id="tenant"
                  placeholder="e.g., my-project"
                  value={formData.tenant_id}
                  onChange={(e) => setFormData(prev => ({ ...prev, tenant_id: e.target.value }))}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="tier">Tier</Label>
                <select
                  id="tier"
                  className="w-full p-2 border rounded-md"
                  value={formData.tier}
                  onChange={(e) => setFormData(prev => ({ ...prev, tier: e.target.value }))}
                >
                  <option value="free">Free</option>
                  <option value="pro">Pro</option>
                  <option value="enterprise">Enterprise</option>
                </select>
              </div>
              <div className="space-y-2">
                <Label htmlFor="expiry">Expiry</Label>
                <Select
                  value={formData.expiry_duration || ""}
                  onValueChange={(value) => setFormData(prev => ({ 
                    ...prev, 
                    expiry_duration: value === "none" ? null : value as "30d" | "90d" | "180d"
                  }))}
                >
                  <SelectTrigger>
                    <SelectValue placeholder="Select expiry duration" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="none">No expiry</SelectItem>
                    <SelectItem value="30d">30 days</SelectItem>
                    <SelectItem value="90d">90 days</SelectItem>
                    <SelectItem value="180d">180 days / 6 months</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div className="flex justify-end space-x-2">
                <Button variant="outline" onClick={() => setIsCreateDialogOpen(false)}>
                  Cancel
                </Button>
                <Button 
                  onClick={handleCreateKey}
                  disabled={isCreating || !formData.name || !formData.integration_name || !formData.tenant_id}
                  className="bg-indigo-600 hover:bg-indigo-700"
                >
                  {isCreating ? "Creating..." : "Create key"}
                </Button>
              </div>
            </div>
          </DialogContent>
        </Dialog>
      </div>

      {/* Error */}
      {error && (
        <div className="mb-4 p-4 border border-red-200 bg-red-50 rounded-lg">
          <p className="text-red-800">{error}</p>
        </div>
      )}

      {/* Keys List */}
      {keys.length === 0 ? (
        <Card>
          <CardHeader className="text-center">
            <Key className="w-12 h-12 mx-auto text-muted-foreground mb-4" />
            <CardTitle>No API keys yet</CardTitle>
            <CardDescription>
              Create your first key to get started with the API
            </CardDescription>
          </CardHeader>
          <CardContent className="text-center">
            <Dialog open={isCreateDialogOpen} onOpenChange={setIsCreateDialogOpen}>
              <DialogTrigger asChild>
                <Button className="bg-indigo-600 hover:bg-indigo-700">
                  <Plus className="w-4 h-4 mr-2" />
                  Create your first key
                </Button>
              </DialogTrigger>
              <DialogContent>
                <DialogHeader>
                  <DialogTitle>Create API Key</DialogTitle>
                  <DialogDescription>
                    Generate a new API key for your integrations.
                  </DialogDescription>
                </DialogHeader>
                <div className="space-y-4">
                  <div className="space-y-2">
                    <Label htmlFor="name">Key name</Label>
                    <Input
                      id="name"
                      placeholder="e.g., My Cursor IDE"
                      value={formData.name}
                      onChange={(e) => setFormData(prev => ({ ...prev, name: e.target.value }))}
                    />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="integration">Integration name</Label>
                    <Input
                      id="integration"
                      placeholder="e.g., cursor-ide"
                      value={formData.integration_name}
                      onChange={(e) => setFormData(prev => ({ ...prev, integration_name: e.target.value }))}
                    />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="tenant">Tenant ID</Label>
                    <Input
                      id="tenant"
                      placeholder="e.g., my-project"
                      value={formData.tenant_id}
                      onChange={(e) => setFormData(prev => ({ ...prev, tenant_id: e.target.value }))}
                    />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="tier">Tier</Label>
                    <select
                      id="tier"
                      className="w-full p-2 border rounded-md"
                      value={formData.tier}
                      onChange={(e) => setFormData(prev => ({ ...prev, tier: e.target.value }))}
                    >
                      <option value="free">Free</option>
                      <option value="pro">Pro</option>
                      <option value="enterprise">Enterprise</option>
                    </select>
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="expiry">Expiry</Label>
                    <Select
                      value={formData.expiry_duration || ""}
                      onValueChange={(value) => setFormData(prev => ({ 
                        ...prev, 
                        expiry_duration: value === "none" ? null : value as "30d" | "90d" | "180d"
                      }))}
                    >
                      <SelectTrigger>
                        <SelectValue placeholder="Select expiry duration" />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="none">No expiry</SelectItem>
                        <SelectItem value="30d">30 days</SelectItem>
                        <SelectItem value="90d">90 days</SelectItem>
                        <SelectItem value="180d">180 days / 6 months</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                  <div className="flex justify-end space-x-2">
                    <Button variant="outline" onClick={() => setIsCreateDialogOpen(false)}>
                      Cancel
                    </Button>
                    <Button 
                      onClick={handleCreateKey}
                      disabled={isCreating || !formData.name || !formData.integration_name || !formData.tenant_id}
                      className="bg-indigo-600 hover:bg-indigo-700"
                    >
                      {isCreating ? "Creating..." : "Create key"}
                    </Button>
                  </div>
                </div>
              </DialogContent>
            </Dialog>
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-4">
          {keys.map((key) => (
            <Card key={key.id}>
              <CardHeader>
                <div className="flex justify-between items-start">
                  <div>
                    <CardTitle className="text-lg">{key.name}</CardTitle>
                    <CardDescription className="text-zinc-500">
                      {key.integration_name}
                    </CardDescription>
                  </div>
                  <div className="flex space-x-2">
                    <Badge className={getTierColor(key.tier)}>
                      {key.tier}
                    </Badge>
                    <Badge variant={key.is_active ? "default" : "secondary"} className={key.is_active ? "bg-green-100 text-green-800 border-green-200" : "bg-red-100 text-red-800 border-red-200"}>
                      {key.is_active ? (
                        <><CheckCircle className="w-3 h-3 mr-1" />Active</>
                      ) : (
                        <><XCircle className="w-3 h-3 mr-1" />Inactive</>
                      )}
                    </Badge>
                    {getExpiryBadge(key) && (
                      <Badge className={getExpiryBadge(key)!.className}>
                        {getExpiryBadge(key)!.text}
                      </Badge>
                    )}
                  </div>
                </div>
              </CardHeader>
              <CardContent>
                <div className="flex justify-between items-center">
                  <div className="text-sm text-muted-foreground">
                    <div>Last used: {formatRelativeTime(key.last_used_at)}</div>
                    <div>Created: {formatRelativeTime(key.created_at)}</div>
                  </div>
                  <AlertDialog>
                    <AlertDialogTrigger asChild>
                      <Button variant="outline" className="text-red-600 border-red-200 hover:bg-red-50" disabled={revokingKeyId === key.id}>
                        <Trash2 className="w-4 h-4 mr-2" />
                        {revokingKeyId === key.id ? "Revoking..." : "Revoke"}
                      </Button>
                    </AlertDialogTrigger>
                    <AlertDialogContent>
                      <AlertDialogHeader>
                        <AlertDialogTitle>Are you sure?</AlertDialogTitle>
                        <AlertDialogDescription>
                          This action cannot be undone. This will permanently delete the API key "{key.name}".
                        </AlertDialogDescription>
                      </AlertDialogHeader>
                      <AlertDialogFooter>
                        <AlertDialogCancel>Cancel</AlertDialogCancel>
                        <AlertDialogAction 
                          onClick={() => handleRevokeKey(key.id)}
                          className="bg-red-600 hover:bg-red-700"
                        >
                          Revoke Key
                        </AlertDialogAction>
                      </AlertDialogFooter>
                    </AlertDialogContent>
                  </AlertDialog>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      {/* Created Key Dialog */}
      {createdKey && (
        <Dialog open={true} onOpenChange={(open) => {
          if (!open) setCreatedKey(null);
        }}>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>API Key Created Successfully!</DialogTitle>
              <DialogDescription>
                Your API key has been generated. Make sure to copy it now as it won't be shown again.
              </DialogDescription>
            </DialogHeader>
            <div className="space-y-4">
              <div className="p-4 bg-green-50 border border-green-200 rounded-lg">
                <p className="text-green-800 text-sm">{createdKey.message}</p>
              </div>
              <div className="space-y-2">
                <Label>Your API Key</Label>
                <div className="flex space-x-2">
                  <div className="flex-1 p-3 bg-zinc-100 border rounded-md font-mono text-sm break-all">
                    {createdKey.key}
                  </div>
                  <Button 
                    variant="outline" 
                    onClick={() => copyToClipboard(createdKey.key)}
                    className="flex-shrink-0"
                  >
                    {copied ? <CheckCircle className="w-4 h-4" /> : <Copy className="w-4 h-4" />}
                  </Button>
                </div>
              </div>
              <div className="p-3 bg-yellow-50 border border-yellow-200 rounded-lg">
                <p className="text-yellow-800 text-sm">
                  ⚠️ This key will never be shown again. Store it securely.
                </p>
              </div>
              <Button onClick={() => setCreatedKey(null)} className="w-full">
                Close
              </Button>
            </div>
          </DialogContent>
        </Dialog>
      )}
    </div>
  );
}
