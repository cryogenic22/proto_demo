"use client";

import { cn } from "@/lib/utils";

// ─── Types ──────────────────────────────────────────────────────────────────

export type ReviewFilterType = "all" | "flagged" | "low_confidence" | "verified";

export interface ReviewFilterProps {
  totalCells: number;
  verifiedCells: number;
  flaggedCells: number;
  lowConfidenceCells: number;
  activeFilter: ReviewFilterType;
  onFilterChange: (filter: ReviewFilterType) => void;
}

// ─── Filter chips config ────────────────────────────────────────────────────

const FILTER_CHIPS: {
  key: ReviewFilterType;
  label: (props: ReviewFilterProps) => string;
  countKey?: keyof Pick<ReviewFilterProps, "totalCells" | "flaggedCells" | "lowConfidenceCells" | "verifiedCells">;
}[] = [
  { key: "all", label: () => "All cells" },
  { key: "flagged", label: (p) => `Needs review (${p.flaggedCells})`, countKey: "flaggedCells" },
  { key: "low_confidence", label: () => "Low confidence", countKey: "lowConfidenceCells" },
  { key: "verified", label: () => "Verified only", countKey: "verifiedCells" },
];

// ─── Component ──────────────────────────────────────────────────────────────

export function ReviewFilter({
  totalCells,
  verifiedCells,
  flaggedCells,
  lowConfidenceCells,
  activeFilter,
  onFilterChange,
}: ReviewFilterProps) {
  const needsReview = totalCells - verifiedCells;
  const verifiedPercent = totalCells > 0 ? (verifiedCells / totalCells) * 100 : 0;

  return (
    <div className="px-4 py-2.5 border-b border-neutral-200 bg-white flex items-center gap-4">
      {/* Filter chips */}
      <div className="flex items-center gap-1.5">
        {FILTER_CHIPS.map((chip) => {
          const isActive = activeFilter === chip.key;
          const count = chip.countKey ? { flaggedCells, lowConfidenceCells, verifiedCells, totalCells }[chip.countKey] : undefined;
          const hasItems = count === undefined || count > 0;

          return (
            <button
              key={chip.key}
              onClick={() => onFilterChange(chip.key)}
              disabled={!hasItems && chip.key !== "all"}
              className={cn(
                "px-2.5 py-1 text-[11px] font-medium rounded-md transition-all duration-150",
                isActive
                  ? "bg-brand-primary text-white shadow-sm"
                  : hasItems
                    ? "bg-neutral-100 text-neutral-600 hover:bg-neutral-200"
                    : "bg-neutral-50 text-neutral-300 cursor-not-allowed"
              )}
            >
              {chip.label({ totalCells, verifiedCells, flaggedCells, lowConfidenceCells, activeFilter, onFilterChange })}
            </button>
          );
        })}
      </div>

      {/* Divider */}
      <div className="w-px h-5 bg-neutral-200" />

      {/* Summary text */}
      <span className="text-[11px] text-neutral-500">
        <span className="font-semibold text-neutral-700">{verifiedCells.toLocaleString()}</span>
        {" of "}
        <span className="font-semibold text-neutral-700">{totalCells.toLocaleString()}</span>
        {" cells fully verified"}
        {needsReview > 0 && (
          <>
            {" — "}
            <span className="font-semibold text-warning">{needsReview}</span>
            {" need review"}
          </>
        )}
      </span>

      {/* Progress bar */}
      <div className="ml-auto flex items-center gap-2 min-w-[140px]">
        <div className="flex-1 h-1.5 bg-neutral-100 rounded-full overflow-hidden flex">
          <div
            className="h-full bg-success rounded-full transition-all duration-500"
            style={{ width: `${verifiedPercent}%` }}
          />
          {needsReview > 0 && (
            <div
              className="h-full bg-warning rounded-full transition-all duration-500"
              style={{ width: `${((flaggedCells / totalCells) * 100)}%` }}
            />
          )}
        </div>
        <span className="text-[10px] font-mono text-neutral-400 tabular-nums">
          {verifiedPercent.toFixed(0)}%
        </span>
      </div>
    </div>
  );
}
