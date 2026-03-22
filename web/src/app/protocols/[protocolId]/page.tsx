"use client";

import { useEffect, useState, useCallback, useMemo } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import {
  getProtocol,
  getKnowledgeElements,
  type ProtocolFull,
  type SectionNode,
  type ExtractedTable,
  type KnowledgeElement,
} from "@/lib/api";
import { sanitizeHtml } from "@/lib/sanitize";
import { TopBar } from "@/components/layout/TopBar";
import { Card, CardHeader, CardBody } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { Tabs } from "@/components/ui/Tabs";
import { SectionTree } from "@/components/protocol/SectionTree";
import { SectionContent } from "@/components/protocol/SectionContent";
import { ProtocolMetaCard } from "@/components/protocol/ProtocolMetaCard";
import { KEBadge } from "@/components/protocol/KEBadge";
import { AssistantPanel, type AssistantMode } from "@/components/protocol/AssistantPanel";
import { SoAReviewAssistant } from "@/components/protocol/SoAReviewAssistant";
import { cn } from "@/lib/utils";

function findSection(sections: SectionNode[], number: string): SectionNode | null {
  for (const s of sections) {
    if (s.number === number) return s;
    const found = findSection(s.children, number);
    if (found) return found;
  }
  return null;
}

function countSections(sections: SectionNode[]): number {
  return sections.reduce((sum, s) => sum + 1 + countSections(s.children), 0);
}

function confidenceColor(c: number): string {
  if (c >= 0.95) return "bg-emerald-100 text-emerald-800";
  if (c >= 0.85) return "bg-sky-100 text-sky-800";
  if (c >= 0.70) return "bg-amber-100 text-amber-800";
  return "bg-red-100 text-red-800";
}

function confidenceBg(c: number): string {
  if (c >= 0.95) return "bg-emerald-50";
  if (c >= 0.85) return "bg-sky-50";
  if (c >= 0.70) return "bg-amber-50";
  return "bg-red-50";
}

// ─── Table Detail View ────────────────────────────────────────────────────

function TableDetailView({ table, onClose }: { table: ExtractedTable; onClose: () => void }) {
  const [activeView, setActiveView] = useState<"grid" | "footnotes" | "procedures" | "review">("grid");
  const cells = table.cells || [];
  const footnotes = table.footnotes || [];
  const procedures = table.procedures || [];
  const reviewItems = table.review_items || [];

  // Build grid from cells
  const maxRow = cells.reduce((m, c) => Math.max(m, c.row), 0);
  const maxCol = cells.reduce((m, c) => Math.max(m, c.col), 0);
  const grid: (typeof cells[0] | null)[][] = [];
  for (let r = 0; r <= maxRow; r++) {
    grid[r] = [];
    for (let c = 0; c <= maxCol; c++) {
      grid[r][c] = cells.find((cell) => cell.row === r && cell.col === c) || null;
    }
  }

  // Column headers from schema_info or first row
  const colHeaders = table.schema_info?.column_headers?.map((h) => h.text) || [];

  return (
    <div className="h-full flex flex-col">
      {/* Header */}
      <div className="px-4 py-3 border-b border-neutral-200 flex items-center justify-between shrink-0 bg-white">
        <div>
          <h3 className="text-sm font-semibold text-neutral-800">
            {table.title || `Table ${table.table_id}`}
          </h3>
          <p className="text-xs text-neutral-400 mt-0.5">
            Pages {(table.source_pages || []).join(", ")} ·{" "}
            {table.schema_info?.num_rows || maxRow + 1} rows × {table.schema_info?.num_cols || maxCol + 1} cols ·{" "}
            {cells.length} cells
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Badge variant={table.table_type === "SOA" ? "brand" : "neutral"}>{table.table_type}</Badge>
          <span className={cn("text-xs font-medium px-2 py-0.5 rounded", confidenceColor(table.overall_confidence))}>
            {(table.overall_confidence * 100).toFixed(0)}%
          </span>
          <button
            onClick={onClose}
            className="p-1.5 rounded-md hover:bg-neutral-100 text-neutral-400 hover:text-neutral-600 transition-colors"
          >
            <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round">
              <path d="M4 4L12 12M12 4L4 12" />
            </svg>
          </button>
        </div>
      </div>

      {/* Sub-tabs */}
      <div className="px-4 pt-2 border-b border-neutral-100 bg-white shrink-0 flex gap-1">
        {[
          { key: "grid" as const, label: "Grid View", count: cells.length },
          { key: "footnotes" as const, label: "Footnotes", count: footnotes.length },
          { key: "procedures" as const, label: "Procedures", count: procedures.length },
          { key: "review" as const, label: "Review Queue", count: reviewItems.length },
        ].map((tab) => (
          <button
            key={tab.key}
            onClick={() => setActiveView(tab.key)}
            className={cn(
              "px-3 py-2 text-xs font-medium border-b-2 -mb-px transition-colors",
              activeView === tab.key
                ? "border-brand-primary text-brand-primary"
                : "border-transparent text-neutral-400 hover:text-neutral-600"
            )}
          >
            {tab.label}
            {tab.count > 0 && (
              <span className="ml-1.5 text-[10px] bg-neutral-100 text-neutral-500 rounded-full px-1.5 py-0.5">
                {tab.count}
              </span>
            )}
          </button>
        ))}
      </div>

      {/* Content */}
      <div className="flex-1 overflow-auto">
        {activeView === "grid" && (
          <div className="overflow-auto">
            <table className="text-xs border-collapse">
              <thead className="sticky top-0 z-10">
                <tr className="bg-neutral-100">
                  <th className="px-3 py-2 text-left font-semibold text-neutral-600 border border-neutral-200 bg-neutral-100 sticky left-0 z-20 min-w-[140px]">
                    Procedure
                  </th>
                  {colHeaders.length > 0
                    ? colHeaders.map((h, i) => (
                        <th key={i} className="px-3 py-2 text-center font-semibold text-neutral-600 border border-neutral-200 bg-neutral-100 whitespace-nowrap min-w-[70px]">
                          {h}
                        </th>
                      ))
                    : Array.from({ length: maxCol + 1 }, (_, i) => (
                        <th key={i} className="px-3 py-2 text-center font-semibold text-neutral-600 border border-neutral-200 bg-neutral-100 min-w-[70px]">
                          Col {i}
                        </th>
                      ))}
                </tr>
              </thead>
              <tbody>
                {grid.map((row, ri) => (
                  <tr key={ri} className="hover:bg-neutral-50/50">
                    <td className="px-3 py-1.5 font-medium text-neutral-700 border border-neutral-200 bg-white sticky left-0 z-10 whitespace-nowrap">
                      {row[0]?.row_header || `Row ${ri}`}
                    </td>
                    {row.slice(colHeaders.length > 0 ? 0 : 0).map((cell, ci) => {
                      if (ci === 0 && colHeaders.length === 0) return null;
                      const c = cell || grid[ri]?.[ci];
                      return (
                        <td
                          key={ci}
                          className={cn(
                            "px-2 py-1.5 text-center border border-neutral-200 font-mono",
                            c ? confidenceBg(c.confidence) : ""
                          )}
                          title={c ? `Confidence: ${(c.confidence * 100).toFixed(0)}%\nType: ${c.data_type}` : ""}
                        >
                          {c?.raw_value || ""}
                          {c?.footnote_markers && c.footnote_markers.length > 0 && (
                            <sup className="text-brand-primary text-[9px] ml-0.5">
                              {c.footnote_markers.join(",")}
                            </sup>
                          )}
                        </td>
                      );
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {activeView === "footnotes" && (
          <div className="p-4 space-y-2">
            {footnotes.length === 0 ? (
              <p className="text-sm text-neutral-400 italic py-8 text-center">No footnotes</p>
            ) : (
              footnotes.map((fn, i) => (
                <div key={i} className="flex gap-3 py-2 border-b border-neutral-100 last:border-0">
                  <sup className="text-brand-primary font-bold text-sm shrink-0">{fn.marker}</sup>
                  <div>
                    <p className="text-xs text-neutral-700">{fn.text}</p>
                    <Badge variant="neutral" className="mt-1">{fn.footnote_type}</Badge>
                  </div>
                </div>
              ))
            )}
          </div>
        )}

        {activeView === "procedures" && (
          <div className="overflow-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="bg-neutral-50">
                  <th className="px-3 py-2 text-left font-medium text-neutral-500 border-b">Raw Name</th>
                  <th className="px-3 py-2 text-left font-medium text-neutral-500 border-b">Canonical</th>
                  <th className="px-3 py-2 text-left font-medium text-neutral-500 border-b">CPT</th>
                  <th className="px-3 py-2 text-left font-medium text-neutral-500 border-b">Category</th>
                  <th className="px-3 py-2 text-center font-medium text-neutral-500 border-b">Cost</th>
                </tr>
              </thead>
              <tbody>
                {procedures.map((p, i) => (
                  <tr key={i} className="hover:bg-neutral-50/50">
                    <td className="px-3 py-2 text-neutral-600 border-b border-neutral-100">{p.raw_name}</td>
                    <td className="px-3 py-2 text-neutral-800 font-medium border-b border-neutral-100">{p.canonical_name}</td>
                    <td className="px-3 py-2 text-neutral-500 font-mono border-b border-neutral-100">{p.code || "—"}</td>
                    <td className="px-3 py-2 border-b border-neutral-100"><Badge variant="neutral">{p.category}</Badge></td>
                    <td className="px-3 py-2 text-center border-b border-neutral-100">{p.estimated_cost_tier}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {activeView === "review" && (
          <div className="p-4 space-y-2">
            {reviewItems.length === 0 ? (
              <p className="text-sm text-neutral-400 italic py-8 text-center">No items flagged for review</p>
            ) : (
              reviewItems.map((item, i) => (
                <div key={i} className="p-3 bg-amber-50/60 rounded-lg border border-amber-100">
                  <div className="flex items-center gap-2 mb-1">
                    <Badge variant="warning">{item.review_type}</Badge>
                    <span className="text-[10px] text-neutral-400">
                      Cell ({item.cell_ref?.row}, {item.cell_ref?.col}) · Page {item.source_page}
                    </span>
                  </div>
                  <p className="text-xs text-neutral-700">{item.reason}</p>
                  <p className="text-xs text-neutral-500 mt-1 font-mono">Value: {item.extracted_value}</p>
                </div>
              ))
            )}
          </div>
        )}
      </div>
    </div>
  );
}

// ─── Main Page ────────────────────────────────────────────────────────────

export default function ProtocolWorkspacePage() {
  const params = useParams();
  const protocolId = params.protocolId as string;

  const [protocol, setProtocol] = useState<ProtocolFull | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedSection, setSelectedSection] = useState<string>("");
  const [activeTab, setActiveTab] = useState("content");
  const [knowledgeElements, setKnowledgeElements] = useState<KnowledgeElement[]>([]);
  const [keLoading, setKeLoading] = useState(false);
  const [assistantMode, setAssistantMode] = useState<AssistantMode>({ kind: "closed" });
  const [expandedTable, setExpandedTable] = useState<ExtractedTable | null>(null);

  useEffect(() => {
    getProtocol(protocolId)
      .then((data) => {
        setProtocol(data);
        if (data.sections.length > 0) {
          setSelectedSection(data.sections[0].number);
        }
      })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [protocolId]);

  const loadKEs = useCallback(() => {
    if (keLoading || knowledgeElements.length > 0) return;
    setKeLoading(true);
    getKnowledgeElements(protocolId)
      .then(setKnowledgeElements)
      .catch(() => {})
      .finally(() => setKeLoading(false));
  }, [protocolId, keLoading, knowledgeElements.length]);

  useEffect(() => {
    if (activeTab === "ke") loadKEs();
  }, [activeTab, loadKEs]);

  const currentSection = protocol ? findSection(protocol.sections, selectedSection) : null;

  const handleAskAboutSection = useCallback((section: SectionNode) => {
    setAssistantMode({
      kind: "ask",
      sectionNumber: section.number,
      sectionTitle: section.title,
      sectionContent: section.content_html,
    });
  }, []);

  if (loading) {
    return (
      <div>
        <TopBar title="Loading..." subtitle="Fetching protocol data" />
        <div className="flex items-center justify-center h-[calc(100vh-3.5rem)]">
          <div className="text-center">
            <div className="w-8 h-8 border-2 border-brand-primary border-t-transparent rounded-full animate-spin mx-auto mb-3" />
            <p className="text-sm text-neutral-400">Loading protocol workspace...</p>
          </div>
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
              <Link href="/protocols" className="inline-flex items-center gap-1 text-sm text-brand-primary hover:underline mt-4">
                &larr; Back to library
              </Link>
            </CardBody>
          </Card>
        </div>
      </div>
    );
  }

  const tabs = [
    { key: "content", label: "Content" },
    { key: "tables", label: "Tables", count: protocol.tables.length },
    { key: "procedures", label: "Procedures", count: protocol.procedures.length },
    { key: "ke", label: "Knowledge Elements", count: knowledgeElements.length || undefined },
  ];

  const totalSections = countSections(protocol.sections);

  // If a table is expanded, show the SoA Review Assistant
  if (expandedTable) {
    const tableIdx = protocol.tables.indexOf(expandedTable);
    return (
      <div className="h-screen">
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

  return (
    <div>
      <TopBar
        title={protocol.metadata.short_title || protocol.metadata.title || protocol.document_name}
        subtitle={`${protocol.metadata.protocol_number || ""} · ${protocol.total_pages} pages`}
      />

      {/* 3-panel layout */}
      <div className="flex h-[calc(100vh-3.5rem)]">
        {/* Left panel — Section Navigator */}
        <div className="w-[260px] shrink-0 bg-neutral-50 border-r border-neutral-200 flex flex-col overflow-hidden">
          <div className="px-4 py-3 border-b border-neutral-200">
            <h3 className="text-xs font-semibold text-neutral-800 uppercase tracking-wide">Sections</h3>
            <p className="text-[11px] text-neutral-400 mt-0.5">{totalSections} sections</p>
          </div>
          <div className="flex-1 overflow-y-auto py-1">
            {protocol.sections.length > 0 ? (
              <SectionTree sections={protocol.sections} selectedNumber={selectedSection} onSelect={setSelectedSection} />
            ) : (
              <div className="p-4 text-xs text-neutral-400 text-center">No sections available</div>
            )}
          </div>
        </div>

        {/* Center panel — Content Area */}
        <div className="flex-1 flex flex-col overflow-hidden bg-white min-w-0">
          <div className="px-4 pt-3 border-b border-neutral-200 bg-white">
            <Tabs tabs={tabs} active={activeTab} onChange={setActiveTab} className="border-b-0" />
          </div>

          <div className="flex-1 overflow-y-auto">
            {activeTab === "content" && (
              <SectionContent section={currentSection} onAsk={handleAskAboutSection} />
            )}

            {activeTab === "tables" && (
              <div className="p-4">
                {protocol.tables.length === 0 ? (
                  <div className="text-center py-12">
                    <p className="text-sm font-medium text-neutral-700">No tables extracted</p>
                    <p className="text-xs text-neutral-400 mt-1">No tables were found in this protocol.</p>
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
                                  <Badge variant={table.table_type === "SOA" ? "brand" : "neutral"}>
                                    {table.table_type}
                                  </Badge>
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
                              {/* High flagged rate warning */}
                              {cells.length > 5 && flagged.length / cells.length > 0.5 && (
                                <div className="mt-2 px-2 py-1 bg-amber-50 border border-amber-200 rounded text-[10px] text-amber-700">
                                  {(flagged.length / cells.length * 100).toFixed(0)}% cells flagged — this may not be an SoA table
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

            {activeTab === "procedures" && (
              <div className="p-4">
                {protocol.procedures.length === 0 ? (
                  <div className="text-center py-12">
                    <p className="text-sm font-medium text-neutral-700">No procedures</p>
                    <p className="text-xs text-neutral-400 mt-1">No procedures were normalized for this protocol.</p>
                  </div>
                ) : (
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
                        {protocol.procedures.map((p, i) => (
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
                )}
              </div>
            )}

            {activeTab === "ke" && (
              <div className="p-6">
                {keLoading ? (
                  <div className="flex items-center justify-center py-12">
                    <div className="w-6 h-6 border-2 border-brand-primary border-t-transparent rounded-full animate-spin" />
                  </div>
                ) : knowledgeElements.length === 0 ? (
                  <div className="text-center py-12">
                    <p className="text-sm font-medium text-neutral-700">No knowledge elements</p>
                    <p className="text-xs text-neutral-400 mt-1">No knowledge elements have been extracted.</p>
                  </div>
                ) : (
                  <div className="space-y-3">
                    {knowledgeElements.map((ke) => (
                      <Card key={ke.ke_id}>
                        <CardBody className="p-4">
                          <div className="flex items-start justify-between gap-3 mb-2">
                            <div className="flex items-center gap-2">
                              <Badge variant="info">{ke.ke_type}</Badge>
                              <h4 className="text-sm font-medium text-neutral-800">{ke.title}</h4>
                            </div>
                            <KEBadge status={ke.status} />
                          </div>
                          <p className="text-xs text-neutral-600 leading-relaxed line-clamp-3">{ke.content}</p>
                        </CardBody>
                      </Card>
                    ))}
                  </div>
                )}
              </div>
            )}
          </div>
        </div>

        {/* Right panel — Context */}
        <div className="w-[280px] shrink-0 bg-neutral-50 border-l border-neutral-200 overflow-y-auto">
          <div className="p-4 space-y-4">
            <ProtocolMetaCard metadata={protocol.metadata} />

            <Card>
              <CardHeader>
                <h3 className="text-xs font-semibold text-neutral-800 uppercase tracking-wide">Quick Stats</h3>
              </CardHeader>
              <CardBody className="py-2">
                <div className="space-y-2">
                  <StatRow label="Sections" value={String(totalSections)} />
                  <StatRow label="Tables" value={String(protocol.tables.length)} />
                  <StatRow label="Procedures" value={String(protocol.procedures.length)} />
                  <StatRow label="Footnotes" value={String(protocol.tables.reduce((sum, t) => sum + (t.footnotes?.length || 0), 0))} />
                  <StatRow label="Budget Lines" value={String(protocol.budget_lines.length)} />
                </div>
              </CardBody>
            </Card>

            {protocol.quality_summary && Object.keys(protocol.quality_summary).length > 0 && (
              <Card>
                <CardHeader>
                  <h3 className="text-xs font-semibold text-neutral-800 uppercase tracking-wide">Quality</h3>
                </CardHeader>
                <CardBody className="py-2">
                  <div className="space-y-2">
                    {Object.entries(protocol.quality_summary).map(([key, value]) => (
                      <StatRow key={key} label={key.replace(/_/g, " ")} value={String(value)} />
                    ))}
                  </div>
                </CardBody>
              </Card>
            )}

            {/* Budget Wizard */}
            <Link href={`/protocols/${protocolId}/budget-wizard`}>
              <Card className="hover:shadow-md hover:border-emerald-300 transition-all cursor-pointer mt-4 border-emerald-200 bg-emerald-50/30">
                <CardBody className="p-4 flex items-center gap-3">
                  <div className="w-10 h-10 rounded-lg bg-emerald-100 flex items-center justify-center shrink-0">
                    <svg className="w-5 h-5 text-emerald-600" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M12 6v12m-3-2.818l.879.659c1.171.879 3.07.879 4.242 0 1.172-.879 1.172-2.303 0-3.182C13.536 12.219 12.768 12 12 12c-.725 0-1.45-.22-2.003-.659-1.106-.879-1.106-2.303 0-3.182s2.9-.879 4.006 0l.415.33M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                    </svg>
                  </div>
                  <div>
                    <h4 className="text-sm font-semibold text-emerald-800">Site Budget Wizard</h4>
                    <p className="text-xs text-emerald-600">
                      {protocol.budget_lines.length > 0
                        ? `${protocol.budget_lines.length} procedures · Review & export`
                        : `${protocol.tables.length} tables · Generate budget`}
                    </p>
                  </div>
                  <svg className="w-4 h-4 text-emerald-400 ml-auto" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M8.25 4.5l7.5 7.5-7.5 7.5" />
                  </svg>
                </CardBody>
              </Card>
            </Link>

            <div className="text-[11px] text-neutral-400 pt-2 border-t border-neutral-200">
              <p>Pipeline: {protocol.pipeline_version}</p>
              <p>Created: {new Date(protocol.created_at).toLocaleString()}</p>
            </div>
          </div>
        </div>
      </div>

      <AssistantPanel
        mode={assistantMode}
        protocolId={protocolId}
        onClose={() => setAssistantMode({ kind: "closed" })}
      />
    </div>
  );
}

function StatRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between py-1.5">
      <span className="text-[11px] text-neutral-500 capitalize">{label}</span>
      <span className="text-xs font-semibold text-neutral-800 font-mono">{value}</span>
    </div>
  );
}
