"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { listProtocols, getProtocol, type ProtocolSummary, type ProtocolFull } from "@/lib/api";
import { TopBar } from "@/components/layout/TopBar";
import { Card, CardHeader, CardBody } from "@/components/ui/Card";
import { cn } from "@/lib/utils";

interface ProtocolQualityRow {
  protocol_id: string;
  name: string;
  soaCells: number;
  corrections: number;
  correctionRate: number;
  procedures: number;
  footnotes: number;
  visionVerified: number;
}

export default function QualityDashboardPage() {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [rows, setRows] = useState<ProtocolQualityRow[]>([]);
  const [totals, setTotals] = useState({
    protocols: 0,
    totalCells: 0,
    overallCorrectionRate: 0,
    visionVerified: 0,
  });

  useEffect(() => {
    async function loadData() {
      try {
        const protocols = await listProtocols();
        const qualityRows: ProtocolQualityRow[] = [];

        // For each protocol, attempt to fetch full data for quality metrics
        const results = await Promise.allSettled(
          protocols.map((p) => getProtocol(p.protocol_id))
        );

        let totalCells = 0;
        let totalCorrections = 0;
        let totalVision = 0;

        results.forEach((result, index) => {
          if (result.status !== "fulfilled") return;
          const protocol = result.value;
          const soaCells = protocol.tables.reduce((sum, t) => sum + t.cells.length, 0);
          const corrections = protocol.tables.reduce(
            (sum, t) => sum + t.review_items.length,
            0
          );
          const footnotes = protocol.tables.reduce(
            (sum, t) => sum + t.footnotes.length,
            0
          );
          const procedures = protocol.procedures.length;
          const qs = protocol.quality_summary || {};
          const vision = typeof qs.vision_verified === "number" ? qs.vision_verified : 0;

          totalCells += soaCells;
          totalCorrections += corrections;
          totalVision += vision;

          qualityRows.push({
            protocol_id: protocol.protocol_id,
            name:
              protocol.metadata.short_title ||
              protocol.metadata.title ||
              protocol.document_name,
            soaCells,
            corrections,
            correctionRate: soaCells > 0 ? corrections / soaCells : 0,
            procedures,
            footnotes,
            visionVerified: vision,
          });
        });

        // Sort by correction rate descending
        qualityRows.sort((a, b) => b.correctionRate - a.correctionRate);

        setRows(qualityRows);
        setTotals({
          protocols: qualityRows.length,
          totalCells,
          overallCorrectionRate: totalCells > 0 ? totalCorrections / totalCells : 0,
          visionVerified: totalVision,
        });
      } catch (e: unknown) {
        setError(e instanceof Error ? e.message : "Failed to load quality data");
      } finally {
        setLoading(false);
      }
    }

    loadData();
  }, []);

  return (
    <div>
      <TopBar title="Quality Dashboard" subtitle="Extraction quality metrics across all protocols" />

      <div className="p-6 space-y-6">
        {/* Header */}
        <div>
          <h2 className="text-xl font-bold text-neutral-800">Quality Dashboard</h2>
          <p className="text-sm text-neutral-500 mt-1">
            Monitor extraction accuracy and review metrics across all stored protocols
          </p>
        </div>

        {/* Loading state */}
        {loading && (
          <div className="flex items-center justify-center py-16">
            <div className="text-center">
              <div className="w-8 h-8 border-2 border-brand-primary border-t-transparent rounded-full animate-spin mx-auto mb-3" />
              <p className="text-sm text-neutral-400">Loading quality metrics...</p>
            </div>
          </div>
        )}

        {/* Error state */}
        {error && !loading && (
          <Card>
            <CardBody className="p-8 text-center">
              <p className="text-sm font-medium text-neutral-700">Failed to load quality data</p>
              <p className="text-xs text-neutral-400 mt-1">{error}</p>
            </CardBody>
          </Card>
        )}

        {!loading && !error && (
          <>
            {/* Overview cards */}
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
              <OverviewCard
                label="Total Protocols"
                value={String(totals.protocols)}
                color="text-brand-primary"
                bg="bg-sky-50"
              />
              <OverviewCard
                label="Total Cells Verified"
                value={totals.totalCells.toLocaleString()}
                color="text-emerald-600"
                bg="bg-emerald-50"
              />
              <OverviewCard
                label="Overall Correction Rate"
                value={`${(totals.overallCorrectionRate * 100).toFixed(1)}%`}
                color={totals.overallCorrectionRate > 0.05 ? "text-amber-600" : "text-emerald-600"}
                bg={totals.overallCorrectionRate > 0.05 ? "bg-amber-50" : "bg-emerald-50"}
              />
              <OverviewCard
                label="Vision-Verified Cells"
                value={totals.visionVerified.toLocaleString()}
                color="text-purple-600"
                bg="bg-purple-50"
              />
            </div>

            {/* Empty state */}
            {rows.length === 0 ? (
              <Card>
                <CardBody className="p-12 text-center">
                  <div className="w-14 h-14 rounded-full bg-neutral-100 flex items-center justify-center mx-auto mb-4">
                    <svg className="w-7 h-7 text-neutral-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M3 13.125C3 12.504 3.504 12 4.125 12h2.25c.621 0 1.125.504 1.125 1.125v6.75C7.5 20.496 6.996 21 6.375 21h-2.25A1.125 1.125 0 013 19.875v-6.75zM9.75 8.625c0-.621.504-1.125 1.125-1.125h2.25c.621 0 1.125.504 1.125 1.125v11.25c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 01-1.125-1.125V8.625zM16.5 4.125c0-.621.504-1.125 1.125-1.125h2.25C20.496 3 21 3.504 21 4.125v15.75c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 01-1.125-1.125V4.125z" />
                    </svg>
                  </div>
                  <h3 className="text-base font-semibold text-neutral-700">No quality data yet</h3>
                  <p className="text-sm text-neutral-400 mt-1">
                    Process protocols to generate quality metrics.
                  </p>
                  <Link
                    href="/"
                    className="inline-flex items-center gap-2 px-4 py-2 bg-brand-primary text-white text-sm font-medium rounded-lg hover:bg-brand-french transition-colors mt-6"
                  >
                    Upload Protocol
                  </Link>
                </CardBody>
              </Card>
            ) : (
              /* Protocol accuracy table */
              <Card>
                <CardHeader>
                  <h3 className="text-sm font-semibold text-neutral-800">
                    Protocol Accuracy
                  </h3>
                  <p className="text-xs text-neutral-400 mt-0.5">
                    Sorted by correction rate (highest first)
                  </p>
                </CardHeader>
                <div className="overflow-x-auto">
                  <table className="w-full text-xs">
                    <thead>
                      <tr className="bg-neutral-50">
                        <th className="px-4 py-2.5 text-left font-medium text-neutral-500 border-b border-neutral-200 sticky top-0 bg-neutral-50">
                          Protocol
                        </th>
                        <th className="px-4 py-2.5 text-right font-medium text-neutral-500 border-b border-neutral-200 sticky top-0 bg-neutral-50">
                          SoA Cells
                        </th>
                        <th className="px-4 py-2.5 text-right font-medium text-neutral-500 border-b border-neutral-200 sticky top-0 bg-neutral-50">
                          Corrections
                        </th>
                        <th className="px-4 py-2.5 text-right font-medium text-neutral-500 border-b border-neutral-200 sticky top-0 bg-neutral-50">
                          Rate
                        </th>
                        <th className="px-4 py-2.5 text-right font-medium text-neutral-500 border-b border-neutral-200 sticky top-0 bg-neutral-50">
                          Procedures
                        </th>
                        <th className="px-4 py-2.5 text-right font-medium text-neutral-500 border-b border-neutral-200 sticky top-0 bg-neutral-50">
                          Footnotes
                        </th>
                        <th className="px-4 py-2.5 text-right font-medium text-neutral-500 border-b border-neutral-200 sticky top-0 bg-neutral-50">
                          Vision
                        </th>
                      </tr>
                    </thead>
                    <tbody>
                      {rows.map((row, i) => (
                        <tr
                          key={row.protocol_id}
                          className={cn(
                            "hover:bg-sky-50/50 transition-colors cursor-pointer",
                            i % 2 === 1 && "bg-neutral-50/30"
                          )}
                          onClick={() => {
                            window.location.href = `/protocols/${row.protocol_id}`;
                          }}
                        >
                          <td className="px-4 py-2.5 text-neutral-800 font-medium border-b border-neutral-100 max-w-xs truncate">
                            {row.name}
                          </td>
                          <td className="px-4 py-2.5 text-right text-neutral-600 font-mono border-b border-neutral-100">
                            {row.soaCells.toLocaleString()}
                          </td>
                          <td className="px-4 py-2.5 text-right font-mono border-b border-neutral-100">
                            <span className={row.corrections > 0 ? "text-amber-600 font-medium" : "text-neutral-400"}>
                              {row.corrections}
                            </span>
                          </td>
                          <td className="px-4 py-2.5 text-right border-b border-neutral-100">
                            <span
                              className={cn(
                                "px-2 py-0.5 rounded text-xs font-medium font-mono",
                                row.correctionRate > 0.05
                                  ? "bg-red-100 text-red-700"
                                  : row.correctionRate > 0.02
                                    ? "bg-amber-100 text-amber-700"
                                    : "bg-emerald-100 text-emerald-700"
                              )}
                            >
                              {(row.correctionRate * 100).toFixed(1)}%
                            </span>
                          </td>
                          <td className="px-4 py-2.5 text-right text-neutral-600 font-mono border-b border-neutral-100">
                            {row.procedures}
                          </td>
                          <td className="px-4 py-2.5 text-right text-neutral-600 font-mono border-b border-neutral-100">
                            {row.footnotes}
                          </td>
                          <td className="px-4 py-2.5 text-right text-neutral-600 font-mono border-b border-neutral-100">
                            {row.visionVerified || "—"}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </Card>
            )}
          </>
        )}
      </div>
    </div>
  );
}

function OverviewCard({
  label,
  value,
  color,
  bg,
}: {
  label: string;
  value: string;
  color: string;
  bg: string;
}) {
  return (
    <Card>
      <CardBody className="p-5">
        <p className="text-[11px] text-neutral-400 uppercase tracking-wide font-medium mb-2">
          {label}
        </p>
        <div className="flex items-end gap-2">
          <span className={cn("text-2xl font-bold font-mono", color)}>{value}</span>
          <span className={cn("w-2 h-2 rounded-full mb-2", bg)} />
        </div>
      </CardBody>
    </Card>
  );
}
