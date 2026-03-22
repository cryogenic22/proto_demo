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

function SectionTreeItem({ section, selectedNumber, onSelect, depth }: SectionTreeItemProps) {
  const [expanded, setExpanded] = useState(depth < 1);
  const hasChildren = section.children && section.children.length > 0;
  const isSelected = section.number === selectedNumber;

  function qualityDot(score: number | null) {
    if (score === null) return null;
    let color = "bg-emerald-500";
    if (score < 0.7) color = "bg-red-500";
    else if (score < 0.85) color = "bg-amber-500";
    return <span className={cn("w-1.5 h-1.5 rounded-full shrink-0", color)} />;
  }

  return (
    <div>
      <button
        onClick={() => {
          onSelect(section.number);
          if (hasChildren) setExpanded(!expanded);
        }}
        className={cn(
          "w-full flex items-center gap-2 py-1.5 px-3 text-left transition-colors group hover:bg-neutral-100",
          isSelected && "bg-brand-primary-light"
        )}
        style={{ paddingLeft: `${12 + depth * 16}px` }}
      >
        {/* Expand/collapse indicator */}
        {hasChildren ? (
          <svg
            className={cn(
              "w-3.5 h-3.5 text-neutral-400 shrink-0 transition-transform",
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
          <span className="w-3.5 shrink-0" />
        )}

        {/* Section number */}
        <span className={cn(
          "font-mono text-[11px] shrink-0",
          isSelected ? "text-brand-primary font-medium" : "text-neutral-400"
        )}>
          {section.number}
        </span>

        {/* Section title */}
        <span className={cn(
          "truncate text-xs",
          isSelected ? "text-brand-primary font-medium" : "text-neutral-700 group-hover:text-neutral-900"
        )}>
          {section.title}
        </span>

        {/* Quality dot */}
        {qualityDot(section.quality_score)}

        {/* Page number */}
        <span className="ml-auto text-[10px] text-neutral-400 shrink-0 font-mono">
          p.{section.page}
        </span>
      </button>

      {/* Children */}
      {hasChildren && expanded && (
        <div>
          {section.children.map((child) => (
            <SectionTreeItem
              key={child.number}
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
