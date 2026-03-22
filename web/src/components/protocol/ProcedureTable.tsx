"use client";

import type { NormalizedProcedure } from "@/lib/api";
import { cn, costTierLabel, costTierColor } from "@/lib/utils";
import { Badge } from "@/components/ui/Badge";

interface ProcedureTableProps {
  procedures: NormalizedProcedure[];
}

export function ProcedureTable({ procedures }: ProcedureTableProps) {
  if (procedures.length === 0) {
    return (
      <div className="text-center py-12 text-sm text-neutral-400">
        <svg className="w-8 h-8 mx-auto mb-2 text-neutral-300" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M3.75 12h16.5m-16.5 3.75h16.5M3.75 19.5h16.5M5.625 4.5h12.75a1.875 1.875 0 010 3.75H5.625a1.875 1.875 0 010-3.75z" />
        </svg>
        No procedures found
      </div>
    );
  }

  // Sort by category
  const sorted = [...procedures].sort((a, b) => a.category.localeCompare(b.category));

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-xs">
        <thead>
          <tr className="bg-neutral-50">
            <th className="px-4 py-2.5 text-left font-medium text-neutral-500 border-b border-neutral-200 sticky top-0 bg-neutral-50">
              Raw Name
            </th>
            <th className="px-4 py-2.5 text-left font-medium text-neutral-500 border-b border-neutral-200 sticky top-0 bg-neutral-50">
              Canonical Name
            </th>
            <th className="px-4 py-2.5 text-left font-medium text-neutral-500 border-b border-neutral-200 sticky top-0 bg-neutral-50">
              CPT Code
            </th>
            <th className="px-4 py-2.5 text-left font-medium text-neutral-500 border-b border-neutral-200 sticky top-0 bg-neutral-50">
              Category
            </th>
            <th className="px-4 py-2.5 text-center font-medium text-neutral-500 border-b border-neutral-200 sticky top-0 bg-neutral-50">
              Cost Tier
            </th>
          </tr>
        </thead>
        <tbody>
          {sorted.map((p, i) => (
            <tr
              key={i}
              className={cn(
                "hover:bg-neutral-50/50 transition-colors",
                i % 2 === 1 && "bg-neutral-50/30"
              )}
            >
              <td className="px-4 py-2.5 text-neutral-600 border-b border-neutral-100">
                {p.raw_name}
              </td>
              <td className="px-4 py-2.5 text-neutral-800 font-medium border-b border-neutral-100">
                {p.canonical_name}
              </td>
              <td className="px-4 py-2.5 text-neutral-500 font-mono border-b border-neutral-100">
                {p.code ? `${p.code} (${p.code_system})` : "—"}
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
  );
}
