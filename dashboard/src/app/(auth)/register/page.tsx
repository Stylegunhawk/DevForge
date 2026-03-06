"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { signIn } from "next-auth/react";
import Link from "next/link";
import { Logo } from "@/components/logo";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

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
      // Register the user
      const registerResponse = await fetch("/api/proxy/auth/register", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          email,
          password,
          name,
        }),
      });

      if (!registerResponse.ok) {
        const errorData = await registerResponse.json().catch(() => ({}));
        if (registerResponse.status === 400) {
          setError("Email already exists");
        } else {
          setError(errorData.message || "Registration failed");
        }
        return;
      }

      // Auto-sign in after successful registration
      const result = await signIn("credentials", {
        email,
        password,
        redirect: false,
      });

      if (result?.error) {
        setError("Registration successful but login failed. Please try signing in manually.");
      } else if (result?.ok) {
        router.push("/dashboard/keys");
      }
    } catch (error) {
      setError("An error occurred. Please try again.");
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <Card className="w-full bg-white dark:bg-zinc-900 border-zinc-200 dark:border-zinc-800 shadow-sm rounded-xl p-8">
      <CardHeader className="text-center px-0 pb-6">
        <div className="flex justify-center mb-4">
          <Logo size="lg" />
        </div>
        <CardTitle className="text-2xl">Create account</CardTitle>
        <CardDescription>
          Enter your information to get started
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4 px-0">
        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="name">Name</Label>
            <Input
              id="name"
              type="text"
              placeholder="John Doe"
              value={name}
              onChange={(e) => setName(e.target.value)}
              disabled={isLoading}
              className="border-zinc-300 dark:border-zinc-700 focus:ring-indigo-500 bg-white dark:bg-zinc-950"
              required
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="email">Email</Label>
            <Input
              id="email"
              type="email"
              placeholder="name@example.com"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              disabled={isLoading}
              className="border-zinc-300 dark:border-zinc-700 focus:ring-indigo-500 bg-white dark:bg-zinc-950"
              required
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="password">Password</Label>
            <Input
              id="password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              disabled={isLoading}
              className="border-zinc-300 dark:border-zinc-700 focus:ring-indigo-500 bg-white dark:bg-zinc-950"
              required
            />
          </div>
          
          {error && (
            <div className="text-red-600 text-sm text-center">
              {error}
            </div>
          )}
          
          <Button 
            type="submit" 
            className="w-full bg-indigo-600 hover:bg-indigo-700 text-white rounded-md py-2.5"
            disabled={isLoading}
          >
            {isLoading ? "Creating account..." : "Create account"}
          </Button>
        </form>
        
        <div className="text-center text-sm text-muted-foreground">
          Already have an account?{" "}
          <Link href="/login" className="text-indigo-600 hover:underline">
            Sign in
          </Link>
        </div>
      </CardContent>
    </Card>
  );
}
