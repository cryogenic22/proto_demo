"use client";

import { useEffect, useState } from "react";
import { checkHealth } from "@/lib/api";
import { cn } from "@/lib/utils";

interface TopBarProps {
  title: string;
  subtitle?: string;
}

export function TopBar({ title, subtitle }: TopBarProps) {
  const [apiHealthy, setApiHealthy] = useState<boolean | null>(null);

  useEffect(() => {
    const check = () => checkHealth().then(setApiHealthy);
    check();
    const interval = setInterval(check, 15000);
    return () => clearInterval(interval);
  }, []);

  return (
    <header className="h-14 bg-white border-b border-neutral-200 flex items-center justify-between px-6 sticky top-0 z-30">
      <div>
        <h1 className="text-base font-semibold text-neutral-800">{title}</h1>
        {subtitle && (
          <p className="text-xs text-neutral-400">{subtitle}</p>
        )}
      </div>

      <div className="flex items-center gap-4">
        {/* API Status */}
        <div className="flex items-center gap-2 text-xs text-neutral-500">
          <span
            className={cn(
              "w-2 h-2 rounded-full",
              apiHealthy === null
                ? "bg-neutral-300"
                : apiHealthy
                  ? "bg-emerald-500"
                  : "bg-red-500"
            )}
          />
          <span>
            {apiHealthy === null ? "Checking..." : apiHealthy ? "API Connected" : "API Offline"}
          </span>
        </div>
      </div>
    </header>
  );
}
