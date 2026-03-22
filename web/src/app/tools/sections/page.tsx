"use client";

import { useEffect, useState, useCallback } from "react";
import {
  listProtocols,
  getProtocol,
  parseSections,
  getPageImageUrl,
  extractVerbatim,
  type ProtocolSummary,
  type ProtocolFull,
  type SectionNode,
  type ParsedSection,
  type VerbatimResult,
} from "@/lib/api";
import { sanitizeHtml } from "@/lib/sanitize";
import { Card, CardBody } from "@/components/ui/Card";
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

function countAll(sections: SectionLike[]): number {
  return sections.reduce((sum, s) => sum + 1 + countAll(s.children || []), 0);
}

type SectionLike = {
  number: string;
  title: string;
  page: number;
  end_page: number | null;
  level: number;
  content_html?: string;
  quality_score?: number | null;
  children: SectionLike[];
};

function toSectionLike(sections: (SectionNode | ParsedSection)[]): SectionLike[] {
  return sections.map((s) => ({
    number: s.number,
    title: s.title,
    page: s.page,
    end_page: s.end_page,
    level: s.level,
    content_html: (s as SectionNode).content_html || undefined,
    quality_score: (s as SectionNode).quality_score ?? null,
    children: toSectionLike(s.children || []),
  }));
}

function stripSectionHeading(html: string): string {
  if (!html) return html;
  return html.replace(/^\s*<h[2-4][^>]*>.*?<\/h[2-4]>\s*/i, "").trim();
}

type Step = "select" | "explore";

// ─── Main Component ──────────────────────────────────────────────────────

export default function DocumentExplorerPage() {
  const [step, setStep] = useState<Step>("select");
  const [protocols, setProtocols] = useState<ProtocolSummary[]>([]);
  const [selectedId, setSelectedId] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Explore state
  const [sections, setSections] = useState<SectionLike[]>([]);
  const [docName, setDocName] = useState("");
  const [totalPages, setTotalPages] = useState(0);
  const [selectedSection, setSelectedSection] = useState<SectionLike | null>(null);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [parseMethod, setParseMethod] = useState("");

  // Upload state
  const [uploadFile, setUploadFile] = useState<File | null>(null);

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

  // ── Load from library ──
  const handleLoadFromLibrary = useCallback(async () => {
    if (!selectedId) return;
    setLoading(true);
    setError(null);
    try {
      const p = await getProtocol(selectedId);
      setSections(toSectionLike(p.sections));
      setDocName(p.metadata.short_title || p.metadata.title || p.document_name);
      setTotalPages(p.total_pages);
      setParseMethod("stored");
      setPdfAvailable(true);
      setSelectedSection(null);
      setVerbatimResult(null);
      setStep("explore");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load");
    } finally {
      setLoading(false);
    }
  }, [selectedId]);

  // ── Parse uploaded file ──
  const handleParseUpload = useCallback(async () => {
    if (!uploadFile) return;
    setLoading(true);
    setError(null);
    try {
      const result = await parseSections(uploadFile);
      setSections(toSectionLike(result.sections));
      setDocName(uploadFile.name);
      setTotalPages(0); // unknown for uploaded files
      setParseMethod(result.method);
      setPdfAvailable(false); // no stored PDF for uploads
      setSelectedId("");
      setSelectedSection(null);
      setVerbatimResult(null);
      setVerbatimFile(uploadFile); // pre-set for verbatim extraction
      setStep("explore");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to parse");
    } finally {
      setLoading(false);
    }
  }, [uploadFile]);

  const handleSectionClick = useCallback((section: SectionLike) => {
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
    setSections([]);
    setSelectedSection(null);
    setVerbatimResult(null);
    setError(null);
  };

  const totalSections = countAll(sections);

  // ── STEP 1: Select Source ──

  if (step === "select") {
    return (
      <div className="min-h-screen bg-neutral-50">
        <div className="max-w-2xl mx-auto pt-12 px-6">
          <div className="text-center mb-8">
            <h1 className="text-2xl font-bold text-neutral-800">Document Explorer</h1>
            <p className="text-sm text-neutral-500 mt-2">
              Parse document structure and explore sections with source pages
            </p>
          </div>

          <div className="space-y-4">
            {/* Option 1: From Library */}
            <Card>
              <CardBody className="p-5">
                <h3 className="text-sm font-semibold text-neutral-800 mb-3">From Protocol Library</h3>
                <div className="flex gap-3">
                  <select
                    value={selectedId}
                    onChange={(e) => setSelectedId(e.target.value)}
                    className="flex-1 px-3 py-2.5 text-sm border border-neutral-200 rounded-lg bg-white focus:outline-none focus:ring-2 focus:ring-brand-primary/30"
                  >
                    <option value="">Choose protocol...</option>
                    {protocols.map((p) => (
                      <option key={p.protocol_id} value={p.protocol_id}>
                        {p.metadata.short_title || p.metadata.title || p.document_name} — {p.total_pages}p
                      </option>
                    ))}
                  </select>
                  <button
                    onClick={handleLoadFromLibrary}
                    disabled={!selectedId || loading}
                    className={cn(
                      "px-5 py-2.5 text-sm font-medium rounded-lg transition-colors whitespace-nowrap",
                      selectedId && !loading
                        ? "bg-brand-primary text-white hover:bg-brand-french"
                        : "bg-neutral-100 text-neutral-400 cursor-not-allowed"
                    )}
                  >
                    {loading && selectedId ? "Loading..." : "Explore"}
                  </button>
                </div>
              </CardBody>
            </Card>

            <div className="text-center text-xs text-neutral-400 font-medium">OR</div>

            {/* Option 2: Upload Document */}
            <Card>
              <CardBody className="p-5">
                <h3 className="text-sm font-semibold text-neutral-800 mb-3">Upload Document</h3>
                <div className="flex gap-3">
                  <input
                    type="file"
                    accept=".pdf,.docx"
                    onChange={(e) => setUploadFile(e.target.files?.[0] || null)}
                    className="flex-1 text-sm text-neutral-600 file:mr-3 file:py-2 file:px-4 file:rounded-lg file:border-0 file:text-xs file:font-medium file:bg-brand-primary file:text-white file:cursor-pointer hover:file:bg-brand-french"
                  />
                  <button
                    onClick={handleParseUpload}
                    disabled={!uploadFile || loading}
                    className={cn(
                      "px-5 py-2.5 text-sm font-medium rounded-lg transition-colors whitespace-nowrap",
                      uploadFile && !loading
                        ? "bg-brand-primary text-white hover:bg-brand-french"
                        : "bg-neutral-100 text-neutral-400 cursor-not-allowed"
                    )}
                  >
                    {loading && uploadFile ? "Parsing..." : "Parse & Explore"}
                  </button>
                </div>
                <p className="text-[11px] text-neutral-400 mt-2">
                  Sections are parsed deterministically using document structure. No LLM required.
                </p>
              </CardBody>
            </Card>

            {error && (
              <div className="bg-red-50 rounded-lg px-4 py-3 text-sm text-red-700 border border-red-200">{error}</div>
            )}
          </div>
        </div>
      </div>
    );
  }

  // ── STEP 2: Explore ──

  return (
    <div className="h-screen flex flex-col bg-neutral-50 overflow-hidden">
      {/* Top bar */}
      <div className="h-11 bg-white border-b border-neutral-200 flex items-center px-4 shrink-0 gap-3">
        <button onClick={handleBack} className="text-neutral-400 hover:text-neutral-600 transition-colors">
          <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M10.5 19.5L3 12m0 0l7.5-7.5M3 12h18" />
          </svg>
        </button>
        <h1 className="text-sm font-semibold text-neutral-800 truncate">{docName}</h1>
        <div className="flex items-center gap-2 ml-auto shrink-0">
          {parseMethod && <Badge variant="neutral">{parseMethod}</Badge>}
          <Badge variant="brand">{totalSections} sections</Badge>
          {totalPages > 0 && <Badge variant="neutral">{totalPages}p</Badge>}
          <button
            onClick={() => setSidebarCollapsed(!sidebarCollapsed)}
            className="p-1 rounded hover:bg-neutral-100 text-neutral-400 hover:text-neutral-600"
            title={sidebarCollapsed ? "Show sections" : "Collapse sections"}
          >
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M3.75 6.75h16.5M3.75 12h16.5m-16.5 5.25h16.5" />
            </svg>
          </button>
          {totalPages > 0 && (
            <label className="text-[11px] text-neutral-500 flex items-center gap-1 cursor-pointer">
              <input
                type="checkbox"
                checked={showPdf}
                onChange={(e) => setShowPdf(e.target.checked)}
                className="rounded border-neutral-300 w-3.5 h-3.5"
              />
              PDF
            </label>
          )}
        </div>
      </div>

      {/* Canvas */}
      <div className="flex-1 flex overflow-hidden">
        {/* Section tree */}
        {!sidebarCollapsed && (
          <div className="w-[280px] shrink-0 bg-white border-r border-neutral-200 flex flex-col overflow-hidden">
            <div className="px-3 py-2 border-b border-neutral-100 shrink-0">
              <span className="text-[11px] font-semibold text-neutral-600 uppercase tracking-wide">
                Section Hierarchy
              </span>
            </div>
            <div className="flex-1 overflow-y-auto">
              {sections.length === 0 ? (
                <div className="p-4 text-xs text-neutral-400 text-center">No sections parsed</div>
              ) : (
                sections.map((s, i) => (
                  <SectionTreeItem
                    key={`${s.number}-${i}`}
                    section={s}
                    selected={selectedSection}
                    onSelect={handleSectionClick}
                    depth={0}
                  />
                ))
              )}
            </div>
          </div>
        )}

        {/* Content + PDF */}
        <div className="flex-1 flex flex-col overflow-hidden min-w-0">
          {/* Section info */}
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

          {/* Panels */}
          <div className="flex-1 flex overflow-hidden">
            {/* Text content */}
            <div className="flex-1 overflow-y-auto p-5 min-w-0">
              {verbatimResult ? (
                <div>
                  <div className="flex items-center gap-2 mb-4 pb-3 border-b border-neutral-100">
                    <Badge variant="success">Verbatim</Badge>
                    <span className="text-xs text-neutral-500">{verbatimResult.explanation}</span>
                    {verbatimResult.source_pages?.length > 0 && (
                      <span className="text-xs text-neutral-400">Pages {verbatimResult.source_pages.join(", ")}</span>
                    )}
                    <button onClick={() => setVerbatimResult(null)} className="ml-auto text-xs text-neutral-400 hover:text-neutral-600 underline">
                      Clear
                    </button>
                  </div>
                  <div className="section-content max-w-none" dangerouslySetInnerHTML={{ __html: sanitizeHtml(verbatimResult.text) }} />
                </div>
              ) : selectedSection?.content_html ? (
                <div className="section-content max-w-none" dangerouslySetInnerHTML={{ __html: sanitizeHtml(stripSectionHeading(selectedSection.content_html)) }} />
              ) : selectedSection ? (
                <div className="text-center py-16 text-neutral-400">
                  <p className="text-sm">No content extracted for this section.</p>
                  <p className="text-xs mt-1">Use the instruction bar below to extract content verbatim.</p>
                </div>
              ) : (
                <div className="text-center py-16 text-neutral-400">
                  <svg className="w-12 h-12 mx-auto mb-3 text-neutral-300" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 14.25v-2.625a3.375 3.375 0 00-3.375-3.375h-1.5A1.125 1.125 0 0113.5 7.125v-1.5a3.375 3.375 0 00-3.375-3.375H8.25m0 12.75h7.5m-7.5 3H12M10.5 2.25H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 00-9-9z" />
                  </svg>
                  <p className="text-sm font-medium">Select a section</p>
                  <p className="text-xs mt-1">Click any section in the hierarchy to view its extracted content</p>
                </div>
              )}
            </div>

            {/* PDF viewer */}
            {showPdf && totalPages > 0 && (
              <div className="w-[400px] shrink-0 border-l border-neutral-200 bg-neutral-100 flex flex-col overflow-hidden">
                <div className="px-3 py-2 bg-white border-b border-neutral-100 flex items-center justify-between shrink-0">
                  <span className="text-[11px] font-semibold text-neutral-600 uppercase tracking-wide">Source</span>
                  <div className="flex items-center gap-1">
                    <button onClick={() => setPdfPage(Math.max(0, pdfPage - 1))} disabled={pdfPage <= 0} className="p-1 rounded hover:bg-neutral-100 disabled:opacity-30 text-neutral-500">
                      <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}><path strokeLinecap="round" strokeLinejoin="round" d="M15.75 19.5L8.25 12l7.5-7.5" /></svg>
                    </button>
                    <span className="text-[11px] font-mono text-neutral-500 min-w-[50px] text-center">{pdfPage + 1}/{totalPages}</span>
                    <button onClick={() => setPdfPage(Math.min(totalPages - 1, pdfPage + 1))} disabled={pdfPage >= totalPages - 1} className="p-1 rounded hover:bg-neutral-100 disabled:opacity-30 text-neutral-500">
                      <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}><path strokeLinecap="round" strokeLinejoin="round" d="M8.25 4.5l7.5 7.5-7.5 7.5" /></svg>
                    </button>
                  </div>
                </div>
                <div className="flex-1 overflow-auto flex items-start justify-center p-2">
                  {!pdfAvailable ? (
                    <div className="text-center py-12 text-neutral-400">
                      <p className="text-xs">PDF not available for this protocol</p>
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
          <div className="px-4 py-2 bg-white border-t border-neutral-200 shrink-0">
            <div className="flex items-center gap-2">
              {!verbatimFile && (
                <input
                  type="file"
                  accept=".pdf,.docx"
                  onChange={(e) => setVerbatimFile(e.target.files?.[0] || null)}
                  className="text-[11px] text-neutral-500 w-[150px] shrink-0 file:mr-1 file:py-0.5 file:px-2 file:rounded file:border-0 file:text-[10px] file:font-medium file:bg-neutral-100 file:text-neutral-600 file:cursor-pointer"
                />
              )}
              {verbatimFile && (
                <span className="text-[11px] text-neutral-500 shrink-0 flex items-center gap-1">
                  <span className="truncate max-w-[120px]">{verbatimFile.name}</span>
                  <button onClick={() => setVerbatimFile(null)} className="text-neutral-400 hover:text-neutral-600">×</button>
                </span>
              )}
              <input
                type="text"
                value={instruction}
                onChange={(e) => setInstruction(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && handleVerbatimExtract()}
                placeholder='e.g. "Copy Section 5.1" or "Extract the inclusion criteria"'
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

      {error && (
        <div className="absolute bottom-16 left-1/2 -translate-x-1/2 bg-red-50 rounded-lg px-4 py-2 text-xs text-red-700 border border-red-200 shadow-lg">
          {error}
          <button onClick={() => setError(null)} className="ml-3 underline">dismiss</button>
        </div>
      )}
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
  section: SectionLike;
  selected: SectionLike | null;
  onSelect: (s: SectionLike) => void;
  depth: number;
}) {
  // All levels expanded by default
  const [expanded, setExpanded] = useState(true);
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
          "w-full flex items-center gap-1.5 py-1.5 px-2 text-left transition-colors hover:bg-neutral-50",
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
          <span className="text-[9px] text-neutral-400 font-mono">{section.page}</span>
        </div>
      </button>
      {hasChildren && expanded && (section.children || []).map((child, i) => (
        <SectionTreeItem
          key={`${child.number}-${i}`}
          section={child}
          selected={selected}
          onSelect={onSelect}
          depth={depth + 1}
        />
      ))}
    </div>
  );
}
