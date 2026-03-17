"use client";

import { useState } from "react";
import type { ExtractedTable, ExtractedCell, CellRef } from "@/lib/api";
import { cn, confidenceBg, confidenceColor, costTierLabel, costTierColor } from "@/lib/utils";
import { Badge } from "@/components/ui/Badge";
import { Card, CardHeader, CardBody } from "@/components/ui/Card";

interface TableViewProps {
  table: ExtractedTable;
}

export function TableView({ table }: TableViewProps) {
  const [activeTab, setActiveTab] = useState<"grid" | "footnotes" | "procedures" | "review">("grid");
  const { schema_info: schema, cells, footnotes, procedures, review_items, visit_windows } = table;

  // Build cell grid
  const cellMap = new Map<string, ExtractedCell>();
  cells.forEach((c) => cellMap.set(`${c.row}-${c.col}`, c));

  // Check if a cell is flagged
  const flaggedSet = new Set(table.flagged_cells.map((f) => `${f.row}-${f.col}`));

  // Get unique row headers for the first column
  const rowHeaders = new Map<number, string>();
  cells.forEach((c) => {
    if (c.row_header && !rowHeaders.has(c.row)) {
      rowHeaders.set(c.row, c.row_header);
    }
  });

  // Get column headers
  const colHeaders = schema.column_headers.length > 0
    ? schema.column_headers.map((h) => h.text)
    : Array.from(new Set(cells.map((c) => c.col_header))).filter(Boolean);

  const maxRow = cells.length > 0 ? Math.max(...cells.map((c) => c.row)) : 0;
  const maxCol = cells.length > 0 ? Math.max(...cells.map((c) => c.col)) : 0;

  const tabs = [
    { key: "grid", label: "Table Grid", count: cells.length },
    { key: "footnotes", label: "Footnotes", count: footnotes.length },
    { key: "procedures", label: "Procedures", count: procedures.length },
    { key: "review", label: "Review Queue", count: review_items.length },
  ] as const;

  return (
    <Card>
      <CardHeader className="space-y-3">
        {/* Title row */}
        <div className="flex items-center justify-between">
          <div>
            <h3 className="text-sm font-semibold text-neutral-800">
              {table.title || `Table ${table.table_id}`}
            </h3>
            <p className="text-xs text-neutral-400 mt-0.5">
              Pages {table.source_pages.join(", ")} &middot;{" "}
              {schema.num_rows} rows &times; {schema.num_cols} cols
            </p>
          </div>
          <div className="flex items-center gap-2">
            <Badge variant={table.table_type === "SOA" ? "brand" : "neutral"}>
              {table.table_type}
            </Badge>
            <div className={cn("text-sm font-medium", confidenceColor(table.overall_confidence))}>
              {(table.overall_confidence * 100).toFixed(0)}% confidence
            </div>
          </div>
        </div>

        {/* Tabs */}
        <div className="flex gap-1 border-b border-neutral-100 -mb-4">
          {tabs.map((tab) => (
            <button
              key={tab.key}
              onClick={() => setActiveTab(tab.key)}
              className={cn(
                "px-3 py-2 text-xs font-medium border-b-2 transition-colors -mb-px",
                activeTab === tab.key
                  ? "border-brand-primary text-brand-primary"
                  : "border-transparent text-neutral-400 hover:text-neutral-600"
              )}
            >
              {tab.label}
              {tab.count > 0 && (
                <span className="ml-1.5 text-[10px] bg-neutral-100 text-neutral-500 rounded-full px-1.5 py-0.5">
                  {tab.count}
                </span>
              )}
            </button>
          ))}
        </div>
      </CardHeader>

      <CardBody className="p-0">
        {activeTab === "grid" && (
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="bg-neutral-50">
                  <th className="px-3 py-2.5 text-left font-medium text-neutral-500 border-b border-neutral-200 sticky left-0 bg-neutral-50 z-10">
                    Procedure
                  </th>
                  {colHeaders.map((h, i) => (
                    <th
                      key={i}
                      className="px-3 py-2.5 text-center font-medium text-neutral-500 border-b border-neutral-200 whitespace-nowrap"
                    >
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {Array.from({ length: maxRow + 1 }, (_, row) => (
                  <tr key={row} className="hover:bg-neutral-50/50 transition-colors">
                    <td className="px-3 py-2 text-neutral-700 font-medium border-b border-neutral-100 sticky left-0 bg-white z-10 whitespace-nowrap">
                      {rowHeaders.get(row) || ""}
                    </td>
                    {Array.from({ length: maxCol + 1 }, (_, col) => {
                      if (col === 0 && rowHeaders.has(row)) return null; // skip if row header
                      const cell = cellMap.get(`${row}-${col}`);
                      const isFlagged = flaggedSet.has(`${row}-${col}`);
                      if (!cell) return (
                        <td key={col} className="px-3 py-2 text-center border-b border-neutral-100 text-neutral-300">
                          -
                        </td>
                      );
                      return (
                        <td
                          key={col}
                          className={cn(
                            "px-3 py-2 text-center border-b border-neutral-100 relative",
                            isFlagged && "ring-2 ring-inset ring-amber-300",
                            confidenceBg(cell.confidence)
                          )}
                          title={`Confidence: ${(cell.confidence * 100).toFixed(0)}%${cell.resolved_footnotes.length > 0 ? "\n" + cell.resolved_footnotes.join("\n") : ""}`}
                        >
                          <span className={cn(
                            cell.data_type === "MARKER" && cell.raw_value ? "font-bold" : "",
                            cell.data_type === "EMPTY" ? "text-neutral-300" : "text-neutral-800"
                          )}>
                            {cell.raw_value || (cell.data_type === "EMPTY" ? "" : "-")}
                          </span>
                          {cell.footnote_markers.length > 0 && (
                            <sup className="text-brand-primary ml-0.5 text-[9px]">
                              {cell.footnote_markers.join(",")}
                            </sup>
                          )}
                        </td>
                      );
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {activeTab === "footnotes" && (
          <div className="p-5 space-y-3">
            {footnotes.length === 0 ? (
              <p className="text-sm text-neutral-400 text-center py-8">No footnotes found</p>
            ) : (
              footnotes.map((fn, i) => (
                <div key={i} className="flex gap-3 items-start">
                  <span className="text-sm font-bold text-brand-primary w-6 text-right shrink-0">
                    {fn.marker}
                  </span>
                  <div>
                    <p className="text-sm text-neutral-700">{fn.text}</p>
                    <div className="flex items-center gap-2 mt-1">
                      <Badge variant={
                        fn.footnote_type === "CONDITIONAL" ? "warning"
                          : fn.footnote_type === "EXCEPTION" ? "danger"
                            : fn.footnote_type === "REFERENCE" ? "info"
                              : "neutral"
                      }>
                        {fn.footnote_type}
                      </Badge>
                      <span className="text-xs text-neutral-400">
                        Applies to {fn.applies_to.length} cell{fn.applies_to.length !== 1 ? "s" : ""}
                      </span>
                    </div>
                  </div>
                </div>
              ))
            )}
          </div>
        )}

        {activeTab === "procedures" && (
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="bg-neutral-50">
                  <th className="px-4 py-2.5 text-left font-medium text-neutral-500 border-b">Raw Name</th>
                  <th className="px-4 py-2.5 text-left font-medium text-neutral-500 border-b">Canonical</th>
                  <th className="px-4 py-2.5 text-left font-medium text-neutral-500 border-b">Code</th>
                  <th className="px-4 py-2.5 text-left font-medium text-neutral-500 border-b">Category</th>
                  <th className="px-4 py-2.5 text-center font-medium text-neutral-500 border-b">Cost</th>
                </tr>
              </thead>
              <tbody>
                {procedures.map((p, i) => (
                  <tr key={i} className="hover:bg-neutral-50/50">
                    <td className="px-4 py-2.5 text-neutral-700 border-b border-neutral-100">{p.raw_name}</td>
                    <td className="px-4 py-2.5 text-neutral-800 font-medium border-b border-neutral-100">{p.canonical_name}</td>
                    <td className="px-4 py-2.5 text-neutral-500 font-mono border-b border-neutral-100">
                      {p.code ? `${p.code} (${p.code_system})` : "-"}
                    </td>
                    <td className="px-4 py-2.5 border-b border-neutral-100">
                      <Badge variant="neutral">{p.category}</Badge>
                    </td>
                    <td className="px-4 py-2.5 text-center border-b border-neutral-100">
                      <span className={cn("px-2 py-0.5 rounded text-xs font-medium", costTierColor(p.estimated_cost_tier))}>
                        {costTierLabel(p.estimated_cost_tier)}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {activeTab === "review" && (
          <div className="p-5 space-y-3">
            {review_items.length === 0 ? (
              <div className="text-center py-8">
                <div className="w-12 h-12 rounded-full bg-emerald-50 flex items-center justify-center mx-auto mb-3">
                  <svg className="w-6 h-6 text-emerald-500" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M4.5 12.75l6 6 9-13.5" />
                  </svg>
                </div>
                <p className="text-sm font-medium text-neutral-700">All clear</p>
                <p className="text-xs text-neutral-400">No cells require human review</p>
              </div>
            ) : (
              review_items.map((item, i) => (
                <div key={i} className="flex gap-3 items-start p-3 rounded-lg bg-amber-50 border border-amber-200">
                  <div className="w-8 h-8 rounded-lg bg-amber-100 flex items-center justify-center shrink-0">
                    <svg className="w-4 h-4 text-amber-600" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126z" />
                    </svg>
                  </div>
                  <div className="flex-1">
                    <div className="flex items-center gap-2 mb-1">
                      <span className="text-xs font-medium text-amber-800">
                        Row {item.cell_ref.row}, Col {item.cell_ref.col}
                      </span>
                      <Badge variant="warning">{item.review_type.replace(/_/g, " ")}</Badge>
                      <span className={cn("px-1.5 py-0.5 rounded text-[10px] font-medium", costTierColor(item.cost_tier))}>
                        {costTierLabel(item.cost_tier)}
                      </span>
                    </div>
                    <p className="text-xs text-neutral-600">{item.reason}</p>
                    {item.extracted_value && (
                      <p className="text-xs text-neutral-500 mt-1">
                        Extracted: <code className="bg-white px-1 py-0.5 rounded font-mono">{item.extracted_value}</code>
                      </p>
                    )}
                  </div>
                </div>
              ))
            )}
          </div>
        )}
      </CardBody>
    </Card>
  );
}
