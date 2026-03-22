"use client";

import { useState } from "react";
import { cn } from "@/lib/utils";
import { Badge } from "@/components/ui/Badge";
import type { VerificationStep, ChallengeIssue } from "@/lib/api";
import { deriveTrustLevel } from "./TrustIndicator";

// ─── Types ──────────────────────────────────────────────────────────────────

interface CellData {
  row: number;
  col: number;
  raw_value: string;
  data_type: string;
  confidence: number;
  row_header: string;
  col_header: string;
  footnote_markers: string[];
  resolved_footnotes: string[];
}

export interface CellEvidenceProps {
  cell: CellData;
  verifications: VerificationStep[];
  challengeIssues: ChallengeIssue[];
  onAccept: () => void;
  onCorrect: (value: string) => void;
  onFlag: (reason: string) => void;
}

// ─── Method labels & icons ──────────────────────────────────────────────────

const METHOD_LABELS: Record<VerificationStep["method"], string> = {
  DUAL_PASS: "Dual-pass extraction",
  OCR_GROUNDING: "OCR grounding",
  VISION_SPATIAL: "Vision spatial",
  CHALLENGER_CLEAR: "Challenger review",
  TEXT_MATCH: "Text match",
  FORMAT_CHECK: "Format check",
};

// ─── Component ──────────────────────────────────────────────────────────────

export function CellEvidence({
  cell,
  verifications,
  challengeIssues,
  onAccept,
  onCorrect,
  onFlag,
}: CellEvidenceProps) {
  const [mode, setMode] = useState<"view" | "correct" | "flag">("view");
  const [correctValue, setCorrectValue] = useState(cell.raw_value);
  const [flagReason, setFlagReason] = useState("");

  const trustLevel = deriveTrustLevel(verifications);
  const isFullyVerified = trustLevel === "verified";
  const hasFailures = verifications.some((v) => v.status === "FAIL");

  return (
    <div className="flex flex-col h-full">
      {/* ── Top: Cell identity ── */}
      <div className="px-4 pt-4 pb-3 border-b border-neutral-100">
        {/* Trust badge */}
        <div className="mb-2">
          {isFullyVerified ? (
            <Badge variant="success" className="gap-1">
              <VerifiedShieldSmall />
              Fully Verified
            </Badge>
          ) : hasFailures ? (
            <Badge variant="warning" className="gap-1">
              <WarningTriangleSmall />
              Needs Review
            </Badge>
          ) : (
            <Badge variant="neutral" className="gap-1">
              Partial Verification
            </Badge>
          )}
        </div>

        {/* Cell location */}
        <div className="text-[11px] text-neutral-400 leading-relaxed">
          <span>Row: <span className="text-neutral-600 font-medium">{cell.row_header}</span></span>
          <span className="mx-1.5">|</span>
          <span>Col: <span className="text-neutral-600 font-medium">{cell.col_header}</span></span>
        </div>

        {/* Extracted value */}
        <div className="mt-2 px-3 py-2 bg-neutral-50 rounded-lg border border-neutral-200">
          <div className="text-[10px] uppercase tracking-wider text-neutral-400 mb-0.5">Extracted Value</div>
          <div className="text-sm font-mono font-semibold text-neutral-800">
            {cell.raw_value || <span className="text-neutral-300 italic">empty</span>}
          </div>
          <div className="text-[10px] text-neutral-400 mt-0.5">
            Type: {cell.data_type} · Confidence: {(cell.confidence * 100).toFixed(0)}%
          </div>
        </div>

        {/* Footnotes */}
        {cell.footnote_markers.length > 0 && (
          <div className="mt-2 text-[11px] text-neutral-500">
            <span className="font-medium text-neutral-600">Footnotes:</span>{" "}
            {cell.footnote_markers.map((m, i) => (
              <span key={i}>
                <sup className="text-brand-primary font-semibold">{m}</sup>
                {cell.resolved_footnotes[i] && (
                  <span className="text-neutral-400 ml-0.5">{cell.resolved_footnotes[i]}</span>
                )}
                {i < cell.footnote_markers.length - 1 && "; "}
              </span>
            ))}
          </div>
        )}
      </div>

      {/* ── Middle: Verification chain (CI/CD pipeline style) ── */}
      <div className="flex-1 overflow-y-auto px-4 py-3">
        <div className="text-[11px] font-semibold text-neutral-800 uppercase tracking-wide mb-2">
          Verification Chain
        </div>
        <div className="space-y-0.5">
          {verifications.map((step, i) => (
            <VerificationRow key={i} step={step} />
          ))}
        </div>

        {/* Challenge issues */}
        {challengeIssues.length > 0 && (
          <div className="mt-4">
            <div className="text-[11px] font-semibold text-neutral-800 uppercase tracking-wide mb-2">
              Challenger Issues ({challengeIssues.length})
            </div>
            <div className="space-y-2">
              {challengeIssues.map((issue, i) => (
                <ChallengeRow key={i} issue={issue} />
              ))}
            </div>
          </div>
        )}
      </div>

      {/* ── Bottom: Action buttons ── */}
      <div className="px-4 py-3 border-t border-neutral-100 bg-neutral-50/50">
        {mode === "view" && (
          <div className="flex items-center gap-2">
            <button
              onClick={onAccept}
              className="flex-1 px-3 py-2 text-xs font-medium rounded-lg bg-success text-white hover:bg-success/90 transition-colors"
            >
              Accept
            </button>
            <button
              onClick={() => setMode("correct")}
              className="flex-1 px-3 py-2 text-xs font-medium rounded-lg border border-neutral-200 text-neutral-700 hover:bg-neutral-50 transition-colors"
            >
              Correct
            </button>
            <button
              onClick={() => setMode("flag")}
              className="flex-1 px-3 py-2 text-xs font-medium rounded-lg bg-warning/10 text-warning border border-warning/20 hover:bg-warning/20 transition-colors"
            >
              Flag
            </button>
          </div>
        )}

        {mode === "correct" && (
          <div className="space-y-2">
            <label className="text-[11px] font-medium text-neutral-600">Correct value:</label>
            <input
              type="text"
              value={correctValue}
              onChange={(e) => setCorrectValue(e.target.value)}
              className="w-full px-3 py-1.5 text-sm border border-neutral-200 rounded-lg font-mono focus:outline-none focus:ring-2 focus:ring-brand-primary/30 focus:border-brand-primary"
              autoFocus
            />
            <div className="flex items-center gap-2">
              <button
                onClick={() => {
                  onCorrect(correctValue);
                  setMode("view");
                }}
                className="flex-1 px-3 py-1.5 text-xs font-medium rounded-lg bg-brand-primary text-white hover:bg-brand-primary/90 transition-colors"
              >
                Save Correction
              </button>
              <button
                onClick={() => {
                  setCorrectValue(cell.raw_value);
                  setMode("view");
                }}
                className="px-3 py-1.5 text-xs font-medium rounded-lg text-neutral-500 hover:text-neutral-700 transition-colors"
              >
                Cancel
              </button>
            </div>
          </div>
        )}

        {mode === "flag" && (
          <div className="space-y-2">
            <label className="text-[11px] font-medium text-neutral-600">Reason for flagging:</label>
            <textarea
              value={flagReason}
              onChange={(e) => setFlagReason(e.target.value)}
              placeholder="Describe the issue..."
              rows={2}
              className="w-full px-3 py-1.5 text-sm border border-neutral-200 rounded-lg resize-none focus:outline-none focus:ring-2 focus:ring-warning/30 focus:border-warning"
              autoFocus
            />
            <div className="flex items-center gap-2">
              <button
                onClick={() => {
                  onFlag(flagReason);
                  setMode("view");
                  setFlagReason("");
                }}
                disabled={!flagReason.trim()}
                className={cn(
                  "flex-1 px-3 py-1.5 text-xs font-medium rounded-lg transition-colors",
                  flagReason.trim()
                    ? "bg-warning text-white hover:bg-warning/90"
                    : "bg-neutral-100 text-neutral-400 cursor-not-allowed"
                )}
              >
                Flag for Expert
              </button>
              <button
                onClick={() => {
                  setFlagReason("");
                  setMode("view");
                }}
                className="px-3 py-1.5 text-xs font-medium rounded-lg text-neutral-500 hover:text-neutral-700 transition-colors"
              >
                Cancel
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

// ─── Sub-components ─────────────────────────────────────────────────────────

function VerificationRow({ step }: { step: VerificationStep }) {
  return (
    <div
      className={cn(
        "flex items-start gap-2.5 px-2.5 py-2 rounded-lg",
        step.status === "FAIL" && "bg-red-50/60"
      )}
    >
      <span className="mt-0.5 shrink-0">
        {step.status === "PASS" && <StepPassIcon />}
        {step.status === "FAIL" && <StepFailIcon />}
        {step.status === "SKIPPED" && <StepSkippedIcon />}
      </span>
      <div className="min-w-0">
        <div
          className={cn(
            "text-xs font-medium",
            step.status === "PASS"
              ? "text-success"
              : step.status === "FAIL"
                ? "text-danger"
                : "text-neutral-400"
          )}
        >
          {METHOD_LABELS[step.method]}
        </div>
        <div className="text-[11px] text-neutral-500 leading-snug mt-0.5">{step.detail}</div>
      </div>
    </div>
  );
}

function ChallengeRow({ issue }: { issue: ChallengeIssue }) {
  return (
    <div className="px-3 py-2 bg-amber-50/60 rounded-lg border border-amber-100">
      <div className="flex items-center gap-1.5 mb-0.5">
        <span className="text-[10px] font-semibold uppercase tracking-wider text-amber-600">
          {issue.challenge_type}
        </span>
        <span className="text-[10px] text-amber-500">
          Severity: {issue.severity}/10
        </span>
      </div>
      <p className="text-[11px] text-neutral-600 leading-snug">{issue.description}</p>
      {issue.suggested_value && (
        <div className="mt-1 text-[11px]">
          <span className="text-neutral-400">Suggested: </span>
          <span className="font-mono font-medium text-neutral-700">{issue.suggested_value}</span>
        </div>
      )}
    </div>
  );
}

// ─── Icons ──────────────────────────────────────────────────────────────────

function StepPassIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
      <circle cx="8" cy="8" r="7" fill="#00A950" fillOpacity="0.1" stroke="#00A950" strokeWidth="1" />
      <path d="M5 8L7 10L11 6" stroke="#00A950" strokeWidth="1.3" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

function StepFailIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
      <circle cx="8" cy="8" r="7" fill="#CC292B" fillOpacity="0.1" stroke="#CC292B" strokeWidth="1" />
      <path d="M6 6L10 10M10 6L6 10" stroke="#CC292B" strokeWidth="1.3" strokeLinecap="round" />
    </svg>
  );
}

function StepSkippedIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
      <circle cx="8" cy="8" r="7" fill="#e2e8f0" fillOpacity="0.5" stroke="#94a3b8" strokeWidth="1" />
      <path d="M5.5 8H10.5" stroke="#94a3b8" strokeWidth="1.3" strokeLinecap="round" />
    </svg>
  );
}

function VerifiedShieldSmall() {
  return (
    <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
      <path d="M6 1L2 2.8V5.6C2 8.08 3.72 10.38 6 11C8.28 10.38 10 8.08 10 5.6V2.8L6 1Z" fill="currentColor" fillOpacity="0.2" stroke="currentColor" strokeWidth="0.8" />
      <path d="M4.5 6L5.5 7L7.5 5" stroke="currentColor" strokeWidth="0.9" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

function WarningTriangleSmall() {
  return (
    <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
      <path d="M6 2L10.5 10H1.5L6 2Z" fill="currentColor" fillOpacity="0.2" stroke="currentColor" strokeWidth="0.8" strokeLinejoin="round" />
      <line x1="6" y1="5" x2="6" y2="7" stroke="currentColor" strokeWidth="0.8" strokeLinecap="round" />
      <circle cx="6" cy="8.3" r="0.45" fill="currentColor" />
    </svg>
  );
}
