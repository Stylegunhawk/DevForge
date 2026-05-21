import * as React from "react";
import { cn } from "@/lib/utils";

export interface BadgeProps extends React.HTMLAttributes<HTMLSpanElement> {
  variant?: "default" | "secondary" | "outline" | "destructive" | "success" | "warning";
}

const variantClasses: Record<NonNullable<BadgeProps["variant"]>, string> = {
  default:
    "bg-[rgb(var(--accent-subtle))] text-[rgb(var(--accent))] border-transparent",
  secondary:
    "bg-[rgb(var(--surface-2))] text-[rgb(var(--text-muted))] border-transparent",
  outline:
    "bg-transparent text-[rgb(var(--text-muted))] border border-[rgb(var(--border))]",
  destructive:
    "bg-[rgb(var(--danger-bg))] text-[rgb(var(--danger))] border-transparent",
  success:
    "bg-[rgb(var(--success-bg))] text-[rgb(var(--success))] border-transparent",
  warning:
    "bg-[rgb(var(--warning-bg))] text-[rgb(var(--warning))] border-transparent",
};

function Badge({ className, variant = "default", ...props }: BadgeProps) {
  return (
    <span
      data-slot="badge"
      className={cn(
        "inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-xs font-medium transition-colors",
        variantClasses[variant],
        className
      )}
      {...props}
    />
  );
}

export { Badge };
