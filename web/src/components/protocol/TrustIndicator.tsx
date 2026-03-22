"use client";

import { cn } from "@/lib/utils";

export type TrustLevel = "verified" | "high" | "medium" | "low" | "unverified";

interface TrustIndicatorProps {
  level: TrustLevel;
  className?: string;
}

/**
 * Tiny inline trust badge for SoA table cells (bottom-right corner).
 * - verified: green shield (all checks passed)
 * - high: blue dot (3+ checks)
 * - medium: no indicator (default — keeps table clean)
 * - low: amber triangle (1 check or conflicts)
 * - unverified: red dot (no checks)
 */
export function TrustIndicator({ level, className }: TrustIndicatorProps) {
  if (level === "medium") return null;

  return (
    <span
      className={cn("inline-flex items-center justify-center shrink-0", className)}
      title={TRUST_LABELS[level]}
    >
      {level === "verified" && <ShieldIcon />}
      {level === "high" && <HighDot />}
      {level === "low" && <AmberTriangle />}
      {level === "unverified" && <RedDot />}
    </span>
  );
}

const TRUST_LABELS: Record<TrustLevel, string> = {
  verified: "Fully verified — all checks passed",
  high: "High confidence — 3+ checks passed",
  medium: "Standard extraction",
  low: "Low confidence — needs review",
  unverified: "Unverified — no checks completed",
};

/** Green shield — 12x12 */
function ShieldIcon() {
  return (
    <svg width="12" height="12" viewBox="0 0 12 12" fill="none" xmlns="http://www.w3.org/2000/svg">
      <path
        d="M6 1L2 2.8V5.6C2 8.08 3.72 10.38 6 11C8.28 10.38 10 8.08 10 5.6V2.8L6 1Z"
        fill="#00A950"
        fillOpacity="0.15"
        stroke="#00A950"
        strokeWidth="0.8"
        strokeLinejoin="round"
      />
      <path
        d="M4.5 6L5.5 7L7.5 5"
        stroke="#00A950"
        strokeWidth="0.9"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

/** Blue dot — 8x8 */
function HighDot() {
  return (
    <span className="block w-2 h-2 rounded-full" style={{ backgroundColor: "#0093D0" }} />
  );
}

/** Amber triangle — 10x10 */
function AmberTriangle() {
  return (
    <svg width="10" height="10" viewBox="0 0 10 10" fill="none" xmlns="http://www.w3.org/2000/svg">
      <path
        d="M5 1.5L9 8.5H1L5 1.5Z"
        fill="#F8971D"
        fillOpacity="0.2"
        stroke="#F8971D"
        strokeWidth="0.8"
        strokeLinejoin="round"
      />
      <line x1="5" y1="4" x2="5" y2="6" stroke="#F8971D" strokeWidth="0.8" strokeLinecap="round" />
      <circle cx="5" cy="7.2" r="0.45" fill="#F8971D" />
    </svg>
  );
}

/** Red dot — 8x8 */
function RedDot() {
  return (
    <span className="block w-2 h-2 rounded-full" style={{ backgroundColor: "#CC292B" }} />
  );
}

/**
 * Derive trust level from verification steps.
 */
export function deriveTrustLevel(
  verifications: { status: "PASS" | "FAIL" | "SKIPPED" }[]
): TrustLevel {
  const passed = verifications.filter((v) => v.status === "PASS").length;
  const failed = verifications.filter((v) => v.status === "FAIL").length;
  const available = verifications.filter((v) => v.status !== "SKIPPED").length;

  if (failed > 0) return "low";
  if (available === 0) return "unverified";
  if (passed === available && passed >= 4) return "verified";
  if (passed >= 3) return "high";
  if (passed >= 2) return "medium";
  return "low";
}
