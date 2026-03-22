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
import { Card, CardHeader, CardBody } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { cn } from "@/lib/utils";

// ─── Helpers ──────────────────────────────────────────────────────────────

function confidenceBadge(score: number | null | undefined) {
  if (score == null) return null;
  const pct = (score * 100).toFixed(0);
  const color =
    score >= 0.95 ? "bg-emerald-100 text-emerald-700" :
    score >= 0.85 ? "bg-sky-100 text-sky-700" :
    score >= 0.70 ? "bg-amber-100 text-amber-700" :
    "bg-red-100 text-red-700";
  return <span className={cn("text-[10px] font-medium px-1.5 py-0.5 rounded-full", color)}>{pct}%</span>;
}

function countAll(sections: SectionNode[]): number {
  return sections.reduce((sum, s) => sum + 1 + countAll(s.children || []), 0);
}

/** Strip the section heading from content_html — show only body text */
function stripSectionHeading(html: string, sectionNumber: string, sectionTitle: string): string {
  if (!html) return html;
  // Remove leading <h2>, <h3>, <h4> tags that contain the section number or title
  let cleaned = html;
  // Remove first heading tag if it matches section title
  cleaned = cleaned.replace(
    /^\s*<h[2-4][^>]*>.*?<\/h[2-4]>\s*/i,
    ""
  );
  return cleaned.trim();
}

type Step = "select" | "explore";

// ─── Main Component ──────────────────────────────────────────────────────

export default function DocumentExplorerPage() {
  // Step 1 state
  const [step, setStep] = useState<Step>("select");
  const [protocols, setProtocols] = useState<ProtocolSummary[]>([]);
  const [selectedId, setSelectedId] = useState("");
  const [protocol, setProtocol] = useState<ProtocolFull | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Explore state
  const [selectedSection, setSelectedSection] = useState<SectionNode | null>(null);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);

  // PDF viewer
  const [pdfPage, setPdfPage] = useState(0);
  const [pdfAvailable, setPdfAvailable] = useState(true);
  const [showPdf, setShowPdf] = useState(true);

  // Verbatim
  const [instruction, setInstruction] = useState("");
  const [verbatimResult, setVerbatimResult] = useState<VerbatimResult | null>(null);
  const [verbatimLoading, setVerbatimLoading] = useState(false);
  const [verbatimFile, setVerbatimFile] = useState<File | null>(null);

  useEffect(() => {
    listProtocols().then(setProtocols).catch(() => {});
  }, []);

  // ── Actions ──

  const handleLoadProtocol = useCallback(async () => {
    if (!selectedId) return;
    setLoading(true);
    setError(null);
    try {
      const p = await getProtocol(selectedId);
      setProtocol(p);
      setSelectedSection(null);
      setVerbatimResult(null);
      setPdfAvailable(true);
      setStep("explore");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load");
    } finally {
      setLoading(false);
    }
  }, [selectedId]);

  const handleSectionClick = useCallback((section: SectionNode) => {
    setSelectedSection(section);
    setPdfPage(Math.max(0, section.page - 1));
    setVerbatimResult(null);
  }, []);

  const handleVerbatimExtract = useCallback(async () => {
    if (!instruction.trim() || !verbatimFile) return;
    setVerbatimLoading(true);
    setVerbatimResult(null);
    try {
      const result = await extractVerbatim(verbatimFile, instruction.trim(), "html");
      setVerbatimResult(result);
      // Navigate PDF to source page if available
      if (result.source_pages?.length > 0) {
        setPdfPage(Math.max(0, result.source_pages[0] - 1));
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Extraction failed");
    } finally {
      setVerbatimLoading(false);
    }
  }, [instruction, verbatimFile]);

  const handleBack = () => {
    setStep("select");
    setProtocol(null);
    setSelectedSection(null);
    setVerbatimResult(null);
  };

  const totalSections = protocol ? countAll(protocol.sections) : 0;

  // ── Step 1: Select Protocol ──

  if (step === "select") {
    return (
      <div className="min-h-screen bg-neutral-50">
        <div className="max-w-2xl mx-auto pt-16 px-6">
          <div className="text-center mb-8">
            <h1 className="text-2xl font-bold text-neutral-800">Document Explorer</h1>
            <p className="text-sm text-neutral-500 mt-2">
              Browse document structure, view extracted content alongside source pages
            </p>
          </div>

          <Card>
            <CardBody className="p-6 space-y-6">
              {/* Protocol selector */}
              <div>
                <label className="text-sm font-medium text-neutral-700 block mb-2">
                  Select a protocol from the library
                </label>
                <select
                  value={selectedId}
                  onChange={(e) => setSelectedId(e.target.value)}
                  className="w-full px-4 py-3 text-sm border border-neutral-200 rounded-xl bg-white focus:outline-none focus:ring-2 focus:ring-brand-primary/30 focus:border-brand-primary"
                >
                  <option value="">Choose protocol...</option>
                  {protocols.map((p) => (
                    <option key={p.protocol_id} value={p.protocol_id}>
                      {p.metadata.short_title || p.metadata.title || p.document_name} — {p.total_pages} pages
                    </option>
                  ))}
                </select>
              </div>

              {/* Action buttons */}
              <div className="flex gap-3">
                <button
                  onClick={handleLoadProtocol}
                  disabled={!selectedId || loading}
                  className={cn(
                    "flex-1 py-3 text-sm font-medium rounded-xl transition-colors",
                    selectedId && !loading
                      ? "bg-brand-primary text-white hover:bg-brand-french"
                      : "bg-neutral-100 text-neutral-400 cursor-not-allowed"
                  )}
                >
                  {loading ? (
                    <span className="flex items-center justify-center gap-2">
                      <span className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
                      Loading...
                    </span>
                  ) : (
                    "Explore Document"
                  )}
                </button>
              </div>

              {/* Error */}
              {error && (
                <div className="bg-red-50 rounded-lg px-4 py-3 text-sm text-red-700 border border-red-200">{error}</div>
              )}
            </CardBody>
          </Card>
        </div>
      </div>
    );
  }

  // ── Step 2: Explore ──

  if (!protocol) return null;

  return (
    <div className="h-screen flex flex-col bg-neutral-50 overflow-hidden">
      {/* Top bar */}
      <div className="h-12 bg-white border-b border-neutral-200 flex items-center px-4 shrink-0 gap-3">
        <button
          onClick={handleBack}
          className="text-neutral-400 hover:text-neutral-600 transition-colors"
        >
          <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M10.5 19.5L3 12m0 0l7.5-7.5M3 12h18" />
          </svg>
        </button>
        <div className="min-w-0">
          <h1 className="text-sm font-semibold text-neutral-800 truncate">
            {protocol.metadata.short_title || protocol.metadata.title || protocol.document_name}
          </h1>
        </div>
        <div className="flex items-center gap-2 ml-auto shrink-0">
          <Badge variant="neutral">{protocol.total_pages} pages</Badge>
          <Badge variant="brand">{totalSections} sections</Badge>
          <button
            onClick={() => setSidebarCollapsed(!sidebarCollapsed)}
            className="p-1.5 rounded-md hover:bg-neutral-100 text-neutral-400 hover:text-neutral-600 transition-colors"
            title={sidebarCollapsed ? "Show sections" : "Hide sections"}
          >
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              {sidebarCollapsed ? (
                <path strokeLinecap="round" strokeLinejoin="round" d="M3.75 6.75h16.5M3.75 12h16.5m-16.5 5.25h16.5" />
              ) : (
                <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
              )}
            </svg>
          </button>
          <label className="text-[11px] text-neutral-500 flex items-center gap-1 cursor-pointer">
            <input
              type="checkbox"
              checked={showPdf}
              onChange={(e) => setShowPdf(e.target.checked)}
              className="rounded border-neutral-300 w-3.5 h-3.5"
            />
            PDF
          </label>
        </div>
      </div>

      {/* Main canvas */}
      <div className="flex-1 flex overflow-hidden">
        {/* Section tree (collapsible) */}
        {!sidebarCollapsed && (
          <div className="w-[280px] shrink-0 bg-white border-r border-neutral-200 flex flex-col overflow-hidden">
            <div className="px-3 py-2 border-b border-neutral-100 flex items-center justify-between shrink-0">
              <span className="text-[11px] font-semibold text-neutral-600 uppercase tracking-wide">Sections</span>
            </div>
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
          </div>
        )}

        {/* Content panel */}
        <div className="flex-1 flex flex-col overflow-hidden min-w-0">
          {/* Section info bar */}
          {selectedSection && (
            <div className="px-4 py-2 bg-white border-b border-neutral-100 flex items-center gap-3 shrink-0">
              <span className="font-mono text-xs text-brand-primary bg-brand-primary-light px-2 py-0.5 rounded font-medium">
                {selectedSection.number}
              </span>
              <span className="text-sm font-medium text-neutral-800 truncate">{selectedSection.title}</span>
              <div className="flex items-center gap-2 ml-auto shrink-0">
                {confidenceBadge(selectedSection.quality_score)}
                <span className="text-[11px] text-neutral-400 font-mono">
                  p.{selectedSection.page}
                  {selectedSection.end_page && selectedSection.end_page !== selectedSection.page
                    ? `–${selectedSection.end_page}` : ""}
                </span>
              </div>
            </div>
          )}

          {/* Content + PDF */}
          <div className="flex-1 flex overflow-hidden">
            {/* Extracted text */}
            <div className="flex-1 overflow-y-auto p-5 min-w-0">
              {verbatimResult ? (
                <div>
                  <div className="flex items-center gap-2 mb-4 pb-3 border-b border-neutral-100">
                    <Badge variant="success">Verbatim</Badge>
                    <span className="text-xs text-neutral-500">
                      {verbatimResult.explanation}
                    </span>
                    <button
                      onClick={() => setVerbatimResult(null)}
                      className="ml-auto text-xs text-neutral-400 hover:text-neutral-600 underline"
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
                  dangerouslySetInnerHTML={{
                    __html: sanitizeHtml(
                      stripSectionHeading(
                        selectedSection.content_html,
                        selectedSection.number,
                        selectedSection.title
                      )
                    ),
                  }}
                />
              ) : selectedSection ? (
                <div className="text-center py-16 text-neutral-400">
                  <p className="text-sm">No content extracted for this section.</p>
                  <p className="text-xs mt-1">Use the verbatim instruction bar below to extract content.</p>
                </div>
              ) : (
                <div className="text-center py-16 text-neutral-400">
                  <svg className="w-12 h-12 mx-auto mb-3 text-neutral-300" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 14.25v-2.625a3.375 3.375 0 00-3.375-3.375h-1.5A1.125 1.125 0 0113.5 7.125v-1.5a3.375 3.375 0 00-3.375-3.375H8.25m0 12.75h7.5m-7.5 3H12M10.5 2.25H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 00-9-9z" />
                  </svg>
                  <p className="text-sm font-medium">Select a section</p>
                  <p className="text-xs mt-1">Click on a section in the tree to view its content</p>
                </div>
              )}
            </div>

            {/* PDF viewer */}
            {showPdf && (
              <div className="w-[400px] shrink-0 border-l border-neutral-200 bg-neutral-100 flex flex-col overflow-hidden">
                <div className="px-3 py-2 bg-white border-b border-neutral-100 flex items-center justify-between shrink-0">
                  <span className="text-[11px] font-semibold text-neutral-600 uppercase tracking-wide">Source</span>
                  <div className="flex items-center gap-1">
                    <button
                      onClick={() => setPdfPage(Math.max(0, pdfPage - 1))}
                      disabled={pdfPage <= 0}
                      className="p-1 rounded hover:bg-neutral-100 disabled:opacity-30 text-neutral-500"
                    >
                      <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                        <path strokeLinecap="round" strokeLinejoin="round" d="M15.75 19.5L8.25 12l7.5-7.5" />
                      </svg>
                    </button>
                    <span className="text-[11px] font-mono text-neutral-500 min-w-[50px] text-center">
                      {pdfPage + 1}/{protocol.total_pages}
                    </span>
                    <button
                      onClick={() => setPdfPage(Math.min(protocol.total_pages - 1, pdfPage + 1))}
                      disabled={pdfPage >= protocol.total_pages - 1}
                      className="p-1 rounded hover:bg-neutral-100 disabled:opacity-30 text-neutral-500"
                    >
                      <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                        <path strokeLinecap="round" strokeLinejoin="round" d="M8.25 4.5l7.5 7.5-7.5 7.5" />
                      </svg>
                    </button>
                  </div>
                </div>
                <div className="flex-1 overflow-auto flex items-start justify-center p-2">
                  {!pdfAvailable ? (
                    <div className="text-center py-12 text-neutral-400">
                      <p className="text-xs">PDF not available</p>
                    </div>
                  ) : (
                    <img
                      key={`${selectedId}-${pdfPage}`}
                      src={getPageImageUrl(selectedId, pdfPage)}
                      alt={`Page ${pdfPage + 1}`}
                      className="max-w-full shadow-lg rounded"
                      onError={() => setPdfAvailable(false)}
                    />
                  )}
                </div>
              </div>
            )}
          </div>

          {/* Verbatim instruction bar */}
          <div className="px-4 py-2.5 bg-white border-t border-neutral-200 shrink-0">
            <div className="flex items-center gap-2">
              <input
                type="file"
                accept=".pdf,.docx"
                onChange={(e) => setVerbatimFile(e.target.files?.[0] || null)}
                className="text-[11px] text-neutral-500 w-[160px] shrink-0 file:mr-1 file:py-0.5 file:px-2 file:rounded file:border-0 file:text-[10px] file:font-medium file:bg-neutral-100 file:text-neutral-600 file:cursor-pointer"
              />
              <input
                type="text"
                value={instruction}
                onChange={(e) => setInstruction(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && handleVerbatimExtract()}
                placeholder='Instruction: "Copy Section 5.1" or "Extract the inclusion criteria"'
                className="flex-1 px-3 py-1.5 text-sm border border-neutral-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-brand-primary/30"
              />
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
                {verbatimLoading ? "..." : "Extract"}
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

// ─── Section Tree ────────────────────────────────────────────────────────

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
  // Start collapsed at depth >= 1 (only show level 1 by default)
  const [expanded, setExpanded] = useState(depth < 1);
  const isSelected = selected === section;
  const hasChildren = (section.children || []).length > 0;

  return (
    <div>
      <button
        onClick={() => {
          onSelect(section);
          if (hasChildren) setExpanded(!expanded);
        }}
        className={cn(
          "w-full flex items-center gap-1.5 py-2 px-2 text-left transition-colors hover:bg-neutral-50",
          isSelected && "bg-brand-primary-light border-r-2 border-brand-primary"
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
          isSelected ? "text-brand-primary font-semibold" : "text-neutral-400"
        )}>
          {section.number}
        </span>
        <span className={cn(
          "truncate text-[11px] leading-tight",
          isSelected ? "text-brand-primary font-medium" : "text-neutral-700"
        )}>
          {section.title}
        </span>
        <div className="ml-auto flex items-center gap-1 shrink-0">
          {confidenceBadge(section.quality_score)}
          <span className="text-[9px] text-neutral-400 font-mono">
            {section.page}
          </span>
        </div>
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
