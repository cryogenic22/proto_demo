"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Card, CardBody } from "@/components/ui/Card";

export default function LoginPage() {
  const router = useRouter();
  const [password, setPassword] = useState("");
  const [error, setError] = useState(false);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    // Navigate with password param — middleware handles validation
    window.location.href = `/?password=${encodeURIComponent(password)}`;
  };

  return (
    <div className="min-h-screen bg-neutral-50 flex items-center justify-center px-4">
      <div className="w-full max-w-sm">
        <div className="text-center mb-6">
          <div className="w-12 h-12 rounded-xl bg-brand-primary flex items-center justify-center mx-auto mb-3">
            <span className="text-white font-bold text-lg">PT</span>
          </div>
          <h1 className="text-xl font-bold text-neutral-800">ProtoExtract</h1>
          <p className="text-sm text-neutral-500 mt-1">Enter password to continue</p>
        </div>

        <Card>
          <CardBody className="p-6">
            <form onSubmit={handleSubmit} className="space-y-4">
              <div>
                <input
                  type="password"
                  value={password}
                  onChange={(e) => { setPassword(e.target.value); setError(false); }}
                  placeholder="Password"
                  autoFocus
                  className="w-full px-4 py-3 text-sm border border-neutral-200 rounded-lg bg-white focus:outline-none focus:ring-2 focus:ring-brand-primary/30 focus:border-brand-primary"
                />
              </div>
              {error && (
                <p className="text-xs text-red-600">Incorrect password</p>
              )}
              <button
                type="submit"
                className="w-full py-3 text-sm font-medium bg-brand-primary text-white rounded-lg hover:bg-brand-french transition-colors"
              >
                Sign In
              </button>
            </form>
          </CardBody>
        </Card>

        <p className="text-[10px] text-neutral-400 text-center mt-4">
          Internal access only — contact your admin for credentials
        </p>
      </div>
    </div>
  );
}
