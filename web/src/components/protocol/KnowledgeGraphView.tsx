"use client";

import { useEffect, useState, useRef, useCallback, useMemo } from "react";
import {
  buildSMBModel,
  getSMBGraph,
  type SMBGraph,
  type SMBGraphNode,
  type SMBGraphEdge,
} from "@/lib/api";
import { cn } from "@/lib/utils";

// ── Color and size configuration ────────────────────────────────────────────

const NODE_COLORS: Record<string, string> = {
  Visit: "#3b82f6",       // blue
  Procedure: "#22c55e",   // green
  Footnote: "#f59e0b",    // amber
  ScheduleEntry: "#9ca3af", // gray
  Phase: "#a855f7",       // purple
  Document: "#ef4444",    // red
};

const NODE_RADII: Record<string, number> = {
  Document: 24,
  Visit: 16,
  Procedure: 16,
  Footnote: 12,
  ScheduleEntry: 6,
  Phase: 18,
};

const ENTITY_TYPE_ORDER = [
  "Document",
  "Visit",
  "Procedure",
  "Footnote",
  "ScheduleEntry",
  "Phase",
];

// ── Simple force-directed layout ────────────────────────────────────────────

interface SimNode {
  id: string;
  x: number;
  y: number;
  vx: number;
  vy: number;
  type: string;
  label: string;
  radius: number;
  data: SMBGraphNode;
}

interface SimEdge {
  source: string;
  target: string;
  type: string;
  data: SMBGraphEdge;
}

function runForceSimulation(
  nodes: SimNode[],
  edges: SimEdge[],
  width: number,
  height: number,
  iterations: number = 120,
): void {
  const nodeMap = new Map<string, SimNode>();
  for (const n of nodes) {
    nodeMap.set(n.id, n);
  }

  const repulsion = 800;
  const attraction = 0.005;
  const damping = 0.92;
  const centerGravity = 0.01;
  const cx = width / 2;
  const cy = height / 2;

  for (let iter = 0; iter < iterations; iter++) {
    // Repulsion between all nodes
    for (let i = 0; i < nodes.length; i++) {
      for (let j = i + 1; j < nodes.length; j++) {
        const a = nodes[i];
        const b = nodes[j];
        let dx = a.x - b.x;
        let dy = a.y - b.y;
        let dist = Math.sqrt(dx * dx + dy * dy) || 1;
        const force = repulsion / (dist * dist);
        const fx = (dx / dist) * force;
        const fy = (dy / dist) * force;
        a.vx += fx;
        a.vy += fy;
        b.vx -= fx;
        b.vy -= fy;
      }
    }

    // Attraction along edges
    for (const edge of edges) {
      const s = nodeMap.get(edge.source);
      const t = nodeMap.get(edge.target);
      if (!s || !t) continue;
      const dx = t.x - s.x;
      const dy = t.y - s.y;
      const dist = Math.sqrt(dx * dx + dy * dy) || 1;
      const force = dist * attraction;
      const fx = (dx / dist) * force;
      const fy = (dy / dist) * force;
      s.vx += fx;
      s.vy += fy;
      t.vx -= fx;
      t.vy -= fy;
    }

    // Center gravity
    for (const n of nodes) {
      n.vx += (cx - n.x) * centerGravity;
      n.vy += (cy - n.y) * centerGravity;
    }

    // Apply velocity and damping
    for (const n of nodes) {
      n.vx *= damping;
      n.vy *= damping;
      n.x += n.vx;
      n.y += n.vy;
      // Clamp to bounds
      n.x = Math.max(n.radius + 10, Math.min(width - n.radius - 10, n.x));
      n.y = Math.max(n.radius + 10, Math.min(height - n.radius - 10, n.y));
    }
  }
}

// ── Main Component ──────────────────────────────────────────────────────────

interface Props {
  protocolId: string;
}

export function KnowledgeGraphView({ protocolId }: Props) {
  const [status, setStatus] = useState<"idle" | "building" | "ready" | "error">("idle");
  const [graph, setGraph] = useState<SMBGraph | null>(null);
  const [errorMsg, setErrorMsg] = useState<string>("");
  const [selectedNode, setSelectedNode] = useState<SMBGraphNode | null>(null);
  const [typeFilter, setTypeFilter] = useState<Set<string>>(new Set());
  const [markFilter, setMarkFilter] = useState<string>("all");
  const [hoveredNode, setHoveredNode] = useState<string | null>(null);
  const svgRef = useRef<SVGSVGElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  // Build and fetch
  useEffect(() => {
    let cancelled = false;

    async function load() {
      setStatus("building");
      try {
        // Try to fetch existing graph first
        try {
          const g = await getSMBGraph(protocolId);
          if (!cancelled) {
            setGraph(g);
            setStatus("ready");
            return;
          }
        } catch {
          // Not built yet, build it
        }

        await buildSMBModel(protocolId);
        if (cancelled) return;

        const g = await getSMBGraph(protocolId);
        if (!cancelled) {
          setGraph(g);
          setStatus("ready");
        }
      } catch (e) {
        if (!cancelled) {
          setStatus("error");
          setErrorMsg(e instanceof Error ? e.message : "Unknown error");
        }
      }
    }

    load();
    return () => { cancelled = true; };
  }, [protocolId]);

  // Compute filtered nodes and edges
  const { simNodes, simEdges, width, height } = useMemo(() => {
    if (!graph) return { simNodes: [] as SimNode[], simEdges: [] as SimEdge[], width: 900, height: 600 };

    const W = 900;
    const H = 600;

    let filteredNodes = graph.nodes;

    // Apply type filter
    if (typeFilter.size > 0) {
      filteredNodes = filteredNodes.filter((n) => typeFilter.has(n.type));
    }

    // Apply mark filter
    if (markFilter !== "all") {
      filteredNodes = filteredNodes.filter((n) => {
        if (n.type !== "ScheduleEntry") return true;
        return (n.properties as Record<string, unknown>).mark_type === markFilter;
      });
    }

    const nodeIds = new Set(filteredNodes.map((n) => n.id));
    const filteredEdges = graph.edges.filter(
      (e) => nodeIds.has(e.source) && nodeIds.has(e.target)
    );

    // Create simulation nodes
    const sNodes: SimNode[] = filteredNodes.map((n, i) => ({
      id: n.id,
      x: W / 2 + (Math.random() - 0.5) * W * 0.7,
      y: H / 2 + (Math.random() - 0.5) * H * 0.7,
      vx: 0,
      vy: 0,
      type: n.type,
      label: n.label,
      radius: NODE_RADII[n.type] || 10,
      data: n,
    }));

    const sEdges: SimEdge[] = filteredEdges.map((e) => ({
      source: e.source,
      target: e.target,
      type: e.type,
      data: e,
    }));

    // Run layout
    if (sNodes.length > 0 && sNodes.length <= 500) {
      const iters = sNodes.length > 200 ? 60 : 120;
      runForceSimulation(sNodes, sEdges, W, H, iters);
    }

    return { simNodes: sNodes, simEdges: sEdges, width: W, height: H };
  }, [graph, typeFilter, markFilter]);

  // Summary stats
  const stats = useMemo(() => {
    if (!graph) return null;
    const counts = graph.entity_counts;
    const totalEntities = graph.nodes.length;
    const totalEdges = graph.edges.length;
    const visits = counts["Visit"] || 0;
    const procedures = counts["Procedure"] || 0;
    const scheduleEntries = counts["ScheduleEntry"] || 0;
    const footnotes = counts["Footnote"] || 0;

    let firmCount = 0;
    let conditionalCount = 0;
    for (const n of graph.nodes) {
      if (n.type === "ScheduleEntry") {
        const mt = (n.properties as Record<string, unknown>).mark_type;
        if (mt === "firm" || mt === "span") firmCount++;
        else if (mt === "conditional") conditionalCount++;
      }
    }

    return {
      totalEntities,
      totalEdges,
      visits,
      procedures,
      scheduleEntries,
      footnotes,
      firmCount,
      conditionalCount,
    };
  }, [graph]);

  const toggleTypeFilter = useCallback((type: string) => {
    setTypeFilter((prev) => {
      const next = new Set(prev);
      if (next.has(type)) next.delete(type);
      else next.add(type);
      return next;
    });
  }, []);

  // Truncate labels for rendering
  const truncLabel = (label: string, maxLen: number = 18) => {
    return label.length > maxLen ? label.substring(0, maxLen - 1) + "\u2026" : label;
  };

  // ── Loading / Error states ────────────────────────────────────────────

  if (status === "idle" || status === "building") {
    return (
      <div className="flex flex-col items-center justify-center py-20 gap-4">
        <div className="w-8 h-8 border-2 border-brand-primary border-t-transparent rounded-full animate-spin" />
        <p className="text-sm text-neutral-500">Building structured model...</p>
        <p className="text-xs text-neutral-400">This may take a few seconds</p>
      </div>
    );
  }

  if (status === "error") {
    return (
      <div className="flex flex-col items-center justify-center py-20 gap-3">
        <div className="w-10 h-10 rounded-full bg-red-100 flex items-center justify-center">
          <svg className="w-5 h-5 text-red-500" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
          </svg>
        </div>
        <p className="text-sm font-medium text-neutral-700">Failed to build model</p>
        <p className="text-xs text-neutral-400 max-w-md text-center">{errorMsg}</p>
        <button
          onClick={() => setStatus("idle")}
          className="px-3 py-1.5 text-xs font-medium bg-brand-primary text-white rounded-lg hover:bg-brand-primary/90 transition-colors mt-2"
        >
          Retry
        </button>
      </div>
    );
  }

  if (!graph || !stats) return null;

  // ── Rendered graph ─────────────────────────────────────────────────────

  // Build a set of connected node IDs for hovered node highlighting
  const connectedIds = new Set<string>();
  if (hoveredNode) {
    connectedIds.add(hoveredNode);
    for (const e of simEdges) {
      if (e.source === hoveredNode) connectedIds.add(e.target);
      if (e.target === hoveredNode) connectedIds.add(e.source);
    }
  }

  const nodeMap = new Map<string, SimNode>();
  for (const n of simNodes) nodeMap.set(n.id, n);

  return (
    <div className="flex flex-col h-full">
      {/* Stats bar */}
      <div className="px-4 py-2.5 border-b border-neutral-200 bg-neutral-50/50 flex items-center gap-5 text-xs shrink-0">
        <StatBadge label="Entities" value={stats.totalEntities} color="text-neutral-700" />
        <StatBadge label="Visits" value={stats.visits} color="text-blue-600" />
        <StatBadge label="Procedures" value={stats.procedures} color="text-emerald-600" />
        <StatBadge label="Schedule" value={stats.scheduleEntries} color="text-neutral-500" />
        <StatBadge label="Footnotes" value={stats.footnotes} color="text-amber-600" />
        <div className="h-4 w-px bg-neutral-200" />
        <StatBadge label="Firm" value={stats.firmCount} color="text-emerald-600" />
        <StatBadge label="Conditional" value={stats.conditionalCount} color="text-amber-600" />
        <div className="h-4 w-px bg-neutral-200" />
        <span className="text-neutral-400">Edges: {stats.totalEdges}</span>
      </div>

      {/* Filter bar */}
      <div className="px-4 py-2 border-b border-neutral-200 flex items-center gap-3 shrink-0 flex-wrap">
        <span className="text-[10px] text-neutral-400 uppercase font-semibold tracking-wider">Filter by type:</span>
        {ENTITY_TYPE_ORDER.map((type) => {
          const count = graph.entity_counts[type] || 0;
          if (count === 0) return null;
          const active = typeFilter.size === 0 || typeFilter.has(type);
          return (
            <button
              key={type}
              onClick={() => toggleTypeFilter(type)}
              className={cn(
                "inline-flex items-center gap-1.5 px-2 py-1 rounded-md text-[11px] font-medium transition-all border",
                active
                  ? "border-neutral-300 bg-white shadow-sm"
                  : "border-transparent bg-neutral-100 text-neutral-400"
              )}
            >
              <span
                className="w-2.5 h-2.5 rounded-full shrink-0"
                style={{ backgroundColor: active ? NODE_COLORS[type] || "#999" : "#d1d5db" }}
              />
              {type}
              <span className="text-neutral-400 text-[10px]">{count}</span>
            </button>
          );
        })}
        <div className="h-4 w-px bg-neutral-200 mx-1" />
        <span className="text-[10px] text-neutral-400 uppercase font-semibold tracking-wider">Mark:</span>
        {["all", "firm", "conditional", "span"].map((m) => (
          <button
            key={m}
            onClick={() => setMarkFilter(m)}
            className={cn(
              "px-2 py-1 rounded-md text-[11px] font-medium transition-all border",
              markFilter === m
                ? "border-neutral-300 bg-white shadow-sm text-neutral-700"
                : "border-transparent bg-neutral-100 text-neutral-400"
            )}
          >
            {m === "all" ? "All marks" : m}
          </button>
        ))}
      </div>

      <div className="flex flex-1 overflow-hidden">
        {/* SVG graph area */}
        <div ref={containerRef} className="flex-1 overflow-auto bg-neutral-50/30 relative">
          <svg
            ref={svgRef}
            viewBox={`0 0 ${width} ${height}`}
            className="w-full h-full min-h-[500px]"
            style={{ minWidth: 700 }}
          >
            <defs>
              <marker
                id="arrowhead"
                markerWidth="8"
                markerHeight="6"
                refX="8"
                refY="3"
                orient="auto"
              >
                <polygon points="0 0, 8 3, 0 6" fill="#cbd5e1" />
              </marker>
            </defs>

            {/* Edges */}
            {simEdges.map((edge) => {
              const s = nodeMap.get(edge.source);
              const t = nodeMap.get(edge.target);
              if (!s || !t) return null;
              const isHighlighted =
                hoveredNode && (connectedIds.has(edge.source) && connectedIds.has(edge.target));
              const isHidden = hoveredNode && !isHighlighted;
              return (
                <g key={edge.data.id}>
                  <line
                    x1={s.x}
                    y1={s.y}
                    x2={t.x}
                    y2={t.y}
                    stroke={isHighlighted ? "#64748b" : "#e2e8f0"}
                    strokeWidth={isHighlighted ? 1.5 : 0.5}
                    opacity={isHidden ? 0.1 : 1}
                    markerEnd="url(#arrowhead)"
                  />
                  {isHighlighted && (
                    <text
                      x={(s.x + t.x) / 2}
                      y={(s.y + t.y) / 2 - 4}
                      textAnchor="middle"
                      fontSize={8}
                      fill="#64748b"
                      fontWeight={500}
                    >
                      {edge.type}
                    </text>
                  )}
                </g>
              );
            })}

            {/* Nodes */}
            {simNodes.map((node) => {
              const color = NODE_COLORS[node.type] || "#6b7280";
              const r = node.radius;
              const isActive = selectedNode?.id === node.id;
              const isHighlighted = hoveredNode
                ? connectedIds.has(node.id)
                : true;
              const opacity = hoveredNode && !isHighlighted ? 0.15 : 1;

              return (
                <g
                  key={node.id}
                  transform={`translate(${node.x},${node.y})`}
                  opacity={opacity}
                  style={{ cursor: "pointer", transition: "opacity 0.15s" }}
                  onClick={() =>
                    setSelectedNode(isActive ? null : node.data)
                  }
                  onMouseEnter={() => setHoveredNode(node.id)}
                  onMouseLeave={() => setHoveredNode(null)}
                >
                  <circle
                    r={r}
                    fill={color}
                    fillOpacity={0.85}
                    stroke={isActive ? "#111" : color}
                    strokeWidth={isActive ? 2.5 : 1}
                    strokeOpacity={0.6}
                  />
                  {r >= 10 && (
                    <text
                      textAnchor="middle"
                      dy={r + 12}
                      fontSize={node.type === "ScheduleEntry" ? 7 : 9}
                      fill="#374151"
                      fontWeight={400}
                    >
                      {truncLabel(node.label, node.type === "ScheduleEntry" ? 12 : 20)}
                    </text>
                  )}
                </g>
              );
            })}
          </svg>

          {/* Legend */}
          <div className="absolute bottom-3 left-3 bg-white/90 rounded-lg border border-neutral-200 px-3 py-2 flex flex-col gap-1">
            <span className="text-[9px] text-neutral-400 font-semibold uppercase tracking-wider mb-0.5">Legend</span>
            {ENTITY_TYPE_ORDER.map((type) => {
              if (!graph.entity_counts[type]) return null;
              return (
                <div key={type} className="flex items-center gap-2 text-[10px] text-neutral-600">
                  <span
                    className="w-3 h-3 rounded-full shrink-0"
                    style={{ backgroundColor: NODE_COLORS[type] || "#999" }}
                  />
                  {type}
                </div>
              );
            })}
          </div>
        </div>

        {/* Detail panel */}
        {selectedNode && (
          <div className="w-80 border-l border-neutral-200 bg-white overflow-y-auto shrink-0">
            <div className="p-4">
              <div className="flex items-center justify-between mb-3">
                <div className="flex items-center gap-2">
                  <span
                    className="w-3 h-3 rounded-full shrink-0"
                    style={{ backgroundColor: NODE_COLORS[selectedNode.type] || "#999" }}
                  />
                  <span className="text-[10px] font-semibold text-neutral-400 uppercase tracking-wider">
                    {selectedNode.type}
                  </span>
                </div>
                <button
                  onClick={() => setSelectedNode(null)}
                  className="p-1 rounded hover:bg-neutral-100 text-neutral-400"
                >
                  <svg width="14" height="14" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round">
                    <path d="M4 4L12 12M12 4L4 12" />
                  </svg>
                </button>
              </div>
              <h3 className="text-sm font-semibold text-neutral-800 mb-1">{selectedNode.label}</h3>
              <p className="text-[10px] text-neutral-400 mb-4 font-mono break-all">ID: {selectedNode.id}</p>

              {/* Properties */}
              <PropertyList properties={selectedNode.properties} />

              {/* Inference trail */}
              <InferenceTrail trail={selectedNode.properties.inference_trail} />

              {/* Confidence */}
              <div className="mt-4 space-y-2">
                <h4 className="text-[10px] font-semibold text-neutral-400 uppercase tracking-wider">Confidence</h4>
                <span
                  className={cn(
                    "inline-block px-2 py-0.5 rounded text-[11px] font-medium",
                    selectedNode.confidence === "high"
                      ? "bg-emerald-100 text-emerald-700"
                      : selectedNode.confidence === "medium"
                        ? "bg-sky-100 text-sky-700"
                        : selectedNode.confidence === "low"
                          ? "bg-amber-100 text-amber-700"
                          : "bg-neutral-100 text-neutral-600"
                  )}
                >
                  {selectedNode.confidence}
                </span>
              </div>

              {/* Connected edges */}
              <div className="mt-4 space-y-2">
                <h4 className="text-[10px] font-semibold text-neutral-400 uppercase tracking-wider">Relationships</h4>
                {graph.edges
                  .filter(
                    (e) =>
                      e.source === selectedNode.id ||
                      e.target === selectedNode.id
                  )
                  .slice(0, 20)
                  .map((e) => {
                    const otherId =
                      e.source === selectedNode.id ? e.target : e.source;
                    const otherNode = graph.nodes.find((n) => n.id === otherId);
                    const direction =
                      e.source === selectedNode.id ? "\u2192" : "\u2190";
                    return (
                      <button
                        key={e.id}
                        onClick={() => {
                          if (otherNode) setSelectedNode(otherNode);
                        }}
                        className="w-full text-left flex items-center gap-1.5 py-1 px-1.5 rounded text-[10px] hover:bg-neutral-50 transition-colors"
                      >
                        <span className="text-neutral-400 font-mono">{direction}</span>
                        <span className="text-neutral-500">{e.type}</span>
                        <span className="text-neutral-700 font-medium truncate">
                          {otherNode?.label || otherId.substring(0, 8)}
                        </span>
                      </button>
                    );
                  })}
                {graph.edges.filter(
                  (e) =>
                    e.source === selectedNode.id ||
                    e.target === selectedNode.id
                ).length > 20 && (
                  <p className="text-[10px] text-neutral-400 italic">
                    +{graph.edges.filter(
                      (e) =>
                        e.source === selectedNode.id ||
                        e.target === selectedNode.id
                    ).length - 20} more
                  </p>
                )}
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

function StatBadge({
  label,
  value,
  color,
}: {
  label: string;
  value: number;
  color: string;
}) {
  return (
    <div className="flex items-center gap-1.5">
      <span className={cn("font-bold font-mono", color)}>{value}</span>
      <span className="text-neutral-400">{label}</span>
    </div>
  );
}

function InferenceTrail({ trail }: { trail: unknown }) {
  if (!trail || !Array.isArray(trail) || trail.length === 0) return null;
  const rules = trail as string[];
  return (
    <div className="mt-4 space-y-2">
      <h4 className="text-[10px] font-semibold text-neutral-400 uppercase tracking-wider">
        Inference Trail
      </h4>
      <div className="space-y-1">
        {rules.map((rule: string, i: number) => (
          <div key={i} className="flex items-center gap-2 text-[11px]">
            <span className="w-1.5 h-1.5 rounded-full bg-purple-400 shrink-0" />
            <span className="text-neutral-600">{rule}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

function PropertyList({ properties }: { properties: Record<string, unknown> }) {
  const entries = Object.entries(properties).filter(
    ([k, v]) => v !== null && v !== "" && v !== undefined && k !== "inference_trail"
  );
  return (
    <div className="space-y-2">
      <h4 className="text-[10px] font-semibold text-neutral-400 uppercase tracking-wider">
        Properties
      </h4>
      {entries.map(([key, value]) => {
        const display: string =
          typeof value === "object" ? JSON.stringify(value) : String(value);
        return (
          <div
            key={key}
            className="flex justify-between items-start py-1 border-b border-neutral-50"
          >
            <span className="text-[11px] text-neutral-500 shrink-0">
              {key.replace(/_/g, " ")}
            </span>
            <span className="text-[11px] text-neutral-800 font-medium text-right ml-3 break-all">
              {display}
            </span>
          </div>
        );
      })}
    </div>
  );
}
