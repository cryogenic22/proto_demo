"use client";

import { useState, useEffect, useMemo, useCallback } from "react";
import type {
  ExtractedTable,
  ExtractedCell,
  ResolvedFootnote,
  NormalizedProcedure,
  ReviewItem,
} from "@/lib/api";
import { getPageImageUrl } from "@/lib/api";
import { Card, CardHeader, CardBody } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { cn } from "@/lib/utils";

// ─── Types ────────────────────────────────────────────────────────────────

interface CritiqueItem {
  category: string;
  severity: "high" | "medium" | "low";
  title: string;
  detail: string;
  count: number;
  icon: string; // emoji-like label
}

type FilterType = "all" | "flagged" | "low_confidence" | "missing_cpt" | "conditional";
type Layer = "overview" | "grid";

// ─── Critique Engine ──────────────────────────────────────────────────────

function generateCritique(table: ExtractedTable): CritiqueItem[] {
  const items: CritiqueItem[] = [];
  const cells = table.cells || [];
  const footnotes = table.footnotes || [];
  const procedures = table.procedures || [];
  const flagged = table.flagged_cells || [];
  const reviewItems = table.review_items || [];
  const meta = table.extraction_metadata || { passes_run: 0, challenger_issues_found: 0, reconciliation_conflicts: 0 };

  // 1. Confidence
  const lowConf = cells.filter((c) => c.confidence < 0.85);
  if (lowConf.length > 0) {
    items.push({
      category: "confidence", severity: lowConf.some((c) => c.confidence < 0.7) ? "high" : "medium",
      title: `${lowConf.length} cell${lowConf.length > 1 ? "s" : ""} with low confidence`,
      detail: `${lowConf.filter((c) => c.confidence < 0.7).length} below 70%, ${lowConf.filter((c) => c.confidence >= 0.7).length} between 70-85%`,
      count: lowConf.length, icon: "!",
    });
  }

  // 2. Conditional footnotes
  const conditional = footnotes.filter((f) => f.footnote_type === "CONDITIONAL");
  if (conditional.length > 0) {
    const affectedCells = conditional.reduce((sum, f) => sum + (f.applies_to?.length || 0), 0);
    items.push({
      category: "footnote_impact", severity: "medium",
      title: `${conditional.length} conditional footnote${conditional.length > 1 ? "s" : ""} affect scheduling`,
      detail: `${affectedCells} cells have conditional visit requirements — impacts budget calculations`,
      count: conditional.length, icon: "\u26A1",
    });
  }

  // 3. CPT gaps
  const noCpt = procedures.filter((p) => !p.code);
  if (noCpt.length > 0) {
    items.push({
      category: "cpt_gap", severity: noCpt.length > 3 ? "high" : "medium",
      title: `${noCpt.length} procedure${noCpt.length > 1 ? "s" : ""} missing CPT codes`,
      detail: noCpt.slice(0, 3).map((p) => p.canonical_name).join(", ") + (noCpt.length > 3 ? "..." : ""),
      count: noCpt.length, icon: "#",
    });
  }

  // 4. Flagged cells
  if (flagged.length > 0) {
    items.push({
      category: "flagged", severity: flagged.length > 10 ? "high" : "medium",
      title: `${flagged.length} cell${flagged.length > 1 ? "s" : ""} flagged for review`,
      detail: `Flagged by the extraction pipeline for manual verification`,
      count: flagged.length, icon: "\u2691",
    });
  }

  // 5. Pass disagreements
  const disagreements = reviewItems.filter((r) => r.reason?.includes("Pass disagreement"));
  if (disagreements.length > 0) {
    const pages = [...new Set(disagreements.map((d) => d.source_page))].sort();
    items.push({
      category: "pass_disagreement", severity: "high",
      title: `${disagreements.length} pass disagreement${disagreements.length > 1 ? "s" : ""}`,
      detail: `Two extraction passes produced different values — check page${pages.length > 1 ? "s" : ""} ${pages.join(", ")}`,
      count: disagreements.length, icon: "\u21C4",
    });
  }

  // 6. Cost risk
  const highCost = procedures.filter((p) => p.estimated_cost_tier === "VERY_HIGH");
  if (highCost.length > 0) {
    items.push({
      category: "cost_risk", severity: "low",
      title: `${highCost.length} high-cost procedure${highCost.length > 1 ? "s" : ""} — verify accuracy`,
      detail: highCost.map((p) => p.canonical_name).join(", "),
      count: highCost.length, icon: "$",
    });
  }

  // Success state
  if (items.length === 0) {
    items.push({
      category: "success", severity: "low",
      title: "No issues found", detail: "Table extraction looks clean — proceed with confidence",
      count: 0, icon: "\u2713",
    });
  }

  return items.sort((a, b) => {
    const order = { high: 0, medium: 1, low: 2 };
    return order[a.severity] - order[b.severity];
  });
}

// ─── Main Component ──────────────────────────────────────────────────────

export function SoAReviewAssistant({
  table,
  protocolId,
  onClose,
  onNextTable,
  onPrevTable,
  tableIndex,
  totalTables,
}: {
  table: ExtractedTable;
  protocolId: string;
  onClose: () => void;
  onNextTable?: () => void;
  onPrevTable?: () => void;
  tableIndex?: number;
  totalTables?: number;
}) {
  const [layer, setLayer] = useState<Layer>("overview");
  const [filter, setFilter] = useState<FilterType>("all");
  const [selectedCell, setSelectedCell] = useState<{ row: number; col: number } | null>(null);
  const [collapsedGroups, setCollapsedGroups] = useState<Set<string>>(new Set());
  const [cellActions, setCellActions] = useState<Map<string, string>>(new Map());
  const [cellCorrections, setCellCorrections] = useState<Map<string, string>>(new Map());
  const [auditLog, setAuditLog] = useState<{ time: string; cell: string; action: string; oldValue?: string; newValue?: string }[]>([]);

  const cells = table.cells || [];
  const footnotes = table.footnotes || [];
  const procedures = table.procedures || [];
  const flagged = table.flagged_cells || [];
  const reviewItems = table.review_items || [];
  const schema = table.schema_info || { column_headers: [], row_groups: [], num_rows: 0, num_cols: 0 };
  const visitWindows = table.visit_windows || [];

  // Memoized lookups
  const cellMap = useMemo(() => {
    const m = new Map<string, ExtractedCell>();
    for (const c of cells) m.set(`${c.row}-${c.col}`, c);
    return m;
  }, [cells]);

  const flaggedSet = useMemo(() => new Set(flagged.map((c) => `${c.row}-${c.col}`)), [flagged]);

  const cellFootnotes = useMemo(() => {
    const m = new Map<string, ResolvedFootnote[]>();
    for (const fn of footnotes) {
      for (const ref of fn.applies_to || []) {
        const key = `${ref.row}-${ref.col}`;
        if (!m.has(key)) m.set(key, []);
        m.get(key)!.push(fn);
      }
    }
    return m;
  }, [footnotes]);

  const critique = useMemo(() => generateCritique(table), [table]);

  const maxRow = cells.reduce((m, c) => Math.max(m, c.row), 0);
  const maxCol = cells.reduce((m, c) => Math.max(m, c.col), 0);
  const confidence = table.overall_confidence || 0;

  const handleCellAction = useCallback(async (row: number, col: number, action: string, correctedValue?: string) => {
    const key = `${row}-${col}`;
    const cell = cellMap.get(key);

    // Update local state
    setCellActions((prev) => new Map(prev).set(key, action));
    if (action === "corrected" && correctedValue !== undefined) {
      setCellCorrections((prev) => new Map(prev).set(key, correctedValue));
    }
    if (action) {
      setAuditLog((prev) => [...prev, {
        time: new Date().toISOString(),
        cell: `${cell?.row_header || row}:${cell?.col_header || col}`,
        action,
        oldValue: cell?.raw_value,
        newValue: action === "corrected" ? correctedValue : undefined,
      }]);

      // Persist to backend — updates protocol JSON + ground truth log
      try {
        const { submitCellReview } = await import("@/lib/api");
        await submitCellReview({
          protocol_id: protocolId,
          table_id: table.table_id,
          row,
          col,
          action: action === "accepted" ? "accept" : action === "corrected" ? "correct" : "flag",
          correct_value: action === "corrected" ? correctedValue : undefined,
          flag_reason: action === "flagged" ? "Flagged during review" : undefined,
        });
      } catch (e) {
        console.error("Failed to persist review action:", e);
      }
    }
  }, [cellMap, protocolId, table.table_id]);

  const toggleGroup = useCallback((name: string) => {
    setCollapsedGroups((prev) => {
      const next = new Set(prev);
      if (next.has(name)) next.delete(name); else next.add(name);
      return next;
    });
  }, []);

  const reviewed = cellActions.size;
  const totalFlagged = flagged.length;

  return (
    <div className="h-full flex flex-col bg-neutral-50">
      {/* Header */}
      <div className="bg-white border-b border-neutral-200 px-4 py-2.5 flex items-center gap-3 shrink-0">
        <button onClick={onClose} className="text-neutral-400 hover:text-neutral-600">
          <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M10.5 19.5L3 12m0 0l7.5-7.5M3 12h18" />
          </svg>
        </button>
        <div className="min-w-0 flex-1">
          <h2 className="text-sm font-semibold text-neutral-800 truncate">
            {table.title || `Table ${table.table_id}`}
          </h2>
          <p className="text-[11px] text-neutral-400">
            {cells.length} cells · {procedures.length} procedures · {footnotes.length} footnotes · Pages {(table.source_pages || []).join(", ")}
          </p>
        </div>
        {/* Layer breadcrumb */}
        <div className="flex items-center gap-1 text-xs">
          <button onClick={() => { setLayer("overview"); setSelectedCell(null); }} className={cn("px-2 py-1 rounded", layer === "overview" ? "bg-brand-primary text-white" : "text-neutral-500 hover:bg-neutral-100")}>Overview</button>
          <button onClick={() => { setLayer("grid"); setSelectedCell(null); }} className={cn("px-2 py-1 rounded", layer === "grid" ? "bg-brand-primary text-white" : "text-neutral-500 hover:bg-neutral-100")}>Grid</button>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          {/* Human Reviewed badge */}
          {reviewed > 0 && reviewed >= cells.length && (
            <span className="text-[10px] font-semibold px-2 py-0.5 rounded-full bg-emerald-100 text-emerald-700 flex items-center gap-1">
              <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}><path strokeLinecap="round" strokeLinejoin="round" d="M9 12.75L11.25 15 15 9.75m-3-7.036A11.959 11.959 0 013.598 6 11.99 11.99 0 003 9.749c0 5.592 3.824 10.29 9 11.623 5.176-1.332 9-6.03 9-11.622 0-1.31-.21-2.571-.598-3.751h-.152c-3.196 0-6.1-1.248-8.25-3.285z" /></svg>
              Human Reviewed
            </span>
          )}
          {reviewed > 0 && reviewed < cells.length && (
            <span className="text-[10px] font-medium text-neutral-500">{reviewed}/{cells.length}</span>
          )}
          <Badge variant={table.table_type === "SOA" ? "brand" : "neutral"}>{table.table_type}</Badge>
          <span className={cn("text-xs font-semibold px-2 py-0.5 rounded", confColor(confidence))}>{(confidence * 100).toFixed(0)}%</span>
          {/* Table navigation */}
          {totalTables && totalTables > 1 && (
            <div className="flex items-center gap-0.5 ml-1">
              <button onClick={onPrevTable} disabled={!onPrevTable || tableIndex === 0} className="p-1 rounded hover:bg-neutral-100 disabled:opacity-30 text-neutral-500">
                <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}><path strokeLinecap="round" strokeLinejoin="round" d="M15.75 19.5L8.25 12l7.5-7.5" /></svg>
              </button>
              <span className="text-[10px] text-neutral-400 font-mono">{(tableIndex || 0) + 1}/{totalTables}</span>
              <button onClick={onNextTable} disabled={!onNextTable || tableIndex === (totalTables || 0) - 1} className="p-1 rounded hover:bg-neutral-100 disabled:opacity-30 text-neutral-500">
                <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}><path strokeLinecap="round" strokeLinejoin="round" d="M8.25 4.5l7.5 7.5-7.5 7.5" /></svg>
              </button>
            </div>
          )}
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 flex overflow-hidden">
        <div className={cn("flex-1 overflow-y-auto", selectedCell && "mr-[380px]")}>
          {layer === "overview" && (
            <OverviewPanel
              cells={cells} flagged={flagged} procedures={procedures} footnotes={footnotes}
              confidence={confidence} critique={critique} reviewed={reviewed}
              meta={table.extraction_metadata}
              onStartReview={() => { setLayer("grid"); setFilter("flagged"); }}
              onJumpToIssues={() => { setLayer("grid"); setFilter("low_confidence"); }}
              onViewGrid={() => { setLayer("grid"); setFilter("all"); }}
            />
          )}
          {layer === "grid" && (
            <SmartGrid
              cells={cells} schema={schema} visitWindows={visitWindows}
              cellMap={cellMap} flaggedSet={flaggedSet} cellFootnotes={cellFootnotes}
              procedures={procedures} footnotes={footnotes}
              filter={filter} collapsedGroups={collapsedGroups}
              cellActions={cellActions} maxRow={maxRow} maxCol={maxCol}
              onFilterChange={setFilter} onCellClick={setSelectedCell}
              onToggleGroup={toggleGroup}
              onCollapseAll={() => {
                const allGroups = new Set((schema?.row_groups || []).map((g) => g.name));
                setCollapsedGroups(allGroups);
              }}
              onExpandAll={() => setCollapsedGroups(new Set())}
              reviewed={reviewed} totalFlagged={totalFlagged}
            />
          )}
        </div>

        {/* Cell detail slide-out */}
        {selectedCell && (
          <CellDetailPanel
            cell={cellMap.get(`${selectedCell.row}-${selectedCell.col}`) || {
              row: selectedCell.row, col: selectedCell.col,
              raw_value: "", normalized_value: null, data_type: "EMPTY" as const,
              footnote_markers: [], resolved_footnotes: [],
              confidence: 0, row_header: cellMap.get(`${selectedCell.row}-0`)?.row_header || `Row ${selectedCell.row}`,
              col_header: (table.schema_info?.column_headers?.[selectedCell.col]?.text) || `Col ${selectedCell.col}`,
            }}
            footnotes={cellFootnotes.get(`${selectedCell.row}-${selectedCell.col}`) || []}
            reviewItem={reviewItems.find((r) => r.cell_ref?.row === selectedCell.row && r.cell_ref?.col === selectedCell.col)}
            isFlagged={flaggedSet.has(`${selectedCell.row}-${selectedCell.col}`)}
            action={cellActions.get(`${selectedCell.row}-${selectedCell.col}`)}
            protocolId={protocolId}
            sourcePages={table.source_pages || []}
            correctedValue={cellCorrections.get(`${selectedCell.row}-${selectedCell.col}`)}
            onClose={() => setSelectedCell(null)}
            onAction={(a, corrected) => handleCellAction(selectedCell.row, selectedCell.col, a, corrected)}
          />
        )}
      </div>
    </div>
  );
}

function confColor(c: number) {
  if (c >= 0.95) return "bg-emerald-100 text-emerald-700";
  if (c >= 0.85) return "bg-sky-100 text-sky-700";
  if (c >= 0.70) return "bg-amber-100 text-amber-700";
  return "bg-red-100 text-red-700";
}

function confBg(c: number) {
  if (c >= 0.95) return "bg-emerald-50";
  if (c >= 0.85) return "bg-sky-50";
  if (c >= 0.70) return "bg-amber-50";
  return "bg-red-50";
}

// ─── Layer 1: Overview ───────────────────────────────────────────────────

function OverviewPanel({
  cells, flagged, procedures, footnotes, confidence, critique, reviewed, meta,
  onStartReview, onJumpToIssues, onViewGrid,
}: {
  cells: ExtractedCell[]; flagged: { row: number; col: number }[];
  procedures: NormalizedProcedure[]; footnotes: ResolvedFootnote[];
  confidence: number; critique: CritiqueItem[]; reviewed: number;
  meta?: { passes_run: number; challenger_issues_found: number; reconciliation_conflicts: number; processing_time_seconds: number };
  onStartReview: () => void; onJumpToIssues: () => void; onViewGrid: () => void;
}) {
  const pct = Math.round(confidence * 100);
  const circumference = 2 * Math.PI * 40;
  const dashOffset = circumference * (1 - confidence);

  return (
    <div className="p-6 max-w-4xl mx-auto space-y-6">
      {/* Summary row */}
      <div className="grid grid-cols-4 gap-4">
        {/* Confidence gauge */}
        <Card>
          <CardBody className="p-4 flex flex-col items-center">
            <svg width="80" height="80" viewBox="0 0 100 100" className="mb-1">
              <circle cx="50" cy="50" r="40" stroke="#e2e8f0" strokeWidth="8" fill="none" />
              <circle cx="50" cy="50" r="40" stroke={pct >= 90 ? "#00A950" : pct >= 80 ? "#0093D0" : pct >= 70 ? "#F8971D" : "#CC292B"} strokeWidth="8" fill="none" strokeLinecap="round" strokeDasharray={circumference} strokeDashoffset={dashOffset} transform="rotate(-90 50 50)" />
              <text x="50" y="55" textAnchor="middle" className="text-lg font-bold" fill="#1e293b">{pct}%</text>
            </svg>
            <span className="text-[11px] text-neutral-500 uppercase tracking-wide">Confidence</span>
          </CardBody>
        </Card>
        <MetricCard label="Total Cells" value={cells.length} color="text-brand-primary" />
        <MetricCard label="Flagged" value={flagged.length} color={flagged.length > 0 ? "text-amber-600" : "text-emerald-600"} />
        <MetricCard label="Procedures" value={procedures.length} color="text-purple-600" />
      </div>

      {/* Critique panel */}
      <Card>
        <CardHeader>
          <h3 className="text-sm font-semibold text-neutral-800">Review Assistant</h3>
          <p className="text-[11px] text-neutral-400 mt-0.5">Automated analysis of extraction quality</p>
        </CardHeader>
        <div className="divide-y divide-neutral-100">
          {critique.map((item, i) => (
            <div key={i} className="px-4 py-3 flex items-start gap-3">
              <span className={cn(
                "w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold shrink-0 mt-0.5",
                item.severity === "high" ? "bg-red-100 text-red-600" :
                item.severity === "medium" ? "bg-amber-100 text-amber-600" :
                item.category === "success" ? "bg-emerald-100 text-emerald-600" :
                "bg-sky-100 text-sky-600"
              )}>
                {item.icon}
              </span>
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium text-neutral-800">{item.title}</p>
                <p className="text-xs text-neutral-500 mt-0.5">{item.detail}</p>
              </div>
              {item.count > 0 && (
                <Badge variant={item.severity === "high" ? "danger" : item.severity === "medium" ? "warning" : "neutral"}>
                  {item.count}
                </Badge>
              )}
            </div>
          ))}
        </div>
      </Card>

      {/* Quick actions */}
      <div className="flex gap-3">
        <button onClick={onStartReview} className="flex-1 py-3 text-sm font-medium bg-brand-primary text-white rounded-lg hover:bg-brand-french transition-colors">
          Start Review {flagged.length > 0 ? `(${flagged.length} flagged)` : ""}
        </button>
        <button onClick={onJumpToIssues} className="flex-1 py-3 text-sm font-medium bg-amber-50 text-amber-700 border border-amber-200 rounded-lg hover:bg-amber-100 transition-colors">
          Low Confidence Cells
        </button>
        <button onClick={onViewGrid} className="flex-1 py-3 text-sm font-medium bg-neutral-100 text-neutral-700 rounded-lg hover:bg-neutral-200 transition-colors">
          View Full Grid
        </button>
      </div>

      {/* Extraction metadata */}
      {meta && (
        <div className="text-[11px] text-neutral-400 flex items-center gap-4">
          <span>{meta.passes_run} extraction passes</span>
          <span>{meta.challenger_issues_found} challenger issues</span>
          <span>{meta.reconciliation_conflicts} conflicts</span>
          <span>{meta.processing_time_seconds?.toFixed(0)}s processing</span>
        </div>
      )}
    </div>
  );
}

function MetricCard({ label, value, color }: { label: string; value: number; color: string }) {
  return (
    <Card>
      <CardBody className="p-4 text-center">
        <p className={cn("text-2xl font-bold font-mono", color)}>{value}</p>
        <span className="text-[11px] text-neutral-500 uppercase tracking-wide">{label}</span>
      </CardBody>
    </Card>
  );
}

// ─── Layer 2: Smart Grid ─────────────────────────────────────────────────

function SmartGrid({
  cells, schema, visitWindows, cellMap, flaggedSet, cellFootnotes, procedures,
  footnotes, filter, collapsedGroups, cellActions, maxRow, maxCol,
  onFilterChange, onCellClick, onToggleGroup, onCollapseAll, onExpandAll,
  reviewed, totalFlagged,
}: {
  cells: ExtractedCell[];
  schema: ExtractedTable["schema_info"];
  visitWindows: ExtractedTable["visit_windows"];
  footnotes: ResolvedFootnote[];
  cellMap: Map<string, ExtractedCell>;
  flaggedSet: Set<string>;
  cellFootnotes: Map<string, ResolvedFootnote[]>;
  procedures: NormalizedProcedure[];
  filter: FilterType;
  collapsedGroups: Set<string>;
  cellActions: Map<string, string>;
  maxRow: number; maxCol: number;
  onFilterChange: (f: FilterType) => void;
  onCellClick: (c: { row: number; col: number }) => void;
  onToggleGroup: (name: string) => void;
  onCollapseAll: () => void;
  onExpandAll: () => void;
  reviewed: number; totalFlagged: number;
}) {
  const colHeaders = schema?.column_headers || [];
  const rowGroups = schema?.row_groups || [];

  // Build row→group lookup
  const rowGroup = useMemo(() => {
    const m = new Map<number, typeof rowGroups[0]>();
    for (const rg of rowGroups) {
      for (let r = rg.start_row; r <= rg.end_row; r++) m.set(r, rg);
    }
    return m;
  }, [rowGroups]);

  // Visit window labels
  const visitLabels = useMemo(() => {
    const m = new Map<number, string>();
    for (const vw of visitWindows || []) {
      if (vw.target_day != null) m.set(vw.col_index, `Day ${vw.target_day}`);
    }
    return m;
  }, [visitWindows]);

  // Conditional cells
  const conditionalCells = useMemo(() => {
    const s = new Set<string>();
    for (const fn of cellFootnotes.values()) {
      // cellFootnotes is keyed by cell, values are arrays of footnotes
    }
    // Rebuild from raw table footnotes
    return s;
  }, [cellFootnotes]);

  // Filter chips
  const filters: { key: FilterType; label: string }[] = [
    { key: "all", label: "All cells" },
    { key: "flagged", label: `Flagged (${flaggedSet.size})` },
    { key: "low_confidence", label: "Low confidence" },
    { key: "missing_cpt", label: "Missing CPT" },
  ];

  // Check if row is visible based on filter
  const isRowVisible = useCallback((row: number) => {
    if (filter === "all") return true;
    for (let col = 0; col <= maxCol; col++) {
      const key = `${row}-${col}`;
      const cell = cellMap.get(key);
      if (!cell) continue;
      if (filter === "flagged" && flaggedSet.has(key)) return true;
      if (filter === "low_confidence" && cell.confidence < 0.85) return true;
    }
    if (filter === "missing_cpt") {
      const firstCell = cellMap.get(`${row}-0`);
      if (firstCell) {
        const proc = procedures.find((p) => p.raw_name === firstCell.row_header || p.raw_name === firstCell.raw_value);
        if (proc && !proc.code) return true;
      }
    }
    return false;
  }, [filter, cellMap, flaggedSet, maxCol, procedures]);

  return (
    <div className="flex flex-col h-full">
      {/* Filter bar */}
      <div className="px-4 py-2 bg-white border-b border-neutral-200 flex items-center gap-2 shrink-0">
        {filters.map((f) => (
          <button
            key={f.key}
            onClick={() => onFilterChange(f.key)}
            className={cn(
              "px-2.5 py-1 text-[11px] font-medium rounded-md transition-colors",
              filter === f.key ? "bg-brand-primary text-white" : "bg-neutral-100 text-neutral-600 hover:bg-neutral-200"
            )}
          >
            {f.label}
          </button>
        ))}
        <div className="ml-auto flex items-center gap-2 text-[11px] text-neutral-400">
          <button onClick={onCollapseAll} className="px-1.5 py-0.5 rounded hover:bg-neutral-100 text-neutral-500">Collapse all</button>
          <button onClick={onExpandAll} className="px-1.5 py-0.5 rounded hover:bg-neutral-100 text-neutral-500">Expand all</button>
          {reviewed > 0 && <span className="text-emerald-600 font-medium">{reviewed} reviewed</span>}
          {totalFlagged > 0 && <span className="ml-1">{totalFlagged} flagged</span>}
        </div>
      </div>

      {/* Grid */}
      <div className="flex-1 overflow-auto">
        <table className="text-xs border-collapse min-w-full">
          <thead className="sticky top-0 z-10">
            <tr className="bg-neutral-100">
              <th className="px-3 py-2 text-left font-semibold text-neutral-600 border border-neutral-200 bg-neutral-100 sticky left-0 z-20 min-w-[180px] max-w-[240px]">
                Procedure
              </th>
              {/* Skip col 0 (procedure name) — already shown as sticky column */}
              {colHeaders.slice(1).map((ch, i) => (
                <th key={i + 1} className="px-2 py-1.5 text-center font-semibold text-neutral-600 border border-neutral-200 bg-neutral-100 min-w-[55px] whitespace-nowrap">
                  <div className="text-[10px] leading-tight">{ch.text}</div>
                  {visitLabels.get(ch.col_index) && (
                    <div className="text-[9px] text-neutral-400 font-normal">{visitLabels.get(ch.col_index)}</div>
                  )}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {Array.from({ length: maxRow + 1 }, (_, row) => {
              const group = rowGroup.get(row);
              const isGroupStart = group && group.start_row === row;
              const isCollapsed = group && collapsedGroups.has(group.name);
              const visible = isRowVisible(row);

              if (isCollapsed && !isGroupStart) return null;
              if (!visible && filter !== "all") return null;

              return (
                <React.Fragment key={row}>
                  {/* Group header */}
                  {isGroupStart && (
                    <tr className="bg-neutral-100">
                      <td
                        colSpan={colHeaders.length}
                        className="px-3 py-1.5 font-semibold text-neutral-700 text-[11px] uppercase tracking-wide cursor-pointer hover:bg-neutral-200"
                        onClick={() => group && onToggleGroup(group.name)}
                      >
                        <span className="flex items-center gap-2">
                          <svg className={cn("w-3 h-3 transition-transform", !isCollapsed && "rotate-90")} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                            <path strokeLinecap="round" strokeLinejoin="round" d="M8.25 4.5l7.5 7.5-7.5 7.5" />
                          </svg>
                          {group!.name}
                          <Badge variant="neutral">{group!.category}</Badge>
                        </span>
                      </td>
                    </tr>
                  )}
                  {/* Data row */}
                  {!isCollapsed && (
                    <tr className="hover:bg-neutral-50/50">
                      <td className="px-3 py-1.5 font-medium text-neutral-700 border border-neutral-200 bg-white sticky left-0 z-10 text-[11px] max-w-[240px]">
                        <div className="truncate" title={cellMap.get(`${row}-0`)?.row_header || ""}>
                          {cellMap.get(`${row}-0`)?.row_header || `Row ${row}`}
                        </div>
                      </td>
                      {/* Skip col 0 — render from col 1 onward */}
                      {colHeaders.slice(1).map((_, ci) => {
                        const colIdx = ci + 1;
                        const key = `${row}-${colIdx}`;
                        const cell = cellMap.get(key);
                        const isFlagged = flaggedSet.has(key);
                        const fns = cellFootnotes.get(key);
                        const acted = cellActions.get(key);

                        // Show corrected value if available
                        const corrected = cellActions.get(key) === "corrected" ? true : false;
                        const displayValue = corrected
                          ? (cellMap.get(key)?.raw_value || "") // Will show original; corrected value shown in panel
                          : (cell?.raw_value || "");

                        return (
                          <td
                            key={colIdx}
                            onClick={() => onCellClick({ row, col: colIdx })}
                            className={cn(
                              "px-1.5 py-1 text-center border border-neutral-200 font-mono text-[11px] cursor-pointer transition-colors relative",
                              acted === "accepted" ? "bg-emerald-50 ring-1 ring-emerald-300" :
                              acted === "corrected" ? "bg-sky-50 ring-1 ring-sky-300" :
                              acted === "flagged" ? "bg-red-50 ring-1 ring-red-300" :
                              cell ? confBg(cell.confidence) : "bg-neutral-50 hover:bg-neutral-100",
                              isFlagged && !acted && "ring-2 ring-amber-400",
                            )}
                            title={cell ? `${cell.raw_value || "(empty)"} (${(cell.confidence * 100).toFixed(0)}%)` : "Click to add value"}
                          >
                            {displayValue || <span className="text-neutral-300">&middot;</span>}
                            {fns && fns.length > 0 && (
                              <sup className="text-brand-primary text-[8px] ml-0.5">
                                {fns.map((f) => f.marker).join(",")}
                                {fns.some((f) => f.footnote_type === "CONDITIONAL") && (
                                  <span className="text-amber-500">\u26A1</span>
                                )}
                              </sup>
                            )}
                            {/* Human verified badge */}
                            {acted && (
                              <span className={cn(
                                "absolute top-0 right-0 w-3 h-3 flex items-center justify-center text-[7px] font-bold rounded-bl",
                                acted === "accepted" ? "bg-emerald-500 text-white" :
                                acted === "corrected" ? "bg-sky-500 text-white" :
                                "bg-red-500 text-white"
                              )}>
                                {acted === "accepted" ? "\u2713" : acted === "corrected" ? "\u270E" : "\u2691"}
                              </span>
                            )}
                          </td>
                        );
                      })}
                    </tr>
                  )}
                </React.Fragment>
              );
            })}
          </tbody>
        </table>

        {/* Footnotes below grid */}
        {footnotes.length > 0 && (
          <div className="px-4 py-3 border-t border-neutral-200 bg-neutral-50">
            <h4 className="text-[10px] font-semibold text-neutral-600 uppercase tracking-wide mb-2">Footnotes</h4>
            <div className="space-y-1">
              {footnotes.map((fn, i) => (
                <div key={i} className="flex gap-2 text-[11px]">
                  <sup className="text-brand-primary font-bold shrink-0">{fn.marker}</sup>
                  <span className="text-neutral-600">{fn.text}</span>
                  <Badge variant={fn.footnote_type === "CONDITIONAL" ? "warning" : "neutral"} className="shrink-0 self-start">
                    {fn.footnote_type}
                  </Badge>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

import React from "react";

// ─── Layer 3: Cell Detail Panel ──────────────────────────────────────────

function CellDetailPanel({
  cell, footnotes, reviewItem, isFlagged, action, protocolId,
  sourcePages, correctedValue, onClose, onAction,
}: {
  cell: ExtractedCell | null;
  footnotes: ResolvedFootnote[];
  reviewItem?: ReviewItem;
  isFlagged: boolean;
  action?: string;
  protocolId: string;
  sourcePages: number[];
  correctedValue?: string;
  onClose: () => void;
  onAction: (action: string, correctedValue?: string) => void;
}) {
  const [showSource, setShowSource] = useState(false);
  const [pdfError, setPdfError] = useState(false);
  const [zoomed, setZoomed] = useState(false);
  const [editMode, setEditMode] = useState(false);
  const [editValue, setEditValue] = useState("");

  // Source page navigation
  const initialPage = reviewItem?.source_page || sourcePages[0] || 1;
  const [currentPage, setCurrentPage] = useState(initialPage);

  if (!cell) return null;

  // 0-indexed for the API (source_pages are 1-indexed in the data,
  // but some protocols use 0-indexed — handle both)
  const pageIndex = currentPage;

  return (
    <div className="fixed top-0 right-0 w-[380px] h-full bg-white border-l border-neutral-200 shadow-lg z-50 flex flex-col">
      {/* Header */}
      <div className="px-4 py-3 border-b border-neutral-200 flex items-center justify-between shrink-0">
        <div>
          <div className="text-[10px] uppercase tracking-wider text-brand-primary font-semibold">Cell Detail</div>
          <div className="text-xs text-neutral-500">
            Row: <span className="font-medium text-neutral-700">{cell.row_header}</span> · Col: <span className="font-medium text-neutral-700">{cell.col_header}</span>
          </div>
        </div>
        <div className="flex items-center gap-1">
          <button
            onClick={() => { setShowSource(!showSource); setPdfError(false); }}
            className={cn(
              "px-2 py-1 text-[10px] font-medium rounded transition-colors",
              showSource ? "bg-brand-primary text-white" : "text-neutral-500 hover:bg-neutral-100"
            )}
            title="Toggle source document view"
          >
            {showSource ? "Hide Source" : "View Source"}
          </button>
          <button onClick={onClose} className="p-1 rounded-md hover:bg-neutral-100 text-neutral-400">
            <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round">
              <path d="M4 4L12 12M12 4L4 12" />
            </svg>
          </button>
        </div>
      </div>

      {/* Source PDF preview */}
      {showSource && (
        <div className={cn(
          "border-b border-neutral-200 bg-neutral-100",
          zoomed ? "fixed inset-0 z-[100] border-0 flex flex-col" : "shrink-0"
        )}>
          <div className="px-3 py-1.5 flex items-center justify-between bg-white border-b border-neutral-100 shrink-0">
            <span className="text-[10px] font-semibold text-neutral-600 uppercase tracking-wide">Source Document</span>
            <div className="flex items-center gap-1">
              <button onClick={() => setCurrentPage(Math.max(0, currentPage - 1))} className="p-0.5 rounded hover:bg-neutral-100 text-neutral-500">
                <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}><path strokeLinecap="round" strokeLinejoin="round" d="M15.75 19.5L8.25 12l7.5-7.5" /></svg>
              </button>
              <span className="text-[10px] text-neutral-500 font-mono min-w-[40px] text-center">{currentPage}</span>
              <button onClick={() => setCurrentPage(currentPage + 1)} className="p-0.5 rounded hover:bg-neutral-100 text-neutral-500">
                <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}><path strokeLinecap="round" strokeLinejoin="round" d="M8.25 4.5l7.5 7.5-7.5 7.5" /></svg>
              </button>
              <button
                onClick={() => setZoomed(!zoomed)}
                className="p-0.5 rounded hover:bg-neutral-100 text-neutral-500 ml-1"
                title={zoomed ? "Exit fullscreen" : "Fullscreen"}
              >
                <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  {zoomed ? (
                    <path strokeLinecap="round" strokeLinejoin="round" d="M9 9V4.5M9 9H4.5M9 9L3.75 3.75M9 15v4.5M9 15H4.5M9 15l-5.25 5.25M15 9h4.5M15 9V4.5M15 9l5.25-5.25M15 15h4.5M15 15v4.5m0-4.5l5.25 5.25" />
                  ) : (
                    <path strokeLinecap="round" strokeLinejoin="round" d="M3.75 3.75v4.5m0-4.5h4.5m-4.5 0L9 9M3.75 20.25v-4.5m0 4.5h4.5m-4.5 0L9 15M20.25 3.75h-4.5m4.5 0v4.5m0-4.5L15 9m5.25 11.25h-4.5m4.5 0v-4.5m0 4.5L15 15" />
                  )}
                </svg>
              </button>
              {zoomed && (
                <button onClick={() => { setZoomed(false); setShowSource(false); }} className="p-0.5 rounded hover:bg-neutral-100 text-neutral-500 ml-1">
                  <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}><path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" /></svg>
                </button>
              )}
            </div>
          </div>
          <div className={cn(
            "overflow-auto flex items-start justify-center p-2",
            zoomed ? "flex-1" : "max-h-[300px]"
          )}>
            {pdfError ? (
              <div className="py-8 text-center text-neutral-400">
                <p className="text-xs">PDF not available for this protocol</p>
                <p className="text-[10px] mt-1">Upload the source document to enable preview</p>
              </div>
            ) : (
              <img
                key={`${protocolId}-${pageIndex}`}
                src={getPageImageUrl(protocolId, pageIndex)}
                alt={`Source page ${currentPage}`}
                className={cn("rounded shadow", zoomed ? "max-h-full" : "max-w-full")}
                onError={() => setPdfError(true)}
              />
            )}
          </div>
          {/* Page range hint */}
          {sourcePages.length > 0 && (
            <div className="px-3 py-1 bg-white border-t border-neutral-100 text-[10px] text-neutral-400 shrink-0">
              Table spans pages: {sourcePages.join(", ")}
            </div>
          )}
        </div>
      )}

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {/* Smart review prompt — the main question */}
        <SmartReviewPrompt
          cell={cell}
          reviewItem={reviewItem}
          isFlagged={isFlagged}
          footnotes={footnotes}
          onViewSource={() => { setShowSource(true); setPdfError(false); }}
          sourcePage={currentPage}
        />

        {/* Correction diff */}
        {action === "corrected" && correctedValue && (
          <div className="px-3 py-2 bg-sky-50 rounded-lg border border-sky-200 text-xs">
            <div className="text-[10px] font-semibold text-sky-700 uppercase tracking-wide mb-1">Correction Applied</div>
            <div className="flex items-center gap-2">
              <span className="line-through text-red-500 font-mono">{cell.raw_value || "(empty)"}</span>
              <span className="text-neutral-400">&rarr;</span>
              <span className="font-mono font-semibold text-sky-700">{correctedValue}</span>
            </div>
          </div>
        )}

        {/* Verification Chain — trust evidence from API */}
        <CellTrustEvidence protocolId={protocolId} row={cell.row} col={cell.col} />

        {/* Expandable technical details */}
        <ExpandableSection title="Cell Details" defaultOpen={false}>
          <div className="space-y-2 text-xs">
            <div className="flex justify-between">
              <span className="text-neutral-500">Extracted value</span>
              <span className="font-mono text-neutral-800">{cell.raw_value || "(empty)"}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-neutral-500">Data type</span>
              <Badge variant="neutral">{cell.data_type}</Badge>
            </div>
            <div className="flex justify-between">
              <span className="text-neutral-500">Confidence</span>
              <span className={cn("font-medium px-1.5 py-0.5 rounded text-[10px]", confColor(cell.confidence))}>{(cell.confidence * 100).toFixed(0)}%</span>
            </div>
            <div className="flex justify-between">
              <span className="text-neutral-500">Position</span>
              <span className="text-neutral-700">Row {cell.row}, Col {cell.col}</span>
            </div>
          </div>
        </ExpandableSection>

        {/* Footnotes */}
        {footnotes.length > 0 && (
          <ExpandableSection title={`Footnotes (${footnotes.length})`} defaultOpen={footnotes.some(f => f.footnote_type === "CONDITIONAL")}>
            <div className="space-y-2">
              {footnotes.map((fn, i) => (
                <div key={i} className={cn("p-2.5 rounded-lg border text-xs", fn.footnote_type === "CONDITIONAL" ? "bg-amber-50 border-amber-200" : "bg-neutral-50 border-neutral-200")}>
                  <div className="flex items-center gap-2 mb-1">
                    <sup className="text-brand-primary font-bold">{fn.marker}</sup>
                    <Badge variant={fn.footnote_type === "CONDITIONAL" ? "warning" : fn.footnote_type === "EXCEPTION" ? "danger" : "neutral"}>
                      {fn.footnote_type}
                    </Badge>
                  </div>
                  <p className="text-neutral-700 leading-relaxed">{fn.text}</p>
                </div>
              ))}
            </div>
          </ExpandableSection>
        )}

        {/* Technical review details */}
        {reviewItem && (
          <ExpandableSection title="Pipeline Details" defaultOpen={false}>
            <div className="p-2.5 bg-neutral-50 rounded-lg border border-neutral-100 text-xs space-y-1.5">
              <div className="flex justify-between">
                <span className="text-neutral-500">Review type</span>
                <Badge variant="neutral">{reviewItem.review_type}</Badge>
              </div>
              <p className="text-neutral-600">{reviewItem.reason}</p>
              {reviewItem.extracted_value && (
                <div className="flex justify-between">
                  <span className="text-neutral-500">Extracted</span>
                  <span className="font-mono text-neutral-700">{reviewItem.extracted_value}</span>
                </div>
              )}
              {reviewItem.source_page > 0 && (
                <button onClick={() => { setShowSource(true); setPdfError(false); }} className="text-brand-primary text-[10px] hover:underline">
                  View source page {reviewItem.source_page}
                </button>
              )}
            </div>
          </ExpandableSection>
        )}
      </div>

      {/* Actions */}
      <div className="px-4 py-3 border-t border-neutral-100 bg-neutral-50/50 shrink-0">
        {editMode ? (
          <div className="space-y-2">
            <label className="text-[11px] font-medium text-neutral-600">Correct value:</label>
            <input
              type="text"
              value={editValue}
              onChange={(e) => setEditValue(e.target.value)}
              className="w-full px-3 py-1.5 text-sm border border-neutral-200 rounded-lg font-mono focus:outline-none focus:ring-2 focus:ring-brand-primary/30"
              autoFocus
            />
            <div className="flex items-center gap-2">
              <button
                onClick={() => { onAction("corrected", editValue); setEditMode(false); }}
                className="flex-1 px-3 py-1.5 text-xs font-medium rounded-lg bg-brand-primary text-white hover:bg-brand-french transition-colors"
              >
                Save Correction
              </button>
              <button
                onClick={() => setEditMode(false)}
                className="px-3 py-1.5 text-xs text-neutral-500 hover:text-neutral-700"
              >
                Cancel
              </button>
            </div>
          </div>
        ) : action ? (
          <div className="flex items-center gap-2 text-sm">
            <span className={cn("px-3 py-1.5 rounded-lg font-medium",
              action === "accepted" ? "bg-emerald-100 text-emerald-700" :
              action === "flagged" ? "bg-red-100 text-red-700" :
              "bg-sky-100 text-sky-700"
            )}>
              {action === "accepted" ? "Accepted" : action === "flagged" ? "Flagged" : "Corrected"}
            </span>
            {action === "corrected" && correctedValue && (
              <span className="text-xs text-neutral-500 font-mono truncate">{correctedValue}</span>
            )}
            <button onClick={() => { onAction(""); setEditMode(false); }} className="text-xs text-neutral-400 hover:text-neutral-600 underline ml-auto">Undo</button>
          </div>
        ) : (
          <div className="flex items-center gap-2">
            <button onClick={() => onAction("accepted")} className="flex-1 px-3 py-2 text-xs font-medium rounded-lg bg-emerald-600 text-white hover:bg-emerald-700 transition-colors">
              Accept
            </button>
            <button onClick={() => { setEditValue(cell?.raw_value || ""); setEditMode(true); }} className="flex-1 px-3 py-2 text-xs font-medium rounded-lg border border-neutral-200 text-neutral-700 hover:bg-neutral-50 transition-colors">
              Correct
            </button>
            <button onClick={() => onAction("flagged")} className="flex-1 px-3 py-2 text-xs font-medium rounded-lg bg-amber-50 text-amber-700 border border-amber-200 hover:bg-amber-100 transition-colors">
              Flag
            </button>
          </div>
        )}
      </div>
    </div>
  );
}

// ─── Smart Review Prompt ─────────────────────────────────────────────────

function SmartReviewPrompt({
  cell, reviewItem, isFlagged, footnotes, onViewSource, sourcePage,
}: {
  cell: ExtractedCell;
  reviewItem?: ReviewItem;
  isFlagged: boolean;
  footnotes: ResolvedFootnote[];
  onViewSource: () => void;
  sourcePage: number;
}) {
  const conf = Math.round(cell.confidence * 100);
  const hasDisagreement = reviewItem?.reason?.includes("Pass disagreement");
  const conditionalFn = footnotes.find((f) => f.footnote_type === "CONDITIONAL");

  let passValue1 = "";
  let passValue2 = "";
  if (hasDisagreement && reviewItem) {
    const m = reviewItem.reason.match(/'([^']*)'\s*vs\s*'([^']*)'/);
    if (m) { passValue1 = m[1]; passValue2 = m[2]; }
  }

  let question = "";
  let context = "";
  let severity: "high" | "medium" | "low" = "low";

  if (hasDisagreement && passValue1 && passValue2) {
    question = `Is the correct value "${passValue1}" or "${passValue2}"?`;
    context = `Two extraction passes disagreed. Please check the source to confirm.`;
    severity = "high";
  } else if (conf < 50) {
    question = `We're unsure about this value. Is "${cell.raw_value || "(empty)"}" correct?`;
    context = `Very low confidence (${conf}%). The extraction may have misread this cell.`;
    severity = "high";
  } else if (conf < 70) {
    question = `Please verify: is "${cell.raw_value}" correct for ${cell.row_header} at ${cell.col_header}?`;
    context = `Low confidence (${conf}%). Verification recommended.`;
    severity = "high";
  } else if (conf < 85) {
    question = `Does ${cell.row_header} have "${cell.raw_value}" at ${cell.col_header}?`;
    context = `Moderate confidence (${conf}%). Quick check recommended.`;
    severity = "medium";
  } else if (conditionalFn) {
    question = `"${cell.raw_value}" is conditional — does footnote ${conditionalFn.marker} apply here?`;
    context = `${conditionalFn.text.slice(0, 120)}${conditionalFn.text.length > 120 ? "..." : ""}`;
    severity = "medium";
  } else if (cell.data_type === "EMPTY" && isFlagged) {
    question = `This cell is empty. Should ${cell.row_header} be performed at ${cell.col_header}?`;
    context = `No value found — may be a missed extraction.`;
    severity = "medium";
  } else if (conf >= 95) {
    question = `"${cell.raw_value}" — high confidence extraction`;
    context = `${conf}% confident. Accept if correct.`;
    severity = "low";
  } else {
    question = `Is "${cell.raw_value}" correct for ${cell.row_header}?`;
    context = `${conf}% confidence.`;
    severity = "low";
  }

  const bg = severity === "high" ? "bg-red-50 border-red-200" : severity === "medium" ? "bg-amber-50 border-amber-200" : "bg-emerald-50 border-emerald-200";
  const ic = severity === "high" ? "text-red-500" : severity === "medium" ? "text-amber-500" : "text-emerald-500";

  return (
    <div className={cn("p-3 rounded-lg border", bg)}>
      <div className="flex gap-2.5">
        <span className={cn("mt-0.5 shrink-0 text-sm", ic)}>
          {severity === "high" ? "\u26A0" : severity === "medium" ? "\u2753" : "\u2713"}
        </span>
        <div className="flex-1 min-w-0">
          <p className="text-sm font-medium text-neutral-800 leading-snug">{question}</p>
          <p className="text-xs text-neutral-500 mt-1">{context}</p>
          {sourcePage > 0 && (
            <button onClick={onViewSource} className="text-[11px] text-brand-primary hover:underline mt-1.5">
              Check source document (page {sourcePage})
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

function ExpandableSection({ title, defaultOpen, children }: { title: string; defaultOpen: boolean; children: React.ReactNode }) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <div>
      <button onClick={() => setOpen(!open)} className="flex items-center gap-1.5 text-[11px] font-semibold text-neutral-500 uppercase tracking-wide hover:text-neutral-700 w-full">
        <svg className={cn("w-3 h-3 transition-transform", open && "rotate-90")} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M8.25 4.5l7.5 7.5-7.5 7.5" />
        </svg>
        {title}
      </button>
      {open && <div className="mt-2">{children}</div>}
    </div>
  );
}

// ─── Cell Trust Evidence (fetches from /api/.../evidence) ─────────────────

const API_URL = process.env.NEXT_PUBLIC_API_URL || "";

interface VerificationStepData {
  method: string;
  status: string;
  detail: string;
  value: string;
  confidence: number;
}

function CellTrustEvidence({ protocolId, row, col }: { protocolId: string; row: number; col: number }) {
  const [steps, setSteps] = useState<VerificationStepData[]>([]);
  const [loading, setLoading] = useState(true);
  const [pass1, setPass1] = useState("");
  const [pass2, setPass2] = useState<string | null>(null);
  const [resolution, setResolution] = useState("");

  useEffect(() => {
    setLoading(true);
    fetch(`${API_URL}/api/protocols/${protocolId}/cells/${row}/${col}/evidence`)
      .then((r) => (r.ok ? r.json() : null))
      .then((data) => {
        if (data?.evidence) {
          setSteps(data.verification_steps || []);
          setPass1(data.evidence.pass1_value || "");
          setPass2(data.evidence.pass2_value ?? null);
          setResolution(data.evidence.resolution_method || "");
        } else {
          setSteps([]);
        }
      })
      .catch(() => setSteps([]))
      .finally(() => setLoading(false));
  }, [protocolId, row, col]);

  if (loading) return <div className="text-[10px] text-neutral-400 py-2">Loading evidence...</div>;
  if (steps.length === 0) return null;

  return (
    <ExpandableSection title="Verification Chain" defaultOpen={true}>
      <div className="space-y-1">
        {steps.map((step, i) => (
          <div key={i} className={cn(
            "flex items-start gap-2 px-2.5 py-1.5 rounded-lg text-xs",
            step.status === "FAIL" && "bg-red-50/60",
            step.status === "PASS" && "bg-emerald-50/40",
          )}>
            <span className="mt-0.5 shrink-0">
              {step.status === "PASS" && <span className="block w-3.5 h-3.5 rounded-full bg-emerald-500/20 border border-emerald-500 text-emerald-600 text-[8px] flex items-center justify-center font-bold">&#10003;</span>}
              {step.status === "FAIL" && <span className="block w-3.5 h-3.5 rounded-full bg-red-500/20 border border-red-500 text-red-600 text-[8px] flex items-center justify-center font-bold">&#10007;</span>}
              {step.status === "SKIPPED" && <span className="block w-3.5 h-3.5 rounded-full bg-neutral-300/30 border border-neutral-400 text-[8px] flex items-center justify-center text-neutral-400">&ndash;</span>}
            </span>
            <div className="min-w-0">
              <div className={cn(
                "text-[11px] font-medium",
                step.status === "PASS" ? "text-emerald-700" : step.status === "FAIL" ? "text-red-700" : "text-neutral-400"
              )}>
                {step.method.replace(/_/g, " ")}
              </div>
              <div className="text-[10px] text-neutral-500 leading-snug">{step.detail}</div>
            </div>
          </div>
        ))}
        {resolution && (
          <div className="text-[10px] text-neutral-400 px-2.5 pt-1">
            Resolution: <span className="font-medium text-neutral-600">{resolution.replace(/_/g, " ")}</span>
          </div>
        )}
      </div>
    </ExpandableSection>
  );
}
