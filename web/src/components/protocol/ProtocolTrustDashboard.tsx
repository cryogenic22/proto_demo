"use client";

import { useEffect, useState } from "react";
import { cn } from "@/lib/utils";

interface ProtocolTrust {
  overall_score: number;
  total_cells: number;
  high_confidence_cells: number;
  medium_confidence_cells: number;
  low_confidence_cells: number;
  dual_pass_agreement_rate: number;
  ocr_match_rate: number | null;
  challenger_issues_total: number;
  challenger_issues_resolved: number;
  procedures_total: number;
  procedures_mapped: number;
  procedures_with_cpt: number;
  noise_rows_filtered: number;
  conditional_footnotes_resolved: number;
  conditional_footnotes_total: number;
  budget_confidence: string;
  flagged_cells: number;
  reviewed_cells: number;
  estimated_review_minutes: number;
  tables_count: number;
  passes_run: number;
  has_ocr_grounding: boolean;
  has_challenger: boolean;
}

interface Props {
  protocolId: string;
  className?: string;
}

const API = process.env.NEXT_PUBLIC_API_URL || "";

export function ProtocolTrustDashboard({ protocolId, className }: Props) {
  const [trust, setTrust] = useState<ProtocolTrust | null>(null);
  const [loading, setLoading] = useState(true);
  const [showMethodology, setShowMethodology] = useState(false);

  useEffect(() => {
    setLoading(true);
    fetch(`${API}/api/protocols/${protocolId}/trust`)
      .then((r) => (r.ok ? r.json() : null))
      .then(setTrust)
      .catch(() => setTrust(null))
      .finally(() => setLoading(false));
  }, [protocolId]);

  if (loading) {
    return (
      <div className={cn("animate-pulse bg-neutral-50 rounded-xl h-24", className)} />
    );
  }

  if (!trust) return null;

  const pct = (trust.overall_score * 100).toFixed(0);
  const scoreColor =
    trust.overall_score >= 0.90
      ? "text-success"
      : trust.overall_score >= 0.75
        ? "text-brand-primary"
        : "text-warning";

  const barColor =
    trust.overall_score >= 0.90
      ? "bg-success"
      : trust.overall_score >= 0.75
        ? "bg-brand-primary"
        : "bg-warning";

  const mappingPct =
    trust.procedures_total > 0
      ? ((trust.procedures_mapped / trust.procedures_total) * 100).toFixed(0)
      : "0";

  return (
    <div className={cn("bg-white rounded-xl border border-neutral-200 overflow-hidden", className)}>
      {/* Header bar */}
      <div className="px-5 py-4 border-b border-neutral-100 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2">
            <TrustShield score={trust.overall_score} />
            <div>
              <div className="text-[11px] uppercase tracking-wider text-neutral-400 font-medium">
                Protocol Trust Score
              </div>
              <div className={cn("text-2xl font-bold tabular-nums", scoreColor)}>
                {pct}%
              </div>
            </div>
          </div>
          {/* Progress bar */}
          <div className="hidden sm:block w-48 h-2 bg-neutral-100 rounded-full overflow-hidden ml-3">
            <div
              className={cn("h-full rounded-full transition-all duration-700", barColor)}
              style={{ width: `${pct}%` }}
            />
          </div>
        </div>
        {trust.estimated_review_minutes > 0 && (
          <div className="text-right">
            <div className="text-xs text-neutral-400">Est. Review Time</div>
            <div className="text-lg font-semibold text-neutral-700">
              ~{trust.estimated_review_minutes} min
            </div>
          </div>
        )}
      </div>

      {/* Stats grid */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-px bg-neutral-100">
        <StatCard
          label="Extraction Quality"
          items={[
            { label: "Cells extracted", value: trust.total_cells.toLocaleString() },
            {
              label: "Dual-pass agreement",
              value: `${(trust.dual_pass_agreement_rate * 100).toFixed(1)}%`,
              color: trust.dual_pass_agreement_rate >= 0.95 ? "text-success" : "text-warning",
            },
            {
              label: "Challenger issues",
              value: `${trust.challenger_issues_total}`,
              color: trust.challenger_issues_total === 0 ? "text-success" : "text-warning",
            },
          ]}
        />
        <StatCard
          label="Procedure Mapping"
          items={[
            {
              label: "Mapped to library",
              value: `${trust.procedures_mapped}/${trust.procedures_total} (${mappingPct}%)`,
              color: Number(mappingPct) >= 90 ? "text-success" : "text-warning",
            },
            { label: "With CPT codes", value: `${trust.procedures_with_cpt}/${trust.procedures_total}` },
            { label: "Noise rows filtered", value: `${trust.noise_rows_filtered}` },
          ]}
        />
        <StatCard
          label="Budget Readiness"
          items={[
            {
              label: "Confidence",
              value: trust.budget_confidence,
              color:
                trust.budget_confidence === "HIGH"
                  ? "text-success"
                  : trust.budget_confidence === "MEDIUM"
                    ? "text-brand-primary"
                    : "text-warning",
            },
            {
              label: "Footnotes resolved",
              value: `${trust.conditional_footnotes_resolved}/${trust.conditional_footnotes_total}`,
            },
            { label: "Tables", value: `${trust.tables_count}` },
          ]}
        />
        <StatCard
          label="Human Review"
          items={[
            {
              label: "Flagged cells",
              value: `${trust.flagged_cells}`,
              color: trust.flagged_cells === 0 ? "text-success" : "text-warning",
            },
            { label: "Reviewed", value: `${trust.reviewed_cells}` },
            {
              label: "Confidence breakdown",
              value: `${trust.high_confidence_cells}H / ${trust.medium_confidence_cells}M / ${trust.low_confidence_cells}L`,
            },
          ]}
        />
      </div>

      {/* Methodology toggle */}
      <div className="px-5 py-2 border-t border-neutral-100">
        <button
          onClick={() => setShowMethodology(!showMethodology)}
          className="text-[11px] text-brand-primary hover:underline font-medium"
        >
          {showMethodology ? "Hide" : "How we calculated this"}
        </button>
        {showMethodology && <MethodologyPanel trust={trust} />}
      </div>
    </div>
  );
}

// ── Sub-components ───────────────────────────────────────────────────────────

function StatCard({
  label,
  items,
}: {
  label: string;
  items: { label: string; value: string; color?: string }[];
}) {
  return (
    <div className="bg-white px-4 py-3">
      <div className="text-[10px] uppercase tracking-wider text-neutral-400 font-semibold mb-2">
        {label}
      </div>
      <div className="space-y-1.5">
        {items.map((item) => (
          <div key={item.label} className="flex items-baseline justify-between gap-2">
            <span className="text-[11px] text-neutral-500 truncate">{item.label}</span>
            <span className={cn("text-xs font-semibold tabular-nums whitespace-nowrap", item.color || "text-neutral-700")}>
              {item.value}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

function MethodologyPanel({ trust }: { trust: ProtocolTrust }) {
  const steps = [
    {
      num: 1,
      title: "EXTRACTION",
      detail: `Protocol PDF → ${trust.tables_count} SoA table${trust.tables_count !== 1 ? "s" : ""} detected. ${trust.passes_run >= 2 ? `Each table extracted by ${trust.passes_run} independent AI passes. ${(trust.dual_pass_agreement_rate * 100).toFixed(1)}% agreement rate.` : "Single-pass extraction."}`,
    },
    {
      num: 2,
      title: "PROCEDURE MATCHING",
      detail: `${trust.procedures_mapped} of ${trust.procedures_total} procedures matched to our clinical trial vocabulary. ${trust.procedures_with_cpt} mapped to CPT codes. ${trust.noise_rows_filtered} noise rows filtered.`,
    },
    {
      num: 3,
      title: "VISIT COUNTING",
      detail: `Firm visits: X marks in SoA cells. Conditional visits: footnote-qualified (budgeted at 60% probability). ${trust.conditional_footnotes_resolved} of ${trust.conditional_footnotes_total} footnotes resolved.`,
    },
    {
      num: 4,
      title: "CONFIDENCE",
      detail: `Overall: ${(trust.overall_score * 100).toFixed(0)}% (${trust.budget_confidence}). ${trust.flagged_cells} cell${trust.flagged_cells !== 1 ? "s" : ""} flagged for review.${trust.estimated_review_minutes > 0 ? ` Estimated review: ~${trust.estimated_review_minutes} min.` : ""}`,
    },
  ];

  return (
    <div className="mt-3 mb-1 p-4 bg-neutral-50 rounded-lg border border-neutral-100">
      <div className="text-xs font-semibold text-neutral-700 mb-3">
        How this budget was calculated
      </div>
      <div className="space-y-3">
        {steps.map((s) => (
          <div key={s.num} className="flex gap-3">
            <div className="shrink-0 w-5 h-5 rounded-full bg-brand-primary/10 text-brand-primary text-[10px] font-bold flex items-center justify-center">
              {s.num}
            </div>
            <div>
              <div className="text-[11px] font-semibold text-neutral-600 uppercase tracking-wider">
                {s.title}
              </div>
              <div className="text-[11px] text-neutral-500 leading-relaxed mt-0.5">
                {s.detail}
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function TrustShield({ score }: { score: number }) {
  const color = score >= 0.90 ? "#00A950" : score >= 0.75 ? "#0093D0" : "#F8971D";
  return (
    <svg width="28" height="28" viewBox="0 0 28 28" fill="none">
      <path
        d="M14 2L4 6.4V13.2C4 19.4 8.68 25.16 14 26.6C19.32 25.16 24 19.4 24 13.2V6.4L14 2Z"
        fill={color}
        fillOpacity="0.12"
        stroke={color}
        strokeWidth="1.5"
        strokeLinejoin="round"
      />
      {score >= 0.75 && (
        <path
          d="M10 14L12.5 16.5L18 11"
          stroke={color}
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      )}
      {score < 0.75 && (
        <>
          <line x1="14" y1="10" x2="14" y2="16" stroke={color} strokeWidth="2" strokeLinecap="round" />
          <circle cx="14" cy="19" r="1" fill={color} />
        </>
      )}
    </svg>
  );
}
