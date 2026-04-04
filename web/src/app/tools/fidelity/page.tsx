"use client";

import { useState, useRef } from "react";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface StyleProfile {
  body_font: string;
  body_size: number;
  heading_fonts: Record<string, string>;
  heading_sizes: Record<string, number>;
  heading_colors: Record<string, string>;
  heading_bold: Record<string, boolean>;
  margin_left: number;
  margin_right: number;
  margin_top: number;
  margin_bottom: number;
  line_spacing: number;
  paragraph_spacing: number;
  primary_color: string;
  accent_color: string;
  list_indent_px: number;
}

interface GenerateResult {
  template_name: string;
  source_name: string;
  html: string;
  style_profile: StyleProfile;
  conformance_report: {
    rules_applied: number;
    rules_skipped: number;
    details: { rule: string; description: string }[];
    skipped_details: { rule: string; description: string }[];
    source_stats: Record<string, number>;
    template_stats: Record<string, number>;
  };
}

interface FidelityIssue {
  category: string;
  severity: string;
  page: number;
  location: string;
  description: string;
  original_text: string;
  suggested_fix: string;
  auto_fixable: boolean;
}

interface FidelityReport {
  document_name: string;
  score: number;
  total_issues: number;
  critical: number;
  high: number;
  medium: number;
  low: number;
  issues: FidelityIssue[];
  formatting_summary: {
    total_pages?: number;
    total_paragraphs?: number;
    fonts_used?: Record<string, number>;
    colors_used?: Record<string, number>;
    styles_used?: Record<string, number>;
    font_match?: number;
    template_fonts?: Record<string, number>;
    generated_fonts?: Record<string, number>;
  };
}

const SEVERITY_COLORS: Record<string, string> = {
  critical: "bg-red-50 text-red-700 border-red-200",
  high: "bg-amber-50 text-amber-700 border-amber-200",
  medium: "bg-blue-50 text-blue-700 border-blue-200",
  low: "bg-slate-50 text-slate-600 border-slate-200",
};

const CATEGORY_LABELS: Record<string, string> = {
  runon_word: "Run-on Word",
  spacing: "Spacing",
  alignment: "Alignment",
  font: "Font",
  color: "Color",
  strikethrough: "Strikethrough",
  template_mismatch: "Template Mismatch",
};

function ScoreGauge({ score }: { score: number }) {
  const color = score >= 80 ? "text-green-600" : score >= 60 ? "text-amber-600" : "text-red-600";
  const bg = score >= 80 ? "bg-green-50" : score >= 60 ? "bg-amber-50" : "bg-red-50";
  return (
    <div className={`${bg} rounded-2xl px-8 py-6 text-center`}>
      <div className={`text-5xl font-bold ${color}`}>{score}</div>
      <div className="text-sm text-neutral-500 mt-1">Fidelity Score</div>
      <div className="text-xs text-neutral-400 mt-0.5">out of 100</div>
    </div>
  );
}

export default function FidelityCheckerPage() {
  const [mode, setMode] = useState<"check" | "compare" | "generate" | "formulas">("check");
  const [loading, setLoading] = useState(false);
  const [report, setReport] = useState<FidelityReport | null>(null);
  const [generateResult, setGenerateResult] = useState<GenerateResult | null>(null);
  const [formulaResult, setFormulaResult] = useState<any>(null);
  const [formulaLoading, setFormulaLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [filterSeverity, setFilterSeverity] = useState<string>("all");
  const fileRef = useRef<HTMLInputElement>(null);
  const templateRef = useRef<HTMLInputElement>(null);
  const generatedRef = useRef<HTMLInputElement>(null);
  const genTemplateRef = useRef<HTMLInputElement>(null);
  const genSourceRef = useRef<HTMLInputElement>(null);

  const handleCheck = async () => {
    const file = fileRef.current?.files?.[0];
    if (!file) return;

    setLoading(true);
    setError(null);
    setReport(null);

    try {
      const formData = new FormData();
      formData.append("file", file);
      const res = await fetch(`${API_BASE}/api/fidelity/check`, {
        method: "POST",
        body: formData,
      });
      if (!res.ok) throw new Error("Fidelity check failed");
      setReport(await res.json());
    } catch (e) {
      setError(e instanceof Error ? e.message : "Check failed");
    } finally {
      setLoading(false);
    }
  };

  const handleCompare = async () => {
    const template = templateRef.current?.files?.[0];
    const generated = generatedRef.current?.files?.[0];
    if (!template || !generated) return;

    setLoading(true);
    setError(null);
    setReport(null);

    try {
      const formData = new FormData();
      formData.append("template", template);
      formData.append("generated", generated);
      const res = await fetch(`${API_BASE}/api/fidelity/compare`, {
        method: "POST",
        body: formData,
      });
      if (!res.ok) throw new Error("Comparison failed");
      setReport(await res.json());
    } catch (e) {
      setError(e instanceof Error ? e.message : "Comparison failed");
    } finally {
      setLoading(false);
    }
  };

  const handleGenerate = async () => {
    const template = genTemplateRef.current?.files?.[0];
    const source = genSourceRef.current?.files?.[0];
    if (!template || !source) return;

    setLoading(true);
    setError(null);
    setGenerateResult(null);

    try {
      const formData = new FormData();
      formData.append("template", template);
      formData.append("source", source);
      const res = await fetch(`${API_BASE}/api/fidelity/generate`, {
        method: "POST",
        body: formData,
      });
      if (!res.ok) throw new Error("Document generation failed");
      setGenerateResult(await res.json());
    } catch (e) {
      setError(e instanceof Error ? e.message : "Generation failed");
    } finally {
      setLoading(false);
    }
  };

  const filteredIssues = report?.issues.filter(
    (i) => filterSeverity === "all" || i.severity === filterSeverity
  ) ?? [];

  return (
    <div className="p-6 max-w-6xl mx-auto">
      <div className="mb-6">
        <h1 className="text-xl font-bold text-neutral-800">Document Fidelity Checker</h1>
        <p className="text-sm text-neutral-500 mt-0.5">
          Check PDF formatting fidelity — detect run-on words, spacing issues, font mismatches, and template conformance
        </p>
      </div>

      {/* Mode toggle */}
      <div className="flex gap-2 mb-6">
        <button
          onClick={() => { setMode("check"); setReport(null); setGenerateResult(null); }}
          className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
            mode === "check"
              ? "bg-brand-primary text-white"
              : "bg-neutral-100 text-neutral-600 hover:bg-neutral-200"
          }`}
        >
          Single Document Check
        </button>
        <button
          onClick={() => { setMode("compare"); setReport(null); setGenerateResult(null); }}
          className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
            mode === "compare"
              ? "bg-brand-primary text-white"
              : "bg-neutral-100 text-neutral-600 hover:bg-neutral-200"
          }`}
        >
          Template Comparison
        </button>
        <button
          onClick={() => { setMode("generate"); setReport(null); setGenerateResult(null); }}
          className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
            mode === "generate"
              ? "bg-brand-primary text-white"
              : "bg-neutral-100 text-neutral-600 hover:bg-neutral-200"
          }`}
        >
          Template Generator
        </button>
        <button
          onClick={() => { setMode("formulas"); setReport(null); setGenerateResult(null); }}
          className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
            mode === "formulas"
              ? "bg-brand-primary text-white"
              : "bg-neutral-100 text-neutral-600 hover:bg-neutral-200"
          }`}
        >
          Formula Detection
        </button>
      </div>

      {/* Upload area */}
      <div className="rounded-xl border border-neutral-200 bg-white p-6 mb-6">
        {mode === "check" ? (
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-neutral-700 mb-1.5">Upload PDF to check</label>
              <input ref={fileRef} type="file" accept=".pdf" className="text-sm" />
            </div>
            <div className="flex gap-3">
              <button
                onClick={handleCheck}
                disabled={loading}
                className="px-6 py-2.5 rounded-lg bg-brand-primary text-white text-sm font-medium hover:bg-brand-french disabled:opacity-50 transition-colors"
              >
                {loading ? "Analyzing..." : "Check Fidelity"}
              </button>
              <button
                onClick={() => {
                  const file = fileRef.current?.files?.[0];
                  if (!file) return;
                  const formData = new FormData();
                  formData.append("file", file);
                  fetch(`${API_BASE}/api/fidelity/export-docx`, { method: "POST", body: formData })
                    .then(r => r.blob())
                    .then(blob => {
                      const url = URL.createObjectURL(blob);
                      const a = document.createElement("a");
                      a.href = url;
                      a.download = file.name.replace(".pdf", ".docx");
                      a.click();
                      URL.revokeObjectURL(url);
                    });
                }}
                className="px-6 py-2.5 rounded-lg border border-neutral-300 text-neutral-700 text-sm font-medium hover:bg-neutral-50 transition-colors"
              >
                Export as DOCX
              </button>
            </div>
          </div>
        ) : mode === "compare" ? (
          <div className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-neutral-700 mb-1.5">Blueprint Template (PDF)</label>
                <input ref={templateRef} type="file" accept=".pdf" className="text-sm" />
              </div>
              <div>
                <label className="block text-sm font-medium text-neutral-700 mb-1.5">Generated Document (PDF)</label>
                <input ref={generatedRef} type="file" accept=".pdf" className="text-sm" />
              </div>
            </div>
            <button
              onClick={handleCompare}
              disabled={loading}
              className="px-6 py-2.5 rounded-lg bg-brand-primary text-white text-sm font-medium hover:bg-brand-french disabled:opacity-50 transition-colors"
            >
              {loading ? "Comparing..." : "Compare Documents"}
            </button>
          </div>
        ) : mode === "generate" ? (
          <div className="space-y-4">
            <p className="text-sm text-neutral-500">
              Upload a blueprint template (formatting source) and a source document (content source).
              The generator will produce a new document with the template&apos;s formatting applied to the source&apos;s content.
            </p>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-neutral-700 mb-1.5">Blueprint Template (PDF)</label>
                <div className="border-2 border-dashed border-neutral-300 rounded-lg p-4 hover:border-brand-primary transition-colors">
                  <input ref={genTemplateRef} type="file" accept=".pdf" className="text-sm" />
                  <p className="text-xs text-neutral-400 mt-1">Formatting will be extracted from this document</p>
                </div>
              </div>
              <div>
                <label className="block text-sm font-medium text-neutral-700 mb-1.5">Source Document (PDF)</label>
                <div className="border-2 border-dashed border-neutral-300 rounded-lg p-4 hover:border-brand-primary transition-colors">
                  <input ref={genSourceRef} type="file" accept=".pdf" className="text-sm" />
                  <p className="text-xs text-neutral-400 mt-1">Content will be extracted from this document</p>
                </div>
              </div>
            </div>
            <div className="flex gap-3">
              <button
                onClick={handleGenerate}
                disabled={loading}
                className="px-6 py-2.5 rounded-lg bg-brand-primary text-white text-sm font-medium hover:bg-brand-french disabled:opacity-50 transition-colors"
              >
                {loading ? "Generating..." : "Generate Document"}
              </button>
              <button
                onClick={() => {
                  const template = genTemplateRef.current?.files?.[0];
                  const source = genSourceRef.current?.files?.[0];
                  if (!template || !source) return;
                  const formData = new FormData();
                  formData.append("template", template);
                  formData.append("source", source);
                  fetch(`${API_BASE}/api/fidelity/export-docx-from-template`, { method: "POST", body: formData })
                    .then(r => r.blob())
                    .then(blob => {
                      const url = URL.createObjectURL(blob);
                      const a = document.createElement("a");
                      a.href = url;
                      a.download = (source.name || "document").replace(".pdf", "_formatted.docx");
                      a.click();
                      URL.revokeObjectURL(url);
                    });
                }}
                className="px-6 py-2.5 rounded-lg border border-neutral-300 text-neutral-700 text-sm font-medium hover:bg-neutral-50 transition-colors"
              >
                Export as DOCX
              </button>
            </div>
          </div>
        ) : (
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-neutral-700 mb-1.5">Upload document to scan for formulas</label>
              <input ref={fileRef} type="file" accept=".pdf,.docx,.pptx,.xlsx,.html" className="text-sm" />
            </div>
            <button
              onClick={async () => {
                const f = fileRef.current?.files?.[0];
                if (!f) return;
                setFormulaLoading(true);
                setFormulaResult(null);
                setError(null);
                const fd = new FormData();
                fd.append("file", f);
                try {
                  const res = await fetch(`${API_BASE}/api/fidelity/detect-formulas`, { method: "POST", body: fd });
                  if (!res.ok) throw new Error("Formula detection failed");
                  const data = await res.json();
                  setFormulaResult(data);
                } catch (e) {
                  setError(e instanceof Error ? e.message : "Formula detection failed");
                }
                setFormulaLoading(false);
              }}
              disabled={formulaLoading}
              className="px-4 py-2 bg-brand-primary text-white rounded-lg text-sm font-medium hover:bg-brand-primary/90 disabled:opacity-50"
            >
              {formulaLoading ? "Scanning..." : "Detect Formulas"}
            </button>
          </div>
        )}
      </div>

      {error && (
        <div className="rounded-xl border border-red-200 bg-red-50 px-5 py-3 mb-6 text-sm text-red-700">
          {error}
        </div>
      )}

      {loading && (
        <div className="flex items-center justify-center py-16">
          <div className="w-8 h-8 border-2 border-brand-primary border-t-transparent rounded-full animate-spin" />
        </div>
      )}

      {/* Formula results */}
      {formulaResult && mode === "formulas" && (
        <div className="mt-6 space-y-4">
          {/* Export buttons */}
          <div className="flex gap-2">
            <button
              onClick={() => {
                const blob = new Blob([formulaResult.rendered_html || ""], { type: "text/html" });
                const url = URL.createObjectURL(blob);
                const a = document.createElement("a"); a.href = url; a.download = "formula_output.html"; a.click();
              }}
              className="px-3 py-1.5 bg-neutral-100 text-neutral-700 rounded-lg text-xs font-medium hover:bg-neutral-200"
            >Download HTML</button>
            <button
              onClick={async () => {
                const f = fileRef.current?.files?.[0];
                if (!f) return;
                const fd = new FormData(); fd.append("file", f);
                const res = await fetch(`${API_BASE}/api/fidelity/formula-export?format=docx`, { method: "POST", body: fd });
                const blob = await res.blob();
                const url = URL.createObjectURL(blob);
                const a = document.createElement("a"); a.href = url; a.download = "formula_output.docx"; a.click();
              }}
              className="px-3 py-1.5 bg-neutral-100 text-neutral-700 rounded-lg text-xs font-medium hover:bg-neutral-200"
            >Download DOCX</button>
            <button
              onClick={async () => {
                const f = fileRef.current?.files?.[0];
                if (!f) return;
                const fd = new FormData(); fd.append("file", f);
                const res = await fetch(`${API_BASE}/api/fidelity/formula-export?format=pdf`, { method: "POST", body: fd });
                const blob = await res.blob();
                const url = URL.createObjectURL(blob);
                const a = document.createElement("a"); a.href = url; a.download = "formula_output.pdf"; a.click();
              }}
              className="px-3 py-1.5 bg-neutral-100 text-neutral-700 rounded-lg text-xs font-medium hover:bg-neutral-200"
            >Download PDF</button>
          </div>

          {/* Rendered output preview */}
          {formulaResult.rendered_html && (
            <div className="rounded-xl border border-neutral-200 bg-white p-4">
              <h3 className="text-sm font-medium text-neutral-500 mb-3">Rendered Output (with formula formatting)</h3>
              <div
                className="prose prose-sm max-w-none border border-neutral-100 rounded-lg p-4 bg-neutral-50 overflow-auto max-h-96"
                dangerouslySetInnerHTML={{ __html: formulaResult.rendered_html }}
              />
            </div>
          )}

          {/* Summary */}
          <div className="grid grid-cols-4 gap-3">
            <div className="bg-blue-50 rounded-lg p-3 text-center">
              <div className="text-2xl font-bold text-blue-700">{formulaResult.total_formulas}</div>
              <div className="text-xs text-blue-500">Total Formulas</div>
            </div>
            {Object.entries(formulaResult.by_type || {}).map(([type, count]) => (
              <div key={type} className="bg-neutral-50 rounded-lg p-3 text-center">
                <div className="text-xl font-bold text-neutral-700">{count as number}</div>
                <div className="text-xs text-neutral-500 capitalize">{type}</div>
              </div>
            ))}
          </div>

          {/* Tier breakdown */}
          <div className="flex gap-2">
            {Object.entries(formulaResult.by_tier || {}).map(([tier, count]) => (
              <span key={tier} className="px-3 py-1 bg-neutral-100 rounded-full text-xs font-medium">
                {tier}: {count as number}
              </span>
            ))}
          </div>

          {/* Formula table */}
          <div className="overflow-x-auto">
            <table className="w-full text-sm border-collapse">
              <thead>
                <tr className="border-b border-neutral-200 text-left">
                  <th className="py-2 px-3 font-medium text-neutral-500">Pg</th>
                  <th className="py-2 px-3 font-medium text-neutral-500">Type</th>
                  <th className="py-2 px-3 font-medium text-neutral-500">Original</th>
                  <th className="py-2 px-3 font-medium text-neutral-500">Formatted</th>
                  <th className="py-2 px-3 font-medium text-neutral-500">LaTeX</th>
                  <th className="py-2 px-3 font-medium text-neutral-500">Tier</th>
                </tr>
              </thead>
              <tbody>
                {(formulaResult.formulas || []).map((f: any, i: number) => (
                  <tr key={i} className="border-b border-neutral-100 hover:bg-neutral-50">
                    <td className="py-2 px-3 text-neutral-400">{f.page}</td>
                    <td className="py-2 px-3">
                      <span className={`px-2 py-0.5 rounded text-xs font-medium ${
                        f.type === "chemical" ? "bg-blue-100 text-blue-700" :
                        f.type === "pk" ? "bg-green-100 text-green-700" :
                        f.type === "statistical" ? "bg-purple-100 text-purple-700" :
                        f.type === "mathematical" ? "bg-orange-100 text-orange-700" :
                        f.type === "dosing" ? "bg-red-100 text-red-700" :
                        f.type === "efficacy" ? "bg-teal-100 text-teal-700" :
                        "bg-neutral-100 text-neutral-700"
                      }`}>{f.type}</span>
                    </td>
                    <td className="py-2 px-3 font-mono text-xs">{f.original}</td>
                    <td className="py-2 px-3" dangerouslySetInnerHTML={{ __html: f.html }} />
                    <td className="py-2 px-3 font-mono text-xs text-neutral-500">{f.latex || "\u2014"}</td>
                    <td className="py-2 px-3">
                      <span className={`px-2 py-0.5 rounded text-xs ${
                        f.complexity === "inline" ? "bg-green-50 text-green-600" :
                        f.complexity === "structured" ? "bg-amber-50 text-amber-600" :
                        "bg-red-50 text-red-600"
                      }`}>{f.complexity}</span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Generate result */}
      {generateResult && (
        <div className="space-y-6">
          {/* Conformance summary bar */}
          <div className="rounded-xl border border-neutral-200 bg-white px-5 py-4">
            <div className="flex items-center justify-between">
              <div>
                <h3 className="text-sm font-semibold text-neutral-700">Conformance Report</h3>
                <p className="text-xs text-neutral-400 mt-0.5">
                  Template: {generateResult.template_name} &rarr; Source: {generateResult.source_name}
                </p>
              </div>
              <div className="flex gap-3">
                <div className="text-center px-4 py-2 rounded-lg bg-green-50 border border-green-200">
                  <div className="text-lg font-bold text-green-700">{generateResult.conformance_report.rules_applied}</div>
                  <div className="text-[10px] text-green-600">Rules Applied</div>
                </div>
                <div className="text-center px-4 py-2 rounded-lg bg-neutral-50 border border-neutral-200">
                  <div className="text-lg font-bold text-neutral-500">{generateResult.conformance_report.rules_skipped}</div>
                  <div className="text-[10px] text-neutral-400">Skipped</div>
                </div>
              </div>
            </div>
          </div>

          {/* Two-panel layout: HTML preview + Style Profile */}
          <div className="grid grid-cols-2 gap-4">
            {/* Left: Generated HTML preview */}
            <div className="rounded-xl border border-neutral-200 bg-white overflow-hidden">
              <div className="px-5 py-3 border-b border-neutral-100 bg-neutral-50">
                <h3 className="text-xs font-semibold text-neutral-500 uppercase tracking-wide">Generated Document Preview</h3>
              </div>
              <div
                className="p-5 prose prose-sm max-w-none overflow-auto"
                style={{ maxHeight: "600px" }}
                dangerouslySetInnerHTML={{ __html: generateResult.html }}
              />
            </div>

            {/* Right: Style profile */}
            <div className="rounded-xl border border-neutral-200 bg-white overflow-hidden">
              <div className="px-5 py-3 border-b border-neutral-100 bg-neutral-50">
                <h3 className="text-xs font-semibold text-neutral-500 uppercase tracking-wide">Extracted Style Profile</h3>
              </div>
              <div className="p-5 space-y-4 overflow-auto" style={{ maxHeight: "600px" }}>
                {/* Body typography */}
                <div>
                  <h4 className="text-xs font-semibold text-neutral-500 uppercase tracking-wide mb-2">Body Typography</h4>
                  <div className="grid grid-cols-2 gap-2">
                    <div className="px-3 py-2 rounded-lg bg-neutral-50">
                      <div className="text-[10px] text-neutral-400">Font</div>
                      <div className="text-sm font-medium text-neutral-800">{generateResult.style_profile.body_font}</div>
                    </div>
                    <div className="px-3 py-2 rounded-lg bg-neutral-50">
                      <div className="text-[10px] text-neutral-400">Size</div>
                      <div className="text-sm font-medium text-neutral-800">{generateResult.style_profile.body_size}pt</div>
                    </div>
                  </div>
                </div>

                {/* Heading styles */}
                {Object.keys(generateResult.style_profile.heading_fonts).length > 0 && (
                  <div>
                    <h4 className="text-xs font-semibold text-neutral-500 uppercase tracking-wide mb-2">Heading Styles</h4>
                    <div className="space-y-1.5">
                      {Object.entries(generateResult.style_profile.heading_fonts).map(([level, font]) => (
                        <div key={level} className="flex items-center gap-2 px-3 py-2 rounded-lg bg-neutral-50">
                          <span className="text-xs font-mono text-brand-primary w-20">{level}</span>
                          <span className="text-xs text-neutral-700">{font}</span>
                          <span className="text-xs text-neutral-400">
                            {generateResult.style_profile.heading_sizes[level]}pt
                          </span>
                          {generateResult.style_profile.heading_colors[level] && (
                            <span
                              className="w-3 h-3 rounded-full border border-neutral-300"
                              style={{ backgroundColor: generateResult.style_profile.heading_colors[level] }}
                            />
                          )}
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Margins */}
                <div>
                  <h4 className="text-xs font-semibold text-neutral-500 uppercase tracking-wide mb-2">Margins (px)</h4>
                  <div className="grid grid-cols-4 gap-2">
                    {([
                      ["Top", generateResult.style_profile.margin_top],
                      ["Right", generateResult.style_profile.margin_right],
                      ["Bottom", generateResult.style_profile.margin_bottom],
                      ["Left", generateResult.style_profile.margin_left],
                    ] as const).map(([label, value]) => (
                      <div key={label} className="px-3 py-2 rounded-lg bg-neutral-50 text-center">
                        <div className="text-[10px] text-neutral-400">{label}</div>
                        <div className="text-sm font-medium text-neutral-800">{value}</div>
                      </div>
                    ))}
                  </div>
                </div>

                {/* Spacing */}
                <div>
                  <h4 className="text-xs font-semibold text-neutral-500 uppercase tracking-wide mb-2">Spacing</h4>
                  <div className="grid grid-cols-2 gap-2">
                    <div className="px-3 py-2 rounded-lg bg-neutral-50">
                      <div className="text-[10px] text-neutral-400">Line Spacing</div>
                      <div className="text-sm font-medium text-neutral-800">{generateResult.style_profile.line_spacing}</div>
                    </div>
                    <div className="px-3 py-2 rounded-lg bg-neutral-50">
                      <div className="text-[10px] text-neutral-400">Paragraph Spacing</div>
                      <div className="text-sm font-medium text-neutral-800">{generateResult.style_profile.paragraph_spacing}px</div>
                    </div>
                  </div>
                </div>

                {/* Colors */}
                <div>
                  <h4 className="text-xs font-semibold text-neutral-500 uppercase tracking-wide mb-2">Colors</h4>
                  <div className="flex gap-3">
                    <div className="flex items-center gap-2 px-3 py-2 rounded-lg bg-neutral-50">
                      <span
                        className="w-4 h-4 rounded border border-neutral-300"
                        style={{ backgroundColor: generateResult.style_profile.primary_color }}
                      />
                      <div>
                        <div className="text-[10px] text-neutral-400">Primary</div>
                        <div className="text-xs font-mono text-neutral-700">{generateResult.style_profile.primary_color}</div>
                      </div>
                    </div>
                    <div className="flex items-center gap-2 px-3 py-2 rounded-lg bg-neutral-50">
                      <span
                        className="w-4 h-4 rounded border border-neutral-300"
                        style={{ backgroundColor: generateResult.style_profile.accent_color }}
                      />
                      <div>
                        <div className="text-[10px] text-neutral-400">Accent</div>
                        <div className="text-xs font-mono text-neutral-700">{generateResult.style_profile.accent_color}</div>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>

          {/* Applied rules detail */}
          <div className="rounded-xl border border-neutral-200 bg-white overflow-hidden">
            <div className="px-5 py-3 border-b border-neutral-100">
              <h3 className="text-sm font-semibold text-neutral-700">
                Applied Style Rules ({generateResult.conformance_report.rules_applied})
              </h3>
            </div>
            <div className="divide-y divide-neutral-100">
              {generateResult.conformance_report.details.map((detail, idx) => (
                <div key={idx} className="px-5 py-2.5 flex items-center gap-3 hover:bg-neutral-50 transition-colors">
                  <span className="text-[10px] px-2 py-0.5 rounded-full font-medium bg-green-50 text-green-700 border border-green-200 shrink-0">
                    applied
                  </span>
                  <span className="text-xs font-mono text-brand-primary w-36 shrink-0">{detail.rule}</span>
                  <span className="text-xs text-neutral-600">{detail.description}</span>
                </div>
              ))}
            </div>
          </div>

          {/* Document stats */}
          <div className="grid grid-cols-2 gap-4">
            <div className="rounded-xl border border-neutral-200 bg-white px-5 py-4">
              <h3 className="text-xs font-semibold text-neutral-500 uppercase tracking-wide mb-3">Template Stats</h3>
              <div className="grid grid-cols-2 gap-2">
                {Object.entries(generateResult.conformance_report.template_stats).map(([key, val]) => (
                  <div key={key} className="px-3 py-2 rounded-lg bg-neutral-50">
                    <div className="text-[10px] text-neutral-400">{key.replace(/_/g, " ")}</div>
                    <div className="text-sm font-medium text-neutral-800">{val}</div>
                  </div>
                ))}
              </div>
            </div>
            <div className="rounded-xl border border-neutral-200 bg-white px-5 py-4">
              <h3 className="text-xs font-semibold text-neutral-500 uppercase tracking-wide mb-3">Source Stats</h3>
              <div className="grid grid-cols-2 gap-2">
                {Object.entries(generateResult.conformance_report.source_stats).map(([key, val]) => (
                  <div key={key} className="px-3 py-2 rounded-lg bg-neutral-50">
                    <div className="text-[10px] text-neutral-400">{key.replace(/_/g, " ")}</div>
                    <div className="text-sm font-medium text-neutral-800">{val}</div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Report */}
      {report && (
        <div className="space-y-6">
          {/* Score + summary row */}
          <div className="grid grid-cols-4 gap-4">
            <ScoreGauge score={report.score} />

            <div className="rounded-xl border border-neutral-200 bg-white px-5 py-4 col-span-3">
              <h3 className="text-xs font-semibold text-neutral-500 uppercase tracking-wide mb-3">Issue Summary</h3>
              <div className="grid grid-cols-4 gap-3">
                {(["critical", "high", "medium", "low"] as const).map((sev) => (
                  <div key={sev} className={`rounded-lg px-4 py-3 text-center border ${SEVERITY_COLORS[sev]}`}>
                    <div className="text-2xl font-bold">{report[sev]}</div>
                    <div className="text-xs capitalize mt-0.5">{sev}</div>
                  </div>
                ))}
              </div>

              {/* Formatting summary */}
              <div className="mt-4 flex flex-wrap gap-4 text-xs text-neutral-500">
                {report.formatting_summary.total_pages && (
                  <span>{report.formatting_summary.total_pages} pages</span>
                )}
                {report.formatting_summary.total_paragraphs && (
                  <span>{report.formatting_summary.total_paragraphs} paragraphs</span>
                )}
                {report.formatting_summary.fonts_used && (
                  <span>{Object.keys(report.formatting_summary.fonts_used).length} fonts</span>
                )}
                {report.formatting_summary.font_match !== undefined && (
                  <span>Font match: {(report.formatting_summary.font_match * 100).toFixed(0)}%</span>
                )}
              </div>
            </div>
          </div>

          {/* Font inventory */}
          {report.formatting_summary.fonts_used && (
            <div className="rounded-xl border border-neutral-200 bg-white px-5 py-4">
              <h3 className="text-xs font-semibold text-neutral-500 uppercase tracking-wide mb-3">Font Usage</h3>
              <div className="flex flex-wrap gap-2">
                {Object.entries(report.formatting_summary.fonts_used).map(([font, count]) => (
                  <span key={font} className="text-xs px-3 py-1 rounded-full bg-neutral-100 text-neutral-700">
                    {font} <span className="text-neutral-400">({count})</span>
                  </span>
                ))}
              </div>
            </div>
          )}

          {/* Issues list */}
          <div className="rounded-xl border border-neutral-200 bg-white overflow-hidden">
            <div className="px-5 py-3 border-b border-neutral-100 flex items-center justify-between">
              <h3 className="text-sm font-semibold text-neutral-700">
                Issues ({filteredIssues.length})
              </h3>
              <select
                value={filterSeverity}
                onChange={(e) => setFilterSeverity(e.target.value)}
                className="text-xs border border-neutral-300 rounded-lg px-2 py-1"
              >
                <option value="all">All Severity</option>
                <option value="critical">Critical</option>
                <option value="high">High</option>
                <option value="medium">Medium</option>
                <option value="low">Low</option>
              </select>
            </div>

            {filteredIssues.length === 0 ? (
              <div className="px-5 py-8 text-center text-sm text-neutral-400">
                {report.total_issues === 0 ? "No issues found — document looks clean!" : "No issues match this filter"}
              </div>
            ) : (
              <div className="divide-y divide-neutral-100">
                {filteredIssues.map((issue, idx) => (
                  <div key={idx} className="px-5 py-3 hover:bg-neutral-50 transition-colors">
                    <div className="flex items-start gap-3">
                      <span className={`text-[10px] px-2 py-0.5 rounded-full font-medium border shrink-0 mt-0.5 ${SEVERITY_COLORS[issue.severity]}`}>
                        {issue.severity}
                      </span>
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 mb-0.5">
                          <span className="text-xs font-medium text-neutral-800">
                            {CATEGORY_LABELS[issue.category] || issue.category}
                          </span>
                          <span className="text-[10px] text-neutral-400">
                            Page {issue.page} &middot; {issue.location}
                          </span>
                          {issue.auto_fixable && (
                            <span className="text-[10px] px-1.5 py-0.5 rounded bg-green-50 text-green-600 border border-green-200">
                              Auto-fixable
                            </span>
                          )}
                        </div>
                        <p className="text-xs text-neutral-600">{issue.description}</p>
                        {issue.suggested_fix && (
                          <p className="text-xs text-green-700 mt-1">
                            Fix: <code className="bg-green-50 px-1 rounded">{issue.suggested_fix}</code>
                          </p>
                        )}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
