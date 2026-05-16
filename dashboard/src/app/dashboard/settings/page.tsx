"use client";

import { useState, useEffect } from "react";
import { useSession, signOut } from "next-auth/react";
import { useRouter } from "next/navigation";
import { useTheme } from "next-themes";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { getCurrentUser, updateProfile, getUserKeys } from "@/lib/api";
import { Copy, Sun, Moon, Monitor, ArrowRight } from "lucide-react";

export default function SettingsPage() {
  const { data: session, update } = useSession();
  const router = useRouter();
  const { theme, setTheme } = useTheme();

  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [currentUser, setCurrentUser] = useState<any>(null);
  const [name, setName] = useState("");
  const [originalName, setOriginalName] = useState("");
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [apiKeys, setApiKeys] = useState<any[]>([]);
  const [keysLoading, setKeysLoading] = useState(true);

  const themes = [
    { value: 'light', label: 'Light', icon: Sun },
    { value: 'dark', label: 'Dark', icon: Moon },
    { value: 'system', label: 'System', icon: Monitor },
  ];

  useEffect(() => {
    if (session?.user?.accessToken) {
      fetchCurrentUser();
      fetchApiKeys();
    }
  }, [session?.user?.accessToken]);

  const fetchCurrentUser = async () => {
    if (!session?.user?.accessToken) return;

    try {
      setLoading(true);
      const userData = await getCurrentUser(session.user.accessToken);
      setCurrentUser(userData);
      setName(userData.name || session.user.name || "");
      setOriginalName(userData.name || session.user.name || "");
      setError("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to fetch user data");
    } finally {
      setLoading(false);
    }
  };

  const fetchApiKeys = async () => {
    if (!session?.user?.accessToken) return;

    try {
      setKeysLoading(true);
      const keys = await getUserKeys(session.user.accessToken);
      setApiKeys(keys);
    } catch (err) {
      console.error('Failed to fetch API keys:', err);
    } finally {
      setKeysLoading(false);
    }
  };

  const formatRelativeTime = (dateString: string | null): string => {
    if (!dateString) return "Never";
    
    const now = new Date();
    const date = new Date(dateString);
    const diffMs = now.getTime() - date.getTime();
    const diffSeconds = Math.floor(diffMs / 1000);
    const diffMinutes = Math.floor(diffSeconds / 60);
    const diffHours = Math.floor(diffMinutes / 60);
    const diffDays = Math.floor(diffHours / 24);

    if (diffSeconds < 60) return "just now";
    if (diffMinutes < 60) return `${diffMinutes}m ago`;
    if (diffHours < 24) return `${diffHours}h ago`;
    return `${diffDays}d ago`;
  };

  const handleSaveProfile = async () => {
    if (!session?.user?.accessToken) return;

    try {
      setSaving(true);
      setError("");
      
      await updateProfile(session.user.accessToken, { name });
      
      // Update session to reflect new name
      await update();
      
      setSuccess("Profile updated");
      setOriginalName(name);
      
      // Clear success message after 3 seconds
      setTimeout(() => setSuccess(""), 3000);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to update profile");
    } finally {
      setSaving(false);
    }
  };

  const handleSignOutAll = async () => {
    await signOut({ callbackUrl: '/login' });
  };

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text);
  };

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'long',
      day: 'numeric'
    });
  };

  if (loading) {
    return (
      <div className="space-y-6">
        <div>
          <h1 className="text-3xl font-bold">Settings</h1>
          <p className="text-muted-foreground">Manage your account preferences</p>
        </div>
        <div className="space-y-6">
          {[1, 2, 3].map((i) => (
            <Card key={i}>
              <CardHeader>
                <Skeleton className="h-6 w-32" />
              </CardHeader>
              <CardContent>
                <div className="space-y-4">
                  <Skeleton className="h-4 w-48" />
                  <Skeleton className="h-10 w-64" />
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold">Settings</h1>
        <p className="text-muted-foreground">Manage your account preferences</p>
      </div>

      {/* Profile Section */}
      <Card>
        <CardHeader>
          <CardTitle>Profile</CardTitle>
          <CardDescription>Update your display name</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="name">Name</Label>
            <Input
              id="name"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Enter your name"
            />
          </div>
          
          <div className="space-y-2">
            <Label htmlFor="email">Email</Label>
            <Input
              id="email"
              value={session?.user?.email || ""}
              disabled
              className="bg-muted text-muted-foreground"
            />
            <p className="text-xs text-muted-foreground">Email cannot be changed</p>
          </div>

          <div className="flex items-center space-x-2">
            <Label>Auth Provider</Label>
            <Badge variant="outline">
              {session?.user?.authProvider === 'google' ? 'Google' : 'Local'}
            </Badge>
          </div>

          {error && (
            <div className="text-sm text-red-600">{error}</div>
          )}
          
          {success && (
            <div className="text-sm text-green-600">{success}</div>
          )}

          <Button 
            onClick={handleSaveProfile}
            disabled={saving || name === originalName}
            className="w-full"
          >
            {saving ? 'Saving...' : 'Save'}
          </Button>
        </CardContent>
      </Card>

      {/* API Key Summary Section */}
      <Card>
        <CardHeader>
          <CardTitle>API Key Summary</CardTitle>
          <CardDescription>Overview of your API keys</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {keysLoading ? (
            <div className="space-y-4">
              <div className="grid grid-cols-3 gap-4">
                <Skeleton className="h-8 w-20" />
                <Skeleton className="h-8 w-20" />
                <Skeleton className="h-8 w-20" />
              </div>
              <div className="space-y-2">
                {[1, 2, 3].map((i) => (
                  <div key={i} className="grid grid-cols-3 gap-4">
                    <Skeleton className="h-4 w-24" />
                    <Skeleton className="h-4 w-20" />
                    <Skeleton className="h-4 w-16" />
                  </div>
                ))}
              </div>
            </div>
          ) : apiKeys.length > 0 ? (
            <>
              <div className="grid grid-cols-3 gap-6 text-center">
                <div>
                  <div className="text-2xl font-bold">{apiKeys.length}</div>
                  <div className="text-sm text-muted-foreground">Total Keys</div>
                </div>
                <div>
                  <div className="text-2xl font-bold">
                    {apiKeys.filter(key => key.is_active).length}
                  </div>
                  <div className="text-sm text-muted-foreground">Active Keys</div>
                </div>
                <div>
                  <div className="text-2xl font-bold">
                    {formatRelativeTime(
                      apiKeys
                        .filter(key => key.last_used)
                        .sort((a, b) => new Date(b.last_used).getTime() - new Date(a.last_used).getTime())[0]?.last_used || null
                    )}
                  </div>
                  <div className="text-sm text-muted-foreground">Last Used</div>
                </div>
              </div>
              
              <div className="space-y-2">
                <div className="grid grid-cols-3 gap-4 text-xs text-muted-foreground uppercase tracking-wide">
                  <div>Name</div>
                  <div>Integration</div>
                  <div>Status</div>
                </div>
                {apiKeys.slice(0, 3).map((key) => (
                  <div key={key.id} className="grid grid-cols-3 gap-4 text-sm">
                    <div className="font-medium">{key.name}</div>
                    <div>{key.integration_name}</div>
                    <div>
                      <Badge variant={key.is_active ? 'default' : 'secondary'}>
                        {key.is_active ? 'Active' : 'Inactive'}
                      </Badge>
                    </div>
                  </div>
                ))}
              </div>
              
              <div className="pt-4 border-t">
                <Button 
                  variant="outline" 
                  onClick={() => router.push('/dashboard/keys')}
                  className="w-full"
                >
                  View all keys
                  <ArrowRight className="h-4 w-4 ml-2" />
                </Button>
              </div>
            </>
          ) : (
            <div className="text-center py-8">
              <p className="text-muted-foreground mb-4">No API keys yet.</p>
              <Button 
                variant="outline" 
                onClick={() => router.push('/dashboard/keys')}
              >
                Create one
                <ArrowRight className="h-4 w-4 ml-2" />
              </Button>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Appearance Section */}
      <Card>
        <CardHeader>
          <CardTitle>Appearance</CardTitle>
          <CardDescription>Customize how DevForge looks</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="flex space-x-2">
            {themes.map((themeOption) => {
              const Icon = themeOption.icon;
              const isActive = theme === themeOption.value;
              
              return (
                <Button
                  key={themeOption.value}
                  variant="outline"
                  onClick={() => setTheme(themeOption.value)}
                  className={`flex items-center space-x-2 ${
                    isActive 
                      ? 'bg-indigo-600 text-white border-indigo-600' 
                      : 'bg-transparent border-border text-muted-foreground'
                  }`}
                >
                  <Icon className="h-4 w-4" />
                  <span>{themeOption.label}</span>
                </Button>
              );
            })}
          </div>
        </CardContent>
      </Card>

      {/* Password Section - Only for local auth */}
      {session?.user?.authProvider === 'local' && (
        <Card>
          <CardHeader>
            <CardTitle>Change Password</CardTitle>
            <CardDescription>Update your account password</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="current-password">Current Password</Label>
              <Input
                id="current-password"
                type="password"
                value={currentPassword}
                onChange={(e) => setCurrentPassword(e.target.value)}
                placeholder="Enter current password"
              />
            </div>
            
            <div className="space-y-2">
              <Label htmlFor="new-password">New Password</Label>
              <Input
                id="new-password"
                type="password"
                value={newPassword}
                onChange={(e) => setNewPassword(e.target.value)}
                placeholder="Enter new password"
              />
            </div>
            
            <div className="space-y-2">
              <Label htmlFor="confirm-password">Confirm New Password</Label>
              <Input
                id="confirm-password"
                type="password"
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                placeholder="Confirm new password"
              />
              {newPassword && confirmPassword && newPassword !== confirmPassword && (
                <p className="text-xs text-red-600">Passwords do not match</p>
              )}
            </div>

            <Button 
              variant="outline"
              disabled
              className="w-full"
            >
              Update password (Coming soon)
            </Button>
            
            <p className="text-xs text-muted-foreground">
              TODO: Backend endpoint not yet implemented
            </p>
          </CardContent>
        </Card>
      )}

      {/* Danger Zone */}
      <Card className="border-red-200 dark:border-red-900">
        <CardHeader>
          <CardTitle className="text-red-600">Danger Zone</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex items-center justify-between">
            <div>
              <h4 className="font-medium">Sign out of all sessions</h4>
              <p className="text-sm text-muted-foreground">Signs you out everywhere</p>
            </div>
            <Button 
              variant="outline" 
              onClick={handleSignOutAll}
              className="border-red-600 text-red-600 hover:bg-red-50 hover:text-red-700"
            >
              Sign out
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Account Information */}
      <Card>
        <CardHeader>
          <CardTitle>Account Information</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex items-center justify-between">
            <span className="text-sm font-medium">User ID</span>
            <div className="flex items-center space-x-2">
              <code className="text-xs bg-muted px-2 py-1 rounded">
                {session?.user?.id}
              </code>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => copyToClipboard(session?.user?.id || "")}
              >
                <Copy className="h-4 w-4" />
              </Button>
            </div>
          </div>
          
          <div className="flex items-center justify-between">
            <span className="text-sm font-medium">Member since</span>
            <span className="text-sm text-muted-foreground">
              {currentUser?.created_at ? formatDate(currentUser.created_at) : 'Unknown'}
            </span>
          </div>
          
          <div className="flex items-center justify-between">
            <span className="text-sm font-medium">Account type</span>
            <Badge variant={session?.user?.isAdmin ? 'default' : 'secondary'}>
              {session?.user?.isAdmin ? 'Admin' : 'User'}
            </Badge>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
