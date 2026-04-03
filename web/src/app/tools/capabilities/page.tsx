"use client";

import { useState } from "react";
import { Card, CardHeader, CardBody } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { cn } from "@/lib/utils";

type Section = "pipeline" | "formula" | "formats" | "quality" | "architecture";

export default function CapabilitiesPage() {
  const [active, setActive] = useState<Section>("pipeline");

  return (
    <div className="min-h-screen bg-neutral-50">
      {/* Hero */}
      <div className="bg-white border-b border-neutral-200">
        <div className="max-w-5xl mx-auto px-6 py-10">
          <h1 className="text-2xl font-bold text-neutral-800">
            Pipeline Capabilities
          </h1>
          <p className="text-sm text-neutral-500 mt-2 max-w-2xl">
            Technical documentation of the document conversion pipeline,
            formula detection system, and quality assurance tools. Every
            number on this page is derived from the codebase.
          </p>
        </div>
      </div>

      {/* Section selector */}
      <div className="max-w-5xl mx-auto px-6 py-6">
        <div className="flex gap-2 mb-8 flex-wrap">
          {[
            { key: "pipeline" as const, label: "Pipeline Overview" },
            { key: "formula" as const, label: "Formula Detection" },
            { key: "formats" as const, label: "Document Formats" },
            { key: "quality" as const, label: "Quality Assurance" },
            { key: "architecture" as const, label: "Architecture" },
          ].map((s) => (
            <button
              key={s.key}
              onClick={() => setActive(s.key)}
              className={cn(
                "px-4 py-2.5 text-sm font-medium rounded-lg transition-all",
                active === s.key
                  ? "bg-brand-primary text-white shadow-md"
                  : "bg-white text-neutral-600 border border-neutral-200 hover:border-brand-primary/30 hover:shadow-sm"
              )}
            >
              {s.label}
            </button>
          ))}
        </div>

        {active === "pipeline" && <PipelineOverview />}
        {active === "formula" && <FormulaDetection />}
        {active === "formats" && <DocumentFormats />}
        {active === "quality" && <QualityAssurance />}
        {active === "architecture" && <ArchitectureSection />}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Section 1: Pipeline Overview
// ---------------------------------------------------------------------------

function PipelineOverview() {
  return (
    <div className="space-y-6">
      <div className="mb-4">
        <h2 className="text-lg font-bold text-neutral-800">Pipeline Overview</h2>
        <p className="text-sm text-neutral-500 mt-1">
          The document conversion pipeline transforms any supported input format
          into any supported output format through a shared intermediate
          representation (IR).
        </p>
      </div>

      {/* Flow diagram */}
      <Card>
        <CardHeader>
          <h3 className="text-sm font-semibold text-neutral-800">
            Conversion Flow
          </h3>
        </CardHeader>
        <CardBody>
          <div className="flex items-center gap-3 overflow-x-auto py-2">
            <FlowBox label="Input" sub="7 formats" color="sky" />
            <FlowArrow />
            <FlowBox label="Ingest" sub="Format-specific parser" color="blue" />
            <FlowArrow />
            <FlowBox label="FormattedDocument IR" sub="Canonical model" color="emerald" />
            <FlowArrow />
            <FlowBox label="Formula Enrichment" sub="Optional step" color="purple" />
            <FlowArrow />
            <FlowBox label="Render" sub="Format-specific writer" color="amber" />
            <FlowArrow />
            <FlowBox label="Output" sub="7 formats" color="red" />
          </div>
        </CardBody>
      </Card>

      {/* Format matrix */}
      <Card>
        <CardHeader>
          <h3 className="text-sm font-semibold text-neutral-800">
            Supported Formats
          </h3>
        </CardHeader>
        <CardBody>
          <div className="grid grid-cols-2 gap-6">
            {/* Input */}
            <div>
              <p className="text-xs font-semibold text-neutral-500 uppercase tracking-wide mb-3">
                Input (Ingestors)
              </p>
              <div className="space-y-2">
                {[
                  { fmt: "PDF", tool: "FormattingExtractor", lib: "PyMuPDF" },
                  { fmt: "DOCX", tool: "DOCXIngestor", lib: "python-docx" },
                  { fmt: "HTML", tool: "HTMLIngestor", lib: "stdlib html.parser" },
                  { fmt: "Markdown", tool: "MarkdownIngestor", lib: "regex-based" },
                  { fmt: "Plain Text", tool: "TextIngestor", lib: "structure detection" },
                  { fmt: "PPTX", tool: "PPTXIngestor", lib: "python-pptx" },
                  { fmt: "XLSX", tool: "ExcelIngestor", lib: "openpyxl" },
                ].map((row) => (
                  <div key={row.fmt} className="flex items-center gap-2">
                    <Badge variant="success">{row.fmt}</Badge>
                    <span className="text-xs text-neutral-600">
                      <code className="text-[11px] bg-neutral-100 px-1 py-0.5 rounded">{row.tool}</code>
                      {" "}via {row.lib}
                    </span>
                  </div>
                ))}
              </div>
            </div>

            {/* Output */}
            <div>
              <p className="text-xs font-semibold text-neutral-500 uppercase tracking-wide mb-3">
                Output (Renderers)
              </p>
              <div className="space-y-2">
                {[
                  { fmt: "DOCX", tool: "DOCXRenderer", lib: "python-docx" },
                  { fmt: "HTML", tool: "HTMLRenderer", lib: "semantic HTML5" },
                  { fmt: "Markdown", tool: "MarkdownRenderer", lib: "CommonMark" },
                  { fmt: "Plain Text", tool: "TextRenderer", lib: "structured text" },
                  { fmt: "JSON", tool: "JSONRenderer", lib: "full IR serialization" },
                  { fmt: "PDF", tool: "PDFRenderer", lib: "reportlab" },
                  { fmt: "PPTX", tool: "PPTXRenderer", lib: "python-pptx" },
                ].map((row) => (
                  <div key={row.fmt} className="flex items-center gap-2">
                    <Badge variant="success">{row.fmt}</Badge>
                    <span className="text-xs text-neutral-600">
                      <code className="text-[11px] bg-neutral-100 px-1 py-0.5 rounded">{row.tool}</code>
                      {" "}{row.lib}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </CardBody>
      </Card>

      {/* Cross-format coverage */}
      <Card>
        <CardHeader>
          <h3 className="text-sm font-semibold text-neutral-800">
            Cross-Format Conversion Matrix
          </h3>
        </CardHeader>
        <CardBody>
          <p className="text-xs text-neutral-500 mb-4">
            Because all formats pass through the shared{" "}
            <code className="text-[11px] bg-neutral-100 px-1 py-0.5 rounded">FormattedDocument</code>{" "}
            IR, every input/output pair is supported. 7 inputs x 7 outputs = 49
            conversion paths, all operational.
          </p>
          <ConversionMatrix />
        </CardBody>
      </Card>

      {/* Key metrics */}
      <Card>
        <CardHeader>
          <h3 className="text-sm font-semibold text-neutral-800">
            Pipeline Metrics
          </h3>
        </CardHeader>
        <CardBody>
          <div className="grid grid-cols-4 gap-4">
            <MetricBox label="Input Formats" value="7" desc="PDF, DOCX, HTML, MD, TXT, PPTX, XLSX" />
            <MetricBox label="Output Formats" value="7" desc="DOCX, HTML, MD, TXT, JSON, PDF, PPTX" />
            <MetricBox label="Conversion Paths" value="49" desc="100% cross-format coverage" />
            <MetricBox label="Pipeline Tools" value="14" desc="7 ingestors + 7 renderers" />
          </div>
        </CardBody>
      </Card>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Section 2: Formula Detection Pipeline
// ---------------------------------------------------------------------------

function FormulaDetection() {
  return (
    <div className="space-y-6">
      <div className="mb-4">
        <h2 className="text-lg font-bold text-neutral-800">
          Formula Detection Pipeline
        </h2>
        <p className="text-sm text-neutral-500 mt-1">
          A 4-tier detection system that identifies and renders pharmaceutical
          formulas from text and images. The orchestrator queries the tool
          registry per step -- no hardcoded workflows.
        </p>
      </div>

      <div className="space-y-0">
        {/* Step 1 */}
        <PipelineStage
          number={1}
          title="Document Ingestion"
          subtitle="Raw bytes to FormattedDocument IR"
          color="sky"
          items={[
            "Converts raw file bytes into a FormattedDocument intermediate representation",
            "Each ingestor extracts formatting metadata: bold, italic, underline, font name, size, color, super/subscript",
            "PDF: PyMuPDF (span-level flags, font, size, color, position)",
            "DOCX: python-docx (style inheritance chain: run > paragraph style > document defaults)",
            "HTML: stdlib html.parser (semantic tag mapping)",
            "PPTX: python-pptx (defRPr XML + size heuristic for bold resolution)",
            "XLSX: openpyxl (cell formatting, merged cells)",
          ]}
          toolName="DocHandler / PipelineOrchestrator"
          detail="The IR preserves all formatting metadata from the source document. This is what enables high-fidelity round-trip conversion and accurate formula enrichment."
        />
        <PipelineConnector />

        {/* Step 2 */}
        <PipelineStage
          number={2}
          title="Formula Detection -- Tier 1+2 (Inline)"
          subtitle="Regex-based detection of inline pharma formulas"
          color="blue"
          items={[
            "51 compiled regex patterns organized by category",
            "Chemical: CO2, H2O, O2, N2, HbA1c, PO4, Ca2+, Na+, K+, Cl-",
            "PK parameters: AUC0-inf, AUC0-t, Cmax, Cmin, Css, t1/2, tmax, Vd",
            "Dosing: mg/m2, mg/mm3, x10^n, Cockcroft-Gault, CKD-EPI, BSA",
            "Statistical: p<0.05, HR, OR, RR, CI, %RSD, %CV, GMT, GMFR, SD, SEM",
            "Mathematical: cm2, m3, 10^n, sigma2, log10, log2, ln, nested exponents",
            "Each match produces a DetectedFormulaSpan with HTML + LaTeX representations",
          ]}
          toolName="RegexFormulaDetector"
          detail="This is the workhorse detector. It handles approximately 75% of formulas found in pharmaceutical documents. Priority 90 (highest among detectors). Confidence: 1.0 for all regex matches."
        />
        <PipelineConnector />

        {/* Step 3 */}
        <PipelineStage
          number={3}
          title="Formula Detection -- Tier 3 (Structured Math)"
          subtitle="Parser-based detection of complex notation"
          color="emerald"
          items={[
            "9 pattern categories requiring full LaTeX representation",
            "Partial derivatives: d2y/dx2 (second-order), df/dx (first-order)",
            "Integrals: bounded (int_a^b f(x)dx) and bare (integral sign)",
            "Summations: sum_{i=1}^{n} with Unicode support",
            "Products: prod_{i=1}^{n} with Unicode support",
            "Limits: lim_{x->0} and verbal form (lim as x approaches 0)",
            "Factorials: n!, (n-k)!",
            "Combinations/Permutations: C(n,k), nCr, nPr",
            "PK ODEs: dC/dt = -k*C (differential equations with RHS)",
            "Named formulas: Cockcroft-Gault (CrCl), Kaplan-Meier (S(t)), sample size, dissolution f2",
          ]}
          toolName="StructuredParser"
          detail="Covers approximately 15% of formulas -- the structured notation that simple sub/sup HTML cannot represent. Priority 80. Confidence: 0.95 default, 0.85 for less certain matches (e.g., dissolution f2)."
        />
        <PipelineConnector />

        {/* Step 4 */}
        <PipelineStage
          number={4}
          title="Formula Detection -- Tier 4 (Image-Based)"
          subtitle="Image classification and OCR for rendered equations"
          color="purple"
          items={[
            "Stage A: HeuristicImageClassifier screens images using geometry + pixel analysis",
            "Aspect ratio filter: equations are 2:1 to 15:1 (wider than tall)",
            "Size filter: height < 200px, width 100-800px, area 500-200,000px",
            "Monochrome check: 85%+ of pixels must be near-black or near-white (via PIL when available)",
            "Stage B: OCR backends extract LaTeX from classified equation images",
            "ClaudeVisionOCR: Anthropic API (claude-haiku-4-5-20251001), confidence 0.8, priority 80",
            "LocalLaTeXOCR: rapid_latex_ocr or pix2tex, confidence 0.7, priority 60",
            "PlaceholderOCR: no-op fallback (priority 1), ensures graceful degradation",
          ]}
          toolName="HeuristicImageClassifier + OCR backends"
          detail="Handles approximately 8% of formulas -- those rendered as images in PDFs. The image classifier runs first as a fast gate (100ms timeout) so OCR only processes likely equations. VLM escalation available when local OCR confidence is below the configurable threshold (default: 0.6)."
        />
        <PipelineConnector />

        {/* Step 5 */}
        <PipelineStage
          number={5}
          title="Formula Enrichment"
          subtitle="Mapping detections back to document spans"
          color="amber"
          items={[
            "Post-ingestion step: runs after any ingestor produces a FormattedDocument",
            "Collects all spans across paragraph lines, tracking cumulative character offsets",
            "Runs formula detection on the full paragraph text string",
            "Maps detected formula offsets back to individual FormattedSpan objects via overlap check",
            "Sets span.formula for each span whose character range overlaps a detected formula",
            "Handles edge cases: empty paragraphs, image paragraphs, zero-length spans",
          ]}
          toolName="FormulaEnricher"
          detail="This is the bridge between the formula orchestrator (which operates on plain text strings) and the document IR (which stores formatting per-span). Without enrichment, detected formulas would have no connection to the IR and renderers could not use them."
        />
        <PipelineConnector />

        {/* Step 6 */}
        <PipelineStage
          number={6}
          title="Formula Rendering"
          subtitle="LaTeX to target output format"
          color="red"
          items={[
            "HTMLFormulaRenderer: produces <sub>/<sup> HTML tags (always available, no dependencies)",
            "MathMLFormulaRenderer: LaTeX to MathML via latex2mathml (MIT, pure Python)",
            "OmmlFormulaRenderer: LaTeX to MathML to OMML via latex2mathml + mathml2omml (for native Word equations)",
            "Rendering is idempotent -- re-rendering an already-rendered formula is a no-op",
            "Target formats configurable via OrchestratorConfig.render_targets (default: html, mathml)",
          ]}
          toolName="HTMLFormulaRenderer / MathMLFormulaRenderer / OmmlFormulaRenderer"
          detail="The rendering chain flows: LaTeX (canonical) to MathML (for HTML display) and LaTeX to MathML to OMML (for DOCX). Each renderer populates a specific field on the FormattedFormula object."
        />
      </div>

      {/* Orchestrator config */}
      <Card className="mt-8">
        <CardHeader>
          <h3 className="text-sm font-semibold text-neutral-800">
            Orchestrator Configuration
          </h3>
        </CardHeader>
        <CardBody>
          <p className="text-xs text-neutral-500 mb-3">
            All behavior is controlled via{" "}
            <code className="text-[11px] bg-neutral-100 px-1 py-0.5 rounded">
              OrchestratorConfig
            </code>{" "}
            -- change config, not code.
          </p>
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="border-b border-neutral-200">
                  <th className="text-left py-2 pr-4 font-semibold text-neutral-700">Parameter</th>
                  <th className="text-left py-2 pr-4 font-semibold text-neutral-700">Default</th>
                  <th className="text-left py-2 font-semibold text-neutral-700">Description</th>
                </tr>
              </thead>
              <tbody className="text-neutral-600">
                {[
                  { param: "enable_regex", def: "True", desc: "Tier 1+2 inline formula detection" },
                  { param: "enable_structured_parser", def: "True", desc: "Tier 3 structured math detection" },
                  { param: "enable_image_ocr", def: "False", desc: "Tier 4 image-based detection (opt-in)" },
                  { param: "render_targets", def: '["html", "mathml"]', desc: "Output formats to pre-render" },
                  { param: "validate_formulas", def: "False", desc: "SymPy validation (opt-in)" },
                  { param: "min_ocr_confidence", def: "0.6", desc: "Below this threshold, flag for review" },
                  { param: "escalate_to_vlm", def: "False", desc: "Use Claude Vision as OCR fallback" },
                  { param: "classify_images", def: "False", desc: "Auto-detect equation images" },
                  { param: "min_classification_confidence", def: "0.7", desc: "Image classification threshold" },
                  { param: "max_detectors_per_step", def: "3", desc: "Tool pool limit per detection step" },
                  { param: "max_ocr_tools_per_step", def: "2", desc: "Tool pool limit per OCR step" },
                ].map((row) => (
                  <tr key={row.param} className="border-b border-neutral-100">
                    <td className="py-2 pr-4">
                      <code className="text-[11px] bg-neutral-100 px-1 py-0.5 rounded">{row.param}</code>
                    </td>
                    <td className="py-2 pr-4 font-mono">{row.def}</td>
                    <td className="py-2">{row.desc}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </CardBody>
      </Card>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Section 3: Document Format Pipeline
// ---------------------------------------------------------------------------

function DocumentFormats() {
  return (
    <div className="space-y-6">
      <div className="mb-4">
        <h2 className="text-lg font-bold text-neutral-800">
          Document Format Pipeline
        </h2>
        <p className="text-sm text-neutral-500 mt-1">
          Each input format has a dedicated ingestor that extracts
          formatting metadata into the shared{" "}
          <code className="text-[11px] bg-neutral-100 px-1 py-0.5 rounded">
            FormattedDocument
          </code>{" "}
          IR.
        </p>
      </div>

      {/* PDF */}
      <FormatCard
        format="PDF"
        adapter="PDFIngestorAdapter"
        inner="FormattingExtractor"
        library="PyMuPDF (fitz)"
        variant="success"
        capabilities={[
          "Span-level extraction: each text run has flags (bold, italic, superscript, subscript), font name, size, color, and x/y position",
          "Table detection via find_tables() with cell boundaries",
          "Image extraction: embedded images with dimensions for Tier 4 formula detection",
          "Page-level metadata: width, height, rotation",
          "No OCR required for digitally-created PDFs (all clinical protocols)",
        ]}
        output="FormattedDocument with per-span font, size, color, bold/italic metadata and positional coordinates"
      />

      {/* DOCX */}
      <FormatCard
        format="DOCX"
        adapter="DOCXIngestorAdapter"
        inner="DOCXIngestor"
        library="python-docx"
        variant="success"
        capabilities={[
          "Style inheritance chain: run-level properties > paragraph style > document defaults",
          "Table support with gridSpan (horizontal merge) and vMerge (vertical merge)",
          "Heading styles (Heading 1-6) mapped to IR heading levels",
          "List detection from paragraph numbering/bullet styles",
          "OMML equation extraction via OmmlExtractor (fractions, radicals, superscripts, subscripts, n-ary operators, delimiters)",
        ]}
        output="FormattedDocument with inherited styles resolved to concrete formatting attributes"
      />

      {/* HTML */}
      <FormatCard
        format="HTML"
        adapter="HTMLIngestorAdapter"
        inner="HTMLIngestor"
        library="stdlib html.parser"
        variant="success"
        capabilities={[
          "Semantic tag mapping: <b>/<strong> to bold, <i>/<em> to italic, <u> to underline",
          "Heading tags <h1>-<h6> mapped to IR heading levels",
          "Nested table detection and flattening",
          "CSS style inheritance for inline styles",
          "List support: <ul>/<ol>/<li> mapped to IR list paragraphs",
        ]}
        output="FormattedDocument with semantically mapped formatting from HTML tags"
      />

      {/* PPTX */}
      <FormatCard
        format="PPTX"
        adapter="PPTXIngestorAdapter"
        inner="PPTXIngestor"
        library="python-pptx"
        variant="success"
        capabilities={[
          "Each slide maps to a FormattedPage in the IR",
          "Text shapes extracted with per-run formatting (font, size, color, bold, italic)",
          "Bold resolution: defRPr XML inspection + font size heuristic for slide master inheritance",
          "Native table shapes parsed with cell formatting",
        ]}
        output="FormattedDocument with one page per slide, preserving text shape and table structure"
      />

      {/* XLSX */}
      <FormatCard
        format="XLSX"
        adapter="ExcelIngestorAdapter"
        inner="ExcelIngestor"
        library="openpyxl"
        variant="success"
        capabilities={[
          "Each worksheet maps to a FormattedPage containing a FormattedTable",
          "Cell formatting: bold, italic, font name, size, color",
          "Merged cell detection and expansion",
          "Number format preservation",
        ]}
        output="FormattedDocument with one page per worksheet, each containing a table"
      />

      {/* Markdown */}
      <FormatCard
        format="Markdown"
        adapter="MarkdownIngestorAdapter"
        inner="MarkdownIngestor"
        library="regex-based parser"
        variant="success"
        capabilities={[
          "Headings (# through ######) mapped to IR heading levels",
          "Bold (**text**) and italic (*text*) detection",
          "Code blocks (fenced and indented) preserved",
          "Lists (ordered and unordered) mapped to IR list paragraphs",
          "Table parsing (pipe-delimited GFM tables)",
          "Image references mapped to IR image paragraphs",
        ]}
        output="FormattedDocument with Markdown structure mapped to semantic IR elements"
      />

      {/* Plain Text */}
      <FormatCard
        format="Plain Text"
        adapter="TextIngestorAdapter"
        inner="TextIngestor"
        library="structure detection"
        variant="success"
        capabilities={[
          "Numbered section detection: lines matching '1.', '1.1', etc. become headings",
          "Bullet line detection: lines starting with -, *, or bullet characters become list items",
          "All other lines become body paragraphs",
          "No formatting metadata (plain text has none)",
        ]}
        output="FormattedDocument with detected structure (headings, lists, body paragraphs)"
      />
    </div>
  );
}

// ---------------------------------------------------------------------------
// Section 4: Quality Assurance
// ---------------------------------------------------------------------------

function QualityAssurance() {
  return (
    <div className="space-y-6">
      <div className="mb-4">
        <h2 className="text-lg font-bold text-neutral-800">
          Quality Assurance Tools
        </h2>
        <p className="text-sm text-neutral-500 mt-1">
          Built-in tools for measuring conversion fidelity and formula
          detection accuracy.
        </p>
      </div>

      {/* SpanForensics */}
      <Card>
        <CardHeader>
          <div className="flex items-center gap-2">
            <h3 className="text-sm font-semibold text-neutral-800">
              SpanForensics
            </h3>
            <Badge variant="info">Attribute-Level</Badge>
          </div>
        </CardHeader>
        <CardBody>
          <p className="text-xs text-neutral-500 mb-3">
            Measures per-attribute fidelity across individual text spans in the
            IR. Compares source document spans against round-tripped output
            spans.
          </p>
          <div className="grid grid-cols-3 gap-3">
            {[
              "bold",
              "italic",
              "underline",
              "superscript",
              "subscript",
              "color",
            ].map((attr) => (
              <div
                key={attr}
                className="flex items-center gap-2 p-2 bg-neutral-50 rounded-lg"
              >
                <div className="w-2 h-2 rounded-full bg-emerald-500" />
                <span className="text-xs text-neutral-700 font-mono">
                  {attr}
                </span>
              </div>
            ))}
          </div>
          <p className="text-xs text-neutral-400 mt-3">
            Each attribute is tested independently. A span is &quot;correct&quot;
            only if all measured attributes match the source.
          </p>
        </CardBody>
      </Card>

      {/* FidelityChecker */}
      <Card>
        <CardHeader>
          <div className="flex items-center gap-2">
            <h3 className="text-sm font-semibold text-neutral-800">
              FidelityChecker
            </h3>
            <Badge variant="info">Document-Level</Badge>
          </div>
        </CardHeader>
        <CardBody>
          <p className="text-xs text-neutral-500 mb-3">
            Scores entire documents by comparing the source and output at the
            page, paragraph, and span levels. Produces an overall fidelity
            score with category breakdowns.
          </p>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <p className="text-xs font-semibold text-neutral-600 mb-2">
                Issue Categories
              </p>
              <div className="space-y-1.5">
                {[
                  { sev: "critical", desc: "Content loss, structural damage" },
                  { sev: "high", desc: "Formatting errors affecting readability" },
                  { sev: "medium", desc: "Minor style deviations" },
                  { sev: "low", desc: "Cosmetic differences" },
                ].map((item) => (
                  <div key={item.sev} className="flex items-center gap-2">
                    <Badge
                      variant={
                        item.sev === "critical"
                          ? "danger"
                          : item.sev === "high"
                          ? "warning"
                          : item.sev === "medium"
                          ? "info"
                          : "neutral"
                      }
                    >
                      {item.sev}
                    </Badge>
                    <span className="text-xs text-neutral-500">{item.desc}</span>
                  </div>
                ))}
              </div>
            </div>
            <div>
              <p className="text-xs font-semibold text-neutral-600 mb-2">
                Scoring Method
              </p>
              <ul className="space-y-1.5">
                {[
                  "Per-page paragraph counts compared",
                  "Font usage distributions compared",
                  "Color palettes compared",
                  "Style category distributions compared",
                  "Issues weighted by severity for final score",
                ].map((item, i) => (
                  <li
                    key={i}
                    className="flex gap-2 text-xs text-neutral-600"
                  >
                    <span className="text-neutral-300 shrink-0">&#8226;</span>
                    <span>{item}</span>
                  </li>
                ))}
              </ul>
            </div>
          </div>
        </CardBody>
      </Card>

      {/* Formula Benchmark */}
      <Card>
        <CardHeader>
          <div className="flex items-center gap-2">
            <h3 className="text-sm font-semibold text-neutral-800">
              Formula Benchmark
            </h3>
            <Badge variant="info">Detection Accuracy</Badge>
          </div>
        </CardHeader>
        <CardBody>
          <p className="text-xs text-neutral-500 mb-3">
            A benchmark suite testing formula detection across 7 formula types.
            Measures detection rate, false positive rate, and unknown
            (undetected) rate.
          </p>
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="border-b border-neutral-200">
                  <th className="text-left py-2 pr-4 font-semibold text-neutral-700">
                    Formula Type
                  </th>
                  <th className="text-left py-2 pr-4 font-semibold text-neutral-700">
                    Examples
                  </th>
                  <th className="text-left py-2 font-semibold text-neutral-700">
                    Tier
                  </th>
                </tr>
              </thead>
              <tbody className="text-neutral-600">
                {[
                  {
                    type: "CHEMICAL",
                    examples: "CO2, H2O, Ca2+, HbA1c",
                    tier: "1+2",
                  },
                  {
                    type: "PK",
                    examples: "AUC0-inf, Cmax, t1/2, Vd",
                    tier: "1+2",
                  },
                  {
                    type: "DOSING",
                    examples: "mg/m2, x10^6, Cockcroft-Gault",
                    tier: "1+2 / 3",
                  },
                  {
                    type: "STATISTICAL",
                    examples: "p<0.05, 95% CI, Kaplan-Meier",
                    tier: "1+2 / 3",
                  },
                  {
                    type: "MATHEMATICAL",
                    examples: "d2y/dx2, integrals, summations, limits",
                    tier: "3",
                  },
                  {
                    type: "EFFICACY",
                    examples: "VE=, NNT=, ARR",
                    tier: "1+2",
                  },
                  {
                    type: "ANALYTICAL",
                    examples: "LOD, LOQ",
                    tier: "1+2",
                  },
                ].map((row) => (
                  <tr
                    key={row.type}
                    className="border-b border-neutral-100"
                  >
                    <td className="py-2 pr-4 font-mono">{row.type}</td>
                    <td className="py-2 pr-4">{row.examples}</td>
                    <td className="py-2">
                      <Badge variant="brand">{row.tier}</Badge>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </CardBody>
      </Card>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Section 5: Architecture
// ---------------------------------------------------------------------------

function ArchitectureSection() {
  return (
    <div className="space-y-6">
      <div className="mb-4">
        <h2 className="text-lg font-bold text-neutral-800">Architecture</h2>
        <p className="text-sm text-neutral-500 mt-1">
          The pipeline follows a Tool Registry pattern. All tools are registered
          centrally and selected at runtime based on format, complexity tier, or
          target output.
        </p>
      </div>

      {/* Tool Registry */}
      <Card>
        <CardHeader>
          <h3 className="text-sm font-semibold text-neutral-800">
            Tool Registry Pattern
          </h3>
        </CardHeader>
        <CardBody className="space-y-4">
          <p className="text-xs text-neutral-500">
            Two registries manage all tools.{" "}
            <code className="text-[11px] bg-neutral-100 px-1 py-0.5 rounded">
              PipelineToolRegistry
            </code>{" "}
            holds ingestors and renderers.{" "}
            <code className="text-[11px] bg-neutral-100 px-1 py-0.5 rounded">
              FormulaToolRegistry
            </code>{" "}
            holds detectors, classifiers, OCR backends, renderers, and validators.
            Each tool declares metadata (name, version, priority, side effects,
            supported complexities/types) and the orchestrator queries the registry
            to assemble the right tool pool per step.
          </p>

          <div className="grid grid-cols-2 gap-4">
            {/* Pipeline Registry */}
            <div className="bg-neutral-50 rounded-lg p-4">
              <p className="text-xs font-semibold text-neutral-700 mb-3">
                PipelineToolRegistry (14 tools)
              </p>
              <div className="space-y-3">
                <div>
                  <p className="text-[11px] font-semibold text-neutral-500 uppercase tracking-wide mb-1">
                    Ingestors (7)
                  </p>
                  <div className="flex flex-wrap gap-1.5">
                    {[
                      "pdf-ingestor",
                      "docx-ingestor",
                      "html-ingestor",
                      "markdown-ingestor",
                      "text-ingestor",
                      "pptx-ingestor",
                      "excel-ingestor",
                    ].map((t) => (
                      <code
                        key={t}
                        className="text-[10px] bg-white border border-neutral-200 px-1.5 py-0.5 rounded"
                      >
                        {t}
                      </code>
                    ))}
                  </div>
                </div>
                <div>
                  <p className="text-[11px] font-semibold text-neutral-500 uppercase tracking-wide mb-1">
                    Renderers (7)
                  </p>
                  <div className="flex flex-wrap gap-1.5">
                    {[
                      "docx-renderer",
                      "html-renderer",
                      "markdown-renderer",
                      "text-renderer",
                      "json-renderer",
                      "pdf-renderer",
                      "pptx-renderer",
                    ].map((t) => (
                      <code
                        key={t}
                        className="text-[10px] bg-white border border-neutral-200 px-1.5 py-0.5 rounded"
                      >
                        {t}
                      </code>
                    ))}
                  </div>
                </div>
              </div>
            </div>

            {/* Formula Registry */}
            <div className="bg-neutral-50 rounded-lg p-4">
              <p className="text-xs font-semibold text-neutral-700 mb-3">
                FormulaToolRegistry (up to 9 tools)
              </p>
              <div className="space-y-3">
                <div>
                  <p className="text-[11px] font-semibold text-neutral-500 uppercase tracking-wide mb-1">
                    Detectors (2)
                  </p>
                  <div className="flex flex-wrap gap-1.5">
                    {["regex_detector", "structured_parser"].map((t) => (
                      <code
                        key={t}
                        className="text-[10px] bg-white border border-neutral-200 px-1.5 py-0.5 rounded"
                      >
                        {t}
                      </code>
                    ))}
                  </div>
                </div>
                <div>
                  <p className="text-[11px] font-semibold text-neutral-500 uppercase tracking-wide mb-1">
                    Renderers (3)
                  </p>
                  <div className="flex flex-wrap gap-1.5">
                    {[
                      "html_formula_renderer",
                      "mathml_formula_renderer",
                      "omml_formula_renderer",
                    ].map((t) => (
                      <code
                        key={t}
                        className="text-[10px] bg-white border border-neutral-200 px-1.5 py-0.5 rounded"
                      >
                        {t}
                      </code>
                    ))}
                  </div>
                </div>
                <div>
                  <p className="text-[11px] font-semibold text-neutral-500 uppercase tracking-wide mb-1">
                    Classifier (1)
                  </p>
                  <div className="flex flex-wrap gap-1.5">
                    <code className="text-[10px] bg-white border border-neutral-200 px-1.5 py-0.5 rounded">
                      heuristic_image_classifier
                    </code>
                  </div>
                </div>
                <div>
                  <p className="text-[11px] font-semibold text-neutral-500 uppercase tracking-wide mb-1">
                    OCR (up to 3)
                  </p>
                  <div className="flex flex-wrap gap-1.5">
                    {[
                      "placeholder_ocr",
                      "claude_vision_ocr",
                      "local_latex_ocr",
                    ].map((t) => (
                      <code
                        key={t}
                        className="text-[10px] bg-white border border-neutral-200 px-1.5 py-0.5 rounded"
                      >
                        {t}
                      </code>
                    ))}
                  </div>
                  <p className="text-[10px] text-neutral-400 mt-1">
                    claude_vision_ocr requires ANTHROPIC_API_KEY. local_latex_ocr
                    requires rapid_latex_ocr or pix2tex. placeholder_ocr always
                    registered as fallback.
                  </p>
                </div>
              </div>
            </div>
          </div>
        </CardBody>
      </Card>

      {/* Design Principles */}
      <Card>
        <CardHeader>
          <h3 className="text-sm font-semibold text-neutral-800">
            Design Principles
          </h3>
        </CardHeader>
        <CardBody>
          <div className="space-y-4">
            {[
              {
                title: "Metadata-first registry",
                desc: "Every tool declares name, version, priority, side-effect profile, supported complexities, and supported types. The registry entry is the source of truth.",
              },
              {
                title: "No hardcoded workflows",
                desc: "The orchestrator queries the registry for tools matching the current step's requirements (format, complexity tier, target output). Swap tools by registering new ones, not by changing orchestrator code.",
              },
              {
                title: "Pluggable backends",
                desc: "OCR backends, formula renderers, and format ingestors are all independently swappable. Register a new backend with higher priority and it takes precedence automatically.",
              },
              {
                title: "Graceful degradation",
                desc: "Missing dependencies never crash the system. PlaceholderOCR ensures image processing always returns a result. MathML renderer falls back if latex2mathml is not installed. Each OCR backend checks for its own imports at construction time.",
              },
              {
                title: "Deduplication by overlap",
                desc: "When multiple detectors find overlapping formulas in the same text, the orchestrator keeps the longest match and discards shorter overlapping spans.",
              },
              {
                title: "Config-driven behavior",
                desc: "OrchestratorConfig controls which tiers are active, render targets, confidence thresholds, VLM escalation, and tool pool limits. Change behavior by changing config, not code.",
              },
            ].map((item) => (
              <div key={item.title} className="flex gap-3">
                <div className="w-2 h-2 rounded-full bg-brand-primary mt-1.5 shrink-0" />
                <div>
                  <p className="text-xs font-semibold text-neutral-700">
                    {item.title}
                  </p>
                  <p className="text-xs text-neutral-500 mt-0.5">
                    {item.desc}
                  </p>
                </div>
              </div>
            ))}
          </div>
        </CardBody>
      </Card>

      {/* OMML Extraction */}
      <Card>
        <CardHeader>
          <h3 className="text-sm font-semibold text-neutral-800">
            DOCX Equation Extraction (OmmlExtractor)
          </h3>
        </CardHeader>
        <CardBody>
          <p className="text-xs text-neutral-500 mb-3">
            DOCX files embed equations as OMML (Office Math Markup Language)
            inside paragraph XML. The{" "}
            <code className="text-[11px] bg-neutral-100 px-1 py-0.5 rounded">
              OmmlExtractor
            </code>{" "}
            walks{" "}
            <code className="text-[11px] bg-neutral-100 px-1 py-0.5 rounded">
              {"<m:oMath>"}
            </code>{" "}
            elements and converts them to both plain text and LaTeX.
          </p>
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="border-b border-neutral-200">
                  <th className="text-left py-2 pr-4 font-semibold text-neutral-700">
                    OMML Element
                  </th>
                  <th className="text-left py-2 pr-4 font-semibold text-neutral-700">
                    Plain Text
                  </th>
                  <th className="text-left py-2 font-semibold text-neutral-700">
                    LaTeX
                  </th>
                </tr>
              </thead>
              <tbody className="text-neutral-600">
                {[
                  { el: "m:f", plain: "num/den", latex: "\\frac{num}{den}" },
                  { el: "m:sSup", plain: "base^{exp}", latex: "base^{exp}" },
                  { el: "m:sSub", plain: "base_{sub}", latex: "base_{sub}" },
                  { el: "m:rad", plain: "sqrt(x)", latex: "\\sqrt{x}" },
                  {
                    el: "m:nary",
                    plain: "sum_{i=1}^{n}(x)",
                    latex: "\\sum_{i=1}^{n} x",
                  },
                  {
                    el: "m:d",
                    plain: "(content)",
                    latex: "\\left( content \\right)",
                  },
                  { el: "m:r/m:t", plain: "literal text", latex: "literal text" },
                ].map((row) => (
                  <tr
                    key={row.el}
                    className="border-b border-neutral-100"
                  >
                    <td className="py-2 pr-4">
                      <code className="text-[11px] bg-neutral-100 px-1 py-0.5 rounded">
                        {row.el}
                      </code>
                    </td>
                    <td className="py-2 pr-4 font-mono">{row.plain}</td>
                    <td className="py-2 font-mono">{row.latex}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </CardBody>
      </Card>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Shared Components
// ---------------------------------------------------------------------------

function PipelineStage({
  number,
  title,
  subtitle,
  color,
  items,
  toolName,
  detail,
}: {
  number: number;
  title: string;
  subtitle: string;
  color: string;
  items: string[];
  toolName: string;
  detail: string;
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
    sky: "bg-sky-500",
    blue: "bg-blue-500",
    emerald: "bg-emerald-500",
    purple: "bg-purple-500",
    amber: "bg-amber-500",
    red: "bg-red-500",
    teal: "bg-teal-500",
  };

  return (
    <div className="flex gap-4">
      {/* Timeline */}
      <div className="flex flex-col items-center w-8 shrink-0">
        <div
          className={cn(
            "w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold",
            colorMap[color] || colorMap.sky
          )}
        >
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
            <div
              className={cn(
                "w-2 h-2 rounded-full mt-1.5",
                dotColor[color] || dotColor.sky
              )}
            />
          </div>

          <div className="mt-2 mb-3">
            <span className="text-[10px] font-semibold text-neutral-400 uppercase tracking-wide">
              Tool:{" "}
            </span>
            <code className="text-[11px] bg-neutral-100 px-1.5 py-0.5 rounded text-neutral-700">
              {toolName}
            </code>
          </div>

          <ul className="space-y-1.5">
            {items.map((item, i) => (
              <li key={i} className="flex gap-2 text-xs text-neutral-600">
                <span className="text-neutral-300 shrink-0 mt-0.5">
                  &#8226;
                </span>
                <span>{item}</span>
              </li>
            ))}
          </ul>

          {detail && (
            <button
              onClick={() => setExpanded(!expanded)}
              className="mt-3 text-[11px] text-brand-primary hover:underline flex items-center gap-1"
            >
              {expanded ? "Hide details" : "Technical detail"}
              <svg
                className={cn(
                  "w-3 h-3 transition-transform",
                  expanded && "rotate-180"
                )}
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
                strokeWidth={2}
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  d="M19.5 8.25l-7.5 7.5-7.5-7.5"
                />
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

function FlowBox({
  label,
  sub,
  color,
}: {
  label: string;
  sub: string;
  color: string;
}) {
  const colorMap: Record<string, string> = {
    sky: "bg-sky-50 border-sky-200 text-sky-800",
    blue: "bg-blue-50 border-blue-200 text-blue-800",
    emerald: "bg-emerald-50 border-emerald-200 text-emerald-800",
    purple: "bg-purple-50 border-purple-200 text-purple-800",
    amber: "bg-amber-50 border-amber-200 text-amber-800",
    red: "bg-red-50 border-red-200 text-red-800",
  };

  return (
    <div
      className={cn(
        "px-4 py-3 rounded-lg border text-center min-w-[120px]",
        colorMap[color] || colorMap.sky
      )}
    >
      <p className="text-xs font-semibold">{label}</p>
      <p className="text-[10px] mt-0.5 opacity-70">{sub}</p>
    </div>
  );
}

function FlowArrow() {
  return (
    <svg
      className="w-5 h-5 text-neutral-400 shrink-0"
      fill="none"
      viewBox="0 0 24 24"
      stroke="currentColor"
      strokeWidth={2}
    >
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        d="M13.5 4.5L21 12m0 0l-7.5 7.5M21 12H3"
      />
    </svg>
  );
}

function FormatCard({
  format,
  adapter,
  inner,
  library,
  variant,
  capabilities,
  output,
}: {
  format: string;
  adapter: string;
  inner: string;
  library: string;
  variant: "success" | "warning";
  capabilities: string[];
  output: string;
}) {
  return (
    <Card>
      <CardHeader>
        <div className="flex items-center gap-3">
          <Badge variant={variant}>{format}</Badge>
          <div>
            <code className="text-[11px] text-neutral-700">
              {adapter}
            </code>
            <span className="text-neutral-400 mx-1">wraps</span>
            <code className="text-[11px] text-neutral-700">{inner}</code>
          </div>
          <span className="text-[10px] text-neutral-400 ml-auto">
            {library}
          </span>
        </div>
      </CardHeader>
      <CardBody>
        <ul className="space-y-1.5 mb-3">
          {capabilities.map((item, i) => (
            <li key={i} className="flex gap-2 text-xs text-neutral-600">
              <span className="text-neutral-300 shrink-0 mt-0.5">&#8226;</span>
              <span>{item}</span>
            </li>
          ))}
        </ul>
        <div className="bg-neutral-50 rounded-lg p-3 border border-neutral-100">
          <span className="text-[10px] font-semibold text-neutral-400 uppercase tracking-wide">
            Output:{" "}
          </span>
          <span className="text-xs text-neutral-600">{output}</span>
        </div>
      </CardBody>
    </Card>
  );
}

function MetricBox({
  label,
  value,
  desc,
}: {
  label: string;
  value: string;
  desc: string;
}) {
  return (
    <div className="text-center p-3 bg-neutral-50 rounded-lg">
      <p className="text-lg font-bold text-brand-primary font-mono">{value}</p>
      <p className="text-xs font-medium text-neutral-700 mt-0.5">{label}</p>
      <p className="text-[10px] text-neutral-400 mt-0.5">{desc}</p>
    </div>
  );
}

function ConversionMatrix() {
  const inputs = ["PDF", "DOCX", "HTML", "MD", "TXT", "PPTX", "XLSX"];
  const outputs = ["DOCX", "HTML", "MD", "TXT", "JSON", "PDF", "PPTX"];

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-[10px]">
        <thead>
          <tr>
            <th className="text-left py-1.5 pr-2 font-semibold text-neutral-500">
              IN \ OUT
            </th>
            {outputs.map((o) => (
              <th
                key={o}
                className="py-1.5 px-2 font-semibold text-neutral-500 text-center"
              >
                {o}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {inputs.map((inp) => (
            <tr key={inp} className="border-t border-neutral-100">
              <td className="py-1.5 pr-2 font-semibold text-neutral-600">
                {inp}
              </td>
              {outputs.map((out) => (
                <td key={out} className="py-1.5 px-2 text-center">
                  <span className="inline-block w-5 h-5 rounded bg-emerald-100 text-emerald-600 leading-5 font-bold">
                    &#10003;
                  </span>
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
