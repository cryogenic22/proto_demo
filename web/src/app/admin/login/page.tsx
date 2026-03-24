"use client";

import { useState } from "react";
import { Card, CardBody } from "@/components/ui/Card";

export default function AdminLoginPage() {
  const [password, setPassword] = useState("");
  const [error, setError] = useState(false);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setError(false);
    window.location.href = `/admin?password=${encodeURIComponent(password)}`;
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-neutral-50 p-4">
      <div className="w-full max-w-sm">
        <div className="text-center mb-6">
          <h1 className="text-xl font-bold text-neutral-800">ProtoExtract Admin</h1>
          <p className="text-sm text-neutral-500 mt-1">Enter admin password</p>
        </div>
        <Card>
          <CardBody className="p-6">
            <form onSubmit={handleSubmit} className="space-y-4">
              <input
                type="password"
                value={password}
                onChange={(e) => { setPassword(e.target.value); setError(false); }}
                placeholder="Admin password"
                autoFocus
                className="w-full px-4 py-3 text-sm border border-neutral-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-red-500/30 focus:border-red-500"
              />
              {error && <p className="text-xs text-red-600">Invalid password</p>}
              <button
                type="submit"
                className="w-full py-3 text-sm font-medium rounded-lg bg-red-600 text-white hover:bg-red-700 transition-colors"
              >
                Login as Admin
              </button>
            </form>
          </CardBody>
        </Card>
      </div>
    </div>
  );
}
