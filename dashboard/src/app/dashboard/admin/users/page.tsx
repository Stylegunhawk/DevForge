"use client";

import { useState, useEffect } from "react";
import { useSession } from "next-auth/react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Shield, ShieldOff, User, UserX, Crown, BarChart3 } from "lucide-react";
import { useRouter } from "next/navigation";
import { getAdminUsers, updateUser, AdminUser } from "@/lib/api";

function formatRelativeTime(timestamp: string): string {
  const now = new Date();
  const time = new Date(timestamp);
  const diffMs = now.getTime() - time.getTime();
  const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));

  if (diffDays === 0) return "Today";
  if (diffDays === 1) return "Yesterday";
  if (diffDays < 30) return `${diffDays} days ago`;
  if (diffDays < 365) return `${Math.floor(diffDays / 30)} months ago`;
  return `${Math.floor(diffDays / 365)} years ago`;
}

export default function AdminUsers() {
  const { data: session } = useSession();
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [updatingUserId, setUpdatingUserId] = useState<string | null>(null);
  const router = useRouter();

  useEffect(() => {
    if (session?.user?.accessToken) {
      fetchUsers();
    }
  }, [session]);

  const fetchUsers = async () => {
    if (!session?.user?.accessToken) return;

    try {
      setLoading(true);
      const response = await getAdminUsers(session.user.accessToken);
      setUsers(response.users);
      setError("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to fetch users");
    } finally {
      setLoading(false);
    }
  };

  const handleToggleAdmin = async (userId: string, currentIsAdmin: boolean) => {
    // Prevent admin from removing their own admin status
    if (userId === session?.user?.id && currentIsAdmin) {
      setError("You cannot remove your own admin status");
      return;
    }

    try {
      setUpdatingUserId(userId);
      await updateUser(session!.user!.accessToken, userId, { is_admin: !currentIsAdmin });
      
      // Update local state
      setUsers(prev => prev.map(user => 
        user.id === userId ? { ...user, is_admin: !currentIsAdmin } : user
      ));
      setError("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to update user");
    } finally {
      setUpdatingUserId(null);
    }
  };

  const handleToggleActive = async (userId: string, currentIsActive: boolean) => {
    // Prevent admin from deactivating themselves
    if (userId === session?.user?.id && currentIsActive) {
      setError("You cannot deactivate your own account");
      return;
    }

    try {
      setUpdatingUserId(userId);
      await updateUser(session!.user!.accessToken, userId, { is_active: !currentIsActive });
      
      // Update local state
      setUsers(prev => prev.map(user => 
        user.id === userId ? { ...user, is_active: !currentIsActive } : user
      ));
      setError("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to update user");
    } finally {
      setUpdatingUserId(null);
    }
  };

  if (loading) {
    return (
      <div className="space-y-4">
        <Card>
          <CardHeader>
            <Skeleton className="h-6 w-32" />
            <Skeleton className="h-4 w-48" />
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              {[1, 2, 3, 4, 5].map((i) => (
                <div key={i} className="flex items-center justify-between p-4 border rounded">
                  <div className="space-y-1">
                    <Skeleton className="h-4 w-32" />
                    <Skeleton className="h-3 w-48" />
                  </div>
                  <div className="flex items-center space-x-4">
                    <Skeleton className="h-6 w-16" />
                    <Skeleton className="h-6 w-16" />
                    <Skeleton className="h-3 w-20" />
                    <div className="flex space-x-2">
                      <Skeleton className="h-8 w-8" />
                      <Skeleton className="h-8 w-8" />
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded">
          {error}
        </div>
      )}

      <Card>
        <CardHeader>
          <CardTitle>User Management</CardTitle>
          <CardDescription>
            Manage user roles and permissions
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            {users.length === 0 ? (
              <p className="text-muted-foreground text-center py-8">
                No users found
              </p>
            ) : (
              <div className="space-y-2">
                {users.map((user) => (
                  <div key={user.id} className="flex items-center justify-between p-4 border rounded-lg">
                    <div className="space-y-1">
                      <div className="flex items-center space-x-2">
                        <span className="font-medium">{user.name}</span>
                        {user.is_admin && <Crown className="h-4 w-4 text-yellow-600" />}
                      </div>
                      <div className="text-sm text-muted-foreground">{user.email}</div>
                    </div>
                    
                    <div className="flex items-center space-x-4">
                      <Badge variant={user.is_admin ? "default" : "secondary"}>
                        {user.is_admin ? "Admin" : "User"}
                      </Badge>
                      
                      <Badge variant={user.is_active ? "default" : "destructive"}>
                        {user.is_active ? "Active" : "Inactive"}
                      </Badge>
                      
                      <span className="text-sm text-muted-foreground">
                        {formatRelativeTime(user.created_at)}
                      </span>
                      
                      <div className="flex space-x-2">
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={() => handleToggleAdmin(user.id, user.is_admin)}
                          disabled={updatingUserId === user.id || user.id === session?.user?.id}
                        >
                          {user.is_admin ? (
                            <ShieldOff className="h-4 w-4" />
                          ) : (
                            <Shield className="h-4 w-4" />
                          )}
                        </Button>
                        
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={() => handleToggleActive(user.id, user.is_active)}
                          disabled={updatingUserId === user.id || user.id === session?.user?.id}
                        >
                          {user.is_active ? (
                            <UserX className="h-4 w-4" />
                          ) : (
                            <User className="h-4 w-4" />
                          )}
                        </Button>
                        
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={() => router.push(`/dashboard/admin/users/${user.id}`)}
                        >
                          <BarChart3 className="h-4 w-4" />
                        </Button>
                      </div>
                    </div>
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
