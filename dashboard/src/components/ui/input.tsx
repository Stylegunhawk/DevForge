import * as React from "react";
import { cn } from "@/lib/utils";

function Input({ className, type, ...props }: React.ComponentProps<"input">) {
  return (
    <input
      type={type}
      data-slot="input"
      className={cn(
        "flex h-9 w-full rounded-[6px] border border-[rgb(var(--border))]",
        "bg-[rgb(var(--surface-2))] px-3 py-1 text-sm text-[rgb(var(--text))]",
        "placeholder:text-[rgb(var(--text-faint))]",
        "focus-visible:outline-none focus-visible:ring-[1.5px] focus-visible:ring-[rgb(var(--accent))]",
        "disabled:cursor-not-allowed disabled:opacity-50",
        "transition-colors",
        "file:border-0 file:bg-transparent file:text-sm file:font-medium file:text-[rgb(var(--text))]",
        className
      )}
      {...props}
    />
  );
}

export { Input };
