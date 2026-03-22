"use client";

import { useState, useCallback } from "react";
import { extractVerbatim, type VerbatimResult } from "@/lib/api";
import { sanitizeHtml } from "@/lib/sanitize";
import { TopBar } from "@/components/layout/TopBar";
import { Card, CardHeader, CardBody } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { cn } from "@/lib/utils";

const EXAMPLE_INSTRUCTIONS = [
  "Copy Section 5.1",
  "Extract the inclusion criteria",
  "Get the Schedule of Activities table",
  "Copy the primary endpoint definition from Section 3",
  "Extract the statistical analysis plan",
  "Copy the dosing regimen from Section 6",
];

export default function VerbatimExtractPage() {
  const [file, setFile] = useState<File | null>(null);
  const [instruction, setInstruction] = useState("");
  const [outputFormat, setOutputFormat] = useState<"html" | "text">("html");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<VerbatimResult | null>(null);

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

  const handleExampleClick = (example: string) => {
    setInstruction(example);
  };

  return (
    <div>
      <TopBar title="Verbatim Extract" subtitle="Extract exact content from protocol documents — zero hallucination" />

      <div className="p-6 space-y-4">
        {/* Input section */}
        <Card>
          <CardHeader>
            <h3 className="text-sm font-semibold text-neutral-800">Extract Content</h3>
            <p className="text-xs text-neutral-400 mt-0.5">
              Upload a PDF and describe what to extract. The LLM locates the content; PyMuPDF extracts the exact text.
            </p>
          </CardHeader>
          <CardBody className="space-y-4">
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
              {/* Example chips */}
              <div className="flex flex-wrap gap-1.5 mt-2">
                {EXAMPLE_INSTRUCTIONS.map((ex) => (
                  <button
                    key={ex}
                    onClick={() => handleExampleClick(ex)}
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
                <label className="text-xs font-medium text-neutral-600 block mb-1">Output Format</label>
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
          </CardBody>
        </Card>

        {/* Error */}
        {error && (
          <div className="bg-red-50 rounded-lg px-4 py-3 text-sm text-red-700 border border-red-200">
            {error}
          </div>
        )}

        {/* Result */}
        {result && (
          <Card>
            <CardHeader>
              <div className="flex items-center justify-between">
                <div>
                  <h3 className="text-sm font-semibold text-neutral-800">
                    Extraction Result
                  </h3>
                  <p className="text-xs text-neutral-400 mt-0.5">
                    {result.explanation}
                  </p>
                </div>
                <div className="flex items-center gap-2">
                  {result.is_verbatim && (
                    <Badge variant="success">Verbatim</Badge>
                  )}
                  <Badge variant="brand">
                    {result.content_type}
                  </Badge>
                </div>
              </div>
              {/* Metadata */}
              <div className="flex items-center gap-4 mt-2 text-xs text-neutral-400">
                {result.sections_found.length > 0 && (
                  <span>
                    Sections: {result.sections_found.join(", ")}
                  </span>
                )}
                {result.source_pages.length > 0 && (
                  <span>
                    Pages: {result.source_pages.join(", ")}
                  </span>
                )}
              </div>
            </CardHeader>

            <CardBody>
              {/* Content */}
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

              {/* Tables */}
              {result.tables && result.tables.length > 0 && (
                <div className="mt-4 pt-4 border-t border-neutral-100">
                  <h4 className="text-xs font-semibold text-neutral-600 mb-2">
                    Extracted Tables ({result.tables.length})
                  </h4>
                  <pre className="text-xs text-neutral-600 bg-neutral-50 rounded-lg p-4 overflow-x-auto font-mono border border-neutral-200">
                    {JSON.stringify(result.tables, null, 2)}
                  </pre>
                </div>
              )}
            </CardBody>
          </Card>
        )}
      </div>
    </div>
  );
}
