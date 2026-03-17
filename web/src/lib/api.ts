const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export interface JobStatus {
  job_id: string;
  status: "pending" | "processing" | "completed" | "failed";
  progress: number;
  message: string;
  document_name: string;
  result: PipelineOutput | null;
  error: string | null;
  created_at: number;
  completed_at: number | null;
}

export interface PipelineOutput {
  document_name: string;
  document_hash: string;
  total_pages: number;
  tables: ExtractedTable[];
  processing_time_seconds: number;
  pipeline_version: string;
  warnings: string[];
}

export interface ExtractedTable {
  table_id: string;
  table_type: string;
  title: string;
  source_pages: number[];
  schema_info: TableSchema;
  cells: ExtractedCell[];
  footnotes: ResolvedFootnote[];
  procedures: NormalizedProcedure[];
  visit_windows: VisitWindow[];
  overall_confidence: number;
  flagged_cells: CellRef[];
  review_items: ReviewItem[];
  extraction_metadata: ExtractionMetadata;
}

export interface TableSchema {
  table_id: string;
  column_headers: ColumnHeader[];
  row_groups: RowGroup[];
  merged_regions: MergedRegion[];
  footnote_markers: string[];
  num_rows: number;
  num_cols: number;
}

export interface ColumnHeader {
  col_index: number;
  text: string;
  span: number;
  level: number;
  parent_col: number | null;
}

export interface RowGroup {
  name: string;
  start_row: number;
  end_row: number;
  category: string;
}

export interface MergedRegion {
  start_row: number;
  end_row: number;
  start_col: number;
  end_col: number;
  value: string;
}

export interface ExtractedCell {
  row: number;
  col: number;
  raw_value: string;
  normalized_value: string | null;
  data_type: "MARKER" | "TEXT" | "NUMERIC" | "EMPTY" | "CONDITIONAL";
  footnote_markers: string[];
  resolved_footnotes: string[];
  confidence: number;
  row_header: string;
  col_header: string;
}

export interface ResolvedFootnote {
  marker: string;
  text: string;
  applies_to: CellRef[];
  footnote_type: "CONDITIONAL" | "CLARIFICATION" | "EXCEPTION" | "REFERENCE";
}

export interface NormalizedProcedure {
  raw_name: string;
  canonical_name: string;
  code: string | null;
  code_system: string | null;
  category: string;
  estimated_cost_tier: "LOW" | "MEDIUM" | "HIGH" | "VERY_HIGH";
}

export interface VisitWindow {
  visit_name: string;
  col_index: number;
  target_day: number | null;
  window_minus: number;
  window_plus: number;
  window_unit: "DAYS" | "WEEKS" | "MONTHS";
  relative_to: string;
  is_unscheduled: boolean;
  cycle: number | null;
}

export interface CellRef {
  row: number;
  col: number;
}

export interface ReviewItem {
  cell_ref: CellRef;
  review_type: "LOCAL_RESOLUTION" | "STRUCTURAL_INTERPRETATION" | "SYSTEMATIC_PATTERN";
  reason: string;
  extracted_value: string;
  source_page: number;
  cost_tier: "LOW" | "MEDIUM" | "HIGH" | "VERY_HIGH";
}

export interface ExtractionMetadata {
  passes_run: number;
  challenger_issues_found: number;
  reconciliation_conflicts: number;
  processing_time_seconds: number;
  timestamp: string;
  model_used: string;
}

export async function uploadProtocol(file: File): Promise<{ job_id: string }> {
  const formData = new FormData();
  formData.append("file", file);

  const res = await fetch(`${API_BASE}/api/extract`, {
    method: "POST",
    body: formData,
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: "Upload failed" }));
    throw new Error(err.detail || "Upload failed");
  }

  return res.json();
}

export async function getJobStatus(jobId: string): Promise<JobStatus> {
  const res = await fetch(`${API_BASE}/api/jobs/${jobId}`);
  if (!res.ok) throw new Error("Failed to fetch job status");
  return res.json();
}

export async function getJobResult(jobId: string): Promise<PipelineOutput> {
  const res = await fetch(`${API_BASE}/api/jobs/${jobId}/result`);
  if (!res.ok) throw new Error("Failed to fetch result");
  return res.json();
}

export async function listJobs(): Promise<JobStatus[]> {
  const res = await fetch(`${API_BASE}/api/jobs`);
  if (!res.ok) throw new Error("Failed to list jobs");
  return res.json();
}

export async function checkHealth(): Promise<boolean> {
  try {
    const res = await fetch(`${API_BASE}/api/health`, { signal: AbortSignal.timeout(3000) });
    return res.ok;
  } catch {
    return false;
  }
}
