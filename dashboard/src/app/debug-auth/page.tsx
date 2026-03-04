"use client";

import { useState } from "react";

export default function DebugAuthPage() {
  const [result, setResult] = useState("");
  const [isLoading, setIsLoading] = useState(false);

  const testBackendAuth = async () => {
    setIsLoading(true);
    setResult("");
    
    try {
      // Test Step 1: Login
      const loginRes = await fetch('http://localhost:8001/api/auth/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          email: 'admin@devforge.ai',
          password: 'adminpass123'
        })
      });
      
      const loginData = await loginRes.json();
      setResult(`Step 1 - Login Response:\n${JSON.stringify(loginData, null, 2)}\n\n`);
      
      if (loginRes.ok && loginData.access_token) {
        // Test Step 2: Get user profile
        const meRes = await fetch('http://localhost:8001/api/auth/me', {
          headers: { 'Authorization': `Bearer ${loginData.access_token}` }
        });
        
        const userData = await meRes.json();
        setResult(prev => prev + `Step 2 - User Profile Response:\n${JSON.stringify(userData, null, 2)}\n\n`);
        
        if (meRes.ok) {
          setResult(prev => prev + "✅ Backend authentication flow working correctly!");
        } else {
          setResult(prev => prev + "❌ User profile fetch failed");
        }
      } else {
        setResult(prev => prev + "❌ Login failed");
      }
      
    } catch (error) {
      setResult(`❌ Error: ${error}`);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="p-8 max-w-4xl mx-auto">
      <h1 className="text-2xl font-bold mb-6">Debug Authentication</h1>
      
      <div className="space-y-6">
        <button
          onClick={testBackendAuth}
          disabled={isLoading}
          className="bg-blue-500 text-white px-6 py-3 rounded-lg"
        >
          {isLoading ? "Testing..." : "Test Backend Auth Flow"}
        </button>
        
        {result && (
          <div className="p-4 border rounded-lg">
            <h2 className="text-lg font-semibold mb-2">Result:</h2>
            <pre className="bg-gray-100 p-4 rounded text-sm overflow-auto whitespace-pre-wrap">
              {result}
            </pre>
          </div>
        )}
      </div>
    </div>
  );
}
