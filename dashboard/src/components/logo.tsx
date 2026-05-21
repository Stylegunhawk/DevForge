import { cn } from "@/lib/utils";

interface LogoProps {
  size?: "sm" | "md" | "lg";
  className?: string;
}

export function Logo({ size = "md", className }: LogoProps) {
  const sizes = {
    sm: { icon: "h-6 w-6", text: "text-sm" },
    md: { icon: "h-8 w-8", text: "text-base" },
    lg: { icon: "h-10 w-10", text: "text-lg" },
  };

  const { icon, text } = sizes[size];

  return (
    <div className={cn("flex items-center gap-2 select-none", className)}>
      {/* Coral square icon with white D */}
      <div
        className={cn(
          "flex items-center justify-center shrink-0 rounded-md bg-[rgb(var(--accent))]",
          icon
        )}
      >
        <span className="font-bold text-white leading-none">D</span>
      </div>
      {/* Wordmark */}
      <span className={cn("font-semibold text-[rgb(var(--text))]", text)}>
        DevForge
      </span>
    </div>
  );
}
