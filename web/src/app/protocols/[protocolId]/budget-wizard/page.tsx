"use client";

import { useEffect, useState, useMemo, useCallback } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import {
  getProtocol,
  getPageImageUrl,
  type ProtocolFull,
  type ExtractedTable,
  type BudgetLine,
} from "@/lib/api";
import { Card, CardHeader, CardBody } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { cn } from "@/lib/utils";

// ─── Types ────────────────────────────────────────────────────────────────

type WizardStep = 1 | 2 | 3 | 4;

type EditableBudgetLine = BudgetLine & {
  _edited: boolean;
};

interface ValidationIssue {
  severity: "error" | "warning" | "info";
  field: string;
  procedure: string;
  message: string;
  page?: number;
}

const STEPS = [
  { num: 1, label: "SoA Review", desc: "Validate extracted tables" },
  { num: 2, label: "Costs & CPT", desc: "Configure pricing" },
  { num: 3, label: "Budget Preview", desc: "Review calculations" },
  { num: 4, label: "Validate & Export", desc: "Final checks" },
];

function formatCurrency(n: number) {
  return new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" }).format(n);
}

function confidenceColor(c: number) {
  if (c >= 0.95) return "text-emerald-700 bg-emerald-100";
  if (c >= 0.85) return "text-sky-700 bg-sky-100";
  if (c >= 0.70) return "text-amber-700 bg-amber-100";
  return "text-red-700 bg-red-100";
}

// ─── Main Component ──────────────────────────────────────────────────────

export default function BudgetWizardPage() {
  const params = useParams();
  const protocolId = params.protocolId as string;

  const [protocol, setProtocol] = useState<ProtocolFull | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [step, setStep] = useState<WizardStep>(1);
  const [budgetLines, setBudgetLines] = useState<EditableBudgetLine[]>([]);
  const [validationIssues, setValidationIssues] = useState<ValidationIssue[]>([]);

  useEffect(() => {
    getProtocol(protocolId)
      .then((p) => {
        setProtocol(p);

        // Use existing budget lines if available, otherwise generate from tables
        let lines = (p.budget_lines || []).map((bl: BudgetLine) => ({ ...bl, _edited: false }));

        if (lines.length === 0 && p.tables.length > 0) {
          // Generate budget lines from procedures in tables
          const seen = new Set<string>();
          const generated: EditableBudgetLine[] = [];
          const COST_MAP: Record<string, number> = { LOW: 75, MEDIUM: 350, HIGH: 1200, VERY_HIGH: 3500 };

          for (const table of p.tables) {
            for (const proc of (table.procedures || [])) {
              const key = proc.canonical_name.toLowerCase();
              if (seen.has(key)) continue;
              seen.add(key);

              // Count visits (cells with MARKER type)
              const markerCells = (table.cells || []).filter(
                (c: { row_header: string; data_type: string }) =>
                  c.row_header?.toLowerCase().includes(proc.raw_name.toLowerCase().slice(0, 20)) &&
                  c.data_type === "MARKER"
              );

              generated.push({
                procedure: proc.raw_name,
                canonical_name: proc.canonical_name,
                cpt_code: proc.code || "",
                category: proc.category,
                cost_tier: proc.estimated_cost_tier,
                visits_required: markerCells.map((_: unknown, i: number) => `Visit ${i + 1}`),
                total_occurrences: Math.max(markerCells.length, 1),
                estimated_unit_cost: COST_MAP[proc.estimated_cost_tier] || 75,
                avg_confidence: 0.85,
                notes: "",
                _edited: false,
              });
            }
          }
          lines = generated;
        }

        setBudgetLines(lines);
      })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [protocolId]);

  // Derived data
  const soaTables = useMemo(() => {
    if (!protocol) return [];
    return protocol.tables.filter(
      (t) => (t.table_type === "SOA" || t.cells?.length > 0) && t.cells?.length > 0
    );
  }, [protocol]);

  const allProcedures = useMemo(() => {
    if (!protocol) return [];
    const procs: Record<string, { raw: string; canonical: string; code: string | null; category: string; cost: string; count: number }> = {};
    for (const t of protocol.tables) {
      for (const p of (t.procedures || [])) {
        const key = p.canonical_name || p.raw_name;
        if (!procs[key]) {
          procs[key] = { raw: p.raw_name, canonical: p.canonical_name, code: p.code, category: p.category, cost: p.estimated_cost_tier, count: 0 };
        }
        procs[key].count++;
      }
    }
    return Object.values(procs);
  }, [protocol]);

  const grandTotal = useMemo(() => {
    return budgetLines.reduce((sum, bl) => sum + bl.estimated_unit_cost * bl.total_occurrences, 0);
  }, [budgetLines]);

  // Budget line editing
  const updateBudgetLine = useCallback((index: number, field: string, value: string | number) => {
    setBudgetLines((prev) => {
      const updated = [...prev];
      const line = { ...updated[index], _edited: true };
      if (field === "estimated_unit_cost") line.estimated_unit_cost = Number(value);
      else if (field === "cpt_code") line.cpt_code = String(value);
      else if (field === "total_occurrences") line.total_occurrences = Number(value);
      updated[index] = line;
      return updated;
    });
  }, []);

  // Validation
  const runValidation = useCallback(() => {
    const issues: ValidationIssue[] = [];
    for (const bl of budgetLines) {
      if (!bl.cpt_code || bl.cpt_code === "null") {
        issues.push({ severity: "warning", field: "cpt_code", procedure: bl.procedure, message: `Missing CPT code for "${bl.procedure}"` });
      }
      if (bl.avg_confidence < 0.85) {
        issues.push({ severity: "warning", field: "confidence", procedure: bl.procedure, message: `Low confidence (${(bl.avg_confidence * 100).toFixed(0)}%) — verify in source document` });
      }
      if (bl.estimated_unit_cost <= 0) {
        issues.push({ severity: "error", field: "cost", procedure: bl.procedure, message: `No unit cost set for "${bl.procedure}"` });
      }
      if (bl.total_occurrences <= 0) {
        issues.push({ severity: "error", field: "occurrences", procedure: bl.procedure, message: `Zero occurrences for "${bl.procedure}"` });
      }
    }
    // Check for procedures in SoA but not in budget
    for (const proc of allProcedures) {
      const inBudget = budgetLines.some((bl) => bl.canonical_name === proc.canonical || bl.procedure === proc.raw);
      if (!inBudget) {
        issues.push({ severity: "info", field: "missing", procedure: proc.canonical, message: `"${proc.canonical}" found in SoA but not in budget` });
      }
    }
    setValidationIssues(issues);
  }, [budgetLines, allProcedures]);

  // Export
  const exportToCSV = useCallback(() => {
    const headers = ["Procedure", "Canonical Name", "CPT Code", "Category", "Cost Tier", "Visits", "Occurrences", "Unit Cost", "Total Cost", "Confidence"];
    const rows = budgetLines.map((bl) => [
      bl.procedure, bl.canonical_name, bl.cpt_code, bl.category, bl.cost_tier,
      (bl.visits_required || []).join("; "), bl.total_occurrences, bl.estimated_unit_cost,
      bl.estimated_unit_cost * bl.total_occurrences, (bl.avg_confidence * 100).toFixed(1) + "%",
    ]);
    const csv = [headers, ...rows].map((r) => r.map((c) => `"${c}"`).join(",")).join("\n");
    const blob = new Blob([csv], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `${protocolId}_site_budget.csv`;
    a.click();
    URL.revokeObjectURL(url);
  }, [budgetLines, protocolId]);

  const exportToXLSX = useCallback(() => {
    const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
    window.open(`${API_BASE}/api/protocols/${protocolId}/budget/export`, "_blank");
  }, [protocolId]);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-screen">
        <div className="w-8 h-8 border-2 border-brand-primary border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  if (error || !protocol) {
    return (
      <div className="p-8 text-center">
        <p className="text-sm text-red-600">{error || "Protocol not found"}</p>
        <Link href="/protocols" className="text-sm text-brand-primary hover:underline mt-2 inline-block">&larr; Back</Link>
      </div>
    );
  }

  return (
    <div className="h-screen flex flex-col bg-neutral-50 overflow-hidden">
      {/* Header */}
      <div className="bg-white border-b border-neutral-200 px-6 py-3 shrink-0">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Link href={`/protocols/${protocolId}`} className="text-neutral-400 hover:text-neutral-600">
              <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M10.5 19.5L3 12m0 0l7.5-7.5M3 12h18" />
              </svg>
            </Link>
            <div>
              <h1 className="text-sm font-semibold text-neutral-800">Site Budget Wizard</h1>
              <p className="text-[11px] text-neutral-400">
                {protocol.metadata.short_title || protocol.document_name}
              </p>
            </div>
          </div>
          <div className="text-sm font-semibold text-neutral-800 font-mono">
            {formatCurrency(grandTotal)}
            <span className="text-[11px] text-neutral-400 font-normal ml-1">per patient</span>
          </div>
        </div>

        {/* Step indicator */}
        <div className="flex items-center gap-1 mt-3">
          {STEPS.map((s, i) => (
            <button
              key={s.num}
              onClick={() => setStep(s.num as WizardStep)}
              className={cn(
                "flex-1 py-2 px-3 rounded-lg text-xs font-medium transition-colors text-left",
                step === s.num
                  ? "bg-brand-primary text-white"
                  : step > s.num
                    ? "bg-emerald-50 text-emerald-700"
                    : "bg-neutral-100 text-neutral-500 hover:bg-neutral-200"
              )}
            >
              <span className="font-semibold">Step {s.num}.</span> {s.label}
              <span className="block text-[10px] opacity-70 mt-0.5">{s.desc}</span>
            </button>
          ))}
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-6">
        {step === 1 && (
          <Step1SoAReview
            tables={soaTables}
            procedures={allProcedures}
            protocolId={protocolId}
            totalPages={protocol.total_pages}
          />
        )}

        {step === 2 && (
          <Step2CostConfig
            budgetLines={budgetLines}
            onUpdate={updateBudgetLine}
          />
        )}

        {step === 3 && (
          <Step3BudgetPreview
            budgetLines={budgetLines}
            grandTotal={grandTotal}
          />
        )}

        {step === 4 && (
          <Step4Validate
            budgetLines={budgetLines}
            issues={validationIssues}
            onRunValidation={runValidation}
            onExport={exportToCSV}
            onExportXLSX={exportToXLSX}
            grandTotal={grandTotal}
          />
        )}
      </div>

      {/* Footer nav */}
      <div className="bg-white border-t border-neutral-200 px-6 py-3 flex items-center justify-between shrink-0">
        <button
          onClick={() => setStep(Math.max(1, step - 1) as WizardStep)}
          disabled={step === 1}
          className="px-4 py-2 text-sm font-medium text-neutral-600 hover:text-neutral-800 disabled:opacity-30"
        >
          &larr; Previous
        </button>
        <span className="text-xs text-neutral-400">Step {step} of 4</span>
        {step < 4 ? (
          <button
            onClick={() => setStep(Math.min(4, step + 1) as WizardStep)}
            className="px-5 py-2 text-sm font-medium bg-brand-primary text-white rounded-lg hover:bg-brand-french"
          >
            Next &rarr;
          </button>
        ) : (
          <button
            onClick={exportToCSV}
            className="px-5 py-2 text-sm font-medium bg-emerald-600 text-white rounded-lg hover:bg-emerald-700"
          >
            Export to CSV
          </button>
        )}
      </div>
    </div>
  );
}

// ─── Step 1: SoA Review ──────────────────────────────────────────────────

function Step1SoAReview({
  tables,
  procedures,
  protocolId,
  totalPages,
}: {
  tables: ExtractedTable[];
  procedures: { raw: string; canonical: string; code: string | null; category: string; cost: string; count: number }[];
  protocolId: string;
  totalPages: number;
}) {
  const [expandedTable, setExpandedTable] = useState<string | null>(null);

  return (
    <div className="space-y-6 max-w-5xl mx-auto">
      <div>
        <h2 className="text-lg font-bold text-neutral-800">Step 1: Review SoA Tables</h2>
        <p className="text-sm text-neutral-500 mt-1">
          Verify the extracted Schedule of Activities data. Tables with low confidence are highlighted.
        </p>
      </div>

      {/* Summary cards */}
      <div className="grid grid-cols-4 gap-3">
        <SummaryCard label="SoA Tables" value={String(tables.length)} color="text-brand-primary" />
        <SummaryCard label="Procedures" value={String(procedures.length)} color="text-emerald-600" />
        <SummaryCard label="Total Cells" value={String(tables.reduce((s, t) => s + (t.cells?.length || 0), 0))} color="text-sky-600" />
        <SummaryCard
          label="Avg Confidence"
          value={tables.length > 0 ? `${(tables.reduce((s, t) => s + (t.overall_confidence || 0), 0) / tables.length * 100).toFixed(0)}%` : "—"}
          color="text-amber-600"
        />
      </div>

      {/* Tables list */}
      <div className="space-y-3">
        {tables.map((table) => {
          const isExpanded = expandedTable === table.table_id;
          const cells = table.cells || [];
          const procs = table.procedures || [];
          const conf = table.overall_confidence || 0;
          const flagged = table.flagged_cells?.length || 0;

          return (
            <Card key={table.table_id} className={cn(flagged > 0 && "border-amber-200")}>
              <button
                onClick={() => setExpandedTable(isExpanded ? null : table.table_id)}
                className="w-full text-left"
              >
                <CardBody className="p-4">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-3">
                      <Badge variant="brand">{table.table_type}</Badge>
                      <div>
                        <h3 className="text-sm font-semibold text-neutral-800">
                          {table.title || `Table ${table.table_id}`}
                        </h3>
                        <p className="text-[11px] text-neutral-400">
                          {cells.length} cells · {procs.length} procedures · Pages {(table.source_pages || []).join(", ")}
                        </p>
                      </div>
                    </div>
                    <div className="flex items-center gap-2">
                      {flagged > 0 && <Badge variant="warning">{flagged} flagged</Badge>}
                      <span className={cn("text-xs font-medium px-2 py-0.5 rounded", confidenceColor(conf))}>
                        {(conf * 100).toFixed(0)}%
                      </span>
                      <svg className={cn("w-4 h-4 text-neutral-400 transition-transform", isExpanded && "rotate-180")} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                        <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 8.25l-7.5 7.5-7.5-7.5" />
                      </svg>
                    </div>
                  </div>
                </CardBody>
              </button>

              {isExpanded && (
                <div className="border-t border-neutral-100 px-4 pb-4">
                  {/* Procedures from this table */}
                  <h4 className="text-xs font-semibold text-neutral-600 uppercase tracking-wide mt-3 mb-2">
                    Procedures ({procs.length})
                  </h4>
                  <div className="overflow-auto max-h-[300px]">
                    <table className="w-full text-xs">
                      <thead>
                        <tr className="bg-neutral-50">
                          <th className="px-2 py-1.5 text-left font-medium text-neutral-500">Raw Name</th>
                          <th className="px-2 py-1.5 text-left font-medium text-neutral-500">Canonical</th>
                          <th className="px-2 py-1.5 text-left font-medium text-neutral-500">CPT</th>
                          <th className="px-2 py-1.5 text-left font-medium text-neutral-500">Category</th>
                          <th className="px-2 py-1.5 text-center font-medium text-neutral-500">Cost Tier</th>
                        </tr>
                      </thead>
                      <tbody>
                        {procs.map((p, i) => (
                          <tr key={i} className="border-b border-neutral-50 hover:bg-neutral-50/50">
                            <td className="px-2 py-1.5 text-neutral-600 max-w-[200px] truncate">{p.raw_name}</td>
                            <td className="px-2 py-1.5 text-neutral-800 font-medium">{p.canonical_name}</td>
                            <td className="px-2 py-1.5 text-neutral-500 font-mono">{p.code || "—"}</td>
                            <td className="px-2 py-1.5"><Badge variant="neutral">{p.category}</Badge></td>
                            <td className="px-2 py-1.5 text-center">{p.estimated_cost_tier}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}
            </Card>
          );
        })}
      </div>
    </div>
  );
}

// ─── Step 2: Cost Configuration ──────────────────────────────────────────

function Step2CostConfig({
  budgetLines,
  onUpdate,
}: {
  budgetLines: EditableBudgetLine[];
  onUpdate: (index: number, field: string, value: string | number) => void;
}) {
  return (
    <div className="space-y-6 max-w-5xl mx-auto">
      <div>
        <h2 className="text-lg font-bold text-neutral-800">Step 2: Configure Costs & CPT Codes</h2>
        <p className="text-sm text-neutral-500 mt-1">
          Review and update unit costs, CPT codes, and visit frequencies. Changes are highlighted in blue.
        </p>
      </div>

      <Card>
        <div className="overflow-auto">
          <table className="w-full text-xs">
            <thead>
              <tr className="bg-neutral-50">
                <th className="px-3 py-2.5 text-left font-semibold text-neutral-600">Procedure</th>
                <th className="px-3 py-2.5 text-left font-semibold text-neutral-600 w-[100px]">CPT Code</th>
                <th className="px-3 py-2.5 text-left font-semibold text-neutral-600">Category</th>
                <th className="px-3 py-2.5 text-center font-semibold text-neutral-600">Visits</th>
                <th className="px-3 py-2.5 text-center font-semibold text-neutral-600 w-[80px]">Occurrences</th>
                <th className="px-3 py-2.5 text-right font-semibold text-neutral-600 w-[110px]">Unit Cost</th>
                <th className="px-3 py-2.5 text-right font-semibold text-neutral-600">Line Total</th>
                <th className="px-3 py-2.5 text-center font-semibold text-neutral-600">Conf.</th>
              </tr>
            </thead>
            <tbody>
              {budgetLines.map((bl, i) => (
                <tr key={i} className={cn("border-b border-neutral-100 hover:bg-neutral-50/50", bl._edited && "bg-sky-50/50")}>
                  <td className="px-3 py-2">
                    <div className="font-medium text-neutral-800">{bl.canonical_name || bl.procedure}</div>
                    {bl.canonical_name !== bl.procedure && (
                      <div className="text-[10px] text-neutral-400">{bl.procedure}</div>
                    )}
                  </td>
                  <td className="px-3 py-2">
                    <input
                      type="text"
                      value={bl.cpt_code || ""}
                      onChange={(e) => onUpdate(i, "cpt_code", e.target.value)}
                      className="w-full px-2 py-1 text-xs font-mono border border-neutral-200 rounded bg-white focus:outline-none focus:ring-1 focus:ring-brand-primary"
                    />
                  </td>
                  <td className="px-3 py-2"><Badge variant="neutral">{bl.category}</Badge></td>
                  <td className="px-3 py-2 text-center">
                    <span className="text-[10px] text-neutral-500 cursor-help underline decoration-dotted" title={`${(bl.visits_required || []).length} visits where X mark detected:\n${(bl.visits_required || []).join(", ")}\n\nCalculation: ${(bl.visits_required || []).length} occurrences × ${formatCurrency(bl.estimated_unit_cost)} = ${formatCurrency(bl.estimated_unit_cost * bl.total_occurrences)}`}>
                      {(bl.visits_required || []).length} visits
                    </span>
                  </td>
                  <td className="px-3 py-2 text-center">
                    <input
                      type="number"
                      value={bl.total_occurrences}
                      onChange={(e) => onUpdate(i, "total_occurrences", e.target.value)}
                      className="w-16 px-2 py-1 text-xs text-center font-mono border border-neutral-200 rounded bg-white focus:outline-none focus:ring-1 focus:ring-brand-primary"
                    />
                  </td>
                  <td className="px-3 py-2 text-right">
                    <input
                      type="number"
                      value={bl.estimated_unit_cost}
                      onChange={(e) => onUpdate(i, "estimated_unit_cost", e.target.value)}
                      className="w-24 px-2 py-1 text-xs text-right font-mono border border-neutral-200 rounded bg-white focus:outline-none focus:ring-1 focus:ring-brand-primary"
                    />
                  </td>
                  <td className="px-3 py-2 text-right font-mono font-medium text-neutral-800">
                    {formatCurrency(bl.estimated_unit_cost * bl.total_occurrences)}
                  </td>
                  <td className="px-3 py-2 text-center">
                    <span className={cn("text-[10px] font-medium px-1.5 py-0.5 rounded-full", confidenceColor(bl.avg_confidence))}>
                      {(bl.avg_confidence * 100).toFixed(0)}%
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  );
}

// ─── Step 3: Budget Preview ──────────────────────────────────────────────

function Step3BudgetPreview({
  budgetLines,
  grandTotal,
}: {
  budgetLines: EditableBudgetLine[];
  grandTotal: number;
}) {
  // Group by category
  const grouped = useMemo(() => {
    const g: Record<string, EditableBudgetLine[]> = {};
    for (const bl of budgetLines) {
      const cat = bl.category || "Uncategorized";
      if (!g[cat]) g[cat] = [];
      g[cat].push(bl);
    }
    return g;
  }, [budgetLines]);

  const categories = Object.keys(grouped).sort();

  return (
    <div className="space-y-6 max-w-5xl mx-auto">
      <div>
        <h2 className="text-lg font-bold text-neutral-800">Step 3: Budget Preview</h2>
        <p className="text-sm text-neutral-500 mt-1">
          Review the calculated per-patient site budget grouped by category.
        </p>
      </div>

      {/* Summary */}
      <div className="grid grid-cols-3 gap-4">
        <SummaryCard label="Total Procedures" value={String(budgetLines.length)} color="text-brand-primary" />
        <SummaryCard label="Per-Patient Cost" value={formatCurrency(grandTotal)} color="text-emerald-600" />
        <SummaryCard label="Categories" value={String(categories.length)} color="text-purple-600" />
      </div>

      {/* Category breakdown */}
      <Card>
        <div className="overflow-auto">
          <table className="w-full text-xs">
            <thead>
              <tr className="bg-neutral-50">
                <th className="px-3 py-2.5 text-left font-semibold text-neutral-600">Procedure</th>
                <th className="px-3 py-2.5 text-left font-semibold text-neutral-600">CPT</th>
                <th className="px-3 py-2.5 text-center font-semibold text-neutral-600">Visits</th>
                <th className="px-3 py-2.5 text-right font-semibold text-neutral-600">Unit Cost</th>
                <th className="px-3 py-2.5 text-right font-semibold text-neutral-600">Total</th>
              </tr>
            </thead>
            <tbody>
              {categories.map((cat) => {
                const lines = grouped[cat];
                const catTotal = lines.reduce((s, bl) => s + bl.estimated_unit_cost * bl.total_occurrences, 0);
                return (
                  <React.Fragment key={cat}>
                    <tr className="bg-neutral-100">
                      <td colSpan={5} className="px-3 py-2 font-semibold text-neutral-700 text-xs uppercase tracking-wide">
                        {cat}
                      </td>
                    </tr>
                    {lines.map((bl, i) => (
                      <tr key={i} className="border-b border-neutral-50 hover:bg-neutral-50/50">
                        <td className="px-3 py-2 font-medium text-neutral-800">{bl.canonical_name || bl.procedure}</td>
                        <td className="px-3 py-2 text-neutral-500 font-mono">{bl.cpt_code || "—"}</td>
                        <td className="px-3 py-2 text-center font-mono">{bl.total_occurrences}</td>
                        <td className="px-3 py-2 text-right font-mono">{formatCurrency(bl.estimated_unit_cost)}</td>
                        <td className="px-3 py-2 text-right font-mono font-medium">{formatCurrency(bl.estimated_unit_cost * bl.total_occurrences)}</td>
                      </tr>
                    ))}
                    <tr className="bg-neutral-50 border-b-2 border-neutral-200">
                      <td colSpan={4} className="px-3 py-2 text-right text-xs font-medium text-neutral-500">
                        Subtotal — {cat}
                      </td>
                      <td className="px-3 py-2 text-right font-mono font-semibold text-neutral-700">
                        {formatCurrency(catTotal)}
                      </td>
                    </tr>
                  </React.Fragment>
                );
              })}
              <tr className="bg-neutral-800 text-white">
                <td colSpan={4} className="px-3 py-3 font-semibold text-sm">Grand Total (Per Patient)</td>
                <td className="px-3 py-3 text-right font-mono font-bold text-sm">{formatCurrency(grandTotal)}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  );
}

// Need React import for Fragment
import React from "react";

// ─── Step 4: Validate & Export ───────────────────────────────────────────

function Step4Validate({
  budgetLines,
  issues,
  onRunValidation,
  onExport,
  onExportXLSX,
  grandTotal,
}: {
  budgetLines: EditableBudgetLine[];
  issues: ValidationIssue[];
  onRunValidation: () => void;
  onExport: () => void;
  onExportXLSX?: () => void;
  grandTotal: number;
}) {
  const errors = issues.filter((i) => i.severity === "error");
  const warnings = issues.filter((i) => i.severity === "warning");
  const infos = issues.filter((i) => i.severity === "info");

  return (
    <div className="space-y-6 max-w-5xl mx-auto">
      <div>
        <h2 className="text-lg font-bold text-neutral-800">Step 4: Validate & Export</h2>
        <p className="text-sm text-neutral-500 mt-1">
          Run validation checks, review issues, and export the final budget.
        </p>
      </div>

      {/* Run validation */}
      <Card>
        <CardBody className="p-5 flex items-center justify-between">
          <div>
            <h3 className="text-sm font-semibold text-neutral-800">Validation Check</h3>
            <p className="text-xs text-neutral-400 mt-0.5">
              Checks for missing CPT codes, low confidence values, zero costs, and unbudgeted procedures.
            </p>
          </div>
          <button
            onClick={onRunValidation}
            className="px-5 py-2.5 text-sm font-medium bg-brand-primary text-white rounded-lg hover:bg-brand-french"
          >
            Run Validation
          </button>
        </CardBody>
      </Card>

      {/* Results */}
      {issues.length > 0 && (
        <div className="space-y-3">
          {/* Summary */}
          <div className="flex gap-3">
            {errors.length > 0 && (
              <Badge variant="danger">{errors.length} error{errors.length !== 1 ? "s" : ""}</Badge>
            )}
            {warnings.length > 0 && (
              <Badge variant="warning">{warnings.length} warning{warnings.length !== 1 ? "s" : ""}</Badge>
            )}
            {infos.length > 0 && (
              <Badge variant="info">{infos.length} info</Badge>
            )}
          </div>

          {/* Issue list */}
          <Card>
            <div className="divide-y divide-neutral-100">
              {issues.map((issue, i) => (
                <div key={i} className={cn("px-4 py-3 flex items-start gap-3", issue.severity === "error" && "bg-red-50/50")}>
                  <span className={cn(
                    "w-2 h-2 rounded-full mt-1.5 shrink-0",
                    issue.severity === "error" ? "bg-red-500" :
                    issue.severity === "warning" ? "bg-amber-500" : "bg-sky-500"
                  )} />
                  <div>
                    <p className="text-xs text-neutral-700">{issue.message}</p>
                    <p className="text-[10px] text-neutral-400 mt-0.5">{issue.field}</p>
                  </div>
                </div>
              ))}
            </div>
          </Card>
        </div>
      )}

      {issues.length === 0 && (
        <Card>
          <CardBody className="p-8 text-center">
            <div className="w-12 h-12 rounded-full bg-emerald-50 flex items-center justify-center mx-auto mb-3">
              <svg className="w-6 h-6 text-emerald-600" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M9 12.75L11.25 15 15 9.75M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
            </div>
            <p className="text-sm font-medium text-neutral-700">Click "Run Validation" to check for issues</p>
          </CardBody>
        </Card>
      )}

      {/* Export */}
      <Card className="border-emerald-200 bg-emerald-50/30">
        <CardBody className="p-5 flex items-center justify-between">
          <div>
            <h3 className="text-sm font-semibold text-neutral-800">Export Budget</h3>
            <p className="text-xs text-neutral-500 mt-0.5">
              {budgetLines.length} procedures · {formatCurrency(grandTotal)} per patient
            </p>
          </div>
          <div className="flex items-center gap-2">
            {onExportXLSX && (
              <button
                onClick={onExportXLSX}
                className="px-5 py-2.5 text-sm font-medium bg-emerald-600 text-white rounded-lg hover:bg-emerald-700 flex items-center gap-2"
              >
                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5M16.5 12L12 16.5m0 0L7.5 12m4.5 4.5V3" />
                </svg>
                Export XLSX
              </button>
            )}
            <button
              onClick={onExport}
              className="px-4 py-2.5 text-sm font-medium border border-neutral-200 text-neutral-700 rounded-lg hover:bg-neutral-50 flex items-center gap-2"
            >
              Export CSV
            </button>
          </div>
        </CardBody>
      </Card>
    </div>
  );
}

// ─── Shared Components ───────────────────────────────────────────────────

function SummaryCard({ label, value, color }: { label: string; value: string; color: string }) {
  return (
    <Card>
      <CardBody className="p-4">
        <p className="text-[11px] text-neutral-400 uppercase tracking-wide font-medium">{label}</p>
        <p className={cn("text-xl font-bold font-mono mt-1", color)}>{value}</p>
      </CardBody>
    </Card>
  );
}
