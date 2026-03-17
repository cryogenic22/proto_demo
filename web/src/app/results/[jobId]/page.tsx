"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { TopBar } from "@/components/layout/TopBar";
import { ResultsSummary } from "@/components/extraction/ResultsSummary";
import { TableView } from "@/components/extraction/TableView";
import { getJobResult, type PipelineOutput } from "@/lib/api";
import { Card, CardBody } from "@/components/ui/Card";

export default function ResultsPage() {
  const params = useParams();
  const jobId = params.jobId as string;
  const [result, setResult] = useState<PipelineOutput | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getJobResult(jobId)
      .then(setResult)
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, [jobId]);

  if (loading) {
    return (
      <>
        <TopBar title="Loading Results..." />
        <main className="p-6 flex justify-center py-20">
          <div className="w-6 h-6 border-2 border-brand-primary border-t-transparent rounded-full animate-spin" />
        </main>
      </>
    );
  }

  if (error || !result) {
    return (
      <>
        <TopBar title="Error" />
        <main className="p-6 max-w-2xl mx-auto">
          <Card>
            <CardBody className="text-center py-12">
              <p className="text-sm text-red-600">{error || "Result not found"}</p>
            </CardBody>
          </Card>
        </main>
      </>
    );
  }

  return (
    <>
      <TopBar
        title={result.document_name}
        subtitle={`${result.tables.length} tables extracted from ${result.total_pages} pages`}
      />

      <main className="p-6 space-y-6">
        {/* Summary KPIs */}
        <ResultsSummary result={result} />

        {/* Warnings */}
        {result.warnings.length > 0 && (
          <div className="bg-amber-50 border border-amber-200 rounded-xl px-5 py-4">
            <p className="text-sm font-medium text-amber-800 mb-2">Warnings</p>
            <ul className="text-xs text-amber-700 space-y-1">
              {result.warnings.map((w, i) => (
                <li key={i} className="flex items-start gap-2">
                  <span className="text-amber-500 mt-0.5">&#8226;</span>
                  {w}
                </li>
              ))}
            </ul>
          </div>
        )}

        {/* Tables */}
        {result.tables.map((table) => (
          <TableView key={table.table_id} table={table} />
        ))}

        {result.tables.length === 0 && (
          <Card>
            <CardBody className="text-center py-16">
              <div className="w-16 h-16 rounded-full bg-neutral-100 flex items-center justify-center mx-auto mb-4">
                <svg className="w-8 h-8 text-neutral-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M3.375 19.5h17.25m-17.25 0a1.125 1.125 0 01-1.125-1.125M3.375 19.5h7.5c.621 0 1.125-.504 1.125-1.125m-9.75 0V5.625m0 12.75v-1.5c0-.621.504-1.125 1.125-1.125m18.375 2.625V5.625m0 12.75c0 .621-.504 1.125-1.125 1.125m1.125-1.125v-1.5c0-.621-.504-1.125-1.125-1.125" />
                </svg>
              </div>
              <p className="text-sm font-medium text-neutral-700">No tables found</p>
              <p className="text-xs text-neutral-400 mt-1">
                The document was processed but no tables were detected.
              </p>
            </CardBody>
          </Card>
        )}

        {/* Raw JSON export */}
        <div className="flex justify-end">
          <button
            onClick={() => {
              const blob = new Blob([JSON.stringify(result, null, 2)], { type: "application/json" });
              const url = URL.createObjectURL(blob);
              const a = document.createElement("a");
              a.href = url;
              a.download = `${result.document_name.replace(".pdf", "")}_extraction.json`;
              a.click();
              URL.revokeObjectURL(url);
            }}
            className="flex items-center gap-2 px-4 py-2 text-xs font-medium text-neutral-600 bg-white border border-neutral-200 rounded-lg hover:bg-neutral-50 transition-colors"
          >
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5M16.5 12L12 16.5m0 0L7.5 12m4.5 4.5V3" />
            </svg>
            Export JSON
          </button>
        </div>
      </main>
    </>
  );
}
