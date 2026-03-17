"use client";

import { SideNav } from "./SideNav";

export function AppShell({ children }: { children: React.ReactNode }) {
  return (
    <div className="min-h-screen bg-neutral-50">
      <SideNav />
      <div className="pl-60 transition-all duration-200">
        {children}
      </div>
    </div>
  );
}
