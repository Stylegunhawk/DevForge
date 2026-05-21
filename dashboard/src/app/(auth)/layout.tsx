import { ThemeToggle } from "@/components/theme-toggle";

export default function AuthLayout({ children }: { children: React.ReactNode }) {
  return (
    <div
      className="min-h-screen bg-[rgb(var(--bg))] flex items-center justify-center relative"
      style={{
        backgroundImage:
          "radial-gradient(circle, rgb(var(--border)) 1px, transparent 1px)",
        backgroundSize: "24px 24px",
      }}
    >
      {/* Radial glow overlay from top */}
      <div
        className="absolute inset-0 pointer-events-none"
        style={{
          backgroundImage:
            "radial-gradient(ellipse 80% 40% at 50% -10%, rgb(var(--accent-subtle)), transparent)",
        }}
      />

      {/* Theme toggle */}
      <div className="absolute top-4 right-4 z-10">
        <ThemeToggle />
      </div>

      <div className="relative z-10 w-full max-w-sm px-4">{children}</div>
    </div>
  );
}
