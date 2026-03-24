"use client";

import { useEffect, useState, useRef, useCallback, useMemo } from "react";
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
  type SMBVisitTimeline,
} from "@/lib/api";
import { cn } from "@/lib/utils";
import { Badge } from "@/components/ui/Badge";

// ── Types ──────────────────────────────────────────────────────────────────

interface Props {
  protocolId: string;
}

interface ChatMessage {
  role: "user" | "assistant";
  content: string;
  timestamp: Date;
}

// ── Color config ───────────────────────────────────────────────────────────

const TYPE_COLORS: Record<string, { bg: string; text: string; border: string }> = {
  Visit:         { bg: "bg-blue-50",   text: "text-blue-700",   border: "border-blue-200" },
  Procedure:     { bg: "bg-emerald-50", text: "text-emerald-700", border: "border-emerald-200" },
  Footnote:      { bg: "bg-amber-50",  text: "text-amber-700",  border: "border-amber-200" },
  ScheduleEntry: { bg: "bg-neutral-50", text: "text-neutral-600", border: "border-neutral-200" },
  Phase:         { bg: "bg-purple-50", text: "text-purple-700", border: "border-purple-200" },
  Document:      { bg: "bg-red-50",    text: "text-red-700",    border: "border-red-200" },
};

const TYPE_ICONS: Record<string, string> = {
  Visit: "\u{1F4C5}", Procedure: "\u{1F52C}", Footnote: "\u{1F4DD}",
  ScheduleEntry: "\u2713", Phase: "\u{1F4CB}", Document: "\u{1F4C4}",
};

// ── localStorage helper ────────────────────────────────────────────────────

const KG_ENABLED_KEY = "protoextract_kg_enabled";

function getKGEnabled(): boolean {
  if (typeof window === "undefined") return true;
  const stored = localStorage.getItem(KG_ENABLED_KEY);
  return stored === null ? true : stored === "true";
}

function setKGEnabled(val: boolean): void {
  if (typeof window !== "undefined") {
    localStorage.setItem(KG_ENABLED_KEY, String(val));
  }
}

// ── Visit phase classification ─────────────────────────────────────────────

type VisitPhase = "screening" | "treatment" | "followup";

function classifyVisitPhase(visitName: string, dayNumber: number | null): VisitPhase {
  const lower = visitName.toLowerCase();
  if (lower.includes("screen") || lower.includes("baseline") || lower.includes("eligib")) {
    return "screening";
  }
  if (lower.includes("follow") || lower.includes("end of study") || lower.includes("eos")
      || lower.includes("safety") || lower.includes("termination") || lower.includes("post")) {
    return "followup";
  }
  return "treatment";
}

const PHASE_COLORS: Record<VisitPhase, { node: string; text: string; bg: string; label: string }> = {
  screening: { node: "#9ca3af", text: "text-neutral-600", bg: "bg-neutral-100", label: "Screening" },
  treatment: { node: "#3b82f6", text: "text-blue-700", bg: "bg-blue-100", label: "Treatment" },
  followup:  { node: "#10b981", text: "text-emerald-700", bg: "bg-emerald-100", label: "Follow-up" },
};

// ── Main Component ─────────────────────────────────────────────────────────

export function KnowledgeGraphView({ protocolId }: Props) {
  const [status, setStatus] = useState<"loading" | "building" | "ready" | "error">("loading");
  const [modelInfo, setModelInfo] = useState<SMBModelInfo | null>(null);
  const [graph, setGraph] = useState<SMBGraph | null>(null);
  const [schedule, setSchedule] = useState<SMBScheduleEntry[]>([]);
  const [error, setError] = useState("");
  const [activeSection, setActiveSection] = useState<"overview" | "visits" | "procedures" | "schedule" | "settings" | "agent">("overview");

  // Settings state
  const [kgEnabled, setKGEnabledState] = useState(true);
  const [rebuilding, setRebuilding] = useState(false);

  // Chat state
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [chatInput, setChatInput] = useState("");
  const [chatLoading, setChatLoading] = useState(false);
  const chatEndRef = useRef<HTMLDivElement>(null);

  // Init kgEnabled from localStorage
  useEffect(() => {
    setKGEnabledState(getKGEnabled());
  }, []);

  // Load data
  const loadData = useCallback(async () => {
    setStatus("building");
    try {
      try { await getSMBModel(protocolId); } catch {
        await buildSMBModel(protocolId);
      }
      const [info, g, sched] = await Promise.all([
        getSMBModel(protocolId),
        getSMBGraph(protocolId),
        getSMBSchedule(protocolId).then(r => r.schedule).catch(() => [] as SMBScheduleEntry[]),
      ]);
      setModelInfo(info);
      setGraph(g);
      setSchedule(sched);
      setStatus("ready");
    } catch (e) {
      setError(String(e));
      setStatus("error");
    }
  }, [protocolId]);

  useEffect(() => {
    let cancelled = false;
    loadData().then(() => {
      if (cancelled) {
        // Reset to loading if cancelled (component unmounted during load)
      }
    });
    return () => { cancelled = true; };
  }, [loadData]);

  // Rebuild handler
  const handleRebuild = useCallback(async () => {
    setRebuilding(true);
    try {
      await buildSMBModel(protocolId);
      const [info, g, sched] = await Promise.all([
        getSMBModel(protocolId),
        getSMBGraph(protocolId),
        getSMBSchedule(protocolId).then(r => r.schedule).catch(() => [] as SMBScheduleEntry[]),
      ]);
      setModelInfo(info);
      setGraph(g);
      setSchedule(sched);
      setStatus("ready");
    } catch (e) {
      setError(String(e));
    } finally {
      setRebuilding(false);
    }
  }, [protocolId]);

  // Chat scroll
  useEffect(() => { chatEndRef.current?.scrollIntoView({ behavior: "smooth" }); }, [messages]);

  const handleAsk = useCallback(async () => {
    const q = chatInput.trim();
    if (!q || chatLoading) return;
    setChatInput("");
    setMessages(prev => [...prev, { role: "user", content: q, timestamp: new Date() }]);
    setChatLoading(true);
    try {
      const resp = await askProtocol(protocolId, q);
      setMessages(prev => [...prev, {
        role: "assistant",
        content: resp.content || JSON.stringify(resp),
        timestamp: new Date(),
      }]);
    } catch {
      setMessages(prev => [...prev, {
        role: "assistant",
        content: "Sorry, I couldn't process that question. The protocol agent may not be available.",
        timestamp: new Date(),
      }]);
    } finally {
      setChatLoading(false);
    }
  }, [chatInput, chatLoading, protocolId]);

  if (status === "loading" || status === "building") {
    return (
      <div className="flex items-center justify-center py-20">
        <div className="text-center">
          <div className="w-8 h-8 border-2 border-brand-primary border-t-transparent rounded-full animate-spin mx-auto mb-3" />
          <p className="text-sm text-neutral-500">Building protocol intelligence model...</p>
          <p className="text-[11px] text-neutral-400 mt-1">Analyzing visits, procedures, footnotes, and relationships</p>
        </div>
      </div>
    );
  }

  if (status === "error") {
    return (
      <div className="p-6 text-center">
        <p className="text-sm text-red-600">Failed to build protocol model</p>
        <p className="text-xs text-neutral-400 mt-1">{error}</p>
      </div>
    );
  }

  if (!modelInfo || !graph) return null;

  const visits = graph.nodes.filter(n => n.type === "Visit");
  const procedures = graph.nodes.filter(n => n.type === "Procedure");
  const footnotes = graph.nodes.filter(n => n.type === "Footnote");
  const entries = graph.nodes.filter(n => n.type === "ScheduleEntry");
  const firmCount = entries.filter(e => e.properties.mark_type === "firm").length;
  const condCount = entries.filter(e => e.properties.mark_type === "conditional").length;
  const spanCount = entries.filter(e => e.properties.is_span).length;

  const SECTIONS = [
    { key: "overview" as const, label: "Overview", icon: "\u{1F4CA}" },
    { key: "visits" as const, label: `Visits (${visits.length})`, icon: "\u{1F4C5}" },
    { key: "procedures" as const, label: `Procedures (${procedures.length})`, icon: "\u{1F52C}" },
    { key: "schedule" as const, label: `Schedule (${entries.length})`, icon: "\u{1F4CB}" },
    { key: "agent" as const, label: "Ask Agent", icon: "\u{1F4AC}" },
    { key: "settings" as const, label: "Settings", icon: "\u2699\uFE0F" },
  ];

  return (
    <div className="h-full flex flex-col">
      {/* Stats bar */}
      <div className="px-4 py-3 bg-white border-b border-neutral-200 flex items-center gap-4 flex-wrap">
        <StatPill label="Visits" value={visits.length} color="blue" />
        <StatPill label="Procedures" value={procedures.length} color="emerald" />
        <StatPill label="Firm" value={firmCount} color="sky" />
        <StatPill label="Conditional" value={condCount} color="amber" />
        {spanCount > 0 && <StatPill label="Spans" value={spanCount} color="purple" />}
        <StatPill label="Footnotes" value={footnotes.length} color="orange" />
        <div className="ml-auto flex items-center gap-2 text-[10px] text-neutral-400">
          <span>Built in {modelInfo.build_time_seconds.toFixed(1)}s</span>
          {modelInfo.validation_passed
            ? <Badge variant="success">Validated</Badge>
            : <Badge variant="warning">{modelInfo.validation_errors.length} errors</Badge>
          }
          {modelInfo.inference_rules_fired.length > 0 && (
            <Badge variant="neutral">{modelInfo.inference_rules_fired.length} rules applied</Badge>
          )}
        </div>
      </div>

      {/* Section tabs */}
      <div className="px-4 bg-white border-b border-neutral-200 flex items-center gap-1">
        {SECTIONS.map(s => (
          <button
            key={s.key}
            onClick={() => setActiveSection(s.key)}
            className={cn(
              "px-3 py-2 text-xs font-medium border-b-2 transition-colors",
              activeSection === s.key
                ? "border-brand-primary text-brand-primary"
                : "border-transparent text-neutral-500 hover:text-neutral-700"
            )}
          >
            <span className="mr-1">{s.icon}</span> {s.label}
          </button>
        ))}
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto bg-neutral-50">
        {activeSection === "overview" && (
          <OverviewSection
            modelInfo={modelInfo}
            graph={graph}
            visits={visits}
            procedures={procedures}
            footnotes={footnotes}
            entries={entries}
            schedule={schedule}
          />
        )}
        {activeSection === "visits" && <VisitSection visits={visits} graph={graph} />}
        {activeSection === "procedures" && <ProcedureSection procedures={procedures} schedule={schedule} />}
        {activeSection === "schedule" && <ScheduleSection schedule={schedule} />}
        {activeSection === "settings" && (
          <SettingsSection
            modelInfo={modelInfo}
            graph={graph}
            kgEnabled={kgEnabled}
            onToggleKG={(val) => { setKGEnabledState(val); setKGEnabled(val); }}
            rebuilding={rebuilding}
            onRebuild={handleRebuild}
          />
        )}
        {activeSection === "agent" && (
          <AgentSection
            messages={messages}
            chatInput={chatInput}
            chatLoading={chatLoading}
            onInputChange={setChatInput}
            onSend={handleAsk}
            chatEndRef={chatEndRef}
            protocolId={protocolId}
          />
        )}
      </div>
    </div>
  );
}

// ── Sub-components ─────────────────────────────────────────────────────────

function StatPill({ label, value, color }: { label: string; value: number; color: string }) {
  const colors: Record<string, string> = {
    blue: "bg-blue-100 text-blue-700",
    emerald: "bg-emerald-100 text-emerald-700",
    sky: "bg-sky-100 text-sky-700",
    amber: "bg-amber-100 text-amber-700",
    purple: "bg-purple-100 text-purple-700",
    orange: "bg-orange-100 text-orange-700",
  };
  return (
    <span className={cn("px-2.5 py-1 rounded-full text-xs font-semibold tabular-nums", colors[color] || colors.blue)}>
      {value} <span className="font-normal opacity-70">{label}</span>
    </span>
  );
}

// ── Overview Section ───────────────────────────────────────────────────────

function OverviewSection({ modelInfo, graph, visits, procedures, footnotes, entries, schedule }: {
  modelInfo: SMBModelInfo;
  graph: SMBGraph;
  visits: SMBGraphNode[];
  procedures: SMBGraphNode[];
  footnotes: SMBGraphNode[];
  entries: SMBGraphNode[];
  schedule: SMBScheduleEntry[];
}) {
  const firmEntries = entries.filter(e => e.properties.mark_type === "firm");
  const condEntries = entries.filter(e => e.properties.mark_type === "conditional");

  return (
    <div className="p-4 space-y-4">
      {/* Protocol identity card */}
      <div className="bg-white rounded-xl border border-neutral-200 p-5">
        {(() => {
          const meta = graph.metadata || {};
          const title = String(meta["title"] || graph.document_id || "Protocol");
          const sponsor = meta["sponsor"] ? String(meta["sponsor"]) : "";
          const phase = meta["phase"] ? String(meta["phase"]) : "";
          const ta = meta["therapeutic_area"] ? String(meta["therapeutic_area"]) : "";
          return (
            <div className="flex items-start gap-4">
              <div className="w-12 h-12 rounded-xl bg-brand-primary/10 flex items-center justify-center text-xl">{"\u{1F4C4}"}</div>
              <div className="flex-1 min-w-0">
                <h2 className="text-base font-semibold text-neutral-800">{title}</h2>
                <div className="flex items-center gap-3 mt-1 text-xs text-neutral-500">
                  {sponsor && <span>Sponsor: <strong>{sponsor}</strong></span>}
                  {phase && <span>Phase: <strong>{phase}</strong></span>}
                  {ta && <span>TA: <strong>{ta}</strong></span>}
                </div>
              </div>
            </div>
          );
        })()}
      </div>

      {/* Model structure cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <StructureCard type="Visit" count={visits.length} description="Scheduled time points" items={visits.slice(0, 5).map(v => v.label)} />
        <StructureCard type="Procedure" count={procedures.length} description="Clinical procedures mapped" items={procedures.slice(0, 5).map(p => p.label)} />
        <StructureCard type="ScheduleEntry" count={entries.length} description={`${firmEntries.length} firm, ${condEntries.length} conditional`} items={[]} />
        <StructureCard type="Footnote" count={footnotes.length} description="Modifiers resolved" items={footnotes.slice(0, 3).map(f => `${f.properties.footnote_marker}: ${String(f.properties.classification || "")}`)} />
      </div>

      {/* Inference trail */}
      {modelInfo.inference_rules_fired.length > 0 && (
        <div className="bg-white rounded-xl border border-neutral-200 p-4">
          <h3 className="text-xs font-semibold text-neutral-800 uppercase tracking-wider mb-3">Inference Rules Applied</h3>
          <div className="flex flex-wrap gap-2">
            {modelInfo.inference_rules_fired.map(rule => (
              <div key={rule} className="flex items-center gap-2 px-3 py-1.5 bg-indigo-50 border border-indigo-200 rounded-lg">
                <span className="w-2 h-2 rounded-full bg-indigo-500" />
                <span className="text-xs font-medium text-indigo-700">{rule.replace("Inference", "")}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Validation status */}
      {(modelInfo.validation_errors.length > 0 || modelInfo.validation_warnings.length > 0) && (
        <div className="bg-white rounded-xl border border-neutral-200 p-4">
          <h3 className="text-xs font-semibold text-neutral-800 uppercase tracking-wider mb-3">Validation</h3>
          {modelInfo.validation_errors.map((e, i) => (
            <div key={i} className="flex items-start gap-2 text-xs text-red-600 mb-1">
              <span className="shrink-0 mt-0.5">{"\u25CF"}</span> {e}
            </div>
          ))}
          {modelInfo.validation_warnings.map((w, i) => (
            <div key={i} className="flex items-start gap-2 text-xs text-amber-600 mb-1">
              <span className="shrink-0 mt-0.5">{"\u25B2"}</span> {w}
            </div>
          ))}
        </div>
      )}

      {/* Visit Journey Timeline */}
      {modelInfo.timeline && modelInfo.timeline.length > 0 && (
        <VisitJourneyTimeline
          timeline={modelInfo.timeline}
          graph={graph}
          schedule={schedule}
        />
      )}
    </div>
  );
}

function StructureCard({ type, count, description, items }: {
  type: string; count: number; description: string; items: string[];
}) {
  const colors = TYPE_COLORS[type] || TYPE_COLORS.ScheduleEntry;
  const icon = TYPE_ICONS[type] || "\u25CF";
  return (
    <div className={cn("rounded-xl border p-4", colors.bg, colors.border)}>
      <div className="flex items-center gap-2 mb-1">
        <span className="text-lg">{icon}</span>
        <span className={cn("text-2xl font-bold tabular-nums", colors.text)}>{count}</span>
      </div>
      <div className={cn("text-[11px] font-medium", colors.text)}>{type === "ScheduleEntry" ? "Schedule Entries" : type + "s"}</div>
      <div className="text-[10px] text-neutral-500 mt-0.5">{description}</div>
      {items.length > 0 && (
        <div className="mt-2 space-y-0.5">
          {items.map((item, i) => (
            <div key={i} className="text-[10px] text-neutral-600 truncate">{item}</div>
          ))}
          {count > items.length && (
            <div className="text-[10px] text-neutral-400">+{count - items.length} more</div>
          )}
        </div>
      )}
    </div>
  );
}

// ── Visit Journey Timeline ────────────────────────────────────────────────

function VisitJourneyTimeline({ timeline, graph, schedule }: {
  timeline: SMBVisitTimeline[];
  graph: SMBGraph;
  schedule: SMBScheduleEntry[];
}) {
  const [expandedVisit, setExpandedVisit] = useState<string | null>(null);

  // Classify each visit and compute positions
  const visitData = useMemo(() => {
    const sorted = [...timeline].sort((a, b) => {
      const da = a.day_number ?? 999999;
      const db = b.day_number ?? 999999;
      return da - db;
    });

    const dayNumbers = sorted.map(v => v.day_number).filter((d): d is number => d !== null);
    const minDay = dayNumbers.length > 0 ? Math.min(...dayNumbers) : 0;
    const maxDay = dayNumbers.length > 0 ? Math.max(...dayNumbers) : 1;
    const dayRange = Math.max(maxDay - minDay, 1);

    return sorted.map((v, idx) => {
      const phase = classifyVisitPhase(v.visit_name, v.day_number);
      // Position: evenly spread if day numbers are missing, else proportional
      const hasDay = v.day_number !== null;
      const position = hasDay
        ? ((v.day_number! - minDay) / dayRange) * 100
        : (idx / Math.max(sorted.length - 1, 1)) * 100;

      return { ...v, phase, position, index: idx };
    });
  }, [timeline]);

  // Get top procedures for a visit from graph edges
  const getVisitProcedures = useCallback((visitName: string) => {
    const visitNode = graph.nodes.find(n => n.type === "Visit" && n.label === visitName);
    if (!visitNode) return [];

    const entryEdges = graph.edges.filter(e => e.type === "HAS_SCHEDULE_ENTRY" && e.source === visitNode.id);
    const procs: { name: string; markType: string; footnotes: string[] }[] = [];

    for (const edge of entryEdges) {
      const entryNode = graph.nodes.find(n => n.id === edge.target);
      if (!entryNode) continue;

      const procEdge = graph.edges.find(e => e.type === "FOR_PROCEDURE" && e.source === entryNode.id);
      if (!procEdge) continue;

      const procNode = graph.nodes.find(n => n.id === procEdge.target);
      if (!procNode) continue;

      const footnoteMarkers = entryNode.properties.footnote_markers as string[] | undefined;
      procs.push({
        name: procNode.label,
        markType: String(entryNode.properties.mark_type || "unknown"),
        footnotes: footnoteMarkers || [],
      });
    }

    return procs.sort((a, b) => a.name.localeCompare(b.name));
  }, [graph]);

  // Detect eDiary / span procedures (procedures that span multiple visits)
  const spanProcedures = useMemo(() => {
    const spans: { name: string; startIdx: number; endIdx: number }[] = [];
    const spanEntries = graph.nodes.filter(n => n.type === "ScheduleEntry" && n.properties.is_span);

    // Group by procedure
    const procSpans: Record<string, number[]> = {};
    for (const entry of spanEntries) {
      const procEdge = graph.edges.find(e => e.type === "FOR_PROCEDURE" && e.source === entry.id);
      if (!procEdge) continue;
      const procNode = graph.nodes.find(n => n.id === procEdge.target);
      if (!procNode) continue;

      const visitEdge = graph.edges.find(e => e.type === "HAS_SCHEDULE_ENTRY" && e.target === entry.id);
      if (!visitEdge) continue;
      const visitNode = graph.nodes.find(n => n.id === visitEdge.source);
      if (!visitNode) continue;

      const visitIdx = visitData.findIndex(v => v.visit_name === visitNode.label);
      if (visitIdx >= 0) {
        if (!procSpans[procNode.label]) procSpans[procNode.label] = [];
        procSpans[procNode.label].push(visitIdx);
      }
    }

    for (const [name, indices] of Object.entries(procSpans)) {
      if (indices.length >= 2) {
        spans.push({
          name,
          startIdx: Math.min(...indices),
          endIdx: Math.max(...indices),
        });
      }
    }

    return spans;
  }, [graph, visitData]);

  const isExpanded = expandedVisit !== null;

  return (
    <div className="bg-white rounded-xl border border-neutral-200 p-4">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-xs font-semibold text-neutral-800 uppercase tracking-wider">Visit Journey</h3>
        <div className="flex items-center gap-3">
          {(["screening", "treatment", "followup"] as VisitPhase[]).map(phase => (
            <div key={phase} className="flex items-center gap-1.5">
              <div className="w-2.5 h-2.5 rounded-full" style={{ backgroundColor: PHASE_COLORS[phase].node }} />
              <span className="text-[10px] text-neutral-500">{PHASE_COLORS[phase].label}</span>
            </div>
          ))}
        </div>
      </div>

      {/* Timeline SVG */}
      <div className="relative overflow-x-auto pb-2">
        <div className="min-w-[600px]">
          {/* Span bars (eDiary / continuous procedures) */}
          {spanProcedures.length > 0 && (
            <div className="mb-3 space-y-1">
              {spanProcedures.slice(0, 3).map((span, i) => {
                const leftPct = (span.startIdx / Math.max(visitData.length - 1, 1)) * 100;
                const widthPct = ((span.endIdx - span.startIdx) / Math.max(visitData.length - 1, 1)) * 100;
                return (
                  <div key={i} className="relative h-5 mx-8">
                    <div
                      className="absolute top-0 h-full rounded-full bg-purple-100 border border-purple-300 flex items-center"
                      style={{
                        left: `${leftPct}%`,
                        width: `${Math.max(widthPct, 2)}%`,
                        minWidth: "60px",
                      }}
                    >
                      <span className="text-[9px] text-purple-700 font-medium px-2 truncate">
                        {span.name}
                      </span>
                    </div>
                  </div>
                );
              })}
            </div>
          )}

          {/* Main timeline line */}
          <div className="relative mx-8">
            {/* Horizontal line */}
            <div className="absolute top-4 left-0 right-0 h-0.5 bg-neutral-200" />

            {/* Visit nodes */}
            <div className="relative flex justify-between" style={{ minHeight: "100px" }}>
              {visitData.map((v, i) => {
                const phase = PHASE_COLORS[v.phase];
                const isSelected = expandedVisit === v.visit_name;
                const topProcs = getVisitProcedures(v.visit_name).slice(0, 3);

                return (
                  <div
                    key={i}
                    className="flex flex-col items-center relative cursor-pointer group"
                    style={{ flex: "1 1 0", maxWidth: `${100 / visitData.length}%` }}
                    onClick={() => setExpandedVisit(isSelected ? null : v.visit_name)}
                  >
                    {/* Node circle */}
                    <div
                      className={cn(
                        "w-8 h-8 rounded-full flex items-center justify-center text-white text-[10px] font-bold z-10 transition-all",
                        "shadow-sm hover:shadow-md hover:scale-110",
                        isSelected && "ring-2 ring-offset-2 ring-blue-400 scale-110"
                      )}
                      style={{ backgroundColor: phase.node }}
                      title={`${v.visit_name} - ${v.procedure_count} procedures`}
                    >
                      {v.procedure_count}
                    </div>

                    {/* Visit label */}
                    <div className="mt-1.5 text-center">
                      <div className="text-[9px] font-medium text-neutral-700 leading-tight truncate max-w-[56px]">
                        {v.visit_name.length > 10 ? v.visit_name.slice(0, 9) + "\u2026" : v.visit_name}
                      </div>
                      {v.day_number !== null && (
                        <div className="text-[8px] text-neutral-400 tabular-nums">D{v.day_number}</div>
                      )}
                    </div>

                    {/* Top procedures preview (shown on hover via group) */}
                    {topProcs.length > 0 && (
                      <div className="hidden group-hover:block absolute top-full mt-1 z-20">
                        <div className="bg-white border border-neutral-200 rounded-lg shadow-lg p-2 min-w-[140px]">
                          {topProcs.map((p, j) => (
                            <div key={j} className="flex items-center gap-1.5 text-[9px] py-0.5">
                              <span className={cn(
                                "w-1.5 h-1.5 rounded-full shrink-0",
                                p.markType === "firm" ? "bg-emerald-500" : "bg-amber-400"
                              )} />
                              <span className="text-neutral-700 truncate">{p.name}</span>
                              {p.footnotes.length > 0 && (
                                <span className="text-neutral-400 text-[8px]">{p.footnotes.join(",")}</span>
                              )}
                            </div>
                          ))}
                          {v.procedure_count > 3 && (
                            <div className="text-[9px] text-neutral-400 mt-0.5">+{v.procedure_count - 3} more</div>
                          )}
                        </div>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      </div>

      {/* Expanded visit detail */}
      {expandedVisit && (() => {
        const v = visitData.find(vd => vd.visit_name === expandedVisit);
        if (!v) return null;
        const procs = getVisitProcedures(expandedVisit);
        const phase = PHASE_COLORS[v.phase];

        return (
          <div className="mt-3 bg-neutral-50 rounded-lg border border-neutral-200 p-4">
            <div className="flex items-center gap-3 mb-3">
              <div className={cn("px-2.5 py-1 rounded-full text-[10px] font-semibold", phase.bg, phase.text)}>
                {phase.label}
              </div>
              <h4 className="text-sm font-semibold text-neutral-800">{v.visit_name}</h4>
              {v.day_number !== null && (
                <span className="text-xs text-neutral-500">Day {v.day_number}</span>
              )}
              {(v.window_minus > 0 || v.window_plus > 0) && (
                <span className="text-[10px] text-neutral-400">
                  Window: -{v.window_minus}/+{v.window_plus} {v.window_unit?.toLowerCase() || "days"}
                </span>
              )}
              <button
                onClick={() => setExpandedVisit(null)}
                className="ml-auto text-xs text-neutral-400 hover:text-neutral-600"
              >
                Close
              </button>
            </div>

            {procs.length > 0 ? (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-1.5">
                {procs.map((p, i) => (
                  <div key={i} className="flex items-center gap-2 px-3 py-1.5 bg-white rounded-md border border-neutral-100">
                    <span className={cn(
                      "w-2 h-2 rounded-full shrink-0",
                      p.markType === "firm" ? "bg-emerald-500" : p.markType === "conditional" ? "bg-amber-400" : "bg-neutral-300"
                    )} />
                    <span className="text-[11px] text-neutral-700 flex-1 truncate">{p.name}</span>
                    <span className={cn(
                      "text-[9px] px-1.5 py-0.5 rounded",
                      p.markType === "firm"
                        ? "bg-emerald-50 text-emerald-600"
                        : p.markType === "conditional"
                          ? "bg-amber-50 text-amber-600"
                          : "bg-neutral-50 text-neutral-500"
                    )}>
                      {p.markType}
                    </span>
                    {p.footnotes.length > 0 && (
                      <span className="text-[9px] text-amber-500 font-mono">{p.footnotes.join(",")}</span>
                    )}
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-xs text-neutral-400">No procedures linked to this visit.</p>
            )}
          </div>
        );
      })()}
    </div>
  );
}

// ── Visit Section ──────────────────────────────────────────────────────────

function VisitSection({ visits, graph }: { visits: SMBGraphNode[]; graph: SMBGraph }) {
  const sorted = [...visits].sort((a, b) => ((a.properties.day_number as number) ?? 9999) - ((b.properties.day_number as number) ?? 9999));
  return (
    <div className="p-4 space-y-2">
      {sorted.map(v => {
        const entryEdges = graph.edges.filter(e => e.type === "HAS_SCHEDULE_ENTRY" && e.source === v.id);
        const procCount = entryEdges.length;
        return (
          <div key={v.id} className="bg-white rounded-lg border border-neutral-200 px-4 py-3 flex items-center gap-4">
            <div className="w-10 h-10 rounded-lg bg-blue-100 flex items-center justify-center text-blue-700 font-bold text-xs">
              {v.properties.day_number != null ? `D${v.properties.day_number}` : "\u2014"}
            </div>
            <div className="flex-1 min-w-0">
              <div className="text-sm font-medium text-neutral-800">{v.label}</div>
              <div className="text-[11px] text-neutral-500">
                {(v.properties.window_minus || v.properties.window_plus)
                  ? `Window: -${String(v.properties.window_minus ?? 0)}/+${String(v.properties.window_plus ?? 0)} days`
                  : "No window"}
                {v.properties.cycle != null && <span className="ml-2">Cycle {String(v.properties.cycle)}</span>}
                {Boolean(v.properties.is_unscheduled) && <Badge variant="warning" className="ml-2 text-[9px]">Unscheduled</Badge>}
              </div>
            </div>
            <div className="text-right">
              <div className="text-sm font-semibold text-neutral-700">{procCount}</div>
              <div className="text-[10px] text-neutral-400">procedures</div>
            </div>
          </div>
        );
      })}
    </div>
  );
}

// ── Procedure Section ──────────────────────────────────────────────────────

function ProcedureSection({ procedures, schedule }: { procedures: SMBGraphNode[]; schedule: SMBScheduleEntry[] }) {
  const sorted = [...procedures].sort((a, b) => a.label.localeCompare(b.label));
  return (
    <div className="p-4 space-y-2">
      {sorted.map(p => {
        const sched = schedule.find(s => s.procedure === p.label || s.canonical_name === p.label);
        return (
          <div key={p.id} className="bg-white rounded-lg border border-neutral-200 px-4 py-3">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-lg bg-emerald-100 flex items-center justify-center text-lg">{"\u{1F52C}"}</div>
              <div className="flex-1 min-w-0">
                <div className="text-sm font-medium text-neutral-800">{p.label}</div>
                <div className="flex items-center gap-2 mt-0.5 text-[11px] text-neutral-500">
                  {p.properties.cpt_code ? (
                    <span className="font-mono bg-neutral-100 px-1.5 py-0.5 rounded text-[10px]">
                      CPT {String(p.properties.cpt_code)}
                    </span>
                  ) : null}
                  <span>{String(p.properties.category ?? "Unknown")}</span>
                  <span className="capitalize">{String(p.properties.cost_tier ?? "").toLowerCase()}</span>
                </div>
              </div>
              {sched && (
                <div className="text-right">
                  <div className="text-sm font-semibold text-neutral-700">{sched.total_occurrences}</div>
                  <div className="text-[10px] text-neutral-400">
                    {sched.firm_occurrences} firm{(sched.conditional_occurrences || 0) > 0 ? `, ${sched.conditional_occurrences} cond` : ""}
                  </div>
                </div>
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}

// ── Schedule Section ───────────────────────────────────────────────────────

function ScheduleSection({ schedule }: { schedule: SMBScheduleEntry[] }) {
  const sorted = [...schedule].sort((a, b) => (b.total_occurrences || 0) - (a.total_occurrences || 0));
  return (
    <div className="p-4">
      <div className="bg-white rounded-xl border border-neutral-200 overflow-hidden">
        <table className="w-full text-xs">
          <thead>
            <tr className="bg-neutral-50 border-b border-neutral-200">
              <th className="text-left px-3 py-2 font-semibold text-neutral-600">Procedure</th>
              <th className="text-center px-2 py-2 font-semibold text-neutral-600">Firm</th>
              <th className="text-center px-2 py-2 font-semibold text-neutral-600">Cond</th>
              <th className="text-center px-2 py-2 font-semibold text-neutral-600">Total</th>
              <th className="text-left px-2 py-2 font-semibold text-neutral-600">CPT</th>
              <th className="text-left px-2 py-2 font-semibold text-neutral-600">Inference</th>
            </tr>
          </thead>
          <tbody>
            {sorted.map((s, i) => (
              <tr key={i} className="border-b border-neutral-100 hover:bg-neutral-50">
                <td className="px-3 py-2 font-medium text-neutral-800">{s.canonical_name || s.procedure}</td>
                <td className="text-center px-2 py-2 text-emerald-700 font-semibold">{s.firm_occurrences}</td>
                <td className="text-center px-2 py-2 text-amber-600">{s.conditional_occurrences || 0}</td>
                <td className="text-center px-2 py-2 font-bold text-neutral-800">{s.total_occurrences}</td>
                <td className="px-2 py-2 font-mono text-neutral-500">{s.cpt_code || "\u2014"}</td>
                <td className="px-2 py-2">
                  <div className="flex flex-wrap gap-1">
                    {((s as unknown as Record<string, unknown>)["inference_rules"] as string[] ?? []).map((r: string, j: number) => (
                      <span key={j} className="px-1.5 py-0.5 bg-indigo-50 text-indigo-600 rounded text-[9px]">
                        {r.replace("Inference", "")}
                      </span>
                    ))}
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

// ── Settings Section ──────────────────────────────────────────────────────

function SettingsSection({ modelInfo, graph, kgEnabled, onToggleKG, rebuilding, onRebuild }: {
  modelInfo: SMBModelInfo;
  graph: SMBGraph;
  kgEnabled: boolean;
  onToggleKG: (val: boolean) => void;
  rebuilding: boolean;
  onRebuild: () => void;
}) {
  const meta = graph.metadata || {};
  const ta = meta["therapeutic_area"] ? String(meta["therapeutic_area"]) : "Auto-detect";
  const domainConfig = meta["domain_config"] ? String(meta["domain_config"]) : graph.domain || "protocol";

  return (
    <div className="p-4 space-y-4">
      {/* Enable/disable toggle */}
      <div className="bg-white rounded-xl border border-neutral-200 p-5">
        <h3 className="text-xs font-semibold text-neutral-800 uppercase tracking-wider mb-4">Knowledge Graph Settings</h3>

        <div className="space-y-4">
          {/* Toggle */}
          <div className="flex items-center justify-between">
            <div>
              <div className="text-sm font-medium text-neutral-700">Enable Knowledge Graph</div>
              <div className="text-[11px] text-neutral-400 mt-0.5">
                When enabled, the KG model is built automatically on protocol load.
              </div>
            </div>
            <button
              onClick={() => onToggleKG(!kgEnabled)}
              className={cn(
                "relative inline-flex h-6 w-11 shrink-0 rounded-full border-2 border-transparent transition-colors cursor-pointer",
                kgEnabled ? "bg-brand-primary" : "bg-neutral-200"
              )}
            >
              <span
                className={cn(
                  "pointer-events-none inline-block h-5 w-5 rounded-full bg-white shadow-sm transition-transform",
                  kgEnabled ? "translate-x-5" : "translate-x-0"
                )}
              />
            </button>
          </div>

          {/* Rebuild button */}
          <div className="flex items-center justify-between">
            <div>
              <div className="text-sm font-medium text-neutral-700">Rebuild Model</div>
              <div className="text-[11px] text-neutral-400 mt-0.5">
                Force rebuild the structured model from the current protocol data.
              </div>
            </div>
            <button
              onClick={onRebuild}
              disabled={rebuilding}
              className={cn(
                "px-4 py-2 rounded-lg text-xs font-medium transition-colors",
                rebuilding
                  ? "bg-neutral-100 text-neutral-400 cursor-not-allowed"
                  : "bg-brand-primary text-white hover:bg-brand-french"
              )}
            >
              {rebuilding ? (
                <span className="flex items-center gap-2">
                  <span className="w-3 h-3 border border-neutral-300 border-t-transparent rounded-full animate-spin" />
                  Rebuilding...
                </span>
              ) : (
                "Rebuild Model"
              )}
            </button>
          </div>
        </div>
      </div>

      {/* Model information */}
      <div className="bg-white rounded-xl border border-neutral-200 p-5">
        <h3 className="text-xs font-semibold text-neutral-800 uppercase tracking-wider mb-4">Model Information</h3>

        <div className="grid grid-cols-2 gap-4">
          <InfoRow label="Therapeutic Area" value={ta} />
          <InfoRow label="Domain Config" value={domainConfig} />
          <InfoRow label="Build Time" value={`${modelInfo.build_time_seconds.toFixed(2)}s`} />
          <InfoRow label="Inference Rules" value={`${modelInfo.inference_rules_fired.length} rules applied`} />
          <InfoRow
            label="Validation"
            value={modelInfo.validation_passed ? "Passed" : `${modelInfo.validation_errors.length} errors`}
            valueClass={modelInfo.validation_passed ? "text-emerald-600" : "text-red-600"}
          />
          <InfoRow label="Entities" value={String(modelInfo.summary.total_entities)} />
          <InfoRow label="Relationships" value={String(modelInfo.summary.total_relationships)} />
          <InfoRow label="Model Version" value={`v${modelInfo.summary.version}`} />
        </div>

        {/* Entity type breakdown */}
        {modelInfo.summary.entity_types && (
          <div className="mt-4 pt-4 border-t border-neutral-100">
            <div className="text-[10px] font-semibold text-neutral-500 uppercase tracking-wider mb-2">Entity Breakdown</div>
            <div className="flex flex-wrap gap-2">
              {Object.entries(modelInfo.summary.entity_types).map(([type, count]) => (
                <span key={type} className="px-2 py-1 bg-neutral-50 border border-neutral-200 rounded text-[10px] text-neutral-600">
                  {type}: <strong>{count}</strong>
                </span>
              ))}
            </div>
          </div>
        )}

        {/* Inference rules list */}
        {modelInfo.inference_rules_fired.length > 0 && (
          <div className="mt-4 pt-4 border-t border-neutral-100">
            <div className="text-[10px] font-semibold text-neutral-500 uppercase tracking-wider mb-2">Inference Rules</div>
            <div className="flex flex-wrap gap-1.5">
              {modelInfo.inference_rules_fired.map(rule => (
                <span key={rule} className="px-2 py-1 bg-indigo-50 border border-indigo-200 rounded text-[10px] text-indigo-700">
                  {rule}
                </span>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

function InfoRow({ label, value, valueClass }: { label: string; value: string; valueClass?: string }) {
  return (
    <div>
      <div className="text-[10px] text-neutral-400 uppercase tracking-wider">{label}</div>
      <div className={cn("text-sm font-medium text-neutral-700 mt-0.5", valueClass)}>{value}</div>
    </div>
  );
}

// ── Agent Section ──────────────────────────────────────────────────────────

function AgentSection({ messages, chatInput, chatLoading, onInputChange, onSend, chatEndRef, protocolId }: {
  messages: ChatMessage[];
  chatInput: string;
  chatLoading: boolean;
  onInputChange: (v: string) => void;
  onSend: () => void;
  chatEndRef: React.RefObject<HTMLDivElement | null>;
  protocolId: string;
}) {
  const suggestions = [
    "What are the inclusion criteria?",
    "How many visits does this protocol have?",
    "Which procedures are conditional?",
    "What is the dosing regimen?",
    "Summarize the study design",
    "What footnotes modify the Schedule of Activities?",
  ];

  return (
    <div className="flex flex-col h-full">
      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-4 space-y-3">
        {messages.length === 0 && (
          <div className="text-center py-8">
            <div className="text-3xl mb-3">{"\u{1F4AC}"}</div>
            <h3 className="text-sm font-semibold text-neutral-700">Protocol Agent</h3>
            <p className="text-xs text-neutral-400 mt-1 max-w-sm mx-auto">
              Ask questions about this protocol. The agent uses the knowledge graph
              and document sections to give grounded answers with source citations.
            </p>
            <div className="flex flex-wrap gap-2 justify-center mt-4">
              {suggestions.map(s => (
                <button
                  key={s}
                  onClick={() => { onInputChange(s); }}
                  className="px-3 py-1.5 text-[11px] bg-white border border-neutral-200 rounded-lg text-neutral-600 hover:bg-neutral-50 hover:border-brand-primary transition-colors"
                >
                  {s}
                </button>
              ))}
            </div>
          </div>
        )}
        {messages.map((m, i) => (
          <div key={i} className={cn("flex", m.role === "user" ? "justify-end" : "justify-start")}>
            <div className={cn(
              "max-w-[80%] px-4 py-2.5 rounded-2xl text-sm leading-relaxed whitespace-pre-wrap",
              m.role === "user"
                ? "bg-brand-primary text-white rounded-br-md"
                : "bg-white border border-neutral-200 text-neutral-700 rounded-bl-md"
            )}>
              {m.content}
            </div>
          </div>
        ))}
        {chatLoading && (
          <div className="flex justify-start">
            <div className="bg-white border border-neutral-200 px-4 py-2.5 rounded-2xl rounded-bl-md">
              <div className="flex items-center gap-1.5">
                <div className="w-2 h-2 rounded-full bg-neutral-300 animate-bounce" />
                <div className="w-2 h-2 rounded-full bg-neutral-300 animate-bounce" style={{ animationDelay: "0.1s" }} />
                <div className="w-2 h-2 rounded-full bg-neutral-300 animate-bounce" style={{ animationDelay: "0.2s" }} />
              </div>
            </div>
          </div>
        )}
        <div ref={chatEndRef} />
      </div>

      {/* Input */}
      <div className="p-3 border-t border-neutral-200 bg-white">
        <div className="flex items-center gap-2">
          <input
            type="text"
            value={chatInput}
            onChange={e => onInputChange(e.target.value)}
            onKeyDown={e => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); onSend(); } }}
            placeholder="Ask about this protocol..."
            className="flex-1 px-4 py-2.5 text-sm border border-neutral-200 rounded-xl bg-neutral-50 focus:outline-none focus:ring-2 focus:ring-brand-primary/30 focus:border-brand-primary focus:bg-white"
            disabled={chatLoading}
          />
          <button
            onClick={onSend}
            disabled={!chatInput.trim() || chatLoading}
            className={cn(
              "px-4 py-2.5 rounded-xl text-sm font-medium transition-colors",
              chatInput.trim() && !chatLoading
                ? "bg-brand-primary text-white hover:bg-brand-french"
                : "bg-neutral-100 text-neutral-400 cursor-not-allowed"
            )}
          >
            Send
          </button>
        </div>
      </div>
    </div>
  );
}
