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

        {/* Library mode: show section content */}
        {sourceMode === "library" && selectedSection && (
          <Card>
            <CardHeader>
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <span className="font-mono text-xs text-neutral-400 bg-neutral-100 px-2 py-0.5 rounded">
                    {selectedSection.number}
                  </span>
                  <h3 className="text-sm font-semibold text-neutral-800">
                    {selectedSection.title}
                  </h3>
                </div>
                <div className="flex items-center gap-2">
                  <Badge variant="success">Verbatim</Badge>
                  <Badge variant="neutral">
                    Page {selectedSection.page}
                    {selectedSection.end_page && selectedSection.end_page !== selectedSection.page
                      ? `–${selectedSection.end_page}`
                      : ""}
                  </Badge>
                </div>
              </div>
            </CardHeader>
            <CardBody>
              {libVerbatimLoading ? (
                <div className="flex items-center justify-center py-8">
                  <div className="text-center">
                    <div className="w-6 h-6 border-2 border-brand-primary border-t-transparent rounded-full animate-spin mx-auto mb-2" />
                    <p className="text-xs text-neutral-500">Extracting content from PDF...</p>
                  </div>
                </div>
              ) : libVerbatimResult?.text ? (
                <div
                  className="section-content max-w-none"
                  dangerouslySetInnerHTML={{ __html: sanitizeHtml(libVerbatimResult.text) }}
                />
              ) : selectedSection.content_html ? (
                <div
                  className="section-content max-w-none"
                  dangerouslySetInnerHTML={{ __html: sanitizeHtml(selectedSection.content_html) }}
                />
              ) : (
                <p className="text-sm text-neutral-400 italic">
                  Content extraction requires the source PDF. The PDF for this protocol may not be available on the server.
                </p>
              )}
            </CardBody>
          </Card>
        )}

        {/* Upload mode: show extraction result */}
        {sourceMode === "upload" && result && (
          <Card>
            <CardHeader>
              <div className="flex items-center justify-between">
                <div>
                  <h3 className="text-sm font-semibold text-neutral-800">Extraction Result</h3>
                  <p className="text-xs text-neutral-400 mt-0.5">{result.explanation}</p>
                </div>
                <div className="flex items-center gap-2">
                  {result.is_verbatim && <Badge variant="success">Verbatim</Badge>}
                  <Badge variant="brand">{result.content_type}</Badge>
                </div>
              </div>
              <div className="flex items-center gap-4 mt-2 text-xs text-neutral-400">
                {result.sections_found.length > 0 && (
                  <span>Sections: {result.sections_found.join(", ")}</span>
                )}
                {result.source_pages.length > 0 && (
                  <span>Pages: {result.source_pages.join(", ")}</span>
                )}
              </div>
            </CardHeader>
            <CardBody>
              {outputFormat === "html" && result.text ? (
                <div
                  className="section-content max-w-none"
                  dangerouslySetInnerHTML={{ __html: sanitizeHtml(result.text) }}
                />
              ) : result.text ? (
                <pre className="text-xs text-neutral-700 bg-neutral-50 rounded-lg p-4 overflow-x-auto whitespace-pre-wrap font-mono border border-neutral-200">
                  {result.text}
                </pre>
              ) : (
                <p className="text-sm text-neutral-400 italic">No text content extracted.</p>
              )}
            </CardBody>
          </Card>
        )}
      </div>
    </div>
  );
}
