"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { signIn } from "next-auth/react";
import Link from "next/link";
import { Logo } from "@/components/logo";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

export default function RegisterPage() {
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const router = useRouter();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setIsLoading(true);
    try {
      const res = await fetch("/api/proxy/auth/register", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password, name }),
      });

      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        setError(res.status === 400 ? "Email already exists" : data.message || "Registration failed");
        return;
      }

      const result = await signIn("credentials", { email, password, redirect: false });
      if (result?.error) {
        setError("Registration succeeded but login failed. Please sign in manually.");
      } else if (result?.ok) {
        router.push("/dashboard/keys");
      }
    } catch {
      setError("An error occurred. Please try again.");
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="bg-[rgb(var(--surface))] border border-[rgb(var(--border))] rounded-[10px] shadow-[0_4px_24px_rgba(26,24,21,0.08)] p-8 w-full max-w-sm">
      {/* Header */}
      <div className="flex flex-col items-center text-center mb-8">
        <Logo size="md" />
        <h1 className="text-xl font-bold text-[rgb(var(--text))] text-center mt-4">
          Create your account
        </h1>
        <p className="text-sm text-[rgb(var(--text-muted))] text-center mt-1">
          Get started with DevForge today
        </p>
      </div>

      {/* Form */}
      <form onSubmit={handleSubmit} className="space-y-4">
        <div className="space-y-1.5">
          <Label htmlFor="name">Full name</Label>
          <Input
            id="name"
            type="text"
            placeholder="Jane Smith"
            value={name}
            onChange={(e) => setName(e.target.value)}
            disabled={isLoading}
            required
            autoComplete="name"
          />
        </div>

        <div className="space-y-1.5">
          <Label htmlFor="email">Email</Label>
          <Input
            id="email"
            type="email"
            placeholder="you@example.com"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            disabled={isLoading}
            required
            autoComplete="email"
          />
        </div>

        <div className="space-y-1.5">
          <Label htmlFor="password">Password</Label>
          <Input
            id="password"
            type="password"
            placeholder="••••••••"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            disabled={isLoading}
            required
            autoComplete="new-password"
          />
        </div>

        {error && (
          <p className="text-sm text-[rgb(var(--danger))]">{error}</p>
        )}

        <Button type="submit" className="w-full mt-2" disabled={isLoading}>
          {isLoading ? "Creating account…" : "Create account"}
        </Button>
      </form>

      {/* Footer */}
      <p className="mt-6 text-center text-sm text-[rgb(var(--text-muted))]">
        Already have an account?{" "}
        <Link href="/login" className="text-[rgb(var(--accent))] hover:underline font-medium">
          Sign in
        </Link>
      </p>
    </div>
  );
}
