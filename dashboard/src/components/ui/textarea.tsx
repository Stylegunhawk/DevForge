import * as React from "react";
import { cn } from "@/lib/utils";

function Textarea({ className, ...props }: React.ComponentProps<"textarea">) {
  return (
    <textarea
      data-slot="textarea"
      className={cn(
        "flex min-h-[80px] w-full rounded-[6px] border border-[rgb(var(--border))]",
        "bg-[rgb(var(--surface-2))] px-3 py-2 text-sm text-[rgb(var(--text))]",
        "placeholder:text-[rgb(var(--text-faint))]",
        "focus-visible:outline-none focus-visible:ring-[1.5px] focus-visible:ring-[rgb(var(--accent))]",
        "disabled:cursor-not-allowed disabled:opacity-50",
        "resize-none transition-colors",
        className
      )}
      {...props}
    />
  );
}

export { Textarea };
