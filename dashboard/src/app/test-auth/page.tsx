"use client";

import { useState } from "react";
import { signIn, signOut, useSession } from "next-auth/react";

export default function TestAuthPage() {
  const { data: session, status } = useSession();
  const [isLoading, setIsLoading] = useState(false);
  const [result, setResult] = useState("");

  const testLogin = async (email: string, password: string) => {
    setIsLoading(true);
    setResult("");
    
    try {
      const res = await signIn("credentials", {
        email,
        password,
        redirect: false,
      });
      
      setResult(JSON.stringify(res, null, 2));
    } catch (error) {
      setResult(`Error: ${error}`);
    } finally {
      setIsLoading(false);
    }
  };

  const testSignOut = () => {
    signOut({ callbackUrl: "/test-auth" });
  };

  return (
    <div className="p-8 max-w-4xl mx-auto">
      <h1 className="text-2xl font-bold mb-6">Authentication Test</h1>
      
      <div className="space-y-6">
        {/* Session Status */}
        <div className="p-4 border rounded-lg">
          <h2 className="text-lg font-semibold mb-2">Session Status</h2>
          <p><strong>Status:</strong> {status}</p>
          <p><strong>Session:</strong></p>
          <pre className="bg-gray-100 p-2 rounded text-sm overflow-auto">
            {JSON.stringify(session, null, 2)}
          </pre>
        </div>

        {/* Test Login */}
        <div className="p-4 border rounded-lg">
          <h2 className="text-lg font-semibold mb-2">Test Login</h2>
          <div className="space-y-2">
            <button
              onClick={() => testLogin("admin@devforge.ai", "adminpass123")}
              disabled={isLoading}
              className="bg-blue-500 text-white px-4 py-2 rounded mr-2"
            >
              Login as Admin
            </button>
            <button
              onClick={() => testLogin("test@devforge.ai", "test123")}
              disabled={isLoading}
              className="bg-green-500 text-white px-4 py-2 rounded mr-2"
            >
              Login as User
            </button>
            <button
              onClick={testSignOut}
              className="bg-red-500 text-white px-4 py-2 rounded"
            >
              Sign Out
            </button>
          </div>
          
          {isLoading && <p className="mt-2">Loading...</p>}
          
          {result && (
            <div className="mt-4">
              <h3 className="font-semibold">Result:</h3>
              <pre className="bg-gray-100 p-2 rounded text-sm overflow-auto">
                {result}
              </pre>
            </div>
          )}
        </div>

        {/* Quick Links */}
        <div className="p-4 border rounded-lg">
          <h2 className="text-lg font-semibold mb-2">Quick Links</h2>
          <div className="space-y-2">
            <a href="/login" className="block text-blue-500 hover:underline">Login Page</a>
            <a href="/register" className="block text-blue-500 hover:underline">Register Page</a>
            <a href="/dashboard/keys" className="block text-blue-500 hover:underline">Dashboard (protected)</a>
          </div>
        </div>
      </div>
    </div>
  );
}
