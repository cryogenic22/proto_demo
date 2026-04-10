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

export type ExtractionMode = "full" | "soa" | "soa_plus" | "deep";

export async function uploadProtocol(file: File, mode: ExtractionMode = "soa"): Promise<{ job_id: string }> {
  const formData = new FormData();
  formData.append("file", file);
  formData.append("extraction_mode", mode);

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

// ─── Verification & Review Types ─────────────────────────────────────────────

export interface VerificationStep {
  method: 'DUAL_PASS' | 'OCR_GROUNDING' | 'VISION_SPATIAL' | 'CHALLENGER_CLEAR' | 'TEXT_MATCH' | 'FORMAT_CHECK';
  status: 'PASS' | 'FAIL' | 'SKIPPED';
  detail: string;
}

export interface ChallengeIssue {
  challenge_type: string;
  description: string;
  suggested_value: string | null;
  severity: number;
}

export interface CellReviewAction {
  protocol_id: string;
  table_id: string;
  row: number;
  col: number;
  action: 'accept' | 'correct' | 'flag';
  correct_value?: string;
  flag_reason?: string;
}

export interface AssistantMessage {
  role: 'user' | 'assistant';
  content: string;
  sources?: { section: string; page: number }[];
}

export interface ProcedureEntry {
  canonical_name: string;
  cpt_code: string | null;
  code_system: string | null;
  category: string;
  cost_tier: string;
  aliases: string[];
  used_in_protocols: number;
}

// ─── Protocol Types ──────────────────────────────────────────────────────────

export interface ProtocolSummary {
  protocol_id: string;
  document_name: string;
  metadata: ProtocolMetadata;
  created_at: string;
  total_pages: number;
}

export interface ProtocolMetadata {
  title: string;
  short_title: string;
  protocol_number: string;
  nct_number: string;
  sponsor: string;
  phase: string;
  therapeutic_area: string;
  indication: string;
  study_type: string;
  arms: string[];
  amendment_number: string;
  version: string;
}

export interface SectionNode {
  number: string;
  title: string;
  page: number;
  end_page: number | null;
  level: number;
  ke_type: string;
  content_html: string;
  children: SectionNode[];
  quality_score: number | null;
}

export interface ProtocolFull {
  protocol_id: string;
  document_name: string;
  document_hash: string;
  total_pages: number;
  metadata: ProtocolMetadata;
  sections: SectionNode[];
  tables: ExtractedTable[];
  procedures: NormalizedProcedure[];
  budget_lines: BudgetLine[];
  quality_summary: Record<string, unknown>;
  knowledge_elements: KnowledgeElement[];
  created_at: string;
  pipeline_version: string;
}

export interface BudgetLine {
  procedure: string;
  canonical_name: string;
  cpt_code: string;
  category: string;
  cost_tier: string;
  visits_required: string[];
  total_occurrences: number;
  firm_occurrences: number;
  conditional_occurrences: number;
  is_phone_call: boolean;
  estimated_unit_cost: number;
  avg_confidence: number;
  source_pages: number[];
  issues: string[];
  notes: string;
}

export interface KnowledgeElement {
  ke_id: string;
  ke_type: string;
  title: string;
  content: string;
  source_pages: number[];
  status: string;
  version: string;
  metadata: Record<string, unknown>;
  children: string[];
  relationships: KERelationship[];
}

export interface KERelationship {
  rel_type: string;
  target_ke_id: string;
  properties: Record<string, unknown>;
}

// ─── Protocol API Functions ──────────────────────────────────────────────────

export async function listProtocols(): Promise<ProtocolSummary[]> {
  const res = await fetch(`${API_BASE}/api/protocols`);
  if (!res.ok) throw new Error("Failed to list protocols");
  return res.json();
}

export async function getProtocol(protocolId: string): Promise<ProtocolFull> {
  const res = await fetch(`${API_BASE}/api/protocols/${protocolId}`);
  if (!res.ok) throw new Error("Failed to fetch protocol");
  return res.json();
}

export async function getProtocolSections(protocolId: string): Promise<SectionNode[]> {
  const res = await fetch(`${API_BASE}/api/protocols/${protocolId}/sections`);
  if (!res.ok) throw new Error("Failed to fetch sections");
  return res.json();
}

export async function getSectionContent(protocolId: string, sectionNumber: string): Promise<SectionNode> {
  const res = await fetch(`${API_BASE}/api/protocols/${protocolId}/sections/${sectionNumber}`);
  if (!res.ok) throw new Error("Failed to fetch section content");
  return res.json();
}

export async function getProtocolBudget(protocolId: string): Promise<BudgetLine[]> {
  const res = await fetch(`${API_BASE}/api/protocols/${protocolId}/budget`);
  if (!res.ok) throw new Error("Failed to fetch budget");
  return res.json();
}

export async function getKnowledgeElements(protocolId: string, keType?: string): Promise<KnowledgeElement[]> {
  const url = keType
    ? `${API_BASE}/api/protocols/${protocolId}/knowledge-elements?ke_type=${keType}`
    : `${API_BASE}/api/protocols/${protocolId}/knowledge-elements`;
  const res = await fetch(url);
  if (!res.ok) throw new Error("Failed to fetch knowledge elements");
  return res.json();
}

// ─── Review & Assistant API Functions ────────────────────────────────────────

export async function askProtocol(protocolId: string, question: string, sectionContext?: string): Promise<AssistantMessage> {
  const res = await fetch(`${API_BASE}/api/protocols/${protocolId}/ask`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ question, section_context: sectionContext }),
  });
  if (!res.ok) throw new Error('Failed to get answer');
  return res.json();
}

export async function submitCellReview(action: CellReviewAction): Promise<{ success: boolean }> {
  const res = await fetch(`${API_BASE}/api/protocols/${action.protocol_id}/review`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(action),
  });
  if (!res.ok) throw new Error('Failed to submit review');
  return res.json();
}

// ─── Procedure Library API Functions ─────────────────────────────────────────

export async function listProcedures(): Promise<ProcedureEntry[]> {
  const res = await fetch(`${API_BASE}/api/procedures/library`);
  if (!res.ok) throw new Error('Failed to list procedures');
  return res.json();
}

export async function updateProcedure(canonicalName: string, updates: Partial<ProcedureEntry>): Promise<{ status: string }> {
  const res = await fetch(`${API_BASE}/api/procedures/${encodeURIComponent(canonicalName)}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(updates),
  });
  if (!res.ok) throw new Error('Failed to update procedure');
  return res.json();
}

export async function deleteProcedure(canonicalName: string): Promise<{ status: string }> {
  const res = await fetch(`${API_BASE}/api/procedures/${encodeURIComponent(canonicalName)}`, {
    method: 'DELETE',
  });
  if (!res.ok) throw new Error('Failed to delete procedure');
  return res.json();
}

// ─── Section Parser & Verbatim API Functions ─────────────────────────────────

export interface ParsedSection {
  number: string;
  title: string;
  page: number;
  end_page: number | null;
  level: number;
  children: ParsedSection[];
}

export interface SectionParseResult {
  sections: ParsedSection[];
  total: number;
  outline: string;
  method: string;
}

export async function parseSections(file: File, useLlm?: boolean): Promise<SectionParseResult> {
  const formData = new FormData();
  formData.append("file", file);
  const url = useLlm
    ? `${API_BASE}/api/sections?use_llm=true`
    : `${API_BASE}/api/sections`;
  const res = await fetch(url, { method: "POST", body: formData });
  if (!res.ok) throw new Error("Failed to parse sections");
  return res.json();
}

export interface VerbatimResult {
  instruction: string;
  sections_found: string[];
  content_type: string;
  text: string;
  tables: unknown[];
  source_pages: number[];
  explanation: string;
  is_verbatim: boolean;
}

export async function extractVerbatim(
  file: File,
  instruction: string,
  outputFormat: "text" | "html" = "html",
): Promise<VerbatimResult> {
  const formData = new FormData();
  formData.append("file", file);
  const params = new URLSearchParams({
    instruction,
    output_format: outputFormat,
  });
  const res = await fetch(`${API_BASE}/api/verbatim?${params}`, {
    method: "POST",
    body: formData,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: "Extraction failed" }));
    throw new Error(err.detail || "Verbatim extraction failed");
  }
  return res.json();
}

export async function extractVerbatimFromProtocol(
  protocolId: string,
  instruction: string,
  outputFormat: "text" | "html" = "html",
): Promise<VerbatimResult> {
  const res = await fetch(`${API_BASE}/api/protocols/${protocolId}/verbatim`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ instruction, output_format: outputFormat }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: "Extraction failed" }));
    throw new Error(err.detail || "Verbatim extraction failed");
  }
  return res.json();
}

// ─── PDF Page Image ──────────────────────────────────────────────────────────

export function getPageImageUrl(protocolId: string, pageNumber: number): string {
  return `${API_BASE}/api/protocols/${protocolId}/page-image/${pageNumber}`;
}

// ─── SMB (Structured Model Builder) API Functions ────────────────────────────

export interface SMBGraphNode {
  id: string;
  type: string;
  label: string;
  properties: Record<string, unknown>;
  confidence: string;
}

export interface SMBGraphEdge {
  id: string;
  type: string;
  source: string;
  target: string;
  properties: Record<string, unknown>;
  confidence: number;
}

export interface SMBGraph {
  document_id: string;
  domain: string;
  nodes: SMBGraphNode[];
  edges: SMBGraphEdge[];
  metadata: Record<string, unknown>;
  entity_counts: Record<string, number>;
}

export interface SMBSummary {
  document_id: string;
  domain: string;
  total_entities: number;
  total_relationships: number;
  entity_types: Record<string, number>;
  relationship_types: Record<string, number>;
  version: number;
}

export interface SMBBuildResult {
  status: "ready" | "building" | "error";
  protocol_id: string;
  summary?: SMBSummary;
  build_time_seconds?: number;
  inference_rules_fired?: string[];
  validation_passed?: boolean;
}

export interface SMBModelInfo {
  protocol_id: string;
  summary: SMBSummary;
  build_time_seconds: number;
  inference_rules_fired: string[];
  validation_passed: boolean;
  validation_errors: string[];
  validation_warnings: string[];
  timeline: SMBVisitTimeline[];
}

export interface SMBVisitTimeline {
  visit_name: string;
  day_number: number | null;
  window_minus: number;
  window_plus: number;
  window_unit: string;
  is_unscheduled: boolean;
  cycle: number | null;
  procedure_count: number;
}

export interface SMBScheduleEntry {
  procedure: string;
  canonical_name: string;
  cpt_code: string;
  category: string;
  cost_tier: string;
  visits_required: string[];
  total_occurrences: number;
  firm_occurrences: number;
  conditional_occurrences: number;
  is_phone_call: boolean;
  cost_multiplier: number;
  subset_fraction: number;
  avg_confidence: number;
  source_pages: number[];
}

export async function buildSMBModel(protocolId: string): Promise<SMBBuildResult> {
  const res = await fetch(`${API_BASE}/api/smb/build/${protocolId}`, {
    method: "POST",
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: "SMB build failed" }));
    throw new Error(err.detail || "SMB build failed");
  }
  return res.json();
}

export async function getSMBModel(protocolId: string): Promise<SMBModelInfo> {
  const res = await fetch(`${API_BASE}/api/smb/model/${protocolId}`);
  if (!res.ok) throw new Error("SMB model not available");
  return res.json();
}

export async function getSMBSchedule(protocolId: string): Promise<{ protocol_id: string; schedule: SMBScheduleEntry[] }> {
  const res = await fetch(`${API_BASE}/api/smb/model/${protocolId}/schedule`);
  if (!res.ok) throw new Error("SMB schedule not available");
  return res.json();
}

export async function getSMBGraph(protocolId: string): Promise<SMBGraph> {
  const res = await fetch(`${API_BASE}/api/smb/model/${protocolId}/graph`);
  if (!res.ok) throw new Error("SMB graph not available");
  return res.json();
}

// ─── Feedback System API Functions ──────────────────────────────────────────

export interface FeedbackEntry {
  id: string;
  submitted_at: number;
  updated_at: number;
  category: string;
  title: string;
  description: string;
  priority: string;
  page_url: string;
  status: string;
  triage: FeedbackTriage | null;
  delivery_report: DeliveryReport | null;
  resolution: string | null;
  delivered_at: number | null;
}

export interface FeedbackTriage {
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
}

export interface DeliveryReport {
  title: string;
  status: string;
  triage_summary: string;
  fix_applied: string;
  spec: Record<string, unknown>;
  tdd_plan: Record<string, unknown>;
  delivered_at: number;
}

export async function submitFeedback(feedback: {
  category: string;
  title: string;
  description: string;
  priority: string;
  page_url: string;
  attachments?: { data: string; filename: string }[];
}): Promise<{ id: string; status: string; message: string }> {
  const res = await fetch(`${API_BASE}/api/feedback`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(feedback),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: "Failed to submit" }));
    throw new Error(err.detail || "Feedback submission failed");
  }
  return res.json();
}

export async function listFeedback(
  status?: string,
  limit = 50,
  offset = 0,
): Promise<{ items: FeedbackEntry[]; total: number }> {
  const params = new URLSearchParams();
  if (status && status !== "all") params.set("status", status);
  params.set("limit", String(limit));
  params.set("offset", String(offset));
  const res = await fetch(`${API_BASE}/api/feedback?${params}`);
  if (!res.ok) throw new Error("Failed to list feedback");
  return res.json();
}

export async function getFeedback(entryId: string): Promise<FeedbackEntry> {
  const res = await fetch(`${API_BASE}/api/feedback/${entryId}`);
  if (!res.ok) throw new Error("Feedback not found");
  return res.json();
}

export async function updateFeedbackStatus(
  entryId: string,
  status: string,
  resolution?: string,
): Promise<FeedbackEntry> {
  const res = await fetch(`${API_BASE}/api/feedback/${entryId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ status, resolution }),
  });
  if (!res.ok) throw new Error("Failed to update feedback");
  return res.json();
}
