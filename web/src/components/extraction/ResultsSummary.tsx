"use client";

import type { PipelineOutput } from "@/lib/api";
import { formatDuration, confidenceColor } from "@/lib/utils";
import { Card, CardBody } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";

interface ResultsSummaryProps {
  result: PipelineOutput;
}

export function ResultsSummary({ result }: ResultsSummaryProps) {
  const totalCells = result.tables.reduce((acc, t) => acc + t.cells.length, 0);
  const totalFlagged = result.tables.reduce((acc, t) => acc + t.flagged_cells.length, 0);
  const totalFootnotes = result.tables.reduce((acc, t) => acc + t.footnotes.length, 0);
  const avgConfidence = result.tables.length > 0
    ? result.tables.reduce((acc, t) => acc + t.overall_confidence, 0) / result.tables.length
    : 0;

  const stats = [
    {
      label: "Tables Found",
      value: result.tables.length,
      icon: (
        <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M3.375 19.5h17.25m-17.25 0a1.125 1.125 0 01-1.125-1.125M3.375 19.5h7.5c.621 0 1.125-.504 1.125-1.125m-9.75 0V5.625m0 12.75v-1.5c0-.621.504-1.125 1.125-1.125m18.375 2.625V5.625m0 12.75c0 .621-.504 1.125-1.125 1.125m1.125-1.125v-1.5c0-.621-.504-1.125-1.125-1.125m0 3.75h-7.5A1.125 1.125 0 0112 18.375m9.75-12.75c0-.621-.504-1.125-1.125-1.125H3.375c-.621 0-1.125.504-1.125 1.125m19.5 0v1.5c0 .621-.504 1.125-1.125 1.125M2.25 5.625v1.5c0 .621.504 1.125 1.125 1.125m0 0h17.25m-17.25 0h7.5c.621 0 1.125.504 1.125 1.125M3.375 8.25c-.621 0-1.125.504-1.125 1.125v1.5c0 .621.504 1.125 1.125 1.125m17.25-3.75h-7.5c-.621 0-1.125.504-1.125 1.125m8.625-1.125c.621 0 1.125.504 1.125 1.125v1.5c0 .621-.504 1.125-1.125 1.125m-17.25 0h7.5m-7.5 0c-.621 0-1.125.504-1.125 1.125v1.5c0 .621.504 1.125 1.125 1.125M12 10.875v-1.5m0 1.5c0 .621-.504 1.125-1.125 1.125M12 10.875c0 .621.504 1.125 1.125 1.125m-2.25 0c.621 0 1.125.504 1.125 1.125M13.125 12h7.5m-7.5 0c-.621 0-1.125.504-1.125 1.125M20.625 12c.621 0 1.125.504 1.125 1.125v1.5c0 .621-.504 1.125-1.125 1.125m-17.25 0h7.5M12 14.625v-1.5m0 1.5c0 .621-.504 1.125-1.125 1.125M12 14.625c0 .621.504 1.125 1.125 1.125m-2.25 0c.621 0 1.125.504 1.125 1.125m0 0v1.5" />
        </svg>
      ),
      color: "text-brand-primary",
      bg: "bg-sky-50",
    },
    {
      label: "Cells Extracted",
      value: totalCells,
      icon: (
        <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M3.75 6A2.25 2.25 0 016 3.75h2.25A2.25 2.25 0 0110.5 6v2.25a2.25 2.25 0 01-2.25 2.25H6a2.25 2.25 0 01-2.25-2.25V6zm0 9.75A2.25 2.25 0 016 13.5h2.25a2.25 2.25 0 012.25 2.25V18a2.25 2.25 0 01-2.25 2.25H6A2.25 2.25 0 013.75 18v-2.25zM13.5 6a2.25 2.25 0 012.25-2.25H18A2.25 2.25 0 0120.25 6v2.25A2.25 2.25 0 0118 10.5h-2.25a2.25 2.25 0 01-2.25-2.25V6zM13.5 15.75a2.25 2.25 0 012.25-2.25H18a2.25 2.25 0 012.25 2.25V18A2.25 2.25 0 0118 20.25h-2.25A2.25 2.25 0 0113.5 18v-2.25z" />
        </svg>
      ),
      color: "text-emerald-600",
      bg: "bg-emerald-50",
    },
    {
      label: "Avg Confidence",
      value: `${(avgConfidence * 100).toFixed(0)}%`,
      icon: (
        <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M9 12.75L11.25 15 15 9.75m-3-7.036A11.959 11.959 0 013.598 6 11.99 11.99 0 003 9.749c0 5.592 3.824 10.29 9 11.623 5.176-1.332 9-6.03 9-11.622 0-1.31-.21-2.571-.598-3.751h-.152c-3.196 0-6.1-1.248-8.25-3.285z" />
        </svg>
      ),
      color: confidenceColor(avgConfidence),
      bg: avgConfidence >= 0.85 ? "bg-emerald-50" : "bg-amber-50",
    },
    {
      label: "Needs Review",
      value: totalFlagged,
      icon: (
        <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126z" />
        </svg>
      ),
      color: totalFlagged > 0 ? "text-amber-600" : "text-emerald-600",
      bg: totalFlagged > 0 ? "bg-amber-50" : "bg-emerald-50",
    },
  ];

  return (
    <div className="space-y-4">
      {/* KPI Cards */}
      <div className="grid grid-cols-4 gap-4">
        {stats.map((stat) => (
          <Card key={stat.label}>
            <CardBody className="flex items-center gap-3">
              <div className={`w-10 h-10 rounded-lg ${stat.bg} flex items-center justify-center ${stat.color}`}>
                {stat.icon}
              </div>
              <div>
                <div className="text-xl font-semibold text-neutral-800">{stat.value}</div>
                <div className="text-xs text-neutral-400">{stat.label}</div>
              </div>
            </CardBody>
          </Card>
        ))}
      </div>

      {/* Meta info */}
      <div className="flex items-center gap-4 text-xs text-neutral-400">
        <span>{result.total_pages} pages</span>
        <span>&middot;</span>
        <span>{formatDuration(result.processing_time_seconds)} processing time</span>
        <span>&middot;</span>
        <span>{totalFootnotes} footnotes resolved</span>
        <span>&middot;</span>
        <span>Pipeline v{result.pipeline_version}</span>
        {result.warnings.length > 0 && (
          <>
            <span>&middot;</span>
            <Badge variant="warning">{result.warnings.length} warning{result.warnings.length !== 1 ? "s" : ""}</Badge>
          </>
        )}
      </div>
    </div>
  );
}
