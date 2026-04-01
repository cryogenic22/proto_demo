"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { SideNav } from "./SideNav";
import { FeedbackWidget } from "../FeedbackWidget";
import { getJobStatus } from "@/lib/api";

function ActiveJobBanner() {
  const pathname = usePathname();
  const [job, setJob] = useState<{
    jobId: string;
    fileName: string;
    progress: number;
    message: string;
  } | null>(null);

  useEffect(() => {
    let cancelled = false;

    const check = async () => {
      const saved = localStorage.getItem("active_job");
      if (!saved) {
        setJob(null);
        return;
      }
      try {
        const { jobId, fileName } = JSON.parse(saved);
        const s = await getJobStatus(jobId);
        if (cancelled) return;
        if (s.status === "processing" || s.status === "pending") {
          setJob({ jobId, fileName, progress: s.progress, message: s.message });
        } else {
          setJob(null);
        }
      } catch {
        // Job not found (404) or network error — clear stale job
        localStorage.removeItem("active_job");
        if (!cancelled) setJob(null);
      }
    };

    check();
    const interval = setInterval(check, 3000);
    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, []);

  // Don't show banner on the upload page (it has its own ProcessingStatus)
  if (!job || pathname === "/") return null;

  return (
    <Link
      href="/"
      className="block bg-brand-primary text-white px-4 py-2 text-xs flex items-center gap-3 hover:bg-brand-french transition-colors"
    >
      <div className="w-3.5 h-3.5 border-2 border-white border-t-transparent rounded-full animate-spin shrink-0" />
      <span className="font-medium truncate">
        Extracting {job.fileName} — {job.progress}%
      </span>
      <span className="text-white/70 shrink-0">{job.message}</span>
      <span className="ml-auto text-white/70 shrink-0">Click to view</span>
    </Link>
  );
}

export function AppShell({ children }: { children: React.ReactNode }) {
  return (
    <div className="min-h-screen bg-neutral-50">
      <SideNav />
      <div className="pl-60 transition-all duration-200">
        <ActiveJobBanner />
        {children}
      </div>
      <FeedbackWidget />
    </div>
  );
}
