"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { getJobStatus, type JobStatus } from "@/lib/api";
import { formatBytes, formatDuration } from "@/lib/utils";
import { Card, CardBody } from "@/components/ui/Card";
import { Progress } from "@/components/ui/Progress";
import { Badge } from "@/components/ui/Badge";

interface ProcessingStatusProps {
  jobId: string;
  fileName: string;
  fileSize: number;
}

const STAGE_MESSAGES: Record<number, string> = {
  0: "Queued for processing...",
  5: "Initializing pipeline...",
  10: "Ingesting PDF pages...",
  20: "Detecting tables...",
  30: "Analyzing table structure...",
  50: "Extracting cell values (pass 1)...",
  60: "Extracting cell values (pass 2)...",
  70: "Resolving footnotes...",
  80: "Running challenger validation...",
  90: "Reconciling results...",
  95: "Finalizing output...",
  100: "Complete!",
};

export function ProcessingStatus({ jobId, fileName, fileSize }: ProcessingStatusProps) {
  const router = useRouter();
  const [status, setStatus] = useState<JobStatus | null>(null);
  const [elapsed, setElapsed] = useState(0);

  useEffect(() => {
    const startTime = Date.now();
    const timer = setInterval(() => setElapsed((Date.now() - startTime) / 1000), 1000);
    return () => clearInterval(timer);
  }, []);

  useEffect(() => {
    let cancelled = false;

    const poll = async () => {
      try {
        const s = await getJobStatus(jobId);
        if (!cancelled) {
          setStatus(s);
          if (s.status === "completed") {
            setTimeout(() => router.push(`/results/${jobId}`), 800);
          }
          if (s.status !== "completed" && s.status !== "failed") {
            setTimeout(poll, 1500);
          }
        }
      } catch {
        if (!cancelled) setTimeout(poll, 3000);
      }
    };

    poll();
    return () => { cancelled = true; };
  }, [jobId, router]);

  const progress = status?.progress ?? 0;
  const isFailed = status?.status === "failed";
  const isComplete = status?.status === "completed";

  return (
    <Card className="max-w-2xl mx-auto">
      <CardBody className="space-y-5">
        {/* File info */}
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-lg bg-red-50 flex items-center justify-center">
            <svg className="w-5 h-5 text-red-500" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 14.25v-2.625a3.375 3.375 0 00-3.375-3.375h-1.5A1.125 1.125 0 0113.5 7.125v-1.5a3.375 3.375 0 00-3.375-3.375H8.25m2.25 0H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 00-9-9z" />
            </svg>
          </div>
          <div className="flex-1 min-w-0">
            <p className="text-sm font-medium text-neutral-800 truncate">{fileName}</p>
            <p className="text-xs text-neutral-400">{formatBytes(fileSize)}</p>
          </div>
          <Badge variant={isFailed ? "danger" : isComplete ? "success" : "brand"}>
            {isFailed ? "Failed" : isComplete ? "Complete" : "Processing"}
          </Badge>
        </div>

        {/* Progress bar */}
        <div className="space-y-2">
          <Progress
            value={progress}
            variant={isFailed ? "danger" : isComplete ? "success" : "brand"}
          />
          <div className="flex justify-between text-xs text-neutral-400">
            <span>{status?.message || "Starting..."}</span>
            <span>{progress}%</span>
          </div>
        </div>

        {/* Elapsed time */}
        <div className="text-xs text-neutral-400 text-center">
          Elapsed: {formatDuration(elapsed)}
        </div>

        {/* Error message */}
        {isFailed && status?.error && (
          <div className="bg-red-50 rounded-lg px-4 py-3 text-sm text-red-700">
            <p className="font-medium mb-1">Extraction failed</p>
            <p className="text-xs">{status.error}</p>
          </div>
        )}
      </CardBody>
    </Card>
  );
}
