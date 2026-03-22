"use client";

import { useState, useMemo, useCallback, useEffect, useRef } from "react";
import { TopBar } from "@/components/layout/TopBar";
import { Card, CardBody } from "@/components/ui/Card";
import { cn } from "@/lib/utils";
import { listProcedures, updateProcedure } from "@/lib/api";
import type { ProcedureEntry } from "@/lib/api";

// ─── Constants ──────────────────────────────────────────────────────────────

const CATEGORIES = [
  "General",
  "Laboratory",
  "Cardiology",
  "Safety",
  "Treatment",
  "Efficacy",
  "Imaging",
] as const;

const COST_TIERS = ["LOW", "MEDIUM", "HIGH", "VERY_HIGH"] as const;

const COST_LABELS: Record<string, string> = {
  LOW: "$",
  MEDIUM: "$$",
  HIGH: "$$$",
  VERY_HIGH: "$$$$",
};

// ─── Page Component ─────────────────────────────────────────────────────────

export default function ProcedureLibraryPage() {
  const [procedures, setProcedures] = useState<ProcedureEntry[]>([]);
  const [searchQuery, setSearchQuery] = useState("");
  const [editingCell, setEditingCell] = useState<{ row: number; col: string } | null>(null);
  const [editValue, setEditValue] = useState("");
  const [pendingChanges, setPendingChanges] = useState(0);
  const [addingNew, setAddingNew] = useState(false);
  const [newProcedure, setNewProcedure] = useState<ProcedureEntry>({
    canonical_name: "",
    cpt_code: null,
    code_system: null,
    category: "General",
    cost_tier: "LOW",
    aliases: [],
    used_in_protocols: 0,
  });

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const editInputRef = useRef<HTMLInputElement>(null);

  // Load procedures from API
  useEffect(() => {
    listProcedures()
      .then(setProcedures)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  // Focus edit input when editing
  useEffect(() => {
    if (editingCell) {
      editInputRef.current?.focus();
      editInputRef.current?.select();
    }
  }, [editingCell]);

  // Filter procedures
  const filtered = useMemo(() => {
    if (!searchQuery.trim()) return procedures;
    const q = searchQuery.toLowerCase();
    return procedures.filter(
      (p) =>
        p.canonical_name.toLowerCase().includes(q) ||
        (p.cpt_code && p.cpt_code.includes(q)) ||
        p.category.toLowerCase().includes(q) ||
        p.aliases.some((a) => a.toLowerCase().includes(q))
    );
  }, [procedures, searchQuery]);

  // Stats
  const totalProcedures = procedures.length;
  const withCPT = procedures.filter((p) => p.cpt_code).length;
  const totalAliases = procedures.reduce((sum, p) => sum + p.aliases.length, 0);

  // ── Editing helpers ──

  const startEdit = useCallback((rowIdx: number, col: string, currentValue: string) => {
    setEditingCell({ row: rowIdx, col });
    setEditValue(currentValue);
  }, []);

  const commitEdit = useCallback(() => {
    if (!editingCell) return;

    setProcedures((prev) => {
      const updated = [...prev];
      const proc = { ...updated[editingCell.row] };
      switch (editingCell.col) {
        case "canonical_name":
          proc.canonical_name = editValue;
          break;
        case "cpt_code":
          proc.cpt_code = editValue || null;
          break;
        case "code_system":
          proc.code_system = editValue || null;
          break;
        case "aliases":
          proc.aliases = editValue.split(",").map((a) => a.trim()).filter(Boolean);
          break;
      }
      updated[editingCell.row] = proc;
      return updated;
    });

    setPendingChanges((c) => c + 1);
    setEditingCell(null);
  }, [editingCell, editValue]);

  const cancelEdit = useCallback(() => {
    setEditingCell(null);
    setEditValue("");
  }, []);

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === "Enter") {
        commitEdit();
      } else if (e.key === "Escape") {
        cancelEdit();
      } else if (e.key === "Tab" && editingCell) {
        e.preventDefault();
        commitEdit();
        // Move to next editable column
        const editableCols = ["canonical_name", "cpt_code", "code_system", "aliases"];
        const currentIdx = editableCols.indexOf(editingCell.col);
        if (currentIdx < editableCols.length - 1) {
          const nextCol = editableCols[currentIdx + 1];
          const proc = procedures[editingCell.row];
          let nextValue = "";
          switch (nextCol) {
            case "canonical_name": nextValue = proc.canonical_name; break;
            case "cpt_code": nextValue = proc.cpt_code || ""; break;
            case "code_system": nextValue = proc.code_system || ""; break;
            case "aliases": nextValue = proc.aliases.join(", "); break;
          }
          startEdit(editingCell.row, nextCol, nextValue);
        }
      }
    },
    [commitEdit, cancelEdit, editingCell, procedures, startEdit]
  );

  const updateCategory = useCallback((idx: number, category: string) => {
    setProcedures((prev) => {
      const updated = [...prev];
      updated[idx] = { ...updated[idx], category };
      return updated;
    });
    setPendingChanges((c) => c + 1);
  }, []);

  const updateCostTier = useCallback((idx: number, cost_tier: string) => {
    setProcedures((prev) => {
      const updated = [...prev];
      updated[idx] = { ...updated[idx], cost_tier };
      return updated;
    });
    setPendingChanges((c) => c + 1);
  }, []);

  const addProcedure = useCallback(() => {
    if (!newProcedure.canonical_name.trim()) return;
    setProcedures((prev) => [newProcedure, ...prev]);
    setPendingChanges((c) => c + 1);
    setAddingNew(false);
    setNewProcedure({
      canonical_name: "",
      cpt_code: null,
      code_system: null,
      category: "General",
      cost_tier: "LOW",
      aliases: [],
      used_in_protocols: 0,
    });
  }, [newProcedure]);

  const savePending = useCallback(async () => {
    try {
      // Batch update all modified procedures
      for (const proc of procedures) {
        await updateProcedure(proc.canonical_name, proc);
      }
      setPendingChanges(0);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Save failed");
    }
  }, [procedures]);

  return (
    <div>
      <TopBar title="Procedure Library" subtitle="Manage canonical names, CPT codes, and aliases" />

      <div className="p-6 space-y-4">
        {/* Loading state */}
        {loading && (
          <div className="flex items-center justify-center py-12">
            <div className="text-center">
              <div className="w-8 h-8 border-2 border-brand-primary border-t-transparent rounded-full animate-spin mx-auto mb-3" />
              <p className="text-sm text-neutral-400">Loading procedures...</p>
            </div>
          </div>
        )}

        {/* Error state */}
        {error && (
          <div className="bg-red-50 border border-red-200 rounded-lg p-4 text-sm text-red-700">
            {error}
          </div>
        )}

        {/* Stats bar */}
        <div className="flex items-center gap-6 text-sm">
          <StatChip label="Procedures" value={totalProcedures} />
          <StatChip label="With CPT codes" value={withCPT} />
          <StatChip label="Aliases" value={totalAliases} />
        </div>

        {/* Controls bar */}
        <div className="flex items-center gap-3">
          {/* Search */}
          <div className="relative flex-1 max-w-md">
            <SearchIcon className="absolute left-3 top-1/2 -translate-y-1/2 text-neutral-400" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search by name, CPT code, or category..."
              className="w-full pl-9 pr-3 py-2 text-sm border border-neutral-200 rounded-lg bg-white focus:outline-none focus:ring-2 focus:ring-brand-primary/30 focus:border-brand-primary"
            />
          </div>

          {/* Add button */}
          <button
            onClick={() => setAddingNew(true)}
            className="px-3 py-2 text-xs font-medium bg-brand-primary text-white rounded-lg hover:bg-brand-primary/90 transition-colors flex items-center gap-1.5"
          >
            <PlusIcon />
            Add Procedure
          </button>

          {/* Save changes */}
          {pendingChanges > 0 && (
            <button
              onClick={savePending}
              className="px-3 py-2 text-xs font-medium bg-success text-white rounded-lg hover:bg-success/90 transition-colors flex items-center gap-1.5"
            >
              Save {pendingChanges} change{pendingChanges !== 1 ? "s" : ""}
            </button>
          )}
        </div>

        {/* Data table */}
        <Card className="overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="bg-neutral-50 border-b border-neutral-200">
                  <th className="text-left px-3 py-2.5 font-semibold text-neutral-600 w-[200px]">Canonical Name</th>
                  <th className="text-left px-3 py-2.5 font-semibold text-neutral-600 w-[90px]">CPT Code</th>
                  <th className="text-left px-3 py-2.5 font-semibold text-neutral-600 w-[80px]">Code System</th>
                  <th className="text-left px-3 py-2.5 font-semibold text-neutral-600 w-[110px]">Category</th>
                  <th className="text-left px-3 py-2.5 font-semibold text-neutral-600 w-[90px]">Cost Tier</th>
                  <th className="text-left px-3 py-2.5 font-semibold text-neutral-600">Aliases</th>
                  <th className="text-right px-3 py-2.5 font-semibold text-neutral-600 w-[70px]">Used In</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-neutral-100">
                {/* New procedure row */}
                {addingNew && (
                  <tr className="bg-brand-primary-light/50">
                    <td className="px-3 py-1.5">
                      <input
                        type="text"
                        value={newProcedure.canonical_name}
                        onChange={(e) => setNewProcedure({ ...newProcedure, canonical_name: e.target.value })}
                        placeholder="Procedure name..."
                        className="w-full px-2 py-1 text-xs border border-brand-primary/30 rounded bg-white focus:outline-none focus:ring-1 focus:ring-brand-primary"
                        autoFocus
                      />
                    </td>
                    <td className="px-3 py-1.5">
                      <input
                        type="text"
                        value={newProcedure.cpt_code || ""}
                        onChange={(e) => setNewProcedure({ ...newProcedure, cpt_code: e.target.value || null })}
                        placeholder="CPT..."
                        className="w-full px-2 py-1 text-xs border border-neutral-200 rounded bg-white focus:outline-none focus:ring-1 focus:ring-brand-primary"
                      />
                    </td>
                    <td className="px-3 py-1.5">
                      <input
                        type="text"
                        value={newProcedure.code_system || ""}
                        onChange={(e) => setNewProcedure({ ...newProcedure, code_system: e.target.value || null })}
                        placeholder="System..."
                        className="w-full px-2 py-1 text-xs border border-neutral-200 rounded bg-white focus:outline-none focus:ring-1 focus:ring-brand-primary"
                      />
                    </td>
                    <td className="px-3 py-1.5">
                      <select
                        value={newProcedure.category}
                        onChange={(e) => setNewProcedure({ ...newProcedure, category: e.target.value })}
                        className="w-full px-1 py-1 text-xs border border-neutral-200 rounded bg-white focus:outline-none focus:ring-1 focus:ring-brand-primary"
                      >
                        {CATEGORIES.map((c) => <option key={c} value={c}>{c}</option>)}
                      </select>
                    </td>
                    <td className="px-3 py-1.5">
                      <select
                        value={newProcedure.cost_tier}
                        onChange={(e) => setNewProcedure({ ...newProcedure, cost_tier: e.target.value })}
                        className="w-full px-1 py-1 text-xs border border-neutral-200 rounded bg-white focus:outline-none focus:ring-1 focus:ring-brand-primary"
                      >
                        {COST_TIERS.map((t) => <option key={t} value={t}>{t} ({COST_LABELS[t]})</option>)}
                      </select>
                    </td>
                    <td className="px-3 py-1.5">
                      <input
                        type="text"
                        value={newProcedure.aliases.join(", ")}
                        onChange={(e) => setNewProcedure({ ...newProcedure, aliases: e.target.value.split(",").map((a) => a.trim()).filter(Boolean) })}
                        placeholder="Comma-separated..."
                        className="w-full px-2 py-1 text-xs border border-neutral-200 rounded bg-white focus:outline-none focus:ring-1 focus:ring-brand-primary"
                      />
                    </td>
                    <td className="px-3 py-1.5 text-right">
                      <div className="flex items-center gap-1 justify-end">
                        <button
                          onClick={addProcedure}
                          disabled={!newProcedure.canonical_name.trim()}
                          className={cn(
                            "px-2 py-1 rounded text-[10px] font-medium transition-colors",
                            newProcedure.canonical_name.trim()
                              ? "bg-success text-white hover:bg-success/90"
                              : "bg-neutral-100 text-neutral-400 cursor-not-allowed"
                          )}
                        >
                          Add
                        </button>
                        <button
                          onClick={() => setAddingNew(false)}
                          className="px-2 py-1 rounded text-[10px] font-medium text-neutral-500 hover:bg-neutral-100 transition-colors"
                        >
                          Cancel
                        </button>
                      </div>
                    </td>
                  </tr>
                )}

                {/* Data rows */}
                {filtered.map((proc, idx) => {
                  // Find original index for editing
                  const originalIdx = procedures.indexOf(proc);

                  return (
                    <tr key={`${proc.canonical_name}-${idx}`} className="hover:bg-neutral-50/50 group">
                      {/* Canonical Name */}
                      <td className="px-3 py-1.5">
                        {editingCell?.row === originalIdx && editingCell?.col === "canonical_name" ? (
                          <input
                            ref={editInputRef}
                            type="text"
                            value={editValue}
                            onChange={(e) => setEditValue(e.target.value)}
                            onKeyDown={handleKeyDown}
                            onBlur={commitEdit}
                            className="w-full px-2 py-0.5 text-xs border border-brand-primary rounded bg-white focus:outline-none focus:ring-1 focus:ring-brand-primary"
                          />
                        ) : (
                          <span
                            onClick={() => startEdit(originalIdx, "canonical_name", proc.canonical_name)}
                            className="cursor-text font-medium text-neutral-800 hover:text-brand-primary transition-colors"
                          >
                            {proc.canonical_name}
                          </span>
                        )}
                      </td>

                      {/* CPT Code */}
                      <td className="px-3 py-1.5">
                        {editingCell?.row === originalIdx && editingCell?.col === "cpt_code" ? (
                          <input
                            ref={editInputRef}
                            type="text"
                            value={editValue}
                            onChange={(e) => setEditValue(e.target.value)}
                            onKeyDown={handleKeyDown}
                            onBlur={commitEdit}
                            className="w-full px-2 py-0.5 text-xs border border-brand-primary rounded bg-white font-mono focus:outline-none focus:ring-1 focus:ring-brand-primary"
                          />
                        ) : (
                          <span
                            onClick={() => startEdit(originalIdx, "cpt_code", proc.cpt_code || "")}
                            className={cn(
                              "cursor-text font-mono",
                              proc.cpt_code ? "text-neutral-700" : "text-neutral-300 italic"
                            )}
                          >
                            {proc.cpt_code || "—"}
                          </span>
                        )}
                      </td>

                      {/* Code System */}
                      <td className="px-3 py-1.5">
                        {editingCell?.row === originalIdx && editingCell?.col === "code_system" ? (
                          <input
                            ref={editInputRef}
                            type="text"
                            value={editValue}
                            onChange={(e) => setEditValue(e.target.value)}
                            onKeyDown={handleKeyDown}
                            onBlur={commitEdit}
                            className="w-full px-2 py-0.5 text-xs border border-brand-primary rounded bg-white focus:outline-none focus:ring-1 focus:ring-brand-primary"
                          />
                        ) : (
                          <span
                            onClick={() => startEdit(originalIdx, "code_system", proc.code_system || "")}
                            className={cn("cursor-text", proc.code_system ? "text-neutral-600" : "text-neutral-300 italic")}
                          >
                            {proc.code_system || "—"}
                          </span>
                        )}
                      </td>

                      {/* Category (dropdown) */}
                      <td className="px-3 py-1.5">
                        <select
                          value={proc.category}
                          onChange={(e) => updateCategory(originalIdx, e.target.value)}
                          className="px-1 py-0.5 text-xs border border-transparent hover:border-neutral-200 rounded bg-transparent focus:outline-none focus:ring-1 focus:ring-brand-primary focus:border-brand-primary cursor-pointer"
                        >
                          {CATEGORIES.map((c) => (
                            <option key={c} value={c}>{c}</option>
                          ))}
                        </select>
                      </td>

                      {/* Cost Tier (dropdown) */}
                      <td className="px-3 py-1.5">
                        <select
                          value={proc.cost_tier}
                          onChange={(e) => updateCostTier(originalIdx, e.target.value)}
                          className="px-1 py-0.5 text-xs border border-transparent hover:border-neutral-200 rounded bg-transparent focus:outline-none focus:ring-1 focus:ring-brand-primary focus:border-brand-primary cursor-pointer"
                        >
                          {COST_TIERS.map((t) => (
                            <option key={t} value={t}>{COST_LABELS[t]} {t}</option>
                          ))}
                        </select>
                      </td>

                      {/* Aliases */}
                      <td className="px-3 py-1.5">
                        {editingCell?.row === originalIdx && editingCell?.col === "aliases" ? (
                          <input
                            ref={editInputRef}
                            type="text"
                            value={editValue}
                            onChange={(e) => setEditValue(e.target.value)}
                            onKeyDown={handleKeyDown}
                            onBlur={commitEdit}
                            className="w-full px-2 py-0.5 text-xs border border-brand-primary rounded bg-white focus:outline-none focus:ring-1 focus:ring-brand-primary"
                          />
                        ) : (
                          <span
                            onClick={() => startEdit(originalIdx, "aliases", proc.aliases.join(", "))}
                            className="cursor-text text-neutral-500 hover:text-neutral-700 transition-colors"
                          >
                            {proc.aliases.length > 0 ? (
                              <span className="flex flex-wrap gap-1">
                                {proc.aliases.slice(0, 3).map((alias, ai) => (
                                  <span key={ai} className="inline-block bg-neutral-100 text-neutral-600 px-1.5 py-0.5 rounded text-[10px]">
                                    {alias}
                                  </span>
                                ))}
                                {proc.aliases.length > 3 && (
                                  <span className="inline-block text-neutral-400 text-[10px] py-0.5">
                                    +{proc.aliases.length - 3} more
                                  </span>
                                )}
                              </span>
                            ) : (
                              <span className="text-neutral-300 italic">None</span>
                            )}
                          </span>
                        )}
                      </td>

                      {/* Used In */}
                      <td className="px-3 py-1.5 text-right">
                        <span className="font-mono text-neutral-600 tabular-nums">{proc.used_in_protocols}</span>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>

          {filtered.length === 0 && (
            <CardBody className="text-center py-12">
              <p className="text-sm text-neutral-500">No procedures match your search.</p>
              <p className="text-xs text-neutral-400 mt-1">Try a different search term or clear the filter.</p>
            </CardBody>
          )}
        </Card>

        {/* Footer info */}
        <div className="text-[11px] text-neutral-400 text-center">
          Showing {filtered.length} of {totalProcedures} procedures
          {pendingChanges > 0 && (
            <span className="ml-2 text-warning font-medium">
              · {pendingChanges} pending correction{pendingChanges !== 1 ? "s" : ""}
            </span>
          )}
        </div>
      </div>
    </div>
  );
}

// ─── Sub-components ─────────────────────────────────────────────────────────

function StatChip({ label, value }: { label: string; value: number }) {
  return (
    <div className="flex items-center gap-1.5">
      <span className="text-lg font-bold text-neutral-800 tabular-nums font-mono">{value.toLocaleString()}</span>
      <span className="text-xs text-neutral-500">{label}</span>
    </div>
  );
}

// ─── Icons ──────────────────────────────────────────────────────────────────

function SearchIcon({ className }: { className?: string }) {
  return (
    <svg width="14" height="14" viewBox="0 0 14 14" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" className={className}>
      <circle cx="6" cy="6" r="4.5" />
      <path d="M9.5 9.5L13 13" />
    </svg>
  );
}

function PlusIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 14 14" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round">
      <path d="M7 2V12M2 7H12" />
    </svg>
  );
}
