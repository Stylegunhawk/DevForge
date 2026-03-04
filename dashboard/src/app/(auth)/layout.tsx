import { ThemeToggle } from "@/components/theme-toggle";

export default function AuthLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div className="min-h-screen flex flex-col items-center justify-center relative bg-zinc-50 dark:bg-zinc-950">
      {/* Background pattern */}
      <div className="absolute inset-0 -z-10">
        <div className="absolute inset-0 bg-[radial-gradient(circle_at_1px_1px,rgb(229_229_229)_1px,transparent_1px)] dark:bg-[radial-gradient(circle_at_1px_1px,rgb(39_39_42)_1px,transparent_1px)] [background-size:24px_24px] opacity-100"></div>
      </div>
      
      {/* Theme toggle in top-right */}
      <div className="absolute top-4 right-4">
        <ThemeToggle />
      </div>
      
      {/* Main content */}
      <div className="w-full max-w-sm px-4">
        {children}
      </div>
    </div>
  );
}
