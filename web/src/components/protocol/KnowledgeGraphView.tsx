"use client";

import { useEffect, useState, useRef, useCallback } from "react";
import {
  buildSMBModel,
  getSMBModel,
  getSMBGraph,
  getSMBSchedule,
  askProtocol,
  type SMBGraph,
  type SMBGraphNode,
  type SMBModelInfo,
  type SMBScheduleEntry,
} from "@/lib/api";
import { cn } from "@/lib/utils";
import { Badge } from "@/components/ui/Badge";

interface Props { protocolId: string; }
interface ChatMessage { role: "user" | "assistant"; content: string; }

const API = process.env.NEXT_PUBLIC_API_URL || "";

export function KnowledgeGraphView({ protocolId }: Props) {
  const [status, setStatus] = useState<"loading" | "ready" | "error">("loading");
  const [modelInfo, setModelInfo] = useState<SMBModelInfo | null>(null);
  const [graph, setGraph] = useState<SMBGraph | null>(null);
  const [schedule, setSchedule] = useState<SMBScheduleEntry[]>([]);
  const [error, setError] = useState("");
  const [tab, setTab] = useState<string>("glance");
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [chatInput, setChatInput] = useState("");
  const [chatLoading, setChatLoading] = useState(false);
  const [expandedVisit, setExpandedVisit] = useState<string | null>(null);
  const [expandedProc, setExpandedProc] = useState<string | null>(null);
  const chatEnd = useRef<HTMLDivElement>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        try { await getSMBModel(protocolId); } catch { await buildSMBModel(protocolId); }
        if (cancelled) return;
        const [info, g, s] = await Promise.all([
          getSMBModel(protocolId),
          getSMBGraph(protocolId),
          getSMBSchedule(protocolId).then(r => r.schedule).catch(() => [] as SMBScheduleEntry[]),
        ]);
        if (!cancelled) { setModelInfo(info); setGraph(g); setSchedule(s); setStatus("ready"); }
      } catch (e) { if (!cancelled) { setError(String(e)); setStatus("error"); } }
    })();
    return () => { cancelled = true; };
  }, [protocolId]);

  useEffect(() => { chatEnd.current?.scrollIntoView({ behavior: "smooth" }); }, [messages]);

  const handleAsk = useCallback(async () => {
    const q = chatInput.trim();
    if (!q || chatLoading) return;
    setChatInput("");
    setMessages(p => [...p, { role: "user", content: q }]);
    setChatLoading(true);
    try {
      const resp = await askProtocol(protocolId, q);
      setMessages(p => [...p, { role: "assistant", content: resp.content || JSON.stringify(resp) }]);
    } catch {
      setMessages(p => [...p, { role: "assistant", content: "Unable to process. Check API connection." }]);
    } finally { setChatLoading(false); }
  }, [chatInput, chatLoading, protocolId]);

  const handleRebuild = async () => {
    setStatus("loading");
    try {
      await buildSMBModel(protocolId);
      const [info, g, s] = await Promise.all([
        getSMBModel(protocolId), getSMBGraph(protocolId),
        getSMBSchedule(protocolId).then(r => r.schedule).catch(() => [] as SMBScheduleEntry[]),
      ]);
      setModelInfo(info); setGraph(g); setSchedule(s); setStatus("ready");
    } catch (e) { setError(String(e)); setStatus("error"); }
  };

  if (status === "loading") return (
    <div className="flex items-center justify-center py-20">
      <div className="text-center">
        <div className="w-8 h-8 border-2 border-brand-primary border-t-transparent rounded-full animate-spin mx-auto mb-3" />
        <p className="text-sm text-neutral-500">Building protocol model...</p>
      </div>
    </div>
  );

  if (status === "error" || !modelInfo || !graph) return (
    <div className="p-6 text-center">
      <p className="text-sm text-red-600">Failed to build model</p>
      <p className="text-xs text-neutral-400 mt-1">{error}</p>
      <button onClick={handleRebuild} className="mt-3 px-4 py-2 text-xs bg-brand-primary text-white rounded-lg">Retry</button>
    </div>
  );

  const visits = graph.nodes.filter(n => n.type === "Visit");
  const procs = graph.nodes.filter(n => n.type === "Procedure");
  const fns = graph.nodes.filter(n => n.type === "Footnote");
  const entries = graph.nodes.filter(n => n.type === "ScheduleEntry");
  const firm = entries.filter(e => e.properties.mark_type === "firm").length;
  const cond = entries.filter(e => e.properties.mark_type === "conditional").length;
  const meta = graph.metadata || {};

  const TABS = [
    { key: "glance", label: "At a Glance" },
    { key: "journey", label: "Visit Journey" },
    { key: "procedures", label: "Procedures" },
    { key: "gaps", label: "Gap Analysis" },
    { key: "assistant", label: "Assistant" },
  ];

  return (
    <div className="h-full flex flex-col">
      {/* Header */}
      <div className="px-4 py-3 bg-white border-b border-neutral-200">
        <div className="flex items-center justify-between mb-2">
          {(() => {
            const title = String(meta["title"] || graph.document_id || "Protocol");
            const sponsor = meta["sponsor"] ? String(meta["sponsor"]) : "";
            const phase = meta["phase"] ? String(meta["phase"]) : "";
            return (
              <div>
                <h2 className="text-sm font-semibold text-neutral-800">{title}</h2>
                <div className="flex items-center gap-3 text-[11px] text-neutral-500">
                  {sponsor && <span>{sponsor}</span>}
                  {phase && <span>Phase {phase}</span>}
                  {modelInfo.inference_rules_fired.length > 0 && (
                    <span className="text-indigo-600">{modelInfo.inference_rules_fired.length} rules applied</span>
                  )}
                  <span>{visits.length} visits, {procs.length} procedures, {firm} firm / {cond} conditional</span>
                </div>
              </div>
            );
          })()}
          <button onClick={handleRebuild} className="px-2.5 py-1 text-[10px] border border-neutral-200 rounded-lg text-neutral-500 hover:bg-neutral-50">Rebuild</button>
        </div>
        <div className="flex gap-1">
          {TABS.map(t => (
            <button key={t.key} onClick={() => setTab(t.key)}
              className={cn("px-3 py-1.5 text-xs font-medium rounded-lg transition-colors",
                tab === t.key ? "bg-brand-primary text-white" : "text-neutral-500 hover:bg-neutral-100"
              )}>{t.label}</button>
          ))}
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto">
        {tab === "glance" && <GlanceTab graph={graph} modelInfo={modelInfo} schedule={schedule} visits={visits} procs={procs} fns={fns} entries={entries} />}
        {tab === "journey" && <JourneyTab visits={visits} graph={graph} schedule={schedule} expandedVisit={expandedVisit} setExpandedVisit={setExpandedVisit} />}
        {tab === "procedures" && <ProceduresTab procs={procs} schedule={schedule} expandedProc={expandedProc} setExpandedProc={setExpandedProc} />}
        {tab === "gaps" && <GapAnalysisTab schedule={schedule} procs={procs} modelInfo={modelInfo} />}
        {tab === "assistant" && <AssistantTab messages={messages} chatInput={chatInput} chatLoading={chatLoading} onInputChange={setChatInput} onSend={handleAsk} chatEnd={chatEnd} />}
      </div>
    </div>
  );
}

// ─── At a Glance ────────────────────────────────────────────────────────

function GlanceTab({ graph, modelInfo, schedule, visits, procs, fns, entries }: {
  graph: SMBGraph; modelInfo: SMBModelInfo; schedule: SMBScheduleEntry[];
  visits: SMBGraphNode[]; procs: SMBGraphNode[]; fns: SMBGraphNode[]; entries: SMBGraphNode[];
}) {
  const firm = entries.filter(e => e.properties.mark_type === "firm").length;
  const cond = entries.filter(e => e.properties.mark_type === "conditional").length;
  const span = entries.filter(e => e.properties.is_span).length;
  const withCpt = procs.filter(p => p.properties.cpt_code).length;
  const meta = graph.metadata || {};

  return (
    <div className="p-4 space-y-4">
      {/* Study Design Summary */}
      <div className="bg-white rounded-xl border border-neutral-200 p-5">
        <h3 className="text-xs font-semibold text-neutral-400 uppercase tracking-wider mb-3">Study Design</h3>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <GlanceStat label="Total Visits" value={visits.length} sub={`${visits.filter(v => v.properties.is_unscheduled).length} unscheduled`} color="blue" />
          <GlanceStat label="Procedures" value={procs.length} sub={`${withCpt} with CPT codes`} color="emerald" />
          <GlanceStat label="Schedule Entries" value={entries.length} sub={`${firm} firm, ${cond} conditional${span ? `, ${span} spans` : ""}`} color="sky" />
          <GlanceStat label="Footnotes" value={fns.length} sub={`${fns.filter(f => f.properties.classification === "CONDITIONAL").length} conditional`} color="amber" />
        </div>
      </div>

      {/* Visit Timeline Minimap */}
      <div className="bg-white rounded-xl border border-neutral-200 p-5">
        <h3 className="text-xs font-semibold text-neutral-400 uppercase tracking-wider mb-3">Visit Timeline</h3>
        <div className="flex items-end gap-[2px] overflow-x-auto pb-1">
          {[...visits].sort((a, b) => (Number(a.properties.day_number) || 9999) - (Number(b.properties.day_number) || 9999)).slice(0, 30).map(v => {
            const procsAtVisit = entries.filter(e => e.properties.visit_entity_id === v.id).length;
            return (
              <div key={v.id} className="flex flex-col items-center min-w-[28px]" title={`${v.label}: ${procsAtVisit} procedures`}>
                <div className={cn("w-5 rounded-t transition-all", procsAtVisit > 10 ? "bg-blue-600" : procsAtVisit > 5 ? "bg-blue-500" : "bg-blue-300")}
                  style={{ height: Math.max(6, procsAtVisit * 3) }} />
                <div className="text-[8px] text-neutral-400 mt-0.5 truncate w-7 text-center">
                  {v.properties.day_number != null ? `D${String(v.properties.day_number)}` : String(v.label).slice(0, 4)}
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Inference & Validation */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {modelInfo.inference_rules_fired.length > 0 && (
          <div className="bg-white rounded-xl border border-neutral-200 p-4">
            <h3 className="text-xs font-semibold text-neutral-400 uppercase tracking-wider mb-2">Rules Applied</h3>
            <div className="space-y-1.5">
              {modelInfo.inference_rules_fired.map(r => (
                <div key={r} className="flex items-center gap-2 text-xs">
                  <span className="w-2 h-2 rounded-full bg-indigo-500" />
                  <span className="text-neutral-700">{r.replace("Inference", " Inference")}</span>
                </div>
              ))}
            </div>
          </div>
        )}
        <div className="bg-white rounded-xl border border-neutral-200 p-4">
          <h3 className="text-xs font-semibold text-neutral-400 uppercase tracking-wider mb-2">Model Health</h3>
          <div className="space-y-1.5">
            <HealthRow label="Validation" ok={modelInfo.validation_passed} detail={modelInfo.validation_passed ? "All checks passed" : `${modelInfo.validation_errors.length} errors`} />
            <HealthRow label="CPT Coverage" ok={withCpt / Math.max(procs.length, 1) > 0.4} detail={`${withCpt}/${procs.length} procedures`} />
            <HealthRow label="Footnote Resolution" ok={fns.length > 0} detail={`${fns.length} footnotes classified`} />
            <HealthRow label="Build Time" ok={modelInfo.build_time_seconds < 5} detail={`${modelInfo.build_time_seconds.toFixed(1)}s`} />
          </div>
          {modelInfo.validation_warnings.length > 0 && (
            <div className="mt-2 pt-2 border-t border-neutral-100">
              {modelInfo.validation_warnings.slice(0, 3).map((w, i) => (
                <p key={i} className="text-[10px] text-amber-600 leading-relaxed">{w}</p>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Top Procedures by Frequency */}
      <div className="bg-white rounded-xl border border-neutral-200 p-4">
        <h3 className="text-xs font-semibold text-neutral-400 uppercase tracking-wider mb-2">Most Frequent Procedures</h3>
        <div className="space-y-1">
          {[...schedule].sort((a, b) => (b.total_occurrences || 0) - (a.total_occurrences || 0)).slice(0, 8).map((s, i) => (
            <div key={i} className="flex items-center gap-2 text-xs">
              <div className="w-24 truncate text-neutral-700 font-medium">{s.canonical_name || s.procedure}</div>
              <div className="flex-1 h-2 bg-neutral-100 rounded-full overflow-hidden">
                <div className="h-full bg-emerald-500 rounded-full" style={{ width: `${Math.min(100, (s.total_occurrences || 0) * 5)}%` }} />
              </div>
              <span className="text-neutral-500 tabular-nums w-8 text-right">{s.total_occurrences}</span>
              {s.cpt_code && <span className="text-[9px] font-mono text-neutral-400">{s.cpt_code}</span>}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function GlanceStat({ label, value, sub, color }: { label: string; value: number; sub: string; color: string }) {
  const bg: Record<string, string> = { blue: "bg-blue-50 text-blue-700", emerald: "bg-emerald-50 text-emerald-700", sky: "bg-sky-50 text-sky-700", amber: "bg-amber-50 text-amber-700" };
  return (
    <div className={cn("rounded-xl p-3", bg[color])}>
      <div className="text-2xl font-bold tabular-nums">{value}</div>
      <div className="text-[11px] font-medium">{label}</div>
      <div className="text-[10px] opacity-60 mt-0.5">{sub}</div>
    </div>
  );
}

function HealthRow({ label, ok, detail }: { label: string; ok: boolean; detail: string }) {
  return (
    <div className="flex items-center justify-between text-xs">
      <div className="flex items-center gap-2">
        <span className={cn("w-2 h-2 rounded-full", ok ? "bg-emerald-500" : "bg-amber-500")} />
        <span className="text-neutral-700">{label}</span>
      </div>
      <span className="text-neutral-500">{detail}</span>
    </div>
  );
}

// ─── Visit Journey ──────────────────────────────────────────────────────

function JourneyTab({ visits, graph, schedule, expandedVisit, setExpandedVisit }: {
  visits: SMBGraphNode[]; graph: SMBGraph; schedule: SMBScheduleEntry[];
  expandedVisit: string | null; setExpandedVisit: (v: string | null) => void;
}) {
  const sorted = [...visits].sort((a, b) => (Number(a.properties.day_number) || 9999) - (Number(b.properties.day_number) || 9999));
  const entries = graph.nodes.filter(n => n.type === "ScheduleEntry");

  const getPhase = (v: SMBGraphNode): string => {
    const name = String(v.label).toLowerCase();
    if (name.includes("screen")) return "Screening";
    if (name.includes("follow") || name.includes("f/u")) return "Follow-up";
    if (name.includes("end of") || name.includes("eot")) return "End of Treatment";
    return "Treatment";
  };

  const phaseColors: Record<string, string> = {
    "Screening": "border-neutral-400 bg-neutral-50",
    "Treatment": "border-blue-400 bg-blue-50",
    "Follow-up": "border-emerald-400 bg-emerald-50",
    "End of Treatment": "border-amber-400 bg-amber-50",
  };

  return (
    <div className="p-4">
      {/* Phase legend */}
      <div className="flex items-center gap-3 mb-4">
        {Object.entries(phaseColors).map(([phase, cls]) => (
          <div key={phase} className="flex items-center gap-1.5 text-[10px] text-neutral-600">
            <div className={cn("w-3 h-3 rounded border-2", cls)} />
            {phase}
          </div>
        ))}
      </div>

      {/* Timeline */}
      <div className="space-y-2">
        {sorted.map((v, i) => {
          const phase = getPhase(v);
          const procsAtVisit = entries.filter(e => e.properties.visit_entity_id === v.id);
          const firmCount = procsAtVisit.filter(e => e.properties.mark_type === "firm").length;
          const condCount = procsAtVisit.filter(e => e.properties.mark_type === "conditional").length;
          const isExpanded = expandedVisit === v.id;

          return (
            <div key={v.id}>
              <button
                onClick={() => setExpandedVisit(isExpanded ? null : v.id)}
                className={cn("w-full text-left rounded-xl border-2 px-4 py-3 transition-all hover:shadow-sm",
                  phaseColors[phase] || phaseColors["Treatment"],
                  isExpanded && "shadow-md"
                )}
              >
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <div className="w-10 h-10 rounded-lg bg-white/80 flex items-center justify-center text-sm font-bold text-neutral-700 border border-neutral-200">
                      {v.properties.day_number != null ? `D${String(v.properties.day_number)}` : `V${i + 1}`}
                    </div>
                    <div>
                      <div className="text-sm font-medium text-neutral-800">{v.label}</div>
                      <div className="text-[11px] text-neutral-500">
                        {phase}
                        {(v.properties.window_minus || v.properties.window_plus) ? ` | Window: -${String(v.properties.window_minus ?? 0)}/+${String(v.properties.window_plus ?? 0)}d` : ""}
                        {v.properties.cycle != null ? ` | Cycle ${String(v.properties.cycle)}` : ""}
                      </div>
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <Badge variant="neutral">{firmCount} firm</Badge>
                    {condCount > 0 && <Badge variant="warning">{condCount} cond</Badge>}
                    <svg className={cn("w-4 h-4 text-neutral-400 transition-transform", isExpanded && "rotate-180")} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
                    </svg>
                  </div>
                </div>
              </button>

              {/* Expanded procedure list */}
              {isExpanded && (
                <div className="ml-6 mt-1 mb-2 bg-white rounded-lg border border-neutral-200 divide-y divide-neutral-100">
                  {procsAtVisit.map(entry => {
                    const proc = graph.nodes.find(n => n.id === entry.properties.procedure_entity_id);
                    const markType = String(entry.properties.mark_type || "firm");
                    const fnMarkers = (Array.isArray(entry.properties.footnote_markers) ? entry.properties.footnote_markers : []) as string[];
                    return (
                      <div key={entry.id} className="px-3 py-2 flex items-center justify-between">
                        <div className="flex items-center gap-2 min-w-0">
                          <span className={cn("w-2 h-2 rounded-full shrink-0",
                            markType === "firm" ? "bg-emerald-500" : markType === "conditional" ? "bg-amber-500" : "bg-purple-500"
                          )} />
                          <span className="text-xs text-neutral-700 truncate">{proc?.label || entry.label}</span>
                          {fnMarkers.length > 0 && (
                            <span className="text-[9px] text-amber-600 font-mono">{fnMarkers.join(",")}</span>
                          )}
                        </div>
                        <div className="flex items-center gap-2 shrink-0">
                          {proc?.properties.cpt_code ? (
                            <span className="text-[9px] font-mono text-neutral-400">{String(proc.properties.cpt_code)}</span>
                          ) : null}
                          <Badge variant={markType === "firm" ? "success" : markType === "conditional" ? "warning" : "neutral"} className="text-[9px]">
                            {markType}
                          </Badge>
                        </div>
                      </div>
                    );
                  })}
                  {procsAtVisit.length === 0 && (
                    <div className="px-3 py-3 text-xs text-neutral-400 text-center">No procedures at this visit</div>
                  )}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ─── Procedures ─────────────────────────────────────────────────────────

function ProceduresTab({ procs, schedule, expandedProc, setExpandedProc }: {
  procs: SMBGraphNode[]; schedule: SMBScheduleEntry[];
  expandedProc: string | null; setExpandedProc: (v: string | null) => void;
}) {
  const sorted = [...procs].sort((a, b) => String(a.label).localeCompare(String(b.label)));
  const categories = [...new Set(procs.map(p => String(p.properties.category || "Unknown")))].sort();

  return (
    <div className="p-4 space-y-4">
      {categories.map(cat => {
        const catProcs = sorted.filter(p => String(p.properties.category || "Unknown") === cat);
        return (
          <div key={cat}>
            <h3 className="text-xs font-semibold text-neutral-400 uppercase tracking-wider mb-2">{cat} ({catProcs.length})</h3>
            <div className="bg-white rounded-xl border border-neutral-200 divide-y divide-neutral-100">
              {catProcs.map(p => {
                const sched = schedule.find(s => s.canonical_name === p.label || s.procedure === p.label);
                const isExpanded = expandedProc === p.id;
                return (
                  <div key={p.id}>
                    <button onClick={() => setExpandedProc(isExpanded ? null : p.id)} className="w-full text-left px-4 py-2.5 hover:bg-neutral-50 transition-colors">
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-2 min-w-0">
                          <span className="text-sm text-neutral-800 truncate">{p.label}</span>
                          {p.properties.cpt_code ? (
                            <span className="text-[9px] font-mono bg-emerald-50 text-emerald-700 px-1.5 py-0.5 rounded">{String(p.properties.cpt_code)}</span>
                          ) : (
                            <span className="text-[9px] bg-neutral-100 text-neutral-400 px-1.5 py-0.5 rounded">No CPT</span>
                          )}
                        </div>
                        {sched && (
                          <div className="flex items-center gap-2 text-xs">
                            <span className="text-emerald-600 font-semibold">{sched.firm_occurrences}</span>
                            {(sched.conditional_occurrences || 0) > 0 && <span className="text-amber-600">+{sched.conditional_occurrences}</span>}
                            <span className="text-neutral-400">=</span>
                            <span className="font-bold text-neutral-800">{sched.total_occurrences}</span>
                          </div>
                        )}
                      </div>
                    </button>
                    {isExpanded && sched && (
                      <div className="px-4 pb-3 text-xs text-neutral-600 bg-neutral-50 space-y-1">
                        <div><strong>Raw name:</strong> {String(p.properties.raw_name || p.label)}</div>
                        <div><strong>Cost tier:</strong> {String(p.properties.cost_tier || "—")}</div>
                        <div><strong>Visits:</strong> {sched.firm_occurrences} firm, {sched.conditional_occurrences || 0} conditional, {sched.total_occurrences} total</div>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          </div>
        );
      })}
    </div>
  );
}

// ─── Gap Analysis ───────────────────────────────────────────────────────

function GapAnalysisTab({ schedule, procs, modelInfo }: {
  schedule: SMBScheduleEntry[]; procs: SMBGraphNode[]; modelInfo: SMBModelInfo;
}) {
  const noCpt = procs.filter(p => !p.properties.cpt_code);
  const unknownCat = procs.filter(p => String(p.properties.category) === "Unknown");
  const lowFreq = schedule.filter(s => s.total_occurrences <= 1 && s.firm_occurrences === 0);
  const highFreq = schedule.filter(s => (s.total_occurrences || 0) > 20);

  const issues: { severity: string; title: string; detail: string; count: number }[] = [];
  if (noCpt.length > 0) issues.push({ severity: "warning", title: "Procedures without CPT codes", detail: noCpt.map(p => p.label).join(", "), count: noCpt.length });
  if (unknownCat.length > 0) issues.push({ severity: "error", title: "Unmapped procedures (Unknown category)", detail: unknownCat.map(p => p.label).join(", "), count: unknownCat.length });
  if (lowFreq.length > 0) issues.push({ severity: "info", title: "Procedures with 0 firm visits", detail: lowFreq.map(s => s.canonical_name || s.procedure).join(", "), count: lowFreq.length });
  if (highFreq.length > 0) issues.push({ severity: "info", title: "High-frequency procedures (>20 occurrences)", detail: highFreq.map(s => `${s.canonical_name || s.procedure} (${s.total_occurrences})`).join(", "), count: highFreq.length });
  modelInfo.validation_errors.forEach(e => issues.push({ severity: "error", title: "Validation error", detail: e, count: 1 }));
  modelInfo.validation_warnings.forEach(w => issues.push({ severity: "warning", title: "Validation warning", detail: w, count: 1 }));

  const sevColors: Record<string, string> = {
    error: "border-red-200 bg-red-50 text-red-800",
    warning: "border-amber-200 bg-amber-50 text-amber-800",
    info: "border-blue-200 bg-blue-50 text-blue-800",
  };

  return (
    <div className="p-4 space-y-3">
      <div className="flex items-center justify-between mb-2">
        <h3 className="text-sm font-semibold text-neutral-800">Gap Analysis</h3>
        <Badge variant={issues.length === 0 ? "success" : issues.some(i => i.severity === "error") ? "danger" : "warning"}>
          {issues.length === 0 ? "No gaps found" : `${issues.length} issue${issues.length > 1 ? "s" : ""}`}
        </Badge>
      </div>

      {issues.length === 0 && (
        <div className="bg-emerald-50 rounded-xl border border-emerald-200 p-6 text-center">
          <p className="text-sm text-emerald-700 font-medium">All procedures mapped, all validations passed</p>
          <p className="text-[11px] text-emerald-600 mt-1">This protocol model is ready for budget calculation</p>
        </div>
      )}

      {issues.map((issue, i) => (
        <div key={i} className={cn("rounded-xl border p-4", sevColors[issue.severity])}>
          <div className="flex items-center justify-between mb-1">
            <h4 className="text-xs font-semibold">{issue.title}</h4>
            <span className="text-[10px] font-mono">{issue.count}</span>
          </div>
          <p className="text-[11px] leading-relaxed opacity-80">{issue.detail}</p>
        </div>
      ))}
    </div>
  );
}

// ─── Assistant ──────────────────────────────────────────────────────────

function AssistantTab({ messages, chatInput, chatLoading, onInputChange, onSend, chatEnd }: {
  messages: ChatMessage[]; chatInput: string; chatLoading: boolean;
  onInputChange: (v: string) => void; onSend: () => void;
  chatEnd: React.RefObject<HTMLDivElement | null>;
}) {
  const quickActions = [
    { label: "Summarize study design", q: "Summarize the study design including arms, phases, and duration" },
    { label: "List inclusion criteria", q: "What are the key inclusion criteria?" },
    { label: "Conditional procedures", q: "Which procedures are conditional and what are their conditions?" },
    { label: "Visit schedule overview", q: "Give me an overview of the visit schedule with key timepoints" },
    { label: "Unmapped procedures", q: "Are there any procedures that are not mapped to CPT codes?" },
    { label: "Footnote summary", q: "Summarize all footnotes and how they affect the schedule" },
    { label: "Budget impact items", q: "What are the highest-cost procedures and their frequency?" },
    { label: "Safety assessments", q: "List all safety-related assessments and their timing" },
  ];

  return (
    <div className="flex flex-col h-full">
      <div className="flex-1 overflow-y-auto p-4 space-y-3">
        {messages.length === 0 && (
          <div className="py-6">
            <h3 className="text-sm font-semibold text-neutral-700 mb-1">Protocol Assistant</h3>
            <p className="text-xs text-neutral-400 mb-4">Ask questions grounded in the structured protocol model. The assistant has access to visits, procedures, footnotes, and schedule data.</p>
            <div className="grid grid-cols-2 gap-2">
              {quickActions.map(a => (
                <button key={a.label} onClick={() => { onInputChange(a.q); }}
                  className="text-left px-3 py-2 text-[11px] bg-white border border-neutral-200 rounded-lg text-neutral-600 hover:bg-blue-50 hover:border-blue-200 transition-colors leading-snug">
                  {a.label}
                </button>
              ))}
            </div>
          </div>
        )}
        {messages.map((m, i) => (
          <div key={i} className={cn("flex", m.role === "user" ? "justify-end" : "justify-start")}>
            <div className={cn("max-w-[85%] px-4 py-2.5 rounded-2xl text-sm leading-relaxed whitespace-pre-wrap",
              m.role === "user" ? "bg-brand-primary text-white rounded-br-md" : "bg-white border border-neutral-200 text-neutral-700 rounded-bl-md"
            )}>{m.content}</div>
          </div>
        ))}
        {chatLoading && (
          <div className="flex justify-start">
            <div className="bg-white border border-neutral-200 px-4 py-3 rounded-2xl rounded-bl-md">
              <div className="flex gap-1.5"><div className="w-2 h-2 rounded-full bg-neutral-300 animate-bounce" /><div className="w-2 h-2 rounded-full bg-neutral-300 animate-bounce" style={{ animationDelay: "0.15s" }} /><div className="w-2 h-2 rounded-full bg-neutral-300 animate-bounce" style={{ animationDelay: "0.3s" }} /></div>
            </div>
          </div>
        )}
        <div ref={chatEnd} />
      </div>
      <div className="p-3 border-t border-neutral-200 bg-white">
        <div className="flex gap-2">
          <input type="text" value={chatInput} onChange={e => onInputChange(e.target.value)}
            onKeyDown={e => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); onSend(); } }}
            placeholder="Ask about this protocol..." disabled={chatLoading}
            className="flex-1 px-4 py-2.5 text-sm border border-neutral-200 rounded-xl bg-neutral-50 focus:outline-none focus:ring-2 focus:ring-brand-primary/30 focus:border-brand-primary focus:bg-white" />
          <button onClick={onSend} disabled={!chatInput.trim() || chatLoading}
            className={cn("px-4 py-2.5 rounded-xl text-sm font-medium transition-colors",
              chatInput.trim() && !chatLoading ? "bg-brand-primary text-white hover:bg-brand-french" : "bg-neutral-100 text-neutral-400 cursor-not-allowed"
            )}>Send</button>
        </div>
      </div>
    </div>
  );
}
