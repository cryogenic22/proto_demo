"use client";

import { useEffect, useState, useCallback } from "react";
import { Card, CardHeader, CardBody } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { cn } from "@/lib/utils";

const API = process.env.NEXT_PUBLIC_API_URL || "";

interface ProtocolInfo {
  protocol_id: string;
  document_name: string;
  title: string;
  tables_count: number;
  total_cells: number;
  total_procedures: number;
}

interface JobInfo {
  job_id: string;
  status: string;
  document_name: string;
  progress: number;
  message: string;
  created_at: number | null;
}

interface AdminStats {
  protocols: ProtocolInfo[];
  jobs: JobInfo[];
  total_protocols: number;
  total_jobs: number;
}

export default function AdminPage() {
  const [stats, setStats] = useState<AdminStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [actionLog, setActionLog] = useState<string[]>([]);

  const loadStats = useCallback(async () => {
    try {
      const res = await fetch(`${API}/api/admin/stats`);
      if (res.ok) setStats(await res.json());
    } catch { /* ignore */ }
    finally { setLoading(false); }
  }, []);

  useEffect(() => { loadStats(); }, [loadStats]);

  const deleteProtocol = async (pid: string) => {
    if (!confirm(`Delete protocol "${pid}"? This cannot be undone.`)) return;
    try {
      const res = await fetch(`${API}/api/admin/protocols/${pid}`, { method: "DELETE" });
      if (res.ok) {
        setActionLog(prev => [`Deleted protocol: ${pid}`, ...prev]);
        loadStats();
      } else {
        const err = await res.json().catch(() => ({}));
        setActionLog(prev => [`Failed to delete ${pid}: ${err.detail || "Unknown error"}`, ...prev]);
      }
    } catch (e) {
      setActionLog(prev => [`Error: ${e}`, ...prev]);
    }
  };

  const deleteJob = async (jid: string) => {
    try {
      const res = await fetch(`${API}/api/jobs/${jid}`, { method: "DELETE" });
      if (res.ok) {
        setActionLog(prev => [`Deleted job: ${jid}`, ...prev]);
        loadStats();
      }
    } catch (e) {
      setActionLog(prev => [`Error: ${e}`, ...prev]);
    }
  };

  const clearAllJobs = async () => {
    if (!confirm("Clear ALL jobs? This cannot be undone.")) return;
    try {
      const res = await fetch(`${API}/api/admin/jobs`, { method: "DELETE" });
      if (res.ok) {
        const data = await res.json();
        setActionLog(prev => [`Cleared ${data.cleared} jobs`, ...prev]);
        loadStats();
      }
    } catch (e) {
      setActionLog(prev => [`Error: ${e}`, ...prev]);
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-neutral-50">
        <div className="w-8 h-8 border-2 border-red-600 border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-neutral-50">
      {/* Header */}
      <header className="bg-red-600 text-white px-6 py-4">
        <div className="flex items-center justify-between max-w-6xl mx-auto">
          <div>
            <h1 className="text-lg font-bold">ProtoExtract Admin</h1>
            <p className="text-red-200 text-xs">Manage protocols, jobs, and system data</p>
          </div>
          <a href="/" className="text-xs text-red-200 hover:text-white underline">Back to App</a>
        </div>
      </header>

      <div className="max-w-6xl mx-auto p-6 space-y-6">
        {/* Stats */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <StatCard label="Protocols" value={stats?.total_protocols ?? 0} color="blue" />
          <StatCard label="Jobs" value={stats?.total_jobs ?? 0} color="amber" />
          <StatCard
            label="Total Cells"
            value={stats?.protocols.reduce((s, p) => s + p.total_cells, 0) ?? 0}
            color="emerald"
          />
          <StatCard
            label="Total Procedures"
            value={stats?.protocols.reduce((s, p) => s + p.total_procedures, 0) ?? 0}
            color="purple"
          />
        </div>

        {/* Protocols */}
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <h2 className="text-sm font-semibold text-neutral-800">Stored Protocols ({stats?.total_protocols})</h2>
            </div>
          </CardHeader>
          <CardBody className="p-0">
            <table className="w-full text-xs">
              <thead>
                <tr className="border-b border-neutral-200 bg-neutral-50">
                  <th className="text-left px-4 py-2 font-semibold text-neutral-600">Protocol ID</th>
                  <th className="text-left px-4 py-2 font-semibold text-neutral-600">Document</th>
                  <th className="text-center px-2 py-2 font-semibold text-neutral-600">Tables</th>
                  <th className="text-center px-2 py-2 font-semibold text-neutral-600">Cells</th>
                  <th className="text-center px-2 py-2 font-semibold text-neutral-600">Procedures</th>
                  <th className="text-right px-4 py-2 font-semibold text-neutral-600">Actions</th>
                </tr>
              </thead>
              <tbody>
                {stats?.protocols.map(p => (
                  <tr key={p.protocol_id} className="border-b border-neutral-100 hover:bg-neutral-50">
                    <td className="px-4 py-2 font-mono text-neutral-700">{p.protocol_id}</td>
                    <td className="px-4 py-2 text-neutral-600 truncate max-w-[200px]">{p.document_name || p.title}</td>
                    <td className="text-center px-2 py-2">{p.tables_count}</td>
                    <td className="text-center px-2 py-2">{p.total_cells}</td>
                    <td className="text-center px-2 py-2">{p.total_procedures}</td>
                    <td className="text-right px-4 py-2">
                      <button
                        onClick={() => deleteProtocol(p.protocol_id)}
                        className="px-2 py-1 text-[10px] font-medium rounded bg-red-100 text-red-700 hover:bg-red-200 transition-colors"
                      >
                        Delete
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </CardBody>
        </Card>

        {/* Jobs */}
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <h2 className="text-sm font-semibold text-neutral-800">Extraction Jobs ({stats?.total_jobs})</h2>
              {(stats?.total_jobs ?? 0) > 0 && (
                <button
                  onClick={clearAllJobs}
                  className="px-3 py-1 text-[10px] font-medium rounded bg-red-600 text-white hover:bg-red-700 transition-colors"
                >
                  Clear All Jobs
                </button>
              )}
            </div>
          </CardHeader>
          <CardBody className="p-0">
            {(stats?.jobs.length ?? 0) === 0 ? (
              <p className="px-4 py-6 text-xs text-neutral-400 text-center">No jobs</p>
            ) : (
              <table className="w-full text-xs">
                <thead>
                  <tr className="border-b border-neutral-200 bg-neutral-50">
                    <th className="text-left px-4 py-2 font-semibold text-neutral-600">Job ID</th>
                    <th className="text-left px-4 py-2 font-semibold text-neutral-600">Document</th>
                    <th className="text-center px-2 py-2 font-semibold text-neutral-600">Status</th>
                    <th className="text-center px-2 py-2 font-semibold text-neutral-600">Progress</th>
                    <th className="text-left px-4 py-2 font-semibold text-neutral-600">Message</th>
                    <th className="text-right px-4 py-2 font-semibold text-neutral-600">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {stats?.jobs.map(j => (
                    <tr key={j.job_id} className="border-b border-neutral-100 hover:bg-neutral-50">
                      <td className="px-4 py-2 font-mono text-neutral-700">{j.job_id}</td>
                      <td className="px-4 py-2 text-neutral-600 truncate max-w-[150px]">{j.document_name}</td>
                      <td className="text-center px-2 py-2">
                        <Badge variant={j.status === "completed" ? "success" : j.status === "failed" ? "danger" : "neutral"}>
                          {j.status}
                        </Badge>
                      </td>
                      <td className="text-center px-2 py-2">{j.progress}%</td>
                      <td className="px-4 py-2 text-neutral-500 truncate max-w-[200px]">{j.message}</td>
                      <td className="text-right px-4 py-2">
                        <button
                          onClick={() => deleteJob(j.job_id)}
                          className="px-2 py-1 text-[10px] font-medium rounded bg-red-100 text-red-700 hover:bg-red-200 transition-colors"
                        >
                          Delete
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </CardBody>
        </Card>

        {/* Action Log */}
        {actionLog.length > 0 && (
          <Card>
            <CardHeader>
              <h2 className="text-sm font-semibold text-neutral-800">Action Log</h2>
            </CardHeader>
            <CardBody>
              <div className="space-y-1">
                {actionLog.map((log, i) => (
                  <div key={i} className="text-xs text-neutral-600 font-mono">
                    {log}
                  </div>
                ))}
              </div>
            </CardBody>
          </Card>
        )}
      </div>
    </div>
  );
}

function StatCard({ label, value, color }: { label: string; value: number; color: string }) {
  const colors: Record<string, string> = {
    blue: "text-blue-700 bg-blue-50 border-blue-200",
    amber: "text-amber-700 bg-amber-50 border-amber-200",
    emerald: "text-emerald-700 bg-emerald-50 border-emerald-200",
    purple: "text-purple-700 bg-purple-50 border-purple-200",
  };
  return (
    <div className={cn("rounded-xl border px-4 py-3", colors[color] || colors.blue)}>
      <div className="text-2xl font-bold tabular-nums">{value.toLocaleString()}</div>
      <div className="text-[11px] font-medium opacity-70">{label}</div>
    </div>
  );
}
