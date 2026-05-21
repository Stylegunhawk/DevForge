"use client";

import { useSession } from "next-auth/react";
import { useRouter } from "next/navigation";
import { useEffect } from "react";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import Link from "next/link";
import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";

export default function AdminLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const { data: session, status } = useSession();
  const router = useRouter();

  useEffect(() => {
    if (status === "loading") return; // Still loading
    
    if (!session?.user?.isAdmin) {
      router.replace("/dashboard/keys");
    }
  }, [session, status, router]);

  if (status === "loading") {
    return (
      <div className="space-y-6">
        <div>
          <Skeleton className="h-8 w-48" />
          <Skeleton className="h-4 w-64 mt-2" />
        </div>
        <Card>
          <CardContent className="p-6">
            <Skeleton className="h-32 w-full" />
          </CardContent>
        </Card>
      </div>
    );
  }

  if (!session?.user?.isAdmin) {
    return null; // Will redirect
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">Admin Panel</h1>
        <p className="text-[rgb(var(--text-muted))]">
          Manage users, monitor requests, and view system analytics
        </p>
      </div>

      <Tabs defaultValue="overview" className="space-y-4">
        <TabsList>
          <TabsTrigger value="overview" asChild>
            <Link href="/dashboard/admin">Overview</Link>
          </TabsTrigger>
          <TabsTrigger value="users" asChild>
            <Link href="/dashboard/admin/users">Users</Link>
          </TabsTrigger>
          <TabsTrigger value="requests" asChild>
            <Link href="/dashboard/admin/requests">Request Logs</Link>
          </TabsTrigger>
        </TabsList>

        <Card>
          <CardContent className="p-6">
            {children}
          </CardContent>
        </Card>
      </Tabs>
    </div>
  );
}
