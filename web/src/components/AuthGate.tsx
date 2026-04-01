"use client";

import { useState, useEffect } from "react";

const APP_PASSWORD = "Protocol1!";
const AUTH_KEY = "proto_auth";

export function AuthGate({ children }: { children: React.ReactNode }) {
  const [authed, setAuthed] = useState(false);
  const [checking, setChecking] = useState(true);
  const [password, setPassword] = useState("");
  const [error, setError] = useState(false);

  useEffect(() => {
    const stored = localStorage.getItem(AUTH_KEY);
    if (stored === APP_PASSWORD) {
      setAuthed(true);
    }
    setChecking(false);
  }, []);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (password === APP_PASSWORD) {
      localStorage.setItem(AUTH_KEY, password);
      setAuthed(true);
      setError(false);
    } else {
      setError(true);
    }
  };

  if (checking) {
    return (
      <div className="min-h-screen bg-neutral-50 flex items-center justify-center">
        <div className="w-6 h-6 border-2 border-brand-primary border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  if (!authed) {
    return (
      <div className="min-h-screen bg-neutral-50 flex items-center justify-center">
        <div className="w-full max-w-sm">
          <div className="bg-white rounded-2xl shadow-lg border border-neutral-200 p-8">
            {/* Logo */}
            <div className="flex items-center gap-3 mb-6">
              <div className="w-10 h-10 rounded-xl bg-brand-primary flex items-center justify-center">
                <span className="text-white font-bold text-lg">PT</span>
              </div>
              <div>
                <h1 className="text-lg font-bold text-neutral-800">ProtoExtract</h1>
                <p className="text-xs text-neutral-400">Protocol Intelligence Platform</p>
              </div>
            </div>

            <form onSubmit={handleSubmit} className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-neutral-700 mb-1.5">
                  Password
                </label>
                <input
                  type="password"
                  value={password}
                  onChange={(e) => {
                    setPassword(e.target.value);
                    setError(false);
                  }}
                  placeholder="Enter access password"
                  autoFocus
                  className={`w-full px-4 py-2.5 rounded-lg border text-sm transition-colors ${
                    error
                      ? "border-red-300 focus:border-red-500 focus:ring-1 focus:ring-red-500"
                      : "border-neutral-300 focus:border-brand-primary focus:ring-1 focus:ring-brand-primary"
                  } placeholder:text-neutral-400`}
                />
                {error && (
                  <p className="text-xs text-red-500 mt-1.5">Incorrect password</p>
                )}
              </div>
              <button
                type="submit"
                className="w-full py-2.5 rounded-lg bg-brand-primary text-white text-sm font-medium hover:bg-brand-french transition-colors"
              >
                Sign In
              </button>
            </form>
          </div>
          <p className="text-center text-xs text-neutral-400 mt-4">
            Access restricted. Contact your administrator.
          </p>
        </div>
      </div>
    );
  }

  return <>{children}</>;
}
