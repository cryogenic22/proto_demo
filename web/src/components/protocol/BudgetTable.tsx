"use client";

import type { BudgetLine } from "@/lib/api";
import { cn, costTierColor, costTierLabel, formatCurrency } from "@/lib/utils";

interface BudgetTableProps {
  lines: BudgetLine[];
}

function confidenceDot(confidence: number) {
  let color = "bg-emerald-500";
  if (confidence < 0.7) color = "bg-red-500";
  else if (confidence < 0.85) color = "bg-amber-500";
  return <span className={cn("inline-block w-2 h-2 rounded-full", color)} title={`${(confidence * 100).toFixed(0)}%`} />;
}

export function BudgetTable({ lines }: BudgetTableProps) {
  if (lines.length === 0) {
    return (
      <div className="text-center py-12 text-sm text-neutral-400">
        <svg className="w-8 h-8 mx-auto mb-2 text-neutral-300" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M2.25 18.75a60.07 60.07 0 0115.797 2.101c.727.198 1.453-.342 1.453-1.096V18.75M3.75 4.5v.75A.75.75 0 013 6h-.75m0 0v-.375c0-.621.504-1.125 1.125-1.125H20.25M2.25 6v9m18-10.5v.75c0 .414.336.75.75.75h.75m-1.5-1.5h.375c.621 0 1.125.504 1.125 1.125v9.75c0 .621-.504 1.125-1.125 1.125h-.375m1.5-1.5H21a.75.75 0 00-.75.75v.75m0 0H3.75m0 0h-.375a1.125 1.125 0 01-1.125-1.125V15m1.5 1.5v-.75A.75.75 0 003 15h-.75M15 10.5a3 3 0 11-6 0 3 3 0 016 0zm3 0h.008v.008H18V10.5zm-12 0h.008v.008H6V10.5z" />
        </svg>
        No budget data available
      </div>
    );
  }

  // Group by category
  const grouped = lines.reduce<Record<string, BudgetLine[]>>((acc, line) => {
    const cat = line.category || "Uncategorized";
    if (!acc[cat]) acc[cat] = [];
    acc[cat].push(line);
    return acc;
  }, {});

  const categories = Object.keys(grouped).sort();
  const grandTotal = lines.reduce((sum, l) => sum + l.estimated_unit_cost * l.total_occurrences, 0);

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-xs">
        <thead>
          <tr className="bg-neutral-50">
            <th className="px-4 py-2.5 text-left font-medium text-neutral-500 border-b border-neutral-200 sticky top-0 bg-neutral-50">
              Procedure
            </th>
            <th className="px-4 py-2.5 text-left font-medium text-neutral-500 border-b border-neutral-200 sticky top-0 bg-neutral-50">
              Canonical Name
            </th>
            <th className="px-4 py-2.5 text-left font-medium text-neutral-500 border-b border-neutral-200 sticky top-0 bg-neutral-50">
              CPT Code
            </th>
            <th className="px-4 py-2.5 text-center font-medium text-neutral-500 border-b border-neutral-200 sticky top-0 bg-neutral-50">
              Cost Tier
            </th>
            <th className="px-4 py-2.5 text-center font-medium text-neutral-500 border-b border-neutral-200 sticky top-0 bg-neutral-50">
              Visits
            </th>
            <th className="px-4 py-2.5 text-center font-medium text-neutral-500 border-b border-neutral-200 sticky top-0 bg-neutral-50">
              Occ.
            </th>
            <th className="px-4 py-2.5 text-right font-medium text-neutral-500 border-b border-neutral-200 sticky top-0 bg-neutral-50">
              Unit Cost
            </th>
            <th className="px-4 py-2.5 text-right font-medium text-neutral-500 border-b border-neutral-200 sticky top-0 bg-neutral-50">
              Total
            </th>
            <th className="px-4 py-2.5 text-center font-medium text-neutral-500 border-b border-neutral-200 sticky top-0 bg-neutral-50">
              Conf.
            </th>
          </tr>
        </thead>
        <tbody>
          {categories.map((category) => {
            const categoryLines = grouped[category];
            const categoryTotal = categoryLines.reduce(
              (sum, l) => sum + l.estimated_unit_cost * l.total_occurrences,
              0
            );

            return (
              <GroupRows
                key={category}
                category={category}
                lines={categoryLines}
                categoryTotal={categoryTotal}
              />
            );
          })}

          {/* Grand total */}
          <tr className="bg-neutral-800 text-white">
            <td colSpan={7} className="px-4 py-3 font-semibold text-sm">
              Grand Total
            </td>
            <td className="px-4 py-3 text-right font-bold text-sm font-mono">
              {formatCurrency(grandTotal)}
            </td>
            <td />
          </tr>
        </tbody>
      </table>
    </div>
  );
}

function GroupRows({
  category,
  lines,
  categoryTotal,
}: {
  category: string;
  lines: BudgetLine[];
  categoryTotal: number;
}) {
  return (
    <>
      {/* Category header */}
      <tr className="bg-neutral-100">
        <td colSpan={9} className="px-4 py-2 font-semibold text-neutral-700 text-xs uppercase tracking-wide">
          {category}
        </td>
      </tr>

      {/* Rows */}
      {lines.map((line, i) => (
        <tr
          key={`${category}-${i}`}
          className={cn(
            "hover:bg-neutral-50/50 transition-colors",
            i % 2 === 1 && "bg-neutral-50/30"
          )}
        >
          <td className="px-4 py-2.5 text-neutral-600 border-b border-neutral-100">
            {line.procedure}
          </td>
          <td className="px-4 py-2.5 text-neutral-800 font-medium border-b border-neutral-100">
            {line.canonical_name}
          </td>
          <td className="px-4 py-2.5 text-neutral-500 font-mono border-b border-neutral-100">
            {line.cpt_code || "—"}
          </td>
          <td className="px-4 py-2.5 text-center border-b border-neutral-100">
            <span className={cn("px-2 py-0.5 rounded text-xs font-medium", costTierColor(line.cost_tier))}>
              {costTierLabel(line.cost_tier)}
            </span>
          </td>
          <td className="px-4 py-2.5 text-center border-b border-neutral-100 font-mono text-neutral-600">
            {line.visits_required.length}
          </td>
          <td className="px-4 py-2.5 text-center border-b border-neutral-100 font-mono text-neutral-600">
            {line.total_occurrences}
          </td>
          <td className="px-4 py-2.5 text-right border-b border-neutral-100 font-mono text-neutral-700">
            {formatCurrency(line.estimated_unit_cost)}
          </td>
          <td className="px-4 py-2.5 text-right border-b border-neutral-100 font-mono font-medium text-neutral-800">
            {formatCurrency(line.estimated_unit_cost * line.total_occurrences)}
          </td>
          <td className="px-4 py-2.5 text-center border-b border-neutral-100">
            {confidenceDot(line.avg_confidence)}
          </td>
        </tr>
      ))}

      {/* Category subtotal */}
      <tr className="bg-neutral-50 border-b-2 border-neutral-200">
        <td colSpan={7} className="px-4 py-2 text-right text-xs font-medium text-neutral-500">
          Subtotal — {category}
        </td>
        <td className="px-4 py-2 text-right font-mono font-semibold text-neutral-700 text-xs">
          {formatCurrency(categoryTotal)}
        </td>
        <td />
      </tr>
    </>
  );
}
