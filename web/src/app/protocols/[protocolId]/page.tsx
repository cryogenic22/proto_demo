"use client";

import { useEffect, useState, useMemo } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import {
  getProtocol,
  type ProtocolFull,
  type ExtractedTable,
} from "@/lib/api";
import { TopBar } from "@/components/layout/TopBar";
import { Card, CardHeader, CardBody } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { Tabs } from "@/components/ui/Tabs";
import { ProtocolMetaCard } from "@/components/protocol/ProtocolMetaCard";
import { SoAReviewAssistant } from "@/components/protocol/SoAReviewAssistant";
import { ProtocolTrustDashboard } from "@/components/protocol/ProtocolTrustDashboard";
import { cn } from "@/lib/utils";

function confidenceColor(c: number) {
  if (c >= 0.95) return "text-emerald-700 bg-emerald-100";
  if (c >= 0.85) return "text-sky-700 bg-sky-100";
  if (c >= 0.70) return "text-amber-700 bg-amber-100";
  return "text-red-700 bg-red-100";
}

export default function ProtocolWorkspacePage() {
  const params = useParams();
  const protocolId = params.protocolId as string;

  const [protocol, setProtocol] = useState<ProtocolFull | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState("tables");
  const [expandedTable, setExpandedTable] = useState<ExtractedTable | null>(null);
  const [pdfAvailable, setPdfAvailable] = useState(false);
  const [showPdfViewer, setShowPdfViewer] = useState(false);
  const [pdfPage, setPdfPage] = useState(0);

  const API = process.env.NEXT_PUBLIC_API_URL || "";

  useEffect(() => {
    getProtocol(protocolId)
      .then(setProtocol)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
    // Check if PDF is available
    fetch(`${API}/api/protocols/${protocolId}/page-image/0`)
      .then((r) => setPdfAvailable(r.ok))
      .catch(() => setPdfAvailable(false));
  }, [protocolId]);

  // Stats
  const stats = useMemo(() => {
    if (!protocol) return null;
    const allCells = protocol.tables.flatMap((t) => t.cells || []);
    const totalFlagged = protocol.tables.reduce((s, t) => s + (t.flagged_cells?.length || 0), 0);
    const allProcs = protocol.tables.flatMap((t) => t.procedures || []);
    const uniqueProcs = new Set(allProcs.map((p) => p.canonical_name));
    const totalFn = protocol.tables.reduce((s, t) => s + (t.footnotes?.length || 0), 0);
    return {
      tables: protocol.tables.length,
      cells: allCells.length,
      flagged: totalFlagged,
      procedures: uniqueProcs.size,
      footnotes: totalFn,
      sections: protocol.sections.length,
      budgetLines: protocol.budget_lines.length,
    };
  }, [protocol]);

  if (loading) {
    return (
      <div>
        <TopBar title="Loading..." subtitle="Fetching protocol data" />
        <div className="flex items-center justify-center h-[calc(100vh-3.5rem)]">
          <div className="w-8 h-8 border-2 border-brand-primary border-t-transparent rounded-full animate-spin" />
        </div>
      </div>
    );
  }

  if (error || !protocol) {
    return (
      <div>
        <TopBar title="Error" subtitle="Could not load protocol" />
        <div className="p-6">
          <Card>
            <CardBody className="p-8 text-center">
              <p className="text-sm font-medium text-neutral-700">Failed to load protocol</p>
              <p className="text-xs text-neutral-400 mt-1">{error}</p>
              <Link href="/protocols" className="text-sm text-brand-primary hover:underline mt-4 inline-block">&larr; Back to library</Link>
            </CardBody>
          </Card>
        </div>
      </div>
    );
  }

  // SoA Review Assistant — full-screen overlay
  if (expandedTable) {
    const tableIdx = protocol.tables.indexOf(expandedTable);
    return (
      <div className="fixed inset-0 z-50 bg-neutral-50">
        <SoAReviewAssistant
          table={expandedTable}
          protocolId={protocolId}
          onClose={() => setExpandedTable(null)}
          tableIndex={tableIdx}
          totalTables={protocol.tables.length}
          onPrevTable={tableIdx > 0 ? () => setExpandedTable(protocol.tables[tableIdx - 1]) : undefined}
          onNextTable={tableIdx < protocol.tables.length - 1 ? () => setExpandedTable(protocol.tables[tableIdx + 1]) : undefined}
        />
      </div>
    );
  }

  const tabs = [
    { key: "tables", label: "SoA Tables", count: protocol.tables.length },
    { key: "procedures", label: "Procedures", count: stats?.procedures },
    { key: "overview", label: "Overview" },
  ];

  return (
    <div>
      <TopBar
        title={protocol.metadata.short_title || protocol.metadata.title || protocol.document_name}
        subtitle={`${protocol.metadata.protocol_number || ""} · ${protocol.total_pages} pages`}
      >
        {pdfAvailable && (
          <button
            onClick={() => setShowPdfViewer(!showPdfViewer)}
            className={cn(
              "px-3 py-1.5 text-xs font-medium rounded-lg transition-colors flex items-center gap-1.5",
              showPdfViewer
                ? "bg-brand-primary text-white"
                : "border border-neutral-200 text-neutral-600 hover:bg-neutral-50"
            )}
          >
            <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 14.25v-2.625a3.375 3.375 0 00-3.375-3.375h-1.5A1.125 1.125 0 0113.5 7.125v-1.5a3.375 3.375 0 00-3.375-3.375H8.25m0 12.75h7.5m-7.5 3H12M10.5 2.25H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 00-9-9z" />
            </svg>
            {showPdfViewer ? "Hide PDF" : "View Source PDF"}
          </button>
        )}
      </TopBar>

      <div className="flex h-[calc(100vh-3.5rem)]">
        {/* PDF Viewer panel */}
        {showPdfViewer && pdfAvailable && (
          <div className="w-[420px] border-r border-neutral-200 bg-neutral-100 flex flex-col shrink-0">
            <div className="px-3 py-2 bg-white border-b border-neutral-200 flex items-center justify-between">
              <span className="text-xs font-semibold text-neutral-700">Source PDF</span>
              <div className="flex items-center gap-1">
                <button onClick={() => setPdfPage(Math.max(0, pdfPage - 1))} className="p-1 rounded hover:bg-neutral-100 text-neutral-500 text-xs">
                  <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}><path strokeLinecap="round" strokeLinejoin="round" d="M15.75 19.5L8.25 12l7.5-7.5" /></svg>
                </button>
                <span className="text-xs text-neutral-500 font-mono min-w-[50px] text-center">Page {pdfPage}</span>
                <button onClick={() => setPdfPage(pdfPage + 1)} className="p-1 rounded hover:bg-neutral-100 text-neutral-500 text-xs">
                  <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}><path strokeLinecap="round" strokeLinejoin="round" d="M8.25 4.5l7.5 7.5-7.5 7.5" /></svg>
                </button>
                <button onClick={() => setShowPdfViewer(false)} className="p-1 rounded hover:bg-neutral-100 text-neutral-400 ml-1">
                  <svg width="14" height="14" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"><path d="M4 4L12 12M12 4L4 12" /></svg>
                </button>
              </div>
            </div>
            <div className="flex-1 overflow-auto p-2">
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img
                key={pdfPage}
                src={`${API}/api/protocols/${protocolId}/page-image/${pdfPage}`}
                alt={`Page ${pdfPage}`}
                className="w-full rounded shadow-sm bg-white"
                onError={(e) => (e.currentTarget.src = "")}
              />
            </div>
          </div>
        )}

        {/* Main content */}
        <div className="flex-1 flex flex-col overflow-hidden bg-white min-w-0">
          <div className="px-4 pt-3 border-b border-neutral-200 bg-white">
            <Tabs tabs={tabs} active={activeTab} onChange={setActiveTab} className="border-b-0" />
          </div>

          <div className="flex-1 overflow-y-auto">
            {/* Tables tab — the primary view */}
            {activeTab === "tables" && (
              <div className="p-4">
                {protocol.tables.length === 0 ? (
                  <div className="text-center py-16">
                    <p className="text-sm font-medium text-neutral-700">No SoA tables extracted</p>
                    <p className="text-xs text-neutral-400 mt-1">Upload the protocol to extract Schedule of Activities tables.</p>
                  </div>
                ) : (
                  <div className="space-y-3">
                    {protocol.tables.map((table) => {
                      const cells = table.cells || [];
                      const footnotes = table.footnotes || [];
                      const procedures = table.procedures || [];
                      const flagged = table.flagged_cells || [];
                      const confidence = table.overall_confidence || 0;
                      return (
                        <button
                          key={table.table_id}
                          onClick={() => setExpandedTable(table)}
                          className="w-full text-left"
                        >
                          <Card className="hover:shadow-md hover:border-brand-primary/30 transition-all cursor-pointer">
                            <CardBody className="p-4">
                              <div className="flex items-center justify-between mb-2">
                                <div className="flex items-center gap-2">
                                  <Badge variant="brand">SoA</Badge>
                                  <h3 className="text-sm font-semibold text-neutral-800">
                                    {table.title || `Table ${table.table_id}`}
                                  </h3>
                                </div>
                                <div className="flex items-center gap-2">
                                  <span className={cn("text-xs font-medium px-2 py-0.5 rounded", confidenceColor(confidence))}>
                                    {(confidence * 100).toFixed(0)}%
                                  </span>
                                  <svg className="w-4 h-4 text-neutral-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                                    <path strokeLinecap="round" strokeLinejoin="round" d="M8.25 4.5l7.5 7.5-7.5 7.5" />
                                  </svg>
                                </div>
                              </div>
                              <div className="flex items-center gap-4 text-xs text-neutral-500">
                                <span>Pages {(table.source_pages || []).join(", ")}</span>
                                <span>{table.schema_info?.num_rows || "?"} rows × {table.schema_info?.num_cols || "?"} cols</span>
                                <span>{cells.length} cells</span>
                                {footnotes.length > 0 && <span>{footnotes.length} footnotes</span>}
                                {procedures.length > 0 && <span>{procedures.length} procedures</span>}
                                {flagged.length > 0 && (
                                  <span className="text-amber-600 font-medium">{flagged.length} flagged</span>
                                )}
                              </div>
                              {cells.length > 5 && flagged.length / cells.length > 0.5 && (
                                <div className="mt-2 px-2 py-1 bg-amber-50 border border-amber-200 rounded text-[10px] text-amber-700">
                                  {(flagged.length / cells.length * 100).toFixed(0)}% cells flagged — verify this table
                                </div>
                              )}
                            </CardBody>
                          </Card>
                        </button>
                      );
                    })}
                  </div>
                )}
              </div>
            )}

            {/* Procedures tab */}
            {activeTab === "procedures" && (
              <div className="p-4">
                {(() => {
                  const allProcs = protocol.tables.flatMap((t) => t.procedures || []);
                  // Deduplicate by canonical name
                  const seen = new Set<string>();
                  const unique = allProcs.filter((p) => {
                    if (seen.has(p.canonical_name)) return false;
                    seen.add(p.canonical_name);
                    return true;
                  });
                  if (unique.length === 0) {
                    return <div className="text-center py-12 text-sm text-neutral-400">No procedures extracted</div>;
                  }
                  return (
                    <div className="overflow-auto">
                      <table className="w-full text-xs">
                        <thead>
                          <tr className="bg-neutral-50">
                            <th className="px-3 py-2 text-left font-medium text-neutral-500 border-b">Raw Name</th>
                            <th className="px-3 py-2 text-left font-medium text-neutral-500 border-b">Canonical</th>
                            <th className="px-3 py-2 text-left font-medium text-neutral-500 border-b">CPT Code</th>
                            <th className="px-3 py-2 text-left font-medium text-neutral-500 border-b">Category</th>
                            <th className="px-3 py-2 text-center font-medium text-neutral-500 border-b">Cost Tier</th>
                          </tr>
                        </thead>
                        <tbody>
                          {unique.sort((a, b) => a.category.localeCompare(b.category)).map((p, i) => (
                            <tr key={i} className={cn("hover:bg-neutral-50/50", i % 2 === 1 && "bg-neutral-50/30")}>
                              <td className="px-3 py-2 text-neutral-600 border-b border-neutral-100">{p.raw_name}</td>
                              <td className="px-3 py-2 text-neutral-800 font-medium border-b border-neutral-100">{p.canonical_name}</td>
                              <td className="px-3 py-2 text-neutral-500 font-mono border-b border-neutral-100">{p.code ? `${p.code} (${p.code_system})` : "—"}</td>
                              <td className="px-3 py-2 border-b border-neutral-100"><Badge variant="neutral">{p.category}</Badge></td>
                              <td className="px-3 py-2 text-center border-b border-neutral-100">{p.estimated_cost_tier}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  );
                })()}
              </div>
            )}

            {/* Overview tab */}
            {activeTab === "overview" && stats && (
              <div className="p-6 max-w-4xl mx-auto space-y-6">
                {/* Stats grid */}
                <div className="grid grid-cols-4 gap-4">
                  <StatCard label="SoA Tables" value={stats.tables} color="text-brand-primary" />
                  <StatCard label="Total Cells" value={stats.cells} color="text-emerald-600" />
                  <StatCard label="Flagged" value={stats.flagged} color={stats.flagged > 0 ? "text-amber-600" : "text-emerald-600"} />
                  <StatCard label="Procedures" value={stats.procedures} color="text-purple-600" />
                </div>

                {/* Trust Dashboard */}
                <ProtocolTrustDashboard protocolId={protocolId} />

                {/* Metadata */}
                <ProtocolMetaCard metadata={protocol.metadata} />

                {/* Quality */}
                {protocol.quality_summary && Object.keys(protocol.quality_summary).length > 0 && (
                  <Card>
                    <CardHeader>
                      <h3 className="text-xs font-semibold text-neutral-800 uppercase tracking-wide">Quality Summary</h3>
                    </CardHeader>
                    <CardBody className="py-2">
                      <div className="space-y-2">
                        {Object.entries(protocol.quality_summary).map(([key, value]) => (
                          <div key={key} className="flex items-center justify-between py-1.5">
                            <span className="text-[11px] text-neutral-500 capitalize">{key.replace(/_/g, " ")}</span>
                            <span className="text-xs font-semibold text-neutral-800 font-mono">{String(value)}</span>
                          </div>
                        ))}
                      </div>
                    </CardBody>
                  </Card>
                )}

                {/* Quick links */}
                <div className="grid grid-cols-2 gap-3">
                  {stats.budgetLines > 0 && (
                    <Link href={`/protocols/${protocolId}/budget-wizard`}>
                      <Card className="hover:shadow-md hover:border-emerald-300 transition-all cursor-pointer border-emerald-200 bg-emerald-50/30 h-full">
                        <CardBody className="p-4">
                          <h4 className="text-sm font-semibold text-emerald-800">Site Budget Wizard</h4>
                          <p className="text-xs text-emerald-600 mt-1">{stats.budgetLines} procedures · Review & export</p>
                        </CardBody>
                      </Card>
                    </Link>
                  )}
                  {stats.sections > 0 && (
                    <Link href="/tools/sections">
                      <Card className="hover:shadow-md hover:border-brand-primary/30 transition-all cursor-pointer h-full">
                        <CardBody className="p-4">
                          <h4 className="text-sm font-semibold text-neutral-800">Document Explorer</h4>
                          <p className="text-xs text-neutral-500 mt-1">{stats.sections} sections · Browse & extract</p>
                        </CardBody>
                      </Card>
                    </Link>
                  )}
                </div>

                {/* Pipeline info */}
                <div className="text-[11px] text-neutral-400 pt-2 border-t border-neutral-200">
                  <p>Pipeline: {protocol.pipeline_version}</p>
                  <p>Created: {new Date(protocol.created_at).toLocaleString()}</p>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

function StatCard({ label, value, color }: { label: string; value: number; color: string }) {
  return (
    <Card>
      <CardBody className="p-4 text-center">
        <p className={cn("text-2xl font-bold font-mono", color)}>{value}</p>
        <span className="text-[11px] text-neutral-500 uppercase tracking-wide">{label}</span>
      </CardBody>
    </Card>
  );
}
