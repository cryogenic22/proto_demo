"use client";

import { useEffect, useState, useCallback, useMemo } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import {
  getProtocol,
  getKnowledgeElements,
  type ProtocolFull,
  type SectionNode,
  type KnowledgeElement,
} from "@/lib/api";
import { TopBar } from "@/components/layout/TopBar";
import { Card, CardHeader, CardBody } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { Tabs } from "@/components/ui/Tabs";
import { SectionTree } from "@/components/protocol/SectionTree";
import { SectionContent } from "@/components/protocol/SectionContent";
import { ProtocolMetaCard } from "@/components/protocol/ProtocolMetaCard";
import { ProcedureTable } from "@/components/protocol/ProcedureTable";
import { KEBadge } from "@/components/protocol/KEBadge";
import { AssistantPanel, type AssistantMode } from "@/components/protocol/AssistantPanel";
import { ReviewFilter, type ReviewFilterType } from "@/components/protocol/ReviewFilter";
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
  let count = sections.length;
  for (const s of sections) {
    count += countSections(s.children);
  }
  return count;
}

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
  const [reviewFilter, setReviewFilter] = useState<ReviewFilterType>("all");

  useEffect(() => {
    getProtocol(protocolId)
      .then((data) => {
        setProtocol(data);
        // Select first section by default
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

  // Load KEs when that tab is activated
  useEffect(() => {
    if (activeTab === "ke") loadKEs();
  }, [activeTab, loadKEs]);

  const currentSection = protocol ? findSection(protocol.sections, selectedSection) : null;

  const cellStats = useMemo(() => {
    if (!protocol) return { totalCells: 0, verifiedCells: 0, flaggedCells: 0, lowConfidenceCells: 0 };
    const allCells = protocol.tables.flatMap(t => t.cells);
    return {
      totalCells: allCells.length,
      verifiedCells: allCells.filter(c => c.confidence >= 0.95).length,
      flaggedCells: protocol.tables.reduce((sum, t) => sum + t.flagged_cells.length, 0),
      lowConfidenceCells: allCells.filter(c => c.confidence < 0.7).length,
    };
  }, [protocol]);

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
              <div className="w-12 h-12 rounded-full bg-red-50 flex items-center justify-center mx-auto mb-3">
                <svg className="w-6 h-6 text-red-500" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m9-.75a9 9 0 11-18 0 9 9 0 0118 0zm-9 3.75h.008v.008H12v-.008z" />
                </svg>
              </div>
              <p className="text-sm font-medium text-neutral-700">Failed to load protocol</p>
              <p className="text-xs text-neutral-400 mt-1">{error}</p>
              <Link
                href="/protocols"
                className="inline-flex items-center gap-1 text-sm text-brand-primary hover:underline mt-4"
              >
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
            <h3 className="text-xs font-semibold text-neutral-800 uppercase tracking-wide">
              Sections
            </h3>
            <p className="text-[11px] text-neutral-400 mt-0.5">{totalSections} sections</p>
          </div>
          <div className="flex-1 overflow-y-auto py-1">
            {protocol.sections.length > 0 ? (
              <SectionTree
                sections={protocol.sections}
                selectedNumber={selectedSection}
                onSelect={setSelectedSection}
              />
            ) : (
              <div className="p-4 text-xs text-neutral-400 text-center">
                No sections available
              </div>
            )}
          </div>
        </div>

        {/* Center panel — Content Area */}
        <div className="flex-1 flex flex-col overflow-hidden bg-white min-w-0">
          {/* Tab bar */}
          <div className="px-4 pt-3 border-b border-neutral-200 bg-white">
            <Tabs tabs={tabs} active={activeTab} onChange={setActiveTab} className="border-b-0" />
          </div>

          {/* Review filter for tables tab */}
          {activeTab === "tables" && protocol.tables.length > 0 && (
            <ReviewFilter
              totalCells={cellStats.totalCells}
              verifiedCells={cellStats.verifiedCells}
              flaggedCells={cellStats.flaggedCells}
              lowConfidenceCells={cellStats.lowConfidenceCells}
              activeFilter={reviewFilter}
              onFilterChange={setReviewFilter}
            />
          )}

          {/* Tab content */}
          <div className="flex-1 overflow-y-auto">
            {activeTab === "content" && (
              <SectionContent section={currentSection} onAsk={handleAskAboutSection} />
            )}

            {activeTab === "tables" && (
              <div className="p-6">
                {protocol.tables.length === 0 ? (
                  <EmptyState
                    icon={
                      <svg className="w-8 h-8" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                        <path strokeLinecap="round" strokeLinejoin="round" d="M3.375 19.5h17.25m-17.25 0a1.125 1.125 0 01-1.125-1.125M3.375 19.5h7.5c.621 0 1.125-.504 1.125-1.125m-9.75 0V5.625m0 12.75v-1.5c0-.621.504-1.125 1.125-1.125m18.375 2.625V5.625m0 12.75c0 .621-.504 1.125-1.125 1.125m1.125-1.125v-1.5c0-.621-.504-1.125-1.125-1.125m0 3.75h-7.5A1.125 1.125 0 0112 18.375m9.75-12.75c0-.621-.504-1.125-1.125-1.125H3.375c-.621 0-1.125.504-1.125 1.125m19.5 0v1.5c0 .621-.504 1.125-1.125 1.125M2.25 5.625v1.5c0 .621.504 1.125 1.125 1.125m0 0h17.25m-17.25 0h7.5c.621 0 1.125.504 1.125 1.125M3.375 8.25c-.621 0-1.125.504-1.125 1.125v1.5c0 .621.504 1.125 1.125 1.125m17.25-3.75h-7.5c-.621 0-1.125.504-1.125 1.125m8.625-1.125c.621 0 1.125.504 1.125 1.125v1.5c0 .621-.504 1.125-1.125 1.125m-17.25 0h7.5m-7.5 0c-.621 0-1.125.504-1.125 1.125v1.5c0 .621.504 1.125 1.125 1.125M12 10.875v-1.5m0 1.5c0 .621-.504 1.125-1.125 1.125M12 10.875c0 .621.504 1.125 1.125 1.125m-2.25 0c.621 0 1.125.504 1.125 1.125M13.125 12h7.5m-7.5 0c-.621 0-1.125.504-1.125 1.125M20.625 12c.621 0 1.125.504 1.125 1.125v1.5c0 .621-.504 1.125-1.125 1.125m-17.25 0h7.5M12 14.625v-1.5m0 1.5c0 .621-.504 1.125-1.125 1.125M12 14.625c0 .621.504 1.125 1.125 1.125m-2.25 0c.621 0 1.125.504 1.125 1.125m0 0v.375" />
                      </svg>
                    }
                    title="No tables extracted"
                    description="No tables were found in this protocol."
                  />
                ) : (
                  <div className="space-y-4">
                    {protocol.tables.map((table) => (
                      <Card key={table.table_id}>
                        <CardHeader>
                          <div className="flex items-center justify-between">
                            <div>
                              <h3 className="text-sm font-semibold text-neutral-800">
                                {table.title || `Table ${table.table_id}`}
                              </h3>
                              <p className="text-xs text-neutral-400 mt-0.5">
                                Pages {table.source_pages.join(", ")} · {table.schema_info.num_rows} rows × {table.schema_info.num_cols} cols
                              </p>
                            </div>
                            <div className="flex items-center gap-2">
                              <Badge variant={table.table_type === "SOA" ? "brand" : "neutral"}>
                                {table.table_type}
                              </Badge>
                              <span className="text-xs font-medium text-neutral-600">
                                {(table.overall_confidence * 100).toFixed(0)}%
                              </span>
                            </div>
                          </div>
                        </CardHeader>
                        <CardBody className="text-xs text-neutral-500">
                          {table.cells.length} cells · {table.footnotes.length} footnotes · {table.procedures.length} procedures
                        </CardBody>
                      </Card>
                    ))}
                  </div>
                )}
              </div>
            )}

            {activeTab === "procedures" && (
              <ProcedureTable procedures={protocol.procedures} />
            )}

            {activeTab === "ke" && (
              <div className="p-6">
                {keLoading ? (
                  <div className="flex items-center justify-center py-12">
                    <div className="w-6 h-6 border-2 border-brand-primary border-t-transparent rounded-full animate-spin" />
                  </div>
                ) : knowledgeElements.length === 0 ? (
                  <EmptyState
                    icon={
                      <svg className="w-8 h-8" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                        <path strokeLinecap="round" strokeLinejoin="round" d="M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09zM18.259 8.715L18 9.75l-.259-1.035a3.375 3.375 0 00-2.455-2.456L14.25 6l1.036-.259a3.375 3.375 0 002.455-2.456L18 2.25l.259 1.035a3.375 3.375 0 002.455 2.456L21.75 6l-1.036.259a3.375 3.375 0 00-2.455 2.456zM16.894 20.567L16.5 21.75l-.394-1.183a2.25 2.25 0 00-1.423-1.423L13.5 18.75l1.183-.394a2.25 2.25 0 001.423-1.423l.394-1.183.394 1.183a2.25 2.25 0 001.423 1.423l1.183.394-1.183.394a2.25 2.25 0 00-1.423 1.423z" />
                      </svg>
                    }
                    title="No knowledge elements"
                    description="No knowledge elements have been extracted for this protocol."
                  />
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
                          <p className="text-xs text-neutral-600 leading-relaxed line-clamp-3">
                            {ke.content}
                          </p>
                          <div className="flex items-center gap-3 mt-2 text-[11px] text-neutral-400">
                            <span>Pages: {ke.source_pages.join(", ")}</span>
                            <span>v{ke.version}</span>
                            {ke.relationships.length > 0 && (
                              <span>{ke.relationships.length} relationship{ke.relationships.length !== 1 ? "s" : ""}</span>
                            )}
                          </div>
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
        <div className="w-[300px] shrink-0 bg-neutral-50 border-l border-neutral-200 overflow-y-auto">
          <div className="p-4 space-y-4">
            {/* Protocol metadata */}
            <ProtocolMetaCard metadata={protocol.metadata} />

            {/* Quick Stats */}
            <Card>
              <CardHeader>
                <h3 className="text-xs font-semibold text-neutral-800 uppercase tracking-wide">
                  Quick Stats
                </h3>
              </CardHeader>
              <CardBody className="py-2">
                <div className="space-y-2">
                  <StatRow label="Sections" value={String(totalSections)} />
                  <StatRow label="Tables" value={String(protocol.tables.length)} />
                  <StatRow label="Procedures" value={String(protocol.procedures.length)} />
                  <StatRow
                    label="Footnotes"
                    value={String(
                      protocol.tables.reduce((sum, t) => sum + t.footnotes.length, 0)
                    )}
                  />
                  <StatRow label="Budget Lines" value={String(protocol.budget_lines.length)} />
                </div>
              </CardBody>
            </Card>

            {/* Quality Summary */}
            {protocol.quality_summary && Object.keys(protocol.quality_summary).length > 0 && (
              <Card>
                <CardHeader>
                  <h3 className="text-xs font-semibold text-neutral-800 uppercase tracking-wide">
                    Quality Summary
                  </h3>
                </CardHeader>
                <CardBody className="py-2">
                  <div className="space-y-2">
                    {Object.entries(protocol.quality_summary).map(([key, value]) => (
                      <StatRow
                        key={key}
                        label={key.replace(/_/g, " ")}
                        value={typeof value === "number" ? String(value) : String(value)}
                      />
                    ))}
                  </div>
                </CardBody>
              </Card>
            )}

            {/* Budget link */}
            {protocol.budget_lines.length > 0 && (
              <Link href={`/protocols/${protocolId}/budget`}>
                <Card className="hover:shadow-md hover:border-brand-primary/30 transition-all cursor-pointer mt-4">
                  <CardBody className="p-4 flex items-center gap-3">
                    <div className="w-10 h-10 rounded-lg bg-emerald-50 flex items-center justify-center shrink-0">
                      <svg className="w-5 h-5 text-emerald-600" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                        <path strokeLinecap="round" strokeLinejoin="round" d="M12 6v12m-3-2.818l.879.659c1.171.879 3.07.879 4.242 0 1.172-.879 1.172-2.303 0-3.182C13.536 12.219 12.768 12 12 12c-.725 0-1.45-.22-2.003-.659-1.106-.879-1.106-2.303 0-3.182s2.9-.879 4.006 0l.415.33M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                      </svg>
                    </div>
                    <div>
                      <h4 className="text-sm font-medium text-neutral-800">Budget Preview</h4>
                      <p className="text-xs text-neutral-400">
                        {protocol.budget_lines.length} line items
                      </p>
                    </div>
                    <svg className="w-4 h-4 text-neutral-400 ml-auto" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M8.25 4.5l7.5 7.5-7.5 7.5" />
                    </svg>
                  </CardBody>
                </Card>
              </Link>
            )}

            {/* Pipeline info */}
            <div className="text-[11px] text-neutral-400 pt-2 border-t border-neutral-200">
              <p>Pipeline: {protocol.pipeline_version}</p>
              <p>Created: {new Date(protocol.created_at).toLocaleString()}</p>
              <p className="font-mono mt-1 truncate" title={protocol.document_hash}>
                Hash: {protocol.document_hash}
              </p>
            </div>
          </div>
        </div>
      </div>

      <AssistantPanel
        mode={assistantMode}
        protocolId={protocolId}
        onClose={() => setAssistantMode({ kind: "closed" })}
        onAcceptCell={(row, col) => { /* TODO: call submitCellReview */ }}
        onCorrectCell={(row, col, value) => { /* TODO: call submitCellReview */ }}
        onFlagCell={(row, col, reason) => { /* TODO: call submitCellReview */ }}
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

function EmptyState({
  icon,
  title,
  description,
}: {
  icon: React.ReactNode;
  title: string;
  description: string;
}) {
  return (
    <div className="text-center py-12">
      <div className="text-neutral-300 flex justify-center mb-3">{icon}</div>
      <p className="text-sm font-medium text-neutral-700">{title}</p>
      <p className="text-xs text-neutral-400 mt-1">{description}</p>
    </div>
  );
}
