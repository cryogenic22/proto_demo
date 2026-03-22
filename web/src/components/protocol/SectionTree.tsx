"use client";

import { useState } from "react";
import type { SectionNode } from "@/lib/api";
import { cn } from "@/lib/utils";

interface SectionTreeProps {
  sections: SectionNode[];
  selectedNumber: string;
  onSelect: (number: string) => void;
}

export function SectionTree({ sections, selectedNumber, onSelect }: SectionTreeProps) {
  return (
    <div className="text-sm">
      {sections.map((section) => (
        <SectionTreeItem
          key={section.number}
          section={section}
          selectedNumber={selectedNumber}
          onSelect={onSelect}
          depth={0}
        />
      ))}
    </div>
  );
}

interface SectionTreeItemProps {
  section: SectionNode;
  selectedNumber: string;
  onSelect: (number: string) => void;
  depth: number;
}

function confidenceBadge(score: number | null) {
  if (score === null || score === undefined) return null;
  const pct = (score * 100).toFixed(0);
  const color =
    score >= 0.95 ? "bg-emerald-100 text-emerald-700" :
    score >= 0.85 ? "bg-sky-100 text-sky-700" :
    score >= 0.70 ? "bg-amber-100 text-amber-700" :
    "bg-red-100 text-red-700";
  return (
    <span className={cn("text-[9px] font-medium px-1 py-0.5 rounded-full shrink-0", color)}>
      {pct}%
    </span>
  );
}

function SectionTreeItem({ section, selectedNumber, onSelect, depth }: SectionTreeItemProps) {
  // All levels expanded by default — full hierarchy visible
  const [expanded, setExpanded] = useState(true);
  const hasChildren = section.children && section.children.length > 0;
  const isSelected = section.number === selectedNumber;

  return (
    <div>
      <button
        onClick={() => {
          onSelect(section.number);
          if (hasChildren) setExpanded(!expanded);
        }}
        className={cn(
          "w-full flex items-center gap-1.5 py-1.5 px-2 text-left transition-colors hover:bg-neutral-50",
          isSelected && "bg-brand-primary-light border-r-2 border-brand-primary"
        )}
        style={{ paddingLeft: `${8 + depth * 14}px` }}
      >
        {hasChildren ? (
          <svg
            className={cn(
              "w-3 h-3 text-neutral-400 shrink-0 transition-transform",
              expanded && "rotate-90"
            )}
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
            strokeWidth={2}
          >
            <path strokeLinecap="round" strokeLinejoin="round" d="M8.25 4.5l7.5 7.5-7.5 7.5" />
          </svg>
        ) : (
          <span className="w-3 shrink-0" />
        )}

        <span className={cn(
          "font-mono text-[10px] shrink-0",
          isSelected ? "text-brand-primary font-semibold" : "text-neutral-400"
        )}>
          {section.number}
        </span>

        <span className={cn(
          "truncate text-[11px] leading-tight",
          isSelected ? "text-brand-primary font-medium" : "text-neutral-700"
        )}>
          {section.title}
        </span>

        <div className="ml-auto flex items-center gap-1 shrink-0">
          {confidenceBadge(section.quality_score)}
          <span className="text-[9px] text-neutral-400 font-mono">
            {section.page}
          </span>
        </div>
      </button>

      {hasChildren && expanded && (
        <div>
          {section.children.map((child) => (
            <SectionTreeItem
              key={child.number || child.title}
              section={child}
              selectedNumber={selectedNumber}
              onSelect={onSelect}
              depth={depth + 1}
            />
          ))}
        </div>
      )}
    </div>
  );
}
