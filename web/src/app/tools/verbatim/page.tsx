"use client";

import { useState, useCallback, useEffect } from "react";
import {
  extractVerbatim,
  extractVerbatimFromProtocol,
  listProtocols,
  getProtocol,
  type VerbatimResult,
  type ProtocolSummary,
  type ProtocolFull,
  type SectionNode,
} from "@/lib/api";
import { sanitizeHtml } from "@/lib/sanitize";
import { TopBar } from "@/components/layout/TopBar";
import { Card, CardHeader, CardBody } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { cn } from "@/lib/utils";

const EXAMPLE_INSTRUCTIONS = [
  "Copy Section 5.1",
  "Extract the inclusion criteria",
  "Get the Schedule of Activities table",
  "Copy the primary endpoint definition",
  "Extract the statistical analysis plan",
  "Copy the dosing regimen",
];

type SourceMode = "upload" | "library";

export default function VerbatimExtractPage() {
  const [sourceMode, setSourceMode] = useState<SourceMode>("library");

  // Upload mode state
  const [file, setFile] = useState<File | null>(null);
  const [instruction, setInstruction] = useState("");
  const [outputFormat, setOutputFormat] = useState<"html" | "text">("html");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<VerbatimResult | null>(null);

  // Library mode state
  const [protocols, setProtocols] = useState<ProtocolSummary[]>([]);
  const [selectedProtocolId, setSelectedProtocolId] = useState("");
  const [protocol, setProtocol] = useState<ProtocolFull | null>(null);
  const [selectedSection, setSelectedSection] = useState<SectionNode | null>(null);
  const [loadingProtocol, setLoadingProtocol] = useState(false);

  // Load protocol list
  useEffect(() => {
    listProtocols().then(setProtocols).catch(() => {});
  }, []);

  const [libVerbatimResult, setLibVerbatimResult] = useState<VerbatimResult | null>(null);
  const [libVerbatimLoading, setLibVerbatimLoading] = useState(false);

  // Load full protocol when selected
  const handleProtocolSelect = useCallback(async (id: string) => {
    setSelectedProtocolId(id);
    setProtocol(null);
    setSelectedSection(null);
    setLibVerbatimResult(null);
    if (!id) return;
    setLoadingProtocol(true);
    try {
      const p = await getProtocol(id);
      setProtocol(p);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load protocol");
    } finally {
      setLoadingProtocol(false);
    }
  }, []);

  // Auto-extract when section selected and has no content_html
  const handleSectionSelect = useCallback(async (section: SectionNode | null) => {
    setSelectedSection(section);
    setLibVerbatimResult(null);
    if (!section || section.content_html) return;
    if (!selectedProtocolId) return;

    setLibVerbatimLoading(true);
    try {
      const sectionRef = section.number
        ? `Copy Section ${section.number}`
        : `Copy the "${section.title}" section`;
      const result = await extractVerbatimFromProtocol(selectedProtocolId, sectionRef, "html");
      setLibVerbatimResult(result);
    } catch {
      // Fail silently — user sees "no content" message
    } finally {
      setLibVerbatimLoading(false);
    }
  }, [selectedProtocolId]);

  // Extract from uploaded file
  const handleExtract = useCallback(async () => {
    if (!file || !instruction.trim()) return;
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const r = await extractVerbatim(file, instruction.trim(), outputFormat);
      setResult(r);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Extraction failed");
    } finally {
      setLoading(false);
    }
  }, [file, instruction, outputFormat]);

  // Flatten section tree for dropdown
  function flattenSections(sections: SectionNode[], prefix = ""): { node: SectionNode; label: string }[] {
    const items: { node: SectionNode; label: string }[] = [];
    for (const s of sections) {
      const indent = "  ".repeat(s.level - 1);
      items.push({ node: s, label: `${indent}${s.number} ${s.title}` });
      if (s.children) items.push(...flattenSections(s.children, prefix));
    }
    return items;
  }

  const sectionOptions = protocol ? flattenSections(protocol.sections) : [];

  return (
    <div>
      <TopBar title="Verbatim Extract" subtitle="Extract exact content from protocol documents — zero hallucination" />

      <div className="p-6 space-y-4">
        {/* Source mode toggle */}
        <Card>
          <CardBody className="p-4">
            <div className="flex items-center gap-2 mb-4">
              <button
                onClick={() => { setSourceMode("library"); setResult(null); setError(null); }}
                className={cn(
                  "px-4 py-2 text-sm font-medium rounded-lg transition-colors",
                  sourceMode === "library"
                    ? "bg-brand-primary text-white"
                    : "bg-neutral-100 text-neutral-600 hover:bg-neutral-200"
                )}
              >
                From Protocol Library
              </button>
              <button
                onClick={() => { setSourceMode("upload"); setResult(null); setError(null); }}
                className={cn(
                  "px-4 py-2 text-sm font-medium rounded-lg transition-colors",
                  sourceMode === "upload"
                    ? "bg-brand-primary text-white"
                    : "bg-neutral-100 text-neutral-600 hover:bg-neutral-200"
                )}
              >
                Upload PDF
              </button>
            </div>

            {sourceMode === "library" ? (
              <div className="space-y-3">
                {/* Protocol selector */}
                <div>
                  <label className="text-xs font-medium text-neutral-600 block mb-1">Protocol</label>
                  <select
                    value={selectedProtocolId}
                    onChange={(e) => handleProtocolSelect(e.target.value)}
                    className="w-full px-3 py-2 text-sm border border-neutral-200 rounded-lg bg-white focus:outline-none focus:ring-2 focus:ring-brand-primary/30 focus:border-brand-primary"
                  >
                    <option value="">Select a protocol...</option>
                    {protocols.map((p) => (
                      <option key={p.protocol_id} value={p.protocol_id}>
                        {p.metadata.short_title || p.metadata.title || p.document_name}
                      </option>
                    ))}
                  </select>
                </div>

                {/* Section selector */}
                {protocol && sectionOptions.length > 0 && (
                  <div>
                    <label className="text-xs font-medium text-neutral-600 block mb-1">
                      Section ({sectionOptions.length} available)
                    </label>
                    <select
                      value={selectedSection?.number || ""}
                      onChange={(e) => {
                        const found = sectionOptions.find((o) => o.node.number === e.target.value);
                        handleSectionSelect(found?.node || null);
                      }}
                      className="w-full px-3 py-2 text-sm border border-neutral-200 rounded-lg bg-white font-mono focus:outline-none focus:ring-2 focus:ring-brand-primary/30 focus:border-brand-primary"
                    >
                      <option value="">Select a section...</option>
                      {sectionOptions.map((opt) => (
                        <option key={opt.node.number} value={opt.node.number}>
                          {opt.label} (p.{opt.node.page})
                        </option>
                      ))}
                    </select>
                  </div>
                )}

                {protocol && sectionOptions.length === 0 && (
                  <p className="text-xs text-neutral-400 italic">
                    This protocol has no parsed sections. Use the upload mode to extract content.
                  </p>
                )}

                {loadingProtocol && (
                  <div className="flex items-center gap-2 text-sm text-neutral-400">
                    <div className="w-4 h-4 border-2 border-brand-primary border-t-transparent rounded-full animate-spin" />
                    Loading protocol...
                  </div>
                )}
              </div>
            ) : (
              <div className="space-y-3">
                {/* File upload */}
                <div>
                  <label className="text-xs font-medium text-neutral-600 block mb-1">Protocol Document</label>
                  <input
                    type="file"
                    accept=".pdf,.docx"
                    onChange={(e) => setFile(e.target.files?.[0] || null)}
                    className="w-full text-sm text-neutral-600 file:mr-3 file:py-1.5 file:px-3 file:rounded-lg file:border-0 file:text-xs file:font-medium file:bg-brand-primary file:text-white file:cursor-pointer hover:file:bg-brand-french"
                  />
                </div>

                {/* Instruction */}
                <div>
                  <label className="text-xs font-medium text-neutral-600 block mb-1">Instruction</label>
                  <textarea
                    value={instruction}
                    onChange={(e) => setInstruction(e.target.value)}
                    placeholder='e.g., "Copy Section 5.1" or "Extract the inclusion criteria"'
                    rows={2}
                    className="w-full px-3 py-2 text-sm border border-neutral-200 rounded-lg bg-white focus:outline-none focus:ring-2 focus:ring-brand-primary/30 focus:border-brand-primary resize-none"
                  />
                  <div className="flex flex-wrap gap-1.5 mt-2">
                    {EXAMPLE_INSTRUCTIONS.map((ex) => (
                      <button
                        key={ex}
                        onClick={() => setInstruction(ex)}
                        className="px-2 py-1 text-[10px] bg-neutral-100 text-neutral-600 rounded-md hover:bg-neutral-200 transition-colors"
                      >
                        {ex}
                      </button>
                    ))}
                  </div>
                </div>

                {/* Options + submit */}
                <div className="flex items-end gap-3">
                  <div>
                    <label className="text-xs font-medium text-neutral-600 block mb-1">Format</label>
                    <select
                      value={outputFormat}
                      onChange={(e) => setOutputFormat(e.target.value as "html" | "text")}
                      className="px-3 py-2 text-sm border border-neutral-200 rounded-lg bg-white focus:outline-none focus:ring-2 focus:ring-brand-primary/30"
                    >
                      <option value="html">HTML (formatted)</option>
                      <option value="text">Plain Text</option>
                    </select>
                  </div>
                  <button
                    onClick={handleExtract}
                    disabled={!file || !instruction.trim() || loading}
                    className={cn(
                      "px-5 py-2 text-sm font-medium rounded-lg transition-colors",
                      file && instruction.trim() && !loading
                        ? "bg-brand-primary text-white hover:bg-brand-french"
                        : "bg-neutral-100 text-neutral-400 cursor-not-allowed"
                    )}
                  >
                    {loading ? (
                      <span className="flex items-center gap-2">
                        <span className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
                        Extracting...
                      </span>
                    ) : (
                      "Extract"
                    )}
                  </button>
                </div>
              </div>
            )}
          </CardBody>
        </Card>

        {/* Error */}
        {error && (
          <div className="bg-red-50 rounded-lg px-4 py-3 text-sm text-red-700 border border-red-200">
            {error}
          </div>
        )}

        {/* Library mode: side-by-side comparison */}
        {sourceMode === "library" && selectedSection && (
          <VerbatimComparison
            protocolId={selectedProtocolId}
            section={selectedSection}
            extractedHtml={libVerbatimResult?.text || selectedSection.content_html || ""}
            explanation={libVerbatimResult?.explanation || ""}
            sourcePages={libVerbatimResult?.source_pages || [selectedSection.page]}
            loading={libVerbatimLoading}
            isVerbatim={true}
          />
        )}

        {/* Upload mode: show extraction result */}
        {sourceMode === "upload" && result && (
          <VerbatimComparison
            protocolId=""
            section={null}
            extractedHtml={outputFormat === "html" ? result.text : ""}
            extractedText={outputFormat === "text" ? result.text : ""}
            explanation={result.explanation}
            sourcePages={result.source_pages}
            sectionsFound={result.sections_found}
            loading={false}
            isVerbatim={result.is_verbatim}
            contentType={result.content_type}
          />
        )}
      </div>
    </div>
  );
}

// ─── Side-by-Side Verbatim Comparison ──────────────────────────────────────

const API = process.env.NEXT_PUBLIC_API_URL || "";

function VerbatimComparison({
  protocolId,
  section,
  extractedHtml,
  extractedText,
  explanation,
  sourcePages,
  sectionsFound,
  loading,
  isVerbatim,
  contentType,
}: {
  protocolId: string;
  section: SectionNode | null;
  extractedHtml?: string;
  extractedText?: string;
  explanation: string;
  sourcePages: number[];
  sectionsFound?: string[];
  loading: boolean;
  isVerbatim: boolean;
  contentType?: string;
}) {
  const [viewMode, setViewMode] = useState<"side-by-side" | "extracted" | "source">("side-by-side");
  const [pdfPage, setPdfPage] = useState(sourcePages[0] || 0);
  const [pdfAvailable, setPdfAvailable] = useState(false);

  // Check PDF availability
  useEffect(() => {
    if (!protocolId) { setPdfAvailable(false); return; }
    fetch(`${API}/api/protocols/${protocolId}/page-image/${sourcePages[0] || 0}`)
      .then((r) => setPdfAvailable(r.ok))
      .catch(() => setPdfAvailable(false));
  }, [protocolId, sourcePages]);

  const hasContent = !!(extractedHtml || extractedText);
  const extractedContent = extractedHtml || extractedText || "";

  // Compute fidelity indicators
  const fidelity = computeFidelity(extractedContent);

  return (
    <div className="bg-white rounded-xl border border-neutral-200 overflow-hidden">
      {/* Header */}
      <div className="px-4 py-3 border-b border-neutral-200 flex items-center justify-between">
        <div className="flex items-center gap-3">
          {section && (
            <>
              <span className="font-mono text-xs text-neutral-400 bg-neutral-100 px-2 py-0.5 rounded">
                {section.number}
              </span>
              <h3 className="text-sm font-semibold text-neutral-800">{section.title}</h3>
            </>
          )}
          {!section && sectionsFound && sectionsFound.length > 0 && (
            <h3 className="text-sm font-semibold text-neutral-800">
              Sections {sectionsFound.join(", ")}
            </h3>
          )}
          <div className="flex items-center gap-1.5">
            {isVerbatim && <Badge variant="success">Verbatim Copy</Badge>}
            {contentType && <Badge variant="brand">{contentType}</Badge>}
            {sourcePages.length > 0 && (
              <Badge variant="neutral">
                Page{sourcePages.length > 1 ? "s" : ""} {sourcePages.join(", ")}
              </Badge>
            )}
          </div>
        </div>
        {/* View mode toggle */}
        <div className="flex items-center gap-1 bg-neutral-100 rounded-lg p-0.5">
          {(["side-by-side", "extracted", "source"] as const).map((mode) => (
            <button
              key={mode}
              onClick={() => setViewMode(mode)}
              disabled={mode === "source" && !pdfAvailable}
              className={cn(
                "px-2.5 py-1 text-[10px] font-medium rounded-md transition-colors",
                viewMode === mode
                  ? "bg-white text-neutral-800 shadow-sm"
                  : "text-neutral-500 hover:text-neutral-700",
                mode === "source" && !pdfAvailable && "opacity-40 cursor-not-allowed"
              )}
            >
              {mode === "side-by-side" ? "Compare" : mode === "extracted" ? "Extracted" : "Source PDF"}
            </button>
          ))}
        </div>
      </div>

      {/* Fidelity bar */}
      {hasContent && (
        <div className="px-4 py-2 bg-neutral-50 border-b border-neutral-100 flex items-center gap-4">
          <span className="text-[10px] font-semibold text-neutral-500 uppercase tracking-wider">Extraction Fidelity</span>
          <div className="flex items-center gap-3">
            <FidelityBadge label="Paragraphs" count={fidelity.paragraphs} icon="P" />
            <FidelityBadge label="Bold spans" count={fidelity.boldSpans} icon="B" />
            <FidelityBadge label="Italic spans" count={fidelity.italicSpans} icon="I" />
            <FidelityBadge label="List items" count={fidelity.listItems} icon="Li" />
            <FidelityBadge label="Tables" count={fidelity.tables} icon="T" />
            <FidelityBadge label="Headings" count={fidelity.headings} icon="H" />
          </div>
          <div className="ml-auto flex items-center gap-1.5">
            <span className="text-[10px] text-neutral-400">Method:</span>
            <Badge variant={isVerbatim ? "success" : "warning"}>
              {isVerbatim ? "Direct Copy (no LLM)" : "LLM-assisted"}
            </Badge>
          </div>
        </div>
      )}

      {/* Explanation */}
      {explanation && (
        <div className="px-4 py-1.5 border-b border-neutral-100">
          <p className="text-[11px] text-neutral-400">{explanation}</p>
        </div>
      )}

      {/* Content area */}
      {loading ? (
        <div className="flex items-center justify-center py-12">
          <div className="text-center">
            <div className="w-6 h-6 border-2 border-brand-primary border-t-transparent rounded-full animate-spin mx-auto mb-2" />
            <p className="text-xs text-neutral-500">Extracting verbatim content...</p>
          </div>
        </div>
      ) : !hasContent ? (
        <div className="p-8 text-center">
          <p className="text-sm text-neutral-400 italic">
            Content extraction requires the source PDF. The PDF for this protocol may not be available on the server.
          </p>
        </div>
      ) : (
        <div className={cn(
          "flex",
          viewMode === "side-by-side" ? "divide-x divide-neutral-200" : ""
        )}>
          {/* Source PDF panel */}
          {(viewMode === "side-by-side" || viewMode === "source") && pdfAvailable && (
            <div className={cn(
              "flex flex-col bg-neutral-100",
              viewMode === "side-by-side" ? "w-1/2" : "w-full"
            )}>
              <div className="px-3 py-1.5 bg-white border-b border-neutral-100 flex items-center justify-between shrink-0">
                <span className="text-[10px] font-semibold text-neutral-600 uppercase tracking-wide">
                  Source Document
                </span>
                <div className="flex items-center gap-1">
                  <button onClick={() => setPdfPage(Math.max(0, pdfPage - 1))} className="p-0.5 rounded hover:bg-neutral-100 text-neutral-500">
                    <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}><path strokeLinecap="round" strokeLinejoin="round" d="M15.75 19.5L8.25 12l7.5-7.5" /></svg>
                  </button>
                  <span className="text-[10px] text-neutral-500 font-mono min-w-[40px] text-center">p.{pdfPage}</span>
                  <button onClick={() => setPdfPage(pdfPage + 1)} className="p-0.5 rounded hover:bg-neutral-100 text-neutral-500">
                    <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}><path strokeLinecap="round" strokeLinejoin="round" d="M8.25 4.5l7.5 7.5-7.5 7.5" /></svg>
                  </button>
                </div>
              </div>
              <div className="overflow-auto p-2" style={{ maxHeight: "600px" }}>
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img
                  key={pdfPage}
                  src={`${API}/api/protocols/${protocolId}/page-image/${pdfPage}`}
                  alt={`Source page ${pdfPage}`}
                  className="w-full rounded shadow-sm bg-white"
                  onError={(e) => { (e.target as HTMLImageElement).style.display = "none"; }}
                />
              </div>
            </div>
          )}

          {/* Extracted content panel */}
          {(viewMode === "side-by-side" || viewMode === "extracted") && (
            <div className={cn(
              "flex flex-col",
              viewMode === "side-by-side" ? "w-1/2" : "w-full"
            )}>
              <div className="px-3 py-1.5 bg-white border-b border-neutral-100 flex items-center justify-between shrink-0">
                <span className="text-[10px] font-semibold text-neutral-600 uppercase tracking-wide">
                  Extracted Content
                </span>
                <Badge variant="success" className="text-[9px]">
                  {isVerbatim ? "Zero Hallucination" : "LLM-assisted"}
                </Badge>
              </div>
              <div className="overflow-auto p-4" style={{ maxHeight: "600px" }}>
                {extractedHtml ? (
                  <div
                    className="section-content max-w-none text-sm"
                    dangerouslySetInnerHTML={{ __html: sanitizeHtml(extractedHtml) }}
                  />
                ) : extractedText ? (
                  <pre className="text-xs text-neutral-700 bg-neutral-50 rounded-lg p-4 overflow-x-auto whitespace-pre-wrap font-mono border border-neutral-200">
                    {extractedText}
                  </pre>
                ) : null}
              </div>
            </div>
          )}

          {/* No PDF available — show only extracted */}
          {viewMode === "source" && !pdfAvailable && (
            <div className="w-full p-8 text-center">
              <p className="text-sm text-neutral-400">
                Source PDF not available for this protocol. Use the "Extracted" view to see the content.
              </p>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ─── Fidelity computation ──────────────────────────────────────────────────

function computeFidelity(html: string) {
  const p = (html.match(/<p[\s>]/gi) || []).length;
  const bold = (html.match(/<(strong|b)[\s>]/gi) || []).length;
  const italic = (html.match(/<(em|i)[\s>]/gi) || []).length;
  const li = (html.match(/<li[\s>]/gi) || []).length;
  const table = (html.match(/<table[\s>]/gi) || []).length;
  const heading = (html.match(/<h[1-6][\s>]/gi) || []).length;
  return { paragraphs: p, boldSpans: bold, italicSpans: italic, listItems: li, tables: table, headings: heading };
}

function FidelityBadge({ label, count, icon }: { label: string; count: number; icon: string }) {
  if (count === 0) return null;
  return (
    <span
      className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded bg-white border border-neutral-200 text-[10px] text-neutral-600"
      title={`${count} ${label} detected in extracted content`}
    >
      <span className="font-bold text-brand-primary">{icon}</span>
      <span className="tabular-nums">{count}</span>
    </span>
  );
}
