import * as React from "react";
import { Slot } from "@radix-ui/react-slot";
import { cn } from "@/lib/utils";

export interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: "default" | "outline" | "ghost" | "destructive" | "secondary" | "link";
  size?: "default" | "sm" | "lg" | "icon";
  asChild?: boolean;
}

const variantClasses: Record<NonNullable<ButtonProps["variant"]>, string> = {
  default:
    "bg-[rgb(var(--accent))] text-white hover:bg-[rgb(var(--accent-hover))] active:scale-[0.98] shadow-sm",
  outline:
    "bg-[rgb(var(--surface))] border border-[rgb(var(--border))] text-[rgb(var(--text))] hover:bg-[rgb(var(--surface-2))]",
  ghost:
    "bg-transparent text-[rgb(var(--text-muted))] hover:bg-[rgb(var(--surface-2))] hover:text-[rgb(var(--text))]",
  secondary:
    "bg-[rgb(var(--surface-2))] text-[rgb(var(--text))] hover:bg-[rgb(var(--surface-3))]",
  destructive:
    "bg-[rgb(var(--danger))] text-white hover:opacity-90 active:scale-[0.98]",
  link:
    "bg-transparent text-[rgb(var(--accent))] underline-offset-4 hover:underline p-0 h-auto",
};

const sizeClasses: Record<NonNullable<ButtonProps["size"]>, string> = {
  default: "h-9 px-4 py-2 text-sm gap-2",
  sm: "h-8 px-3 text-xs gap-1.5",
  lg: "h-11 px-6 text-base gap-2",
  icon: "h-9 w-9 p-0 [&_svg]:size-4",
};

const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  (
    {
      className,
      variant = "default",
      size = "default",
      asChild,
      disabled,
      ...props
    },
    ref
  ) => {
    const Comp = asChild ? Slot : "button";
    return (
      <Comp
        ref={ref}
        disabled={disabled}
        className={cn(
          "inline-flex items-center justify-center font-medium rounded-[6px] cursor-pointer",
          "transition-all duration-150 select-none whitespace-nowrap",
          "focus-visible:outline-none focus-visible:ring-[1.5px] focus-visible:ring-[rgb(var(--accent))]",
          "disabled:pointer-events-none disabled:opacity-40",
          "[&_svg]:pointer-events-none [&_svg]:shrink-0",
          variantClasses[variant],
          sizeClasses[size],
          className
        )}
        {...props}
      />
    );
  }
);
Button.displayName = "Button";

export { Button };
