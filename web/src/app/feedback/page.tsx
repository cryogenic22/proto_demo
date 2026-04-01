"use client";

import { useEffect, useState } from "react";
import Link from "next/link";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface FeedbackEntry {
  id: string;
  submitted_at: number;
  updated_at: number;
  category: string;
  title: string;
  description: string;
  priority: string;
  page_url: string;
  status: string;
  triage: {
    severity: string;
    affected_modules: string[];
    root_cause_hypothesis: string;
    spec: {
      summary: string;
      acceptance_criteria: string[];
      files_to_modify: string[];
      estimated_effort: string;
    };
    tdd_plan: {
      test_file: string;
      test_cases: { name: string; description: string }[];
    };
    suggested_fix: string;
    error?: string;
  } | null;
  delivery_report: {
    title: string;
    status: string;
    triage_summary: string;
    fix_applied: string;
    spec: Record<string, unknown>;
    tdd_plan: Record<string, unknown>;
    delivered_at: number;
  } | null;
  resolution: string | null;
  delivered_at: number | null;
}

const STATUS_COLORS: Record<string, string> = {
  new: "bg-blue-50 text-blue-700 border-blue-200",
  triaging: "bg-purple-50 text-purple-700 border-purple-200",
  spec_ready: "bg-indigo-50 text-indigo-700 border-indigo-200",
  in_progress: "bg-amber-50 text-amber-700 border-amber-200",
  testing: "bg-cyan-50 text-cyan-700 border-cyan-200",
  deploying: "bg-orange-50 text-orange-700 border-orange-200",
  delivered: "bg-green-50 text-green-700 border-green-200",
  rejected: "bg-red-50 text-red-700 border-red-200",
};

const CATEGORY_ICONS: Record<string, string> = {
  bug: "\uD83D\uDC1B",
  issue: "\u26A0\uFE0F",
  enhancement: "\u2728",
  feature: "\uD83D\uDE80",
};

const PRIORITY_COLORS: Record<string, string> = {
  low: "bg-slate-100 text-slate-600",
  medium: "bg-blue-100 text-blue-600",
  high: "bg-amber-100 text-amber-700",
  critical: "bg-red-100 text-red-700",
};

function formatTime(ts: number): string {
  return new Date(ts * 1000).toLocaleString("en-US", {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}

export default function FeedbackTrackerPage() {
  const [entries, setEntries] = useState<FeedbackEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState<string>("all");
  const [selected, setSelected] = useState<FeedbackEntry | null>(null);

  const fetchEntries = async () => {
    try {
      const url = statusFilter === "all"
        ? `${API_BASE}/api/feedback`
        : `${API_BASE}/api/feedback?status=${statusFilter}`;
      const res = await fetch(url);
      if (res.ok) {
        const data = await res.json();
        setEntries(data.items || []);
      }
    } catch {
      // silently handle
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchEntries();
    const interval = setInterval(fetchEntries, 10000); // poll every 10s
    return () => clearInterval(interval);
  }, [statusFilter]);

  return (
    <div className="p-6 max-w-7xl mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-xl font-bold text-neutral-800">Feedback Tracker</h1>
          <p className="text-sm text-neutral-500 mt-0.5">
            Track your feedback, see auto-triage results, and view delivery reports
          </p>
        </div>
        <div className="flex items-center gap-3">
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="text-sm border border-neutral-300 rounded-lg px-3 py-1.5 bg-white"
          >
            <option value="all">All Status</option>
            <option value="new">New</option>
            <option value="triaging">Triaging</option>
            <option value="spec_ready">Spec Ready</option>
            <option value="in_progress">In Progress</option>
            <option value="testing">Testing</option>
            <option value="deploying">Deploying</option>
            <option value="delivered">Delivered</option>
            <option value="rejected">Rejected</option>
          </select>
          <button
            onClick={fetchEntries}
            className="text-sm px-3 py-1.5 rounded-lg border border-neutral-300 hover:bg-neutral-50 text-neutral-600"
          >
            Refresh
          </button>
        </div>
      </div>

      {loading ? (
        <div className="flex items-center justify-center py-20">
          <div className="w-6 h-6 border-2 border-brand-primary border-t-transparent rounded-full animate-spin" />
        </div>
      ) : entries.length === 0 ? (
        <div className="text-center py-20">
          <div className="w-16 h-16 mx-auto rounded-full bg-neutral-100 flex items-center justify-center mb-4">
            <svg className="w-7 h-7 text-neutral-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M7.5 8.25h9m-9 3H12m-9.75 1.51c0 1.6 1.123 2.994 2.707 3.227 1.129.166 2.27.293 3.423.379.35.026.67.21.865.501L12 21l2.755-4.133a1.14 1.14 0 01.865-.501 48.172 48.172 0 003.423-.379c1.584-.233 2.707-1.626 2.707-3.228V6.741c0-1.602-1.123-2.995-2.707-3.228A48.394 48.394 0 0012 3c-2.392 0-4.744.175-7.043.513C3.373 3.746 2.25 5.14 2.25 6.741v6.018z" />
            </svg>
          </div>
          <p className="text-neutral-500 text-sm">No feedback submitted yet</p>
          <p className="text-neutral-400 text-xs mt-1">Use the feedback button to report issues or suggest improvements</p>
        </div>
      ) : (
        <div className="flex gap-6">
          {/* List */}
          <div className="flex-1 space-y-3">
            {entries.map((entry) => (
              <button
                key={entry.id}
                onClick={() => setSelected(entry)}
                className={`w-full text-left rounded-xl border p-4 transition-all hover:shadow-sm ${
                  selected?.id === entry.id
                    ? "border-brand-primary bg-brand-primary/5 shadow-sm"
                    : "border-neutral-200 bg-white hover:border-neutral-300"
                }`}
              >
                <div className="flex items-start gap-3">
                  <span className="text-lg mt-0.5">{CATEGORY_ICONS[entry.category] || "?"}</span>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-1">
                      <h3 className="text-sm font-semibold text-neutral-800 truncate">{entry.title}</h3>
                    </div>
                    <p className="text-xs text-neutral-500 line-clamp-2">{entry.description}</p>
                    <div className="flex items-center gap-2 mt-2">
                      <span className={`text-[10px] px-2 py-0.5 rounded-full font-medium border ${STATUS_COLORS[entry.status] || "bg-neutral-100 text-neutral-600"}`}>
                        {entry.status.replace("_", " ")}
                      </span>
                      <span className={`text-[10px] px-2 py-0.5 rounded-full font-medium ${PRIORITY_COLORS[entry.priority] || ""}`}>
                        {entry.priority}
                      </span>
                      <span className="text-[10px] text-neutral-400 ml-auto font-mono">{entry.id}</span>
                      <span className="text-[10px] text-neutral-400">{formatTime(entry.submitted_at)}</span>
                    </div>
                  </div>
                </div>
              </button>
            ))}
          </div>

          {/* Detail Panel */}
          {selected && (
            <div className="w-[440px] shrink-0 sticky top-6 self-start">
              <div className="rounded-xl border border-neutral-200 bg-white overflow-hidden">
                {/* Detail Header */}
                <div className="px-5 py-4 border-b border-neutral-100">
                  <div className="flex items-center gap-2 mb-2">
                    <span className="text-lg">{CATEGORY_ICONS[selected.category]}</span>
                    <span className={`text-[10px] px-2 py-0.5 rounded-full font-medium border ${STATUS_COLORS[selected.status]}`}>
                      {selected.status.replace("_", " ")}
                    </span>
                    <span className={`text-[10px] px-2 py-0.5 rounded-full font-medium ${PRIORITY_COLORS[selected.priority]}`}>
                      {selected.priority}
                    </span>
                    <button
                      onClick={() => setSelected(null)}
                      className="ml-auto p-1 rounded hover:bg-neutral-100 text-neutral-400"
                    >
                      <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                        <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
                      </svg>
                    </button>
                  </div>
                  <h2 className="text-sm font-bold text-neutral-800">{selected.title}</h2>
                  <p className="text-xs text-neutral-500 mt-1">{selected.description}</p>
                  <div className="flex gap-4 mt-3 text-[10px] text-neutral-400">
                    <span>ID: <span className="font-mono">{selected.id}</span></span>
                    <span>Page: <span className="font-mono">{selected.page_url || "/"}</span></span>
                    <span>{formatTime(selected.submitted_at)}</span>
                  </div>
                </div>

                {/* Triage Results */}
                {selected.triage && !selected.triage.error && (
                  <div className="px-5 py-4 border-b border-neutral-100">
                    <h3 className="text-xs font-semibold text-neutral-700 uppercase tracking-wide mb-3">Auto-Triage</h3>

                    <div className="space-y-3">
                      <div>
                        <span className="text-[10px] text-neutral-500 uppercase">Root Cause</span>
                        <p className="text-xs text-neutral-700 mt-0.5">{selected.triage.root_cause_hypothesis}</p>
                      </div>

                      {selected.triage.affected_modules?.length > 0 && (
                        <div>
                          <span className="text-[10px] text-neutral-500 uppercase">Affected Modules</span>
                          <div className="flex flex-wrap gap-1 mt-1">
                            {selected.triage.affected_modules.map((m, i) => (
                              <span key={i} className="text-[10px] px-2 py-0.5 rounded bg-neutral-100 text-neutral-600 font-mono">
                                {m}
                              </span>
                            ))}
                          </div>
                        </div>
                      )}

                      <div>
                        <span className="text-[10px] text-neutral-500 uppercase">Suggested Fix</span>
                        <p className="text-xs text-neutral-700 mt-0.5">{selected.triage.suggested_fix}</p>
                      </div>
                    </div>
                  </div>
                )}

                {/* Spec */}
                {selected.triage?.spec && (
                  <div className="px-5 py-4 border-b border-neutral-100">
                    <h3 className="text-xs font-semibold text-neutral-700 uppercase tracking-wide mb-3">Spec</h3>
                    <p className="text-xs text-neutral-700 mb-2">{selected.triage.spec.summary}</p>

                    {selected.triage.spec.acceptance_criteria?.length > 0 && (
                      <div className="mb-2">
                        <span className="text-[10px] text-neutral-500 uppercase">Acceptance Criteria</span>
                        <ul className="mt-1 space-y-1">
                          {selected.triage.spec.acceptance_criteria.map((ac, i) => (
                            <li key={i} className="text-xs text-neutral-600 flex gap-1.5">
                              <span className="text-green-500 shrink-0">&#10003;</span>
                              {ac}
                            </li>
                          ))}
                        </ul>
                      </div>
                    )}

                    {selected.triage.spec.files_to_modify?.length > 0 && (
                      <div className="mb-2">
                        <span className="text-[10px] text-neutral-500 uppercase">Files to Modify</span>
                        <div className="flex flex-wrap gap-1 mt-1">
                          {selected.triage.spec.files_to_modify.map((f, i) => (
                            <span key={i} className="text-[10px] px-2 py-0.5 rounded bg-amber-50 text-amber-700 font-mono">{f}</span>
                          ))}
                        </div>
                      </div>
                    )}

                    <span className={`text-[10px] px-2 py-0.5 rounded-full font-medium ${
                      selected.triage.spec.estimated_effort === "small" ? "bg-green-100 text-green-700" :
                      selected.triage.spec.estimated_effort === "medium" ? "bg-amber-100 text-amber-700" :
                      "bg-red-100 text-red-700"
                    }`}>
                      Effort: {selected.triage.spec.estimated_effort}
                    </span>
                  </div>
                )}

                {/* TDD Plan */}
                {(selected.triage?.tdd_plan?.test_cases?.length ?? 0) > 0 && (
                  <div className="px-5 py-4 border-b border-neutral-100">
                    <h3 className="text-xs font-semibold text-neutral-700 uppercase tracking-wide mb-3">TDD Plan</h3>
                    <p className="text-[10px] text-neutral-500 font-mono mb-2">{selected.triage!.tdd_plan.test_file}</p>
                    <div className="space-y-1.5">
                      {selected.triage!.tdd_plan.test_cases.map((tc, i) => (
                        <div key={i} className="flex gap-2 text-xs">
                          <span className="text-brand-primary shrink-0 font-mono">def</span>
                          <div>
                            <span className="font-mono text-neutral-800">{tc.name}</span>
                            <p className="text-neutral-500 text-[10px]">{tc.description}</p>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Delivery Report */}
                {selected.delivery_report && (
                  <div className="px-5 py-4 bg-green-50/50">
                    <h3 className="text-xs font-semibold text-green-800 uppercase tracking-wide mb-3">Delivery Report</h3>
                    <div className="space-y-2">
                      <div>
                        <span className="text-[10px] text-green-700/70 uppercase">Fix Applied</span>
                        <p className="text-xs text-green-900 mt-0.5">{selected.delivery_report.fix_applied}</p>
                      </div>
                      {selected.delivery_report.delivered_at && (
                        <p className="text-[10px] text-green-600">
                          Delivered {formatTime(selected.delivery_report.delivered_at)}
                        </p>
                      )}
                    </div>
                  </div>
                )}

                {/* Pending triage state */}
                {(selected.status === "new" || selected.status === "triaging") && !selected.triage && (
                  <div className="px-5 py-8 text-center">
                    <div className="w-6 h-6 border-2 border-brand-primary border-t-transparent rounded-full animate-spin mx-auto mb-3" />
                    <p className="text-xs text-neutral-500">Auto-triage in progress...</p>
                    <p className="text-[10px] text-neutral-400 mt-1">AI is analyzing your feedback and generating a spec</p>
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
