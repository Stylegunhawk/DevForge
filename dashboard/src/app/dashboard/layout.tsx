"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useSession, signOut } from "next-auth/react";
import { cn } from "@/lib/utils";
import { Logo } from "@/components/logo";
import { ThemeToggle } from "@/components/theme-toggle";
import { Button } from "@/components/ui/button";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { Separator } from "@/components/ui/separator";
import {
  KeyRound,
  BarChart3,
  BookOpen,
  Settings,
  Shield,
  LogOut,
  User,
} from "lucide-react";

const navigation = [
  { name: "API Keys", href: "/dashboard/keys", icon: KeyRound },
  { name: "Usage", href: "/dashboard/usage", icon: BarChart3 },
  { name: "Docs", href: "/dashboard/docs", icon: BookOpen },
  { name: "Settings", href: "/dashboard/settings", icon: Settings },
];

const adminNavigation = [
  { name: "Admin", href: "/dashboard/admin", icon: Shield },
];

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const pathname = usePathname();
  const { data: session } = useSession();

  const handleSignOut = () => {
    signOut({ callbackUrl: "/login" });
  };

  return (
    <div className="flex h-screen bg-background">
      {/* Sidebar */}
      <div className="w-60 border-r border-border bg-sidebar">
        <div className="flex h-full flex-col">
          {/* Logo */}
          <div className="flex h-16 items-center px-4">
            <Logo size="md" />
          </div>
          <Separator />
          
          {/* Navigation */}
          <nav className="flex-1 space-y-1 p-4">
            {navigation.map((item) => {
              const isActive = pathname === item.href;
              return (
                <Link
                  key={item.name}
                  href={item.href}
                  className={cn(
                    "flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors",
                    isActive
                      ? "bg-sidebar-accent text-sidebar-accent-foreground"
                      : "text-sidebar-foreground hover:bg-sidebar-accent/50"
                  )}
                >
                  <item.icon className="h-4 w-4" />
                  {item.name}
                </Link>
              );
            })}
            
            {/* Admin section - conditionally rendered */}
            {session?.user?.isAdmin && (
              <div className="pt-4">
                <Separator className="mb-4" />
                {adminNavigation.map((item) => {
                  const isActive = pathname === item.href;
                  return (
                    <Link
                      key={item.name}
                      href={item.href}
                      className={cn(
                        "flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors",
                        isActive
                          ? "bg-sidebar-accent text-sidebar-accent-foreground"
                          : "text-sidebar-foreground hover:bg-sidebar-accent/50"
                      )}
                    >
                      <item.icon className="h-4 w-4" />
                      {item.name}
                    </Link>
                  );
                })}
              </div>
            )}
          </nav>
          
          {/* User section */}
          <div className="border-t border-border p-4">
            <div className="flex items-center gap-3 mb-3">
              <Avatar className="h-8 w-8">
                <AvatarImage src="" alt="User" />
                <AvatarFallback>
                  <User className="h-4 w-4" />
                </AvatarFallback>
              </Avatar>
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium text-sidebar-foreground truncate">
                  {session?.user?.name || "User"}
                </p>
                <p className="text-xs text-muted-foreground truncate">
                  {session?.user?.email || "user@example.com"}
                </p>
              </div>
            </div>
            <div className="flex items-center gap-2">
              <ThemeToggle />
              <Button variant="ghost" size="sm" className="w-full justify-start" onClick={handleSignOut}>
                <LogOut className="h-4 w-4 mr-2" />
                Sign out
              </Button>
            </div>
          </div>
        </div>
      </div>
      
      {/* Main content */}
      <div className="flex-1 overflow-auto">
        <main className="h-full">
          {children}
        </main>
      </div>
    </div>
  );
}
