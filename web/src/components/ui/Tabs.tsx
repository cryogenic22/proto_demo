"use client";

import { cn } from "@/lib/utils";

interface Tab {
  key: string;
  label: string;
  count?: number;
}

interface TabsProps {
  tabs: Tab[];
  active: string;
  onChange: (key: string) => void;
  className?: string;
}

export function Tabs({ tabs, active, onChange, className }: TabsProps) {
  return (
    <div className={cn("flex gap-1 border-b border-neutral-200", className)}>
      {tabs.map((tab) => (
        <button
          key={tab.key}
          onClick={() => onChange(tab.key)}
          className={cn(
            "px-3 py-2 text-xs font-medium border-b-2 transition-colors -mb-px",
            active === tab.key
              ? "border-brand-primary text-brand-primary"
              : "border-transparent text-neutral-400 hover:text-neutral-600"
          )}
        >
          {tab.label}
          {tab.count != null && tab.count > 0 && (
            <span className="ml-1.5 text-[10px] bg-neutral-100 text-neutral-500 rounded-full px-1.5 py-0.5">
              {tab.count}
            </span>
          )}
        </button>
      ))}
    </div>
  );
}
