"use client";

import { useEffect, useState, useCallback } from "react";
import {
  listProtocols,
  getProtocol,
  getPageImageUrl,
  extractVerbatim,
  type ProtocolSummary,
  type ProtocolFull,
  type SectionNode,
  type VerbatimResult,
} from "@/lib/api";
import { sanitizeHtml } from "@/lib/sanitize";
import { TopBar } from "@/components/layout/TopBar";
import { Card, CardHeader, CardBody } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { cn } from "@/lib/utils";

function confidenceBadge(score: number | null) {
  if (score === null || score === undefined) return null;
  const pct = (score * 100).toFixed(0);
  const color =
    score >= 0.95 ? "bg-emerald-100 text-emerald-700" :
    score >= 0.85 ? "bg-sky-100 text-sky-700" :
    score >= 0.70 ? "bg-amber-100 text-amber-700" :
    "bg-red-100 text-red-700";
  return (
    <span className={cn("text-[10px] font-medium px-1.5 py-0.5 rounded-full", color)}>
      {pct}%
    </span>
  );
}

function countAll(sections: SectionNode[]): number {
  return sections.reduce((sum, s) => sum + 1 + countAll(s.children || []), 0);
}

export default function DocumentExplorerPage() {
  const [protocols, setProtocols] = useState<ProtocolSummary[]>([]);
  const [selectedId, setSelectedId] = useState("");
  const [protocol, setProtocol] = useState<ProtocolFull | null>(null);
  const [selectedSection, setSelectedSection] = useState<SectionNode | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // PDF viewer state
  const [pdfPage, setPdfPage] = useState<number>(0);
  const [pdfError, setPdfError] = useState(false);
  const [showPdf, setShowPdf] = useState(true);

  // Verbatim instruction state
  const [instruction, setInstruction] = useState("");
  const [verbatimResult, setVerbatimResult] = useState<VerbatimResult | null>(null);
  const [verbatimLoading, setVerbatimLoading] = useState(false);
  const [verbatimFile, setVerbatimFile] = useState<File | null>(null);

  useEffect(() => {
    listProtocols().then(setProtocols).catch(() => {});
  }, []);

  const loadProtocol = useCallback(async (id: string) => {
    setSelectedId(id);
    setProtocol(null);
    setSelectedSection(null);
    setVerbatimResult(null);
    setPdfError(false);
    if (!id) return;
    setLoading(true);
    setError(null);
    try {
      const p = await getProtocol(id);
      setProtocol(p);
      if (p.sections.length > 0) {
        setSelectedSection(p.sections[0]);
        setPdfPage(p.sections[0].page - 1); // 0-indexed
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load");
    } finally {
      setLoading(false);
    }
  }, []);

  const handleSectionClick = useCallback((section: SectionNode) => {
    setSelectedSection(section);
    setPdfPage(Math.max(0, section.page - 1)); // 0-indexed for API
    setVerbatimResult(null);
  }, []);

  const handleVerbatimExtract = useCallback(async () => {
    if (!instruction.trim() || !verbatimFile) return;
    setVerbatimLoading(true);
    setVerbatimResult(null);
    try {
      const result = await extractVerbatim(verbatimFile, instruction.trim(), "html");
      setVerbatimResult(result);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Extraction failed");
    } finally {
      setVerbatimLoading(false);
    }
  }, [instruction, verbatimFile]);

  const totalSections = protocol ? countAll(protocol.sections) : 0;

  return (
    <div>
      <TopBar title="Document Explorer" subtitle="Browse sections, view source pages, and extract content" />

      <div className="p-4 space-y-3">
        {/* Protocol selector + upload */}
        <Card>
          <CardBody className="p-3">
            <div className="flex items-end gap-3 flex-wrap">
              <div className="flex-1 min-w-[200px]">
                <label className="text-xs font-medium text-neutral-600 block mb-1">Protocol</label>
                <select
                  value={selectedId}
                  onChange={(e) => loadProtocol(e.target.value)}
                  className="w-full px-3 py-2 text-sm border border-neutral-200 rounded-lg bg-white focus:outline-none focus:ring-2 focus:ring-brand-primary/30"
                >
                  <option value="">Select a protocol...</option>
                  {protocols.map((p) => (
                    <option key={p.protocol_id} value={p.protocol_id}>
                      {p.metadata.short_title || p.metadata.title || p.document_name} ({p.total_pages}p)
                    </option>
                  ))}
                </select>
              </div>
              <div className="flex items-center gap-2">
                <label className="text-xs text-neutral-500 flex items-center gap-1.5 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={showPdf}
                    onChange={(e) => setShowPdf(e.target.checked)}
                    className="rounded border-neutral-300"
                  />
                  Show PDF
                </label>
              </div>
            </div>
          </CardBody>
        </Card>

        {error && (
          <div className="bg-red-50 rounded-lg px-4 py-3 text-sm text-red-700 border border-red-200">{error}</div>
        )}

        {loading && (
          <div className="flex items-center justify-center py-16">
            <div className="w-8 h-8 border-2 border-brand-primary border-t-transparent rounded-full animate-spin" />
          </div>
        )}

        {/* Main layout */}
        {protocol && !loading && (
          <div className="flex gap-3" style={{ height: "calc(100vh - 200px)" }}>
            {/* Left: Section tree */}
            <Card className="w-[300px] shrink-0 flex flex-col overflow-hidden">
              <CardHeader className="shrink-0 py-2">
                <div className="flex items-center justify-between">
                  <h3 className="text-xs font-semibold text-neutral-800 uppercase tracking-wide">
                    Sections
                  </h3>
                  <Badge variant="brand">{totalSections}</Badge>
                </div>
              </CardHeader>
              <div className="flex-1 overflow-y-auto">
                {protocol.sections.map((s) => (
                  <SectionTreeItem
                    key={s.number || s.title}
                    section={s}
                    selected={selectedSection}
                    onSelect={handleSectionClick}
                    depth={0}
                  />
                ))}
              </div>
            </Card>

            {/* Center: Content */}
            <div className="flex-1 flex flex-col overflow-hidden min-w-0">
              {/* Section header */}
              {selectedSection && (
                <Card className="shrink-0 mb-3">
                  <CardBody className="p-3">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <span className="font-mono text-xs text-neutral-400 bg-neutral-100 px-2 py-0.5 rounded">
                          {selectedSection.number}
                        </span>
                        <h3 className="text-sm font-semibold text-neutral-800">{selectedSection.title}</h3>
                      </div>
                      <div className="flex items-center gap-2">
                        {confidenceBadge(selectedSection.quality_score)}
                        <Badge variant="neutral">
                          p.{selectedSection.page}
                          {selectedSection.end_page && selectedSection.end_page !== selectedSection.page
                            ? `–${selectedSection.end_page}` : ""}
                        </Badge>
                      </div>
                    </div>
                  </CardBody>
                </Card>
              )}

              {/* Content + PDF side by side */}
              <div className={cn("flex-1 flex gap-3 overflow-hidden", !showPdf && "flex-col")}>
                {/* Extracted content */}
                <Card className={cn("flex-1 flex flex-col overflow-hidden", showPdf && "min-w-0")}>
                  <CardHeader className="shrink-0 py-2">
                    <h4 className="text-xs font-semibold text-neutral-600 uppercase tracking-wide">
                      Extracted Content
                    </h4>
                  </CardHeader>
                  <div className="flex-1 overflow-y-auto p-4">
                    {verbatimResult ? (
                      <div>
                        <div className="flex items-center gap-2 mb-3">
                          <Badge variant="success">Verbatim</Badge>
                          <span className="text-xs text-neutral-400">
                            {verbatimResult.sections_found.join(", ")} · Pages {verbatimResult.source_pages.join(", ")}
                          </span>
                          <button
                            onClick={() => setVerbatimResult(null)}
                            className="ml-auto text-xs text-neutral-400 hover:text-neutral-600"
                          >
                            Clear
                          </button>
                        </div>
                        <div
                          className="section-content max-w-none"
                          dangerouslySetInnerHTML={{ __html: sanitizeHtml(verbatimResult.text) }}
                        />
                      </div>
                    ) : selectedSection?.content_html ? (
                      <div
                        className="section-content max-w-none"
                        dangerouslySetInnerHTML={{ __html: sanitizeHtml(selectedSection.content_html) }}
                      />
                    ) : (
                      <p className="text-sm text-neutral-400 italic">
                        {selectedSection ? "No content available for this section." : "Select a section to view content."}
                      </p>
                    )}
                  </div>
                </Card>

                {/* PDF viewer */}
                {showPdf && (
                  <Card className="w-[420px] shrink-0 flex flex-col overflow-hidden">
                    <CardHeader className="shrink-0 py-2">
                      <div className="flex items-center justify-between">
                        <h4 className="text-xs font-semibold text-neutral-600 uppercase tracking-wide">
                          Source Document
                        </h4>
                        <div className="flex items-center gap-1">
                          <button
                            onClick={() => setPdfPage(Math.max(0, pdfPage - 1))}
                            disabled={pdfPage <= 0}
                            className="p-1 rounded hover:bg-neutral-100 disabled:opacity-30"
                          >
                            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                              <path strokeLinecap="round" strokeLinejoin="round" d="M15.75 19.5L8.25 12l7.5-7.5" />
                            </svg>
                          </button>
                          <span className="text-xs font-mono text-neutral-500 min-w-[60px] text-center">
                            {pdfPage + 1} / {protocol.total_pages}
                          </span>
                          <button
                            onClick={() => setPdfPage(Math.min(protocol.total_pages - 1, pdfPage + 1))}
                            disabled={pdfPage >= protocol.total_pages - 1}
                            className="p-1 rounded hover:bg-neutral-100 disabled:opacity-30"
                          >
                            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                              <path strokeLinecap="round" strokeLinejoin="round" d="M8.25 4.5l7.5 7.5-7.5 7.5" />
                            </svg>
                          </button>
                        </div>
                      </div>
                    </CardHeader>
                    <div className="flex-1 overflow-auto bg-neutral-100 flex items-start justify-center p-2">
                      {pdfError ? (
                        <div className="text-center py-12 text-neutral-400">
                          <svg className="w-10 h-10 mx-auto mb-2 text-neutral-300" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1}>
                            <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 14.25v-2.625a3.375 3.375 0 00-3.375-3.375h-1.5A1.125 1.125 0 0113.5 7.125v-1.5a3.375 3.375 0 00-3.375-3.375H8.25m2.25 0H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 00-9-9z" />
                          </svg>
                          <p className="text-xs">PDF not available for this protocol</p>
                          <p className="text-[10px] mt-1 text-neutral-300">Upload the PDF to enable source viewing</p>
                        </div>
                      ) : (
                        <img
                          key={`${selectedId}-${pdfPage}`}
                          src={getPageImageUrl(selectedId, pdfPage)}
                          alt={`Page ${pdfPage + 1}`}
                          className="max-w-full shadow-lg rounded"
                          onError={() => setPdfError(true)}
                        />
                      )}
                    </div>
                  </Card>
                )}
              </div>

              {/* Verbatim instruction bar */}
              <Card className="shrink-0 mt-3">
                <CardBody className="p-3">
                  <div className="flex items-center gap-2">
                    <div className="flex-1 flex items-center gap-2">
                      <input
                        type="file"
                        accept=".pdf,.docx"
                        onChange={(e) => setVerbatimFile(e.target.files?.[0] || null)}
                        className="text-xs text-neutral-500 w-[180px] file:mr-2 file:py-1 file:px-2 file:rounded file:border-0 file:text-[10px] file:font-medium file:bg-neutral-100 file:text-neutral-600 file:cursor-pointer"
                      />
                      <input
                        type="text"
                        value={instruction}
                        onChange={(e) => setInstruction(e.target.value)}
                        onKeyDown={(e) => e.key === "Enter" && handleVerbatimExtract()}
                        placeholder='Instruction: e.g. "Copy Section 5.1" or "Extract inclusion criteria"'
                        className="flex-1 px-3 py-1.5 text-sm border border-neutral-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-brand-primary/30"
                      />
                    </div>
                    <button
                      onClick={handleVerbatimExtract}
                      disabled={!instruction.trim() || !verbatimFile || verbatimLoading}
                      className={cn(
                        "px-4 py-1.5 text-xs font-medium rounded-lg transition-colors whitespace-nowrap",
                        instruction.trim() && verbatimFile && !verbatimLoading
                          ? "bg-brand-primary text-white hover:bg-brand-french"
                          : "bg-neutral-100 text-neutral-400 cursor-not-allowed"
                      )}
                    >
                      {verbatimLoading ? "Extracting..." : "Extract Verbatim"}
                    </button>
                  </div>
                  <div className="flex flex-wrap gap-1 mt-2">
                    {["Copy Section 5.1", "Extract inclusion criteria", "Get the Schedule of Activities"].map((ex) => (
                      <button
                        key={ex}
                        onClick={() => setInstruction(ex)}
                        className="px-2 py-0.5 text-[10px] bg-neutral-50 text-neutral-500 rounded hover:bg-neutral-100 transition-colors"
                      >
                        {ex}
                      </button>
                    ))}
                  </div>
                </CardBody>
              </Card>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

function SectionTreeItem({
  section,
  selected,
  onSelect,
  depth,
}: {
  section: SectionNode;
  selected: SectionNode | null;
  onSelect: (s: SectionNode) => void;
  depth: number;
}) {
  const [expanded, setExpanded] = useState(depth < 2);
  const isSelected = selected?.number === section.number && selected?.title === section.title;
  const hasChildren = (section.children || []).length > 0;

  return (
    <div>
      <button
        onClick={() => {
          onSelect(section);
          if (hasChildren) setExpanded(!expanded);
        }}
        className={cn(
          "w-full flex items-center gap-1.5 py-1.5 px-2 text-left transition-colors group hover:bg-neutral-100",
          isSelected && "bg-brand-primary-light"
        )}
        style={{ paddingLeft: `${8 + depth * 14}px` }}
      >
        {hasChildren ? (
          <svg
            className={cn("w-3 h-3 text-neutral-400 shrink-0 transition-transform", expanded && "rotate-90")}
            fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}
          >
            <path strokeLinecap="round" strokeLinejoin="round" d="M8.25 4.5l7.5 7.5-7.5 7.5" />
          </svg>
        ) : (
          <span className="w-3 shrink-0" />
        )}
        <span className={cn(
          "font-mono text-[10px] shrink-0",
          isSelected ? "text-brand-primary font-medium" : "text-neutral-400"
        )}>
          {section.number}
        </span>
        <span className={cn(
          "truncate text-[11px]",
          isSelected ? "text-brand-primary font-medium" : "text-neutral-700"
        )}>
          {section.title}
        </span>
        {confidenceBadge(section.quality_score)}
        <span className="ml-auto text-[9px] text-neutral-400 shrink-0 font-mono">
          p.{section.page}
        </span>
      </button>
      {hasChildren && expanded && (section.children || []).map((child) => (
        <SectionTreeItem
          key={child.number || child.title}
          section={child}
          selected={selected}
          onSelect={onSelect}
          depth={depth + 1}
        />
      ))}
    </div>
  );
}
