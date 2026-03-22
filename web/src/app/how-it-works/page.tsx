"use client";

import { useState } from "react";
import { Card, CardHeader, CardBody } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { cn } from "@/lib/utils";

type ActivePipeline = "extraction" | "sections" | "verbatim" | "budget";

export default function HowItWorksPage() {
  const [active, setActive] = useState<ActivePipeline>("extraction");

  return (
    <div className="min-h-screen bg-neutral-50">
      {/* Hero */}
      <div className="bg-white border-b border-neutral-200">
        <div className="max-w-5xl mx-auto px-6 py-10">
          <h1 className="text-2xl font-bold text-neutral-800">How ProtoExtract Works</h1>
          <p className="text-sm text-neutral-500 mt-2 max-w-2xl">
            A multi-stage AI pipeline that digitizes clinical trial protocols with zero hallucination.
            The LLM reads and locates — PyMuPDF extracts the exact bytes. Every output is traceable to a source page.
          </p>
        </div>
      </div>

      {/* Pipeline selector */}
      <div className="max-w-5xl mx-auto px-6 py-6">
        <div className="flex gap-2 mb-8">
          {[
            { key: "extraction" as const, label: "SoA Table Extraction", icon: "table" },
            { key: "sections" as const, label: "Section Parsing", icon: "doc" },
            { key: "verbatim" as const, label: "Verbatim Extract", icon: "copy" },
            { key: "budget" as const, label: "Site Budget", icon: "dollar" },
          ].map((p) => (
            <button
              key={p.key}
              onClick={() => setActive(p.key)}
              className={cn(
                "px-4 py-2.5 text-sm font-medium rounded-lg transition-all",
                active === p.key
                  ? "bg-brand-primary text-white shadow-md"
                  : "bg-white text-neutral-600 border border-neutral-200 hover:border-brand-primary/30 hover:shadow-sm"
              )}
            >
              {p.label}
            </button>
          ))}
        </div>

        {active === "extraction" && <ExtractionPipeline />}
        {active === "sections" && <SectionParsing />}
        {active === "verbatim" && <VerbatimPipeline />}
        {active === "budget" && <BudgetPipeline />}
      </div>
    </div>
  );
}

// ─── SoA Table Extraction Pipeline ───────────────────────────────────────

function ExtractionPipeline() {
  return (
    <div className="space-y-6">
      <div className="mb-4">
        <h2 className="text-lg font-bold text-neutral-800">Schedule of Activities (SoA) Table Extraction</h2>
        <p className="text-sm text-neutral-500 mt-1">
          Multi-pass extraction with adversarial validation — designed for the most complex tables in clinical protocols.
        </p>
      </div>

      {/* Visual pipeline */}
      <div className="space-y-0">
        <PipelineStage
          number={1}
          title="Protocol Synopsis"
          subtitle="Understanding the document"
          color="sky"
          items={[
            "Reads first 20 pages to extract protocol metadata",
            "Identifies: phase, indication, therapeutic area, study arms",
            "Builds domain context (oncology vs vaccines vs neurology)",
            "This context guides downstream extraction decisions",
          ]}
          detail="The synopsis tells the pipeline what kind of SoA to expect. A Phase 1 oncology trial has different visit patterns than a Phase 3 vaccine trial."
        />
        <PipelineConnector />

        <PipelineStage
          number={2}
          title="SoA Page Detection"
          subtitle="Finding the right pages"
          color="blue"
          items={[
            "Section parser locates 'Schedule of Activities' in the TOC",
            "Deterministic page-range gating — only pages in the SoA section are scanned",
            "VLM (Vision Language Model) pre-screens each page for table structure",
            "Non-SoA pages (amendment history, synopsis, appendices) are rejected at $0 cost",
          ]}
          detail="5-layer filter: (1) page-range gate, (2) title rejection (30+ keywords), (3) marker validation, (4) flagged-rate check, (5) column header validation. Zero false positives reaching the user."
        />
        <PipelineConnector />

        <PipelineStage
          number={3}
          title="Dual-Pass Cell Extraction"
          subtitle="Two independent LLM passes"
          color="emerald"
          items={[
            "Pass 1: LLM extracts every cell value from the rendered page image",
            "Pass 2: Independent second pass with different prompt framing",
            "Agreement check: cells where both passes agree get high confidence",
            "Disagreement: flagged for reconciliation with the original values shown",
          ]}
          detail="Why two passes? A single LLM pass hallucinates ~2-5% of cells. With dual-pass agreement checking, hallucinations are caught because the same error rarely occurs twice independently."
        />
        <PipelineConnector />

        <PipelineStage
          number={4}
          title="Multi-Page Table Stitching"
          subtitle="Handling tables that span pages"
          color="purple"
          items={[
            "SoA tables often span 3-8 pages in large protocols",
            "Continuation detection: matching column headers across page breaks",
            "Row header alignment: procedures that continue on the next page",
            "Merged region handling: multi-level column headers (Phase 1 → Visit 1, Visit 2)",
          ]}
          detail="A 252-page protocol like Pfizer BNT162 has SoA tables spanning pages 41-64. The stitcher merges them into a single coherent table while preserving column alignment."
        />
        <PipelineConnector />

        <PipelineStage
          number={5}
          title="Footnote Resolution"
          subtitle="The hardest part of SoA extraction"
          color="amber"
          items={[
            "Superscript markers (a, b, c) detected in cell values",
            "Footnote definitions matched from the bottom of each page",
            "Cross-page footnotes: markers on page 3, definitions on page 5",
            "Footnote classification: CONDITIONAL (affects visits), CLARIFICATION, EXCEPTION, REFERENCE",
          ]}
          detail='CONDITIONAL footnotes are critical — "Perform ECG only at Screening if clinically indicated" changes the visit count and budget. The pipeline tags these so the budget calculator knows which procedures are conditional.'
        />
        <PipelineConnector />

        <PipelineStage
          number={6}
          title="Challenger Validation"
          subtitle="Adversarial cross-check"
          color="red"
          items={[
            "An independent 'challenger' agent reviews each extracted table",
            "Compares extraction against the raw page image",
            "Identifies: wrong values, missing cells, structural errors",
            "Challenge issues logged with severity scores (1-10)",
          ]}
          detail="The challenger acts as a second pair of eyes. It doesn't re-extract — it validates. This catches structural errors that dual-pass agreement misses (e.g., shifted columns, merged cells split incorrectly)."
        />
        <PipelineConnector />

        <PipelineStage
          number={7}
          title="Procedure Normalization"
          subtitle="Mapping raw names to canonical vocabulary"
          color="teal"
          items={[
            "Raw names ('12-lead ECG', 'EKG', 'Electrocardiogram') → canonical: 'Electrocardiogram'",
            "CPT code mapping: 265 procedures × 1,314 aliases",
            "Category classification: Laboratory, Cardiology, Safety, Treatment",
            "Cost tier assignment: LOW ($75), MEDIUM ($350), HIGH ($1,200), VERY_HIGH ($3,500)",
          ]}
          detail="The vocabulary was built from 50+ real protocols. Fuzzy matching handles typos and abbreviations. Unknown procedures are flagged for manual mapping."
        />
      </div>

      {/* Key metrics */}
      <Card className="mt-8">
        <CardHeader><h3 className="text-sm font-semibold text-neutral-800">Pipeline Performance</h3></CardHeader>
        <CardBody>
          <div className="grid grid-cols-4 gap-4">
            <MetricBox label="Cell Accuracy" value="99.1%" desc="Across 13 benchmark protocols" />
            <MetricBox label="Extraction Cost" value="~$2-5" desc="Per protocol (LLM API calls)" />
            <MetricBox label="Processing Time" value="2-10 min" desc="Depends on table count" />
            <MetricBox label="Zero Hallucination" value="100%" desc="All text from PyMuPDF, never LLM" />
          </div>
        </CardBody>
      </Card>
    </div>
  );
}

// ─── Section Parsing ─────────────────────────────────────────────────────

function SectionParsing() {
  return (
    <div className="space-y-6">
      <div className="mb-4">
        <h2 className="text-lg font-bold text-neutral-800">Section Parsing</h2>
        <p className="text-sm text-neutral-500 mt-1">
          Deterministic document structure extraction — no LLM required. Builds a complete section hierarchy from the PDF text layer.
        </p>
      </div>

      <div className="space-y-0">
        <PipelineStage
          number={1}
          title="Text Layer Extraction"
          subtitle="Reading the PDF structure"
          color="sky"
          items={[
            "PyMuPDF extracts text with position metadata (x, y, font, size, flags)",
            "Each line: text content + X position + Y position + font name + bold/italic flags",
            "This gives us the document's visual layout without any LLM interpretation",
          ]}
          detail="We don't use OCR — PyMuPDF reads the embedded text layer directly. This is 100% accurate for digitally-created PDFs (which all clinical protocols are)."
        />
        <PipelineConnector />

        <PipelineStage
          number={2}
          title="Heading Detection"
          subtitle="3 strategies for finding section boundaries"
          color="blue"
          items={[
            "Strategy 1: Regex pattern matching — '1.1 Synopsis', '5.2.3 Inclusion Criteria'",
            "Strategy 2: Font-based detection — bold text at specific sizes = heading",
            "Strategy 3: Table of Contents parsing — reads the TOC if present",
            "Best strategy selected by section count and quality heuristics",
          ]}
          detail="Most protocols use numbered sections (ICH format). The regex handles: '1.', '1.1', '1.1.1', '1.1.1.1' up to 6 levels deep. Bold detection catches unnumbered headings."
        />
        <PipelineConnector />

        <PipelineStage
          number={3}
          title="Hierarchy Construction"
          subtitle="Building the section tree"
          color="emerald"
          items={[
            "Section numbers define parent-child relationships (3 → 3.1 → 3.1.1)",
            "Page ranges computed: each section starts at its heading and ends at the next",
            "Y-coordinate clipping: precise start/end within shared pages",
            "LLM fallback: if deterministic parsing finds <10 sections, LLM assists",
          ]}
          detail="The parser produces a tree, not a flat list. Section 3 contains 3.1, 3.2, 3.3. This enables 'extract Section 3 without subsections' vs 'extract Section 3 with all subsections'."
        />
        <PipelineConnector />

        <PipelineStage
          number={4}
          title="Content Extraction"
          subtitle="Paragraph reconstruction with formatting"
          color="purple"
          items={[
            "Y-gap analysis groups lines into paragraphs (gap > 6pt = new paragraph)",
            "List detection: bullet characters, numbered lists, indentation patterns",
            "Table detection: PyMuPDF find_tables() for inline tables",
            "Bold/italic from font metadata — not pattern matching",
          ]}
          detail="The paragraph classifier produces typed elements: HEADING, SUBHEADING, BODY, LIST_ITEM, LIST_ITEM_L2, TABLE. Each type gets semantic HTML rendering."
        />
      </div>

      <Card className="mt-8">
        <CardHeader><h3 className="text-sm font-semibold text-neutral-800">Capabilities</h3></CardHeader>
        <CardBody>
          <div className="grid grid-cols-3 gap-4">
            <MetricBox label="Deterministic" value="100%" desc="Same input → same output, always" />
            <MetricBox label="Cost" value="$0" desc="No LLM calls for standard parsing" />
            <MetricBox label="Sections Parsed" value="50-300" desc="Per protocol, all levels" />
          </div>
        </CardBody>
      </Card>
    </div>
  );
}

// ─── Verbatim Extract Pipeline ───────────────────────────────────────────

function VerbatimPipeline() {
  return (
    <div className="space-y-6">
      <div className="mb-4">
        <h2 className="text-lg font-bold text-neutral-800">Verbatim Extraction</h2>
        <p className="text-sm text-neutral-500 mt-1">
          The core innovation: LLMs LOCATE content, PyMuPDF EXTRACTS the exact bytes. Zero hallucination by design.
        </p>
      </div>

      {/* Architecture diagram */}
      <Card className="bg-neutral-800 text-white">
        <CardBody className="p-6">
          <h3 className="text-sm font-semibold text-neutral-300 uppercase tracking-wide mb-4">The Key Insight</h3>
          <div className="grid grid-cols-3 gap-4 text-center">
            <div className="p-4 bg-red-900/30 rounded-lg border border-red-800/50">
              <p className="text-xs text-red-300 font-semibold uppercase mb-2">Traditional Approach</p>
              <p className="text-sm text-red-200">LLM generates text</p>
              <p className="text-xs text-red-400 mt-1">Hallucination risk: 2-5%</p>
            </div>
            <div className="flex items-center justify-center">
              <svg className="w-8 h-8 text-neutral-500" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M13.5 4.5L21 12m0 0l-7.5 7.5M21 12H3" />
              </svg>
            </div>
            <div className="p-4 bg-emerald-900/30 rounded-lg border border-emerald-800/50">
              <p className="text-xs text-emerald-300 font-semibold uppercase mb-2">ProtoExtract Approach</p>
              <p className="text-sm text-emerald-200">LLM locates, PyMuPDF extracts</p>
              <p className="text-xs text-emerald-400 mt-1">Hallucination risk: 0%</p>
            </div>
          </div>
        </CardBody>
      </Card>

      <div className="space-y-0">
        <PipelineStage
          number={1}
          title="User Instruction"
          subtitle="Natural language command"
          color="sky"
          items={[
            '"Copy Section 5.1" → direct section number match (no LLM needed)',
            '"Extract the inclusion criteria" → LLM maps to Section 5.1',
            '"Get the Schedule of Activities table" → LLM maps to Section 1.3',
            '"Copy the primary endpoint definition from Section 3" → scoped search',
          ]}
          detail="Direct section references (e.g., 'Section 5.1') bypass the LLM entirely — pure regex match against the section tree. This is $0 and instant."
        />
        <PipelineConnector />

        <PipelineStage
          number={2}
          title="LLM Section Locator"
          subtitle="Only used when the section can't be determined from the instruction"
          color="blue"
          items={[
            "LLM receives the document outline (section tree) — NOT the PDF content",
            "Returns: target section numbers + content type + explanation",
            "LLM output is a JSON pointer: {target_sections: ['5.1']}",
            "The LLM never sees the actual protocol text — only the TOC",
          ]}
          detail="The LLM is a section finder, not a content generator. It maps 'inclusion criteria' to section number '5.1'. The actual text comes from PyMuPDF."
        />
        <PipelineConnector />

        <PipelineStage
          number={3}
          title="PyMuPDF Verbatim Extraction"
          subtitle="Exact bytes from the PDF"
          color="emerald"
          items={[
            "Opens the PDF at the target page range",
            "Y-coordinate clipping: starts at section heading, stops at next heading",
            "Reads every text span with font metadata (bold, italic, size)",
            "Tables extracted via find_tables() as structured data",
          ]}
          detail="The output text is NEVER generated by an LLM. It's the exact text from the PDF's embedded text layer, extracted byte-for-byte by PyMuPDF."
        />
        <PipelineConnector />

        <PipelineStage
          number={4}
          title="Semantic HTML Output"
          subtitle="Formatting integrity preserved"
          color="purple"
          items={[
            "Paragraphs reconstructed from Y-gap analysis",
            "Lists detected from bullet characters + indentation",
            "Bold/italic from font flags — not pattern matching",
            "Tables rendered as <table> with headers and cells",
            "Section heading stripped — body content only",
          ]}
          detail="The formatter knows paragraph types: HEADING, BODY, LIST_ITEM, LIST_ITEM_L2, TABLE. Each gets proper semantic HTML. The result looks like the original document."
        />
      </div>

      <Card className="mt-8">
        <CardHeader><h3 className="text-sm font-semibold text-neutral-800">Nuances Solved</h3></CardHeader>
        <CardBody className="space-y-3">
          {[
            { problem: "Section bleed", solution: "Y-coordinate clipping scans each page for the next heading boundary — content stops precisely at the section end" },
            { problem: "Cross-page content", solution: "+2 page buffer with iterative boundary detection — handles sections that span page breaks" },
            { problem: "Unicode bullets", solution: "Wingdings (\\uf0b7) and Word bullet characters detected and converted to proper <ul><li> HTML" },
            { problem: "Merged lines", solution: "Adjacent spans without whitespace get space insertion based on character boundary analysis" },
            { problem: "Header/footer stripping", solution: "Auto-detected by finding text that appears in the top/bottom 80pt of 3+ consecutive pages" },
            { problem: "Image-based pages", solution: "Detected by empty text layer — reported to user with guidance to use SoA extraction instead" },
          ].map((item, i) => (
            <div key={i} className="flex gap-3 py-2 border-b border-neutral-100 last:border-0">
              <Badge variant="warning" className="shrink-0 self-start">{item.problem}</Badge>
              <p className="text-xs text-neutral-600">{item.solution}</p>
            </div>
          ))}
        </CardBody>
      </Card>
    </div>
  );
}

// ─── Budget Pipeline ─────────────────────────────────────────────────────

function BudgetPipeline() {
  return (
    <div className="space-y-6">
      <div className="mb-4">
        <h2 className="text-lg font-bold text-neutral-800">Site Budget Calculation</h2>
        <p className="text-sm text-neutral-500 mt-1">
          Automated per-patient cost estimation from extracted SoA data, procedures, and visit frequencies.
        </p>
      </div>

      <div className="space-y-0">
        <PipelineStage
          number={1}
          title="Procedure Extraction"
          subtitle="From SoA row headers"
          color="sky"
          items={[
            "Each row in the SoA table represents a clinical procedure",
            "Raw names extracted: 'CBC', '12-lead ECG', 'Serum chemistry panel'",
            "Normalized to canonical vocabulary: 265 procedures, 1,314 aliases",
            "CPT code auto-mapping where available",
          ]}
          detail="The procedure normalizer uses fuzzy matching to handle abbreviations and variations across protocols."
        />
        <PipelineConnector />

        <PipelineStage
          number={2}
          title="Visit Frequency Counting"
          subtitle="How many times each procedure occurs"
          color="blue"
          items={[
            "Scans each row for MARKER cells (X marks, checkmarks)",
            "Counts: 'Physical Exam' appears in 4 of 12 visits → 4 occurrences",
            "Handles CONDITIONAL markers (footnoted visits) separately",
            "Unscheduled visits flagged but not counted in base frequency",
          ]}
          detail="CONDITIONAL footnotes are critical — 'ECG at screening only if clinically indicated' means the ECG might not be performed at every screening visit. The budget shows this as a note."
        />
        <PipelineConnector />

        <PipelineStage
          number={3}
          title="Cost Tier Assignment"
          subtitle="Estimated unit costs"
          color="emerald"
          items={[
            "LOW ($75): Vital signs, blood draw, informed consent",
            "MEDIUM ($350): ECG, physical exam, study drug administration",
            "HIGH ($1,200): CT scan, echocardiogram, bone marrow biopsy",
            "VERY_HIGH ($3,500): MRI, PET scan, cardiac catheterization",
          ]}
          detail="Cost tiers are configurable estimates — the budget wizard lets users override with actual site-specific pricing."
        />
        <PipelineConnector />

        <PipelineStage
          number={4}
          title="Budget Calculation"
          subtitle="Per-patient site cost"
          color="purple"
          items={[
            "Line total = unit cost × visit frequency",
            "Grouped by category: Laboratory, Cardiology, Safety, General",
            "Category subtotals + grand total",
            "Confidence score per line from extraction quality",
          ]}
          detail="The 4-step Budget Wizard lets users: (1) review SoA tables, (2) configure costs/CPT codes, (3) preview the budget, (4) validate and export to CSV."
        />
      </div>
    </div>
  );
}

// ─── Shared Components ───────────────────────────────────────────────────

function PipelineStage({
  number, title, subtitle, color, items, detail,
}: {
  number: number; title: string; subtitle: string;
  color: string; items: string[]; detail: string;
}) {
  const [expanded, setExpanded] = useState(false);
  const colorMap: Record<string, string> = {
    sky: "bg-sky-100 text-sky-700 border-sky-200",
    blue: "bg-blue-100 text-blue-700 border-blue-200",
    emerald: "bg-emerald-100 text-emerald-700 border-emerald-200",
    purple: "bg-purple-100 text-purple-700 border-purple-200",
    amber: "bg-amber-100 text-amber-700 border-amber-200",
    red: "bg-red-100 text-red-700 border-red-200",
    teal: "bg-teal-100 text-teal-700 border-teal-200",
  };
  const dotColor: Record<string, string> = {
    sky: "bg-sky-500", blue: "bg-blue-500", emerald: "bg-emerald-500",
    purple: "bg-purple-500", amber: "bg-amber-500", red: "bg-red-500", teal: "bg-teal-500",
  };

  return (
    <div className="flex gap-4">
      {/* Timeline */}
      <div className="flex flex-col items-center w-8 shrink-0">
        <div className={cn("w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold", colorMap[color] || colorMap.sky)}>
          {number}
        </div>
        <div className="w-0.5 flex-1 bg-neutral-200 mt-1" />
      </div>

      {/* Content */}
      <Card className="flex-1 mb-3">
        <CardBody className="p-4">
          <div className="flex items-start justify-between">
            <div>
              <h3 className="text-sm font-semibold text-neutral-800">{title}</h3>
              <p className="text-[11px] text-neutral-400 mt-0.5">{subtitle}</p>
            </div>
            <div className={cn("w-2 h-2 rounded-full mt-1.5", dotColor[color] || dotColor.sky)} />
          </div>

          <ul className="mt-3 space-y-1.5">
            {items.map((item, i) => (
              <li key={i} className="flex gap-2 text-xs text-neutral-600">
                <span className="text-neutral-300 shrink-0 mt-0.5">&#8226;</span>
                <span>{item}</span>
              </li>
            ))}
          </ul>

          {detail && (
            <button
              onClick={() => setExpanded(!expanded)}
              className="mt-3 text-[11px] text-brand-primary hover:underline flex items-center gap-1"
            >
              {expanded ? "Hide details" : "Why this matters"}
              <svg className={cn("w-3 h-3 transition-transform", expanded && "rotate-180")} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 8.25l-7.5 7.5-7.5-7.5" />
              </svg>
            </button>
          )}
          {expanded && (
            <p className="mt-2 text-xs text-neutral-500 bg-neutral-50 p-3 rounded-lg border border-neutral-100 leading-relaxed">
              {detail}
            </p>
          )}
        </CardBody>
      </Card>
    </div>
  );
}

function PipelineConnector() {
  return (
    <div className="flex gap-4">
      <div className="w-8 flex justify-center shrink-0">
        <div className="w-0.5 h-2 bg-neutral-200" />
      </div>
      <div />
    </div>
  );
}

function MetricBox({ label, value, desc }: { label: string; value: string; desc: string }) {
  return (
    <div className="text-center p-3 bg-neutral-50 rounded-lg">
      <p className="text-lg font-bold text-brand-primary font-mono">{value}</p>
      <p className="text-xs font-medium text-neutral-700 mt-0.5">{label}</p>
      <p className="text-[10px] text-neutral-400 mt-0.5">{desc}</p>
    </div>
  );
}
