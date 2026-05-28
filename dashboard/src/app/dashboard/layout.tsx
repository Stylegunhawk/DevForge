"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useSession, signOut } from "next-auth/react";
import { cn } from "@/lib/utils";
import { Logo } from "@/components/logo";
import { ThemeToggle } from "@/components/theme-toggle";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import {
  KeyRound,
  BarChart3,
  BookOpen,
  Settings,
  Shield,
  LogOut,
  LayoutDashboard,
  FlaskConical,
} from "lucide-react";

const navigation = [
  { name: "Overview",    href: "/dashboard",            icon: LayoutDashboard },
  { name: "API Keys",    href: "/dashboard/keys",       icon: KeyRound },
  { name: "Usage",       href: "/dashboard/usage",      icon: BarChart3 },
  { name: "Playground",  href: "/dashboard/playground", icon: FlaskConical },
  { name: "Docs",        href: "/dashboard/docs",       icon: BookOpen },
  { name: "Settings",    href: "/dashboard/settings",   icon: Settings },
];

const adminNavigation = [
  { name: "Admin",       href: "/dashboard/admin",      icon: Shield },
];

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const { data: session } = useSession();

  const initials = session?.user?.name
    ? session.user.name.split(" ").map((n: string) => n[0]).join("").toUpperCase().slice(0, 2)
    : "?";

  return (
    <div className="flex h-screen bg-[rgb(var(--bg))] overflow-hidden">
      {/* ── Sidebar ── */}
      <aside className="w-56 shrink-0 flex flex-col border-r border-[rgb(var(--border))] bg-[rgb(var(--sidebar-bg))]">
        {/* Logo */}
        <div className="flex h-14 items-center px-4 border-b border-[rgb(var(--border))]">
          <Logo size="sm" />
        </div>

        {/* Navigation */}
        <nav className="flex-1 p-2 space-y-0.5 overflow-y-auto">
          {navigation.map((item) => {
            const active = pathname === item.href;
            return (
              <Link
                key={item.name}
                href={item.href}
                className={cn(
                  "group flex items-center gap-2.5 rounded-lg px-3 py-2 text-sm font-medium transition-colors duration-100 border-l-2",
                  active
                    ? "border-l-2 border-[rgb(var(--accent))] bg-[rgb(var(--accent-subtle))] text-[rgb(var(--accent))]"
                    : "border-l-2 border-transparent text-[rgb(var(--text-muted))] hover:bg-[rgb(var(--surface-2))] hover:text-[rgb(var(--text))]"
                )}
              >
                <item.icon
                  className={cn(
                    "h-4 w-4 shrink-0 transition-colors",
                    active ? "text-[rgb(var(--accent))]" : "text-[rgb(var(--text-muted))] group-hover:text-[rgb(var(--text))]"
                  )}
                />
                {item.name}
              </Link>
            );
          })}

          {/* Admin section */}
          {session?.user?.isAdmin && (
            <>
              <div className="my-2 border-t border-[rgb(var(--border))]" />
              {adminNavigation.map((item) => {
                const active = pathname === item.href;
                return (
                  <Link
                    key={item.name}
                    href={item.href}
                    className={cn(
                      "group flex items-center gap-2.5 rounded-lg px-3 py-2 text-sm font-medium transition-colors duration-100 border-l-2",
                      active
                        ? "border-l-2 border-[rgb(var(--accent))] bg-[rgb(var(--accent-subtle))] text-[rgb(var(--accent))]"
                        : "border-l-2 border-transparent text-[rgb(var(--text-muted))] hover:bg-[rgb(var(--surface-2))] hover:text-[rgb(var(--text))]"
                    )}
                  >
                    <item.icon className="h-4 w-4 shrink-0" />
                    {item.name}
                  </Link>
                );
              })}
            </>
          )}
        </nav>

        {/* User footer */}
        <div className="p-3 border-t border-[rgb(var(--border))]">
          <div className="flex items-center gap-2.5 mb-2.5 px-1">
            <Avatar className="h-7 w-7 shrink-0">
              <AvatarFallback className="text-xs">{initials}</AvatarFallback>
            </Avatar>
            <div className="flex-1 min-w-0">
              <p className="text-xs font-medium text-[rgb(var(--text))] truncate">
                {session?.user?.name ?? "User"}
              </p>
              <p className="text-[10px] text-[rgb(var(--text-muted))] truncate">
                {session?.user?.email ?? ""}
              </p>
            </div>
          </div>
          <div className="flex items-center gap-1">
            <ThemeToggle />
            <button
              onClick={() => signOut({ callbackUrl: "/" })}
              className="flex flex-1 items-center gap-2 rounded-lg px-2 py-1.5 text-xs font-medium text-[rgb(var(--text-muted))] hover:bg-[rgb(var(--surface-2))] hover:text-[rgb(var(--text))] transition-colors duration-100"
            >
              <LogOut className="h-3.5 w-3.5 shrink-0" />
              Sign out
            </button>
          </div>
        </div>
      </aside>

      {/* ── Main ── */}
      <main className="flex-1 overflow-auto px-8 py-8">
        {children}
      </main>
    </div>
  );
}
