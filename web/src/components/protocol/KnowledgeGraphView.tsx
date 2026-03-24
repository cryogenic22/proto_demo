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
  Visit: "📅", Procedure: "🔬", Footnote: "📝",
  ScheduleEntry: "✓", Phase: "📋", Document: "📄",
};

// ── Main Component ─────────────────────────────────────────────────────────

export function KnowledgeGraphView({ protocolId }: Props) {
  const [status, setStatus] = useState<"loading" | "building" | "ready" | "error">("loading");
  const [modelInfo, setModelInfo] = useState<SMBModelInfo | null>(null);
  const [graph, setGraph] = useState<SMBGraph | null>(null);
  const [schedule, setSchedule] = useState<SMBScheduleEntry[]>([]);
  const [error, setError] = useState("");
  const [activeSection, setActiveSection] = useState<"overview" | "visits" | "procedures" | "schedule" | "agent">("overview");

  // Chat state
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [chatInput, setChatInput] = useState("");
  const [chatLoading, setChatLoading] = useState(false);
  const chatEndRef = useRef<HTMLDivElement>(null);

  // Load data
  useEffect(() => {
    let cancelled = false;
    async function load() {
      setStatus("building");
      try {
        // Build if needed, then fetch
        try { await getSMBModel(protocolId); } catch {
          await buildSMBModel(protocolId);
        }
        if (cancelled) return;
        const [info, g, sched] = await Promise.all([
          getSMBModel(protocolId),
          getSMBGraph(protocolId),
          getSMBSchedule(protocolId).then(r => r.schedule).catch(() => []),
        ]);
        if (!cancelled) {
          setModelInfo(info);
          setGraph(g);
          setSchedule(sched);
          setStatus("ready");
        }
      } catch (e) {
        if (!cancelled) { setError(String(e)); setStatus("error"); }
      }
    }
    load();
    return () => { cancelled = true; };
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
    { key: "overview", label: "Overview", icon: "📊" },
    { key: "visits", label: `Visits (${visits.length})`, icon: "📅" },
    { key: "procedures", label: `Procedures (${procedures.length})`, icon: "🔬" },
    { key: "schedule", label: `Schedule (${entries.length})`, icon: "📋" },
    { key: "agent", label: "Ask Agent", icon: "💬" },
  ] as const;

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
          />
        )}
        {activeSection === "visits" && <VisitSection visits={visits} graph={graph} />}
        {activeSection === "procedures" && <ProcedureSection procedures={procedures} schedule={schedule} />}
        {activeSection === "schedule" && <ScheduleSection schedule={schedule} />}
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

function OverviewSection({ modelInfo, graph, visits, procedures, footnotes, entries }: {
  modelInfo: SMBModelInfo;
  graph: SMBGraph;
  visits: SMBGraphNode[];
  procedures: SMBGraphNode[];
  footnotes: SMBGraphNode[];
  entries: SMBGraphNode[];
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
              <div className="w-12 h-12 rounded-xl bg-brand-primary/10 flex items-center justify-center text-xl">📄</div>
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
              <span className="shrink-0 mt-0.5">●</span> {e}
            </div>
          ))}
          {modelInfo.validation_warnings.map((w, i) => (
            <div key={i} className="flex items-start gap-2 text-xs text-amber-600 mb-1">
              <span className="shrink-0 mt-0.5">▲</span> {w}
            </div>
          ))}
        </div>
      )}

      {/* Visit timeline */}
      {modelInfo.timeline && modelInfo.timeline.length > 0 && (
        <div className="bg-white rounded-xl border border-neutral-200 p-4">
          <h3 className="text-xs font-semibold text-neutral-800 uppercase tracking-wider mb-3">Visit Timeline</h3>
          <div className="flex items-end gap-1 overflow-x-auto pb-2">
            {modelInfo.timeline.slice(0, 20).map((v, i) => (
              <div key={i} className="flex flex-col items-center min-w-[48px]">
                <div
                  className="w-8 bg-blue-500 rounded-t"
                  style={{ height: `${Math.max(8, (v.procedure_count || 0) * 3)}px` }}
                  title={`${v.procedure_count || 0} procedures`}
                />
                <div className="text-[9px] text-neutral-500 mt-1 text-center leading-tight">{v.visit_name?.slice(0, 8)}</div>
                {v.day_number != null && (
                  <div className="text-[8px] text-neutral-400">D{v.day_number}</div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function StructureCard({ type, count, description, items }: {
  type: string; count: number; description: string; items: string[];
}) {
  const colors = TYPE_COLORS[type] || TYPE_COLORS.ScheduleEntry;
  const icon = TYPE_ICONS[type] || "●";
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
              {v.properties.day_number != null ? `D${v.properties.day_number}` : "—"}
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
              <div className="w-10 h-10 rounded-lg bg-emerald-100 flex items-center justify-center text-lg">🔬</div>
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
                <td className="px-2 py-2 font-mono text-neutral-500">{s.cpt_code || "—"}</td>
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
            <div className="text-3xl mb-3">💬</div>
            <h3 className="text-sm font-semibold text-neutral-700">Protocol Agent</h3>
            <p className="text-xs text-neutral-400 mt-1 max-w-sm mx-auto">
              Ask questions about this protocol. The agent uses the structured model
              to give grounded answers from the actual document.
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
              "max-w-[80%] px-4 py-2.5 rounded-2xl text-sm leading-relaxed",
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
