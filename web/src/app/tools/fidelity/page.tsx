"use client";

import { useState, useRef } from "react";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

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
  const [mode, setMode] = useState<"check" | "compare">("check");
  const [loading, setLoading] = useState(false);
  const [report, setReport] = useState<FidelityReport | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [filterSeverity, setFilterSeverity] = useState<string>("all");
  const fileRef = useRef<HTMLInputElement>(null);
  const templateRef = useRef<HTMLInputElement>(null);
  const generatedRef = useRef<HTMLInputElement>(null);

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
          onClick={() => { setMode("check"); setReport(null); }}
          className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
            mode === "check"
              ? "bg-brand-primary text-white"
              : "bg-neutral-100 text-neutral-600 hover:bg-neutral-200"
          }`}
        >
          Single Document Check
        </button>
        <button
          onClick={() => { setMode("compare"); setReport(null); }}
          className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
            mode === "compare"
              ? "bg-brand-primary text-white"
              : "bg-neutral-100 text-neutral-600 hover:bg-neutral-200"
          }`}
        >
          Template Comparison
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
            <button
              onClick={handleCheck}
              disabled={loading}
              className="px-6 py-2.5 rounded-lg bg-brand-primary text-white text-sm font-medium hover:bg-brand-french disabled:opacity-50 transition-colors"
            >
              {loading ? "Analyzing..." : "Check Fidelity"}
            </button>
          </div>
        ) : (
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
