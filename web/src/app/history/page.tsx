"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { TopBar } from "@/components/layout/TopBar";
import { listJobs, type JobStatus } from "@/lib/api";
import { Card, CardBody, CardHeader } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { formatDuration } from "@/lib/utils";

export default function HistoryPage() {
  const [jobs, setJobs] = useState<JobStatus[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    listJobs()
      .then(setJobs)
      .catch(() => {})
      .finally(() => setLoading(false));

    const interval = setInterval(() => {
      listJobs().then(setJobs).catch(() => {});
    }, 5000);
    return () => clearInterval(interval);
  }, []);

  const statusVariant = (s: string) => {
    switch (s) {
      case "completed": return "success" as const;
      case "failed": return "danger" as const;
      case "processing": return "brand" as const;
      default: return "neutral" as const;
    }
  };

  return (
    <>
      <TopBar title="Extraction History" subtitle="All protocol extraction jobs" />

      <main className="p-6 max-w-4xl mx-auto">
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <h2 className="text-sm font-semibold text-neutral-800">Recent Extractions</h2>
              <span className="text-xs text-neutral-400">{jobs.length} jobs</span>
            </div>
          </CardHeader>

          {loading ? (
            <CardBody className="flex justify-center py-12">
              <div className="w-5 h-5 border-2 border-brand-primary border-t-transparent rounded-full animate-spin" />
            </CardBody>
          ) : jobs.length === 0 ? (
            <CardBody className="text-center py-12">
              <p className="text-sm text-neutral-400">No extractions yet. Upload a protocol to get started.</p>
            </CardBody>
          ) : (
            <div className="divide-y divide-neutral-100">
              {jobs.map((job) => (
                <div
                  key={job.job_id}
                  className="px-5 py-3.5 flex items-center gap-4 hover:bg-neutral-50/50 transition-colors"
                >
                  {/* File icon */}
                  <div className="w-9 h-9 rounded-lg bg-red-50 flex items-center justify-center shrink-0">
                    <svg className="w-4.5 h-4.5 text-red-500" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 14.25v-2.625a3.375 3.375 0 00-3.375-3.375h-1.5A1.125 1.125 0 0113.5 7.125v-1.5a3.375 3.375 0 00-3.375-3.375H8.25m2.25 0H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 00-9-9z" />
                    </svg>
                  </div>

                  {/* Info */}
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium text-neutral-800 truncate">
                      {job.document_name}
                    </p>
                    <p className="text-xs text-neutral-400 mt-0.5">
                      {new Date(job.created_at * 1000).toLocaleString()} &middot; {job.message}
                    </p>
                  </div>

                  {/* Status */}
                  <Badge variant={statusVariant(job.status)}>
                    {job.status}
                  </Badge>

                  {/* View button */}
                  {job.status === "completed" && (
                    <Link
                      href={`/results/${job.job_id}`}
                      className="text-xs font-medium text-brand-primary hover:underline shrink-0"
                    >
                      View Results
                    </Link>
                  )}
                </div>
              ))}
            </div>
          )}
        </Card>
      </main>
    </>
  );
}
