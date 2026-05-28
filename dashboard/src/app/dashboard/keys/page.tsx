"use client";

import { useState, useEffect } from "react";
import { useSession } from "next-auth/react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle, DialogTrigger,
} from "@/components/ui/dialog";
import {
  AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent,
  AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle, AlertDialogTrigger,
} from "@/components/ui/alert-dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { ApiKey, CreateKeyRequest, getUserKeys, createUserKey, revokeUserKey } from "@/lib/api";
import { Key, Plus, Copy, Trash2, CheckCircle, XCircle, Clock } from "lucide-react";
import { cn } from "@/lib/utils";

function formatRelativeTime(timestamp: string | null): string {
  if (!timestamp) return "Never";
  const diffMs = Date.now() - new Date(timestamp).getTime();
  const diffSecs = Math.floor(diffMs / 1000);
  const diffMins = Math.floor(diffSecs / 60);
  const diffHrs = Math.floor(diffMins / 60);
  const diffDays = Math.floor(diffHrs / 24);
  if (diffSecs < 60) return "just now";
  if (diffMins < 60) return `${diffMins}m ago`;
  if (diffHrs < 24) return `${diffHrs}h ago`;
  return `${diffDays}d ago`;
}

function tierVariant(tier: string): "default" | "warning" | "secondary" {
  if (tier?.toLowerCase() === "pro") return "warning";
  if (tier?.toLowerCase() === "enterprise") return "default";
  return "secondary";
}

function expiryBadge(key: ApiKey): { text: string; variant: "destructive" | "warning" | "secondary" | "outline" } | null {
  if (key.days_remaining === null) return null;
  if (key.is_expired) return { text: "Expired", variant: "destructive" };
  const d = key.days_remaining;
  if (d <= 7) return { text: `${d}d left`, variant: "destructive" };
  if (d <= 30) return { text: `${d}d left`, variant: "warning" };
  return { text: `${d}d left`, variant: "outline" };
}

function CreateKeyForm({
  formData,
  setFormData,
  onSubmit,
  isCreating,
  onCancel,
}: {
  formData: CreateKeyRequest;
  setFormData: (v: CreateKeyRequest) => void;
  onSubmit: () => void;
  isCreating: boolean;
  onCancel: () => void;
}) {
  const update = (patch: Partial<CreateKeyRequest>) =>
    setFormData({ ...formData, ...patch });

  return (
    <div className="space-y-4">
      <div className="space-y-1.5">
        <Label htmlFor="name">Key name</Label>
        <Input
          id="name"
          placeholder="e.g., Cursor IDE"
          value={formData.name}
          onChange={(e) => update({ name: e.target.value })}
        />
      </div>
      <div className="space-y-1.5">
        <Label htmlFor="integration">Integration</Label>
        <Input
          id="integration"
          placeholder="e.g., cursor-ide"
          value={formData.integration_name}
          onChange={(e) => update({ integration_name: e.target.value })}
        />
      </div>
      <div className="space-y-1.5">
        <Label htmlFor="tenant">Tenant ID</Label>
        <Input
          id="tenant"
          placeholder="e.g., my-project"
          value={formData.tenant_id}
          onChange={(e) => update({ tenant_id: e.target.value })}
        />
      </div>
      <div className="grid grid-cols-2 gap-3">
        <div className="space-y-1.5">
          <Label htmlFor="tier">Tier</Label>
          <Select value={formData.tier} onValueChange={(v) => update({ tier: v })}>
            <SelectTrigger id="tier">
              <SelectValue placeholder="Tier" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="free">Free</SelectItem>
              <SelectItem value="pro">Pro</SelectItem>
              <SelectItem value="enterprise">Enterprise</SelectItem>
            </SelectContent>
          </Select>
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="expiry">Expiry</Label>
          <Select
            value={formData.expiry_duration || "none"}
            onValueChange={(v) =>
              update({ expiry_duration: v === "none" ? null : (v as "30d" | "90d" | "180d") })
            }
          >
            <SelectTrigger id="expiry">
              <SelectValue placeholder="Expiry" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="none">No expiry</SelectItem>
              <SelectItem value="30d">30 days</SelectItem>
              <SelectItem value="90d">90 days</SelectItem>
              <SelectItem value="180d">6 months</SelectItem>
            </SelectContent>
          </Select>
        </div>
      </div>
      <div className="flex justify-end gap-2 pt-1">
        <Button variant="outline" onClick={onCancel}>Cancel</Button>
        <Button
          onClick={onSubmit}
          disabled={isCreating || !formData.name || !formData.integration_name || !formData.tenant_id}
        >
          {isCreating ? "Creating…" : "Create key"}
        </Button>
      </div>
    </div>
  );
}

const EMPTY_FORM: CreateKeyRequest = {
  name: "", integration_name: "", tenant_id: "", tier: "free", scopes: [], expiry_duration: null,
};

export default function KeysPage() {
  const { data: session } = useSession();
  const [keys, setKeys] = useState<ApiKey[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [dialogOpen, setDialogOpen] = useState(false);
  const [createdKey, setCreatedKey] = useState<{ key: string; message: string } | null>(null);
  const [copied, setCopied] = useState(false);
  const [revokingId, setRevokingId] = useState<string | null>(null);
  const [formData, setFormData] = useState<CreateKeyRequest>(EMPTY_FORM);
  const [isCreating, setIsCreating] = useState(false);

  useEffect(() => {
    if (session?.user?.accessToken) fetchKeys();
  }, [session?.user?.accessToken]);

  const fetchKeys = async () => {
    if (!session?.user?.accessToken) return;
    try {
      setLoading(true);
      setKeys(await getUserKeys(session.user.accessToken));
      setError("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to fetch keys");
    } finally {
      setLoading(false);
    }
  };

  const handleCreate = async () => {
    if (!session?.user?.accessToken) return;
    try {
      setIsCreating(true);
      const result = await createUserKey(session.user.accessToken, formData);
      setCreatedKey(result);
      setDialogOpen(false);
      setFormData(EMPTY_FORM);
      await fetchKeys();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create key");
    } finally {
      setIsCreating(false);
    }
  };

  const handleRevoke = async (keyId: string) => {
    if (!session?.user?.accessToken) return;
    try {
      setRevokingId(keyId);
      await revokeUserKey(session.user.accessToken, keyId);
      setKeys((prev) => prev.filter((k) => k.id !== keyId));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to revoke key");
      await fetchKeys();
    } finally {
      setRevokingId(null);
    }
  };

  const copyToClipboard = async (text: string) => {
    await navigator.clipboard.writeText(text).catch(() => {});
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const activeCount = keys.filter((k) => k.is_active).length;
  const expiredCount = keys.filter((k) => k.is_expired).length;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">API Keys</h1>
          <p className="text-[rgb(var(--text-muted))] mt-1">
            Manage access keys for your integrations
          </p>
        </div>
        <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
          <DialogTrigger asChild>
            <Button>
              <Plus className="h-4 w-4 mr-1.5" />
              New key
            </Button>
          </DialogTrigger>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Create API Key</DialogTitle>
              <DialogDescription>Generate a new key for your integration.</DialogDescription>
            </DialogHeader>
            <CreateKeyForm
              formData={formData}
              setFormData={setFormData}
              onSubmit={handleCreate}
              isCreating={isCreating}
              onCancel={() => setDialogOpen(false)}
            />
          </DialogContent>
        </Dialog>
      </div>

      {/* Error */}
      {error && (
        <div className="rounded-lg border border-[rgb(var(--danger)/0.3)] bg-[rgb(var(--danger)/0.08)] px-4 py-3 text-sm text-[rgb(var(--danger))]">
          {error}
        </div>
      )}

      {/* Key list */}
      {loading ? (
        <div className="space-y-3">
          {[1, 2, 3].map((i) => (
            <Skeleton key={i} className="h-28 w-full rounded-xl" />
          ))}
        </div>
      ) : keys.length === 0 ? (
        <Card>
          <CardContent className="py-20">
            <div className="flex flex-col items-center text-center gap-4">
              <div className="rounded-2xl border border-[rgb(var(--border-2))] bg-[rgb(var(--surface-2))] p-5">
                <Key className="h-7 w-7 text-[rgb(var(--text-muted))]" />
              </div>
              <div>
                <p className="font-semibold text-[rgb(var(--text))]">No API keys yet</p>
                <p className="text-sm text-[rgb(var(--text-muted))] mt-1">
                  Create your first key to start making API requests
                </p>
              </div>
              <Button onClick={() => setDialogOpen(true)}>
                <Plus className="h-4 w-4 mr-1.5" />
                Create first key
              </Button>
            </div>
          </CardContent>
        </Card>
      ) : (
        <>
          {/* Summary strip */}
          <div className="flex items-center gap-4 text-sm text-[rgb(var(--text-muted))]">
            <span>{keys.length} {keys.length === 1 ? "key" : "keys"}</span>
            <span className="text-[rgb(var(--border-2))]">·</span>
            <span className="text-[rgb(var(--success))]">{activeCount} active</span>
            {expiredCount > 0 && (
              <>
                <span className="text-[rgb(var(--border-2))]">·</span>
                <span className="text-[rgb(var(--danger))]">{expiredCount} expired</span>
              </>
            )}
          </div>

          <div className="space-y-3">
            {keys.map((key) => {
              const expiry = expiryBadge(key);
              return (
                <Card
                  key={key.id}
                  className={cn(
                    "transition-all duration-150 border-l-[3px] hover:shadow-sm",
                    key.is_active
                      ? "border-l-[rgb(var(--success))]"
                      : "border-l-[rgb(var(--danger))] opacity-70"
                  )}
                >
                  <CardContent className="p-5">
                    {/* Top row: icon + name + badges + delete */}
                    <div className="flex items-start justify-between gap-4">
                      <div className="flex items-center gap-3 min-w-0 flex-1">
                        <div className="shrink-0 rounded-lg bg-[rgb(var(--accent-subtle))] p-2.5">
                          <Key className="h-4 w-4 text-[rgb(var(--accent))]" />
                        </div>
                        <div className="min-w-0 flex-1">
                          <div className="flex items-center gap-2 flex-wrap">
                            <span className="font-semibold text-[rgb(var(--text))]">{key.name}</span>
                            <Badge variant={tierVariant(key.tier)} className="text-xs capitalize">{key.tier}</Badge>
                            {key.is_active ? (
                              <Badge variant="success" className="text-xs">
                                <CheckCircle className="h-3 w-3 mr-1" />Active
                              </Badge>
                            ) : (
                              <Badge variant="destructive" className="text-xs">
                                <XCircle className="h-3 w-3 mr-1" />Inactive
                              </Badge>
                            )}
                            {expiry && <Badge variant={expiry.variant} className="text-xs">{expiry.text}</Badge>}
                          </div>
                        </div>
                      </div>

                      <AlertDialog>
                        <AlertDialogTrigger asChild>
                          <Button
                            variant="ghost"
                            size="icon"
                            className="text-[rgb(var(--text-muted))] hover:text-[rgb(var(--danger))] hover:bg-[rgb(var(--danger)/0.08)] shrink-0"
                            disabled={revokingId === key.id}
                          >
                            <Trash2 className="h-4 w-4" />
                          </Button>
                        </AlertDialogTrigger>
                        <AlertDialogContent>
                          <AlertDialogHeader>
                            <AlertDialogTitle>Revoke API key?</AlertDialogTitle>
                            <AlertDialogDescription>
                              This will permanently delete <strong>{key.name}</strong>. Any integrations
                              using this key will stop working immediately.
                            </AlertDialogDescription>
                          </AlertDialogHeader>
                          <AlertDialogFooter>
                            <AlertDialogCancel>Cancel</AlertDialogCancel>
                            <AlertDialogAction
                              variant="destructive"
                              onClick={() => handleRevoke(key.id)}
                            >
                              Revoke key
                            </AlertDialogAction>
                          </AlertDialogFooter>
                        </AlertDialogContent>
                      </AlertDialog>
                    </div>

                    {/* Metadata grid */}
                    <div className="grid grid-cols-4 gap-x-6 gap-y-0 mt-4 pt-3 border-t border-[rgb(var(--border))]">
                      <div>
                        <p className="text-[10px] text-[rgb(var(--text-muted))] uppercase tracking-wide mb-0.5">Integration</p>
                        <p className="text-xs font-mono text-[rgb(var(--text))] truncate" title={key.integration_name}>{key.integration_name}</p>
                      </div>
                      <div>
                        <p className="text-[10px] text-[rgb(var(--text-muted))] uppercase tracking-wide mb-0.5">Tenant</p>
                        <p className="text-xs font-mono text-[rgb(var(--text))] truncate" title={key.tenant_id}>{key.tenant_id}</p>
                      </div>
                      <div>
                        <p className="text-[10px] text-[rgb(var(--text-muted))] uppercase tracking-wide mb-0.5">Created</p>
                        <p className="text-xs text-[rgb(var(--text))] flex items-center gap-1">
                          <Clock className="h-3 w-3 text-[rgb(var(--text-muted))]" />
                          {formatRelativeTime(key.created_at)}
                        </p>
                      </div>
                      <div>
                        <p className="text-[10px] text-[rgb(var(--text-muted))] uppercase tracking-wide mb-0.5">Last used</p>
                        <p className="text-xs text-[rgb(var(--text))]">{formatRelativeTime(key.last_used_at)}</p>
                      </div>
                    </div>
                  </CardContent>
                </Card>
              );
            })}
          </div>
        </>
      )}

      {/* Created key reveal dialog */}
      {createdKey && (
        <Dialog open={true} onOpenChange={(open) => { if (!open) setCreatedKey(null); }}>
          <DialogContent showCloseButton={false}>
            <DialogHeader>
              <DialogTitle>API key created</DialogTitle>
              <DialogDescription>
                Copy your key now — it won't be shown again.
              </DialogDescription>
            </DialogHeader>

            <div className="space-y-3 mt-2">
              <div className="rounded-lg border border-[rgb(var(--success)/0.3)] bg-[rgb(var(--success)/0.08)] px-3 py-2 text-sm text-[rgb(var(--success))]">
                {createdKey.message}
              </div>

              <div>
                <Label className="mb-1.5 block">Your API Key</Label>
                <div className="flex gap-2">
                  <code className="flex-1 rounded-lg border border-[rgb(var(--border))] bg-[rgb(var(--surface-2))] px-3 py-2 text-xs font-mono text-[rgb(var(--text))] break-all">
                    {createdKey.key}
                  </code>
                  <Button
                    variant="outline"
                    size="icon"
                    onClick={() => copyToClipboard(createdKey.key)}
                    className="shrink-0"
                  >
                    {copied ? <CheckCircle className="h-4 w-4 text-[rgb(var(--success))]" /> : <Copy className="h-4 w-4" />}
                  </Button>
                </div>
              </div>

              <div className="rounded-lg border border-[rgb(var(--warning)/0.3)] bg-[rgb(var(--warning)/0.08)] px-3 py-2 text-xs text-[rgb(var(--warning))]">
                Store this key securely — it cannot be retrieved later.
              </div>

              <Button className="w-full" onClick={() => setCreatedKey(null)}>
                Done
              </Button>
            </div>
          </DialogContent>
        </Dialog>
      )}
    </div>
  );
}
