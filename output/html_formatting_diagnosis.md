# HTML Formatting Diagnosis Report

**Document**: `formula_test_document_v2.pdf` (26 pages)
**Output**: `formula_output.html` (606 KB, 959 lines)
**Date**: 2026-04-02

---

## Category 1: Content Duplication

**Severity: CRITICAL**

### 1A. Every table is rendered twice -- once as `<p>` paragraphs, once as `<table>` elements

All 7 tables in the document appear in duplicate. The extractor produces both paragraph-based text (from `get_text("dict")`) and structured tables (from `find_tables()`). The `_filter_table_overlapping_lines()` deduplication is failing for these tables.

| Table | `<p>` location | `<table>` location | Duplicated content |
|-------|----------------|--------------------|--------------------|
| Table 4.1 (Dose Modification) | pos ~35,600 | pos ~45,700 | "Toxicity Grade", "CrCl (mL/min)", all 4 data rows |
| Table 5.1 (PK Parameters) | pos ~50,500 | pos ~73,200 | "Parameter", "Geometric Mean", 8 data rows |
| Table 6.1 (Statistical Methods) | pos ~103,400 | pos ~106,700 | "Endpoint", "Analysis Method", 7 data rows |
| Table 9.1 (Lab Ranges) | pos ~125,500 | pos ~136,100 | "Analyte", "Normal Range", all data rows |
| Table 10.1 (Dissolution) | pos ~146,300 | pos ~156,900 | "Time (min)", "Test (% dissolved)" |
| Table 11 (SoA) | pos ~169,000 | pos ~172,300 | "Assessment", all visit columns |
| Document History | pos ~603,000 | pos ~604,900 | "Version", "Author", 3 data rows |

**Root cause**: `extractor.py`, `_filter_table_overlapping_lines()` (line ~606). The bounding-box overlap check is failing -- the text blocks extracted by PyMuPDF have bounding boxes that do not precisely match the `find_tables()` bounding boxes, causing the filter to miss them. Additionally, the `<p>`-based "table header row" is being rendered as `<h4>` (see Category 5B below), which means even if the text dedup worked for body rows, the header row duplicate would remain.

**Impact**: Users see every table twice. The `<p>`-based version has no column structure (all cells concatenated in a single line), making the document confusing and unprofessional.

### 1B. Table header rows rendered as `<h4>` headings

12 `<h4>` tags in the output correspond to table titles AND table header row content:

- `<h4>: Toxicity GradeCrCl (mL/min)Dose AdjustmentRe-escalation` -- this is the header ROW of Table 4.1, incorrectly rendered as an HTML heading
- `<h4>: ParameterUnitGeometric MeanCV%90% CI` -- header row of Table 5.1
- `<h4>: AnalyteUnitNormal RangeCTCAE Grade 3CTCAE Grade 4` -- header row of Table 9.1
- 4 more similar cases

**Root cause**: `extractor.py`, `_classify_paragraph()` (line ~485). The table header rows have bold text, short word count, and large spacing before them, which scores >= 3.5 on the heading detection model, triggering `heading4` classification. The classifier doesn't know this text came from a table.

---

## Category 2: Text Joining/Splitting

**Severity: HIGH**

### 2A. Paragraphs split mid-sentence across `<p>` tags

22 paragraphs are broken at PDF line boundaries. The sentence continues in the next `<p>` tag with no visual connection:

| Location | End of first `<p>` | Start of next `<p>` |
|----------|-------------------|---------------------|
| Page 3, Synopsis | "...include overall survival (OS), objective" | "response rate (ORR) per RECIST v1.1..." |
| Page 3 | "...powered at 90% to detect a" | "hazard ratio (HR) of 0.65..." |
| Page 4, Background | "...targeting VEGFR-2, PDGFR-beta, and c-KIT with" | "demonstrated anti-tumour activity..." |
| Page 4 | "...across the 25-200 mg/m2 dose range, with a mean terminal" | "half-life (t1/2) of 14.3 hours..." |
| Page 5 | "...confidence interval (CI). The null" | "hypothesis H0: HR = 1.0..." |

**Root cause**: `extractor.py`, `_group_paragraphs()` (line ~409). The paragraph grouping uses `y_gap > prev_size * 1.5` as the threshold. In this PDF, the line spacing is exactly or slightly more than 1.5x the font size (14pt line spacing for 10pt text), so some paragraph-internal line breaks are misidentified as paragraph breaks. The threshold needs tuning or the algorithm needs to also check whether the previous line ended with a sentence-terminal character.

### 2B. Missing spaces between spans (199 occurrences)

When two adjacent `</span><span>` elements have no whitespace between them, words run together in the rendered output. Examples:

- "administered**o**rally" (should be "administered orally")
- "endpoint is**p**rogression-free" (should be "endpoint is progression-free")
- "65 sites in 12**c**ountries" (should be "12 countries")
- "described by the**H**ill equation" (should be "the Hill equation")
- "kinetics follows**M**ichaelis-Menten" (should be "follows Michaelis-Menten")

**Root cause**: `extractor.py`, space injection logic (line ~352). The space injection only fires when `gap > char_width` AND both adjacent characters are `isalpha()`. But this misses cases where the gap in the PDF is real but narrow, or where line breaks within a block don't get spaces injected. The `_render_spans_html()` method in the renderer also concatenates spans with `"".join()` (line 233), providing no inter-span whitespace.

### 2C. Run-on words at paragraph-internal line boundaries (27+ visible instances)

Beyond missing spaces between spans, full words are joined at line breaks:

- "IndicationAdvanced Solid Tumours" (should be "Indication  Advanced Solid Tumours")
- "Study DesignRandomised, Double-Blind" (should be separate field/value pairs)
- "if norecoveryNot permitted" (should be "if no recovery  Not permitted")
- "data points is shown inFigure B.1:" (should be "shown in Figure B.1:")

**Root cause**: Same as 2B. The space injection heuristic in the extractor doesn't handle all cases where PDF blocks have visual spacing that isn't represented by explicit space characters.

---

## Category 3: Headers/Footers

**Severity: CRITICAL**

### 3A. Page headers/footers rendered as body content with `<sub>` tags

Every page has 4 header/footer text elements that appear in the HTML output:
- "CONFIDENTIAL" (header, 7pt, gray #616161)
- "Protocol ZS-FDP-2026-001  |  Version 3.0" (header, 7pt, gray #616161)
- "Sponsor: ZS Pharmaceuticals Ltd.  |  IND 123456" (footer, 7pt, gray #9E9E9E)
- "Page N" (footer, 7pt, gray #9E9E9E)

These produce **104 `<sub>` tags** in the output (4 per page x 26 pages), all incorrectly subscripted.

**Root cause (subscript misclassification)**: `extractor.py`, subscript detection (line ~337). When a 7pt header/footer line is grouped into the same paragraph as a 16pt heading (see 3B below), the dominant size becomes 16pt. Then 7 < 16 * 0.8 = 12.8 is true, so the header/footer text is marked as `subscript = True`. The renderer then wraps it in `<sub>`.

**Root cause (not filtered)**: `html_renderer.py` has NO code to skip paragraphs with `style="header"` or `style="footer"`. The `_render_paragraph()` method renders all paragraphs. The extractor's `_mark_headers_footers()` method (line 645) does mark them, but the renderer ignores the marking. Furthermore, many header/footer lines are merged into heading paragraphs (see 3B), so they wouldn't have a separate `style="header"` to filter anyway.

### 3B. Footer text merged INTO heading tags

On 16 of 26 pages, the footer text ("Sponsor: ZS Pharmaceuticals Ltd.  |  IND 123456" + "Page N") is merged into the `<h1>` tag for the section heading. Example:

```html
<h1 style="margin-top:36pt">
  <span style="...font-size:7.0pt"><sub>Sponsor: ZS Pharmaceuticals Ltd.  |  IND 123456</sub></span>
  <span style="...font-size:7.0pt"><sub>Page 3</sub></span>
  <span style="...font-size:16.0pt"><strong>1. SYNOPSIS</strong></span>
</h1>
```

This happens on every page where a section heading follows the footer block.

**Root cause**: `extractor.py`, `_group_paragraphs()` (line ~409). PyMuPDF extracts text blocks in document object order, not visual order. The footer block (y=786) appears as Block 1 in the PDF's internal structure, and the heading block (y=89) appears as Block 2. When computing the Y gap: `89 - 786 = -697`, which is negative, so `y_gap > prev_size * 1.5` evaluates to `False`, and the lines are NOT broken into separate paragraphs. They merge into one paragraph, which then gets classified as `heading1` because the heading text dominates the scoring.

**Impact**: Section headings display "Sponsor: ZS Pharmaceuticals Ltd. | IND 123456 Page 3 1. SYNOPSIS" as their accessible text, breaking navigation, screen readers, and table-of-contents generation.

---

## Category 4: Table Formatting

**Severity: MEDIUM**

### 4A. Table cells lose subscript/superscript formatting

Table cells are extracted as plain text via `tab.extract()` in PyMuPDF, which strips all formatting. Subscripts in table cells become plain text with line breaks:

| Expected | Actual in `<td>` |
|----------|-------------------|
| AUC<sub>0-inf</sub> | `AUC\n0-inf` |
| C<sub>max</sub> | `C\nmax` |
| V<sub>d</sub>/F | `V /F\nd` |
| 125 mg/m<sup>2</sup> | `2\nReduce to 125 mg/m` |

The last example is particularly bad: the superscript "2" gets separated and placed on its own line BEFORE the dose text.

**Root cause**: `extractor.py`, `_extract_tables()` (line 719). The `FormattedTableCell` dataclass only stores plain `text: str` -- it has no span-level formatting support. The `tab.extract()` method returns raw strings that flatten subscripts into newline-separated tokens. The renderer's `_render_table()` method (line 319) uses `html_module.escape(cell.text)`, which preserves these newlines as literal text.

### 4B. Table header background color differs from PDF

PDF table headers use white text (#ffffff) on an implied dark background (the PDF fills the cell background). The HTML output uses:
```
background:#1565C0; color:#fff
```
The `#1565C0` (Material Design Blue 800) is a reasonable but arbitrary choice -- the actual PDF background color is not extracted.

**Root cause**: `html_renderer.py`, `_css_for_cell()` (line 455). The header styling is hardcoded rather than extracted from the PDF.

**Severity**: LOW -- cosmetic only, the visual result is acceptable.

---

## Category 5: Font/Size/Color Fidelity

**Severity: HIGH**

### 5A. Sections 10, 11 rendered without `<h1>` tag

Section 10 ("10. CMC: DRUG SUBSTANCE AND DRUG PRODUCT") is rendered as a `<p>` tag instead of `<h1>`. Section 11 closes with `</h1>` suggesting an inconsistent open/close. The issue is visible in the heading hierarchy:

- Sections 1-9: `<h1>` (correct, though contaminated with header/footer text)
- Section 10: `<p>` (WRONG)
- Section 11: `<h1>` (correct)
- Appendix D: `<h1>` (correct)

**Root cause**: The heading classifier in `extractor.py` `_classify_paragraph()` depends on multiple signals. When footer text is merged with the heading (3B), the combined paragraph has different properties (longer word count, mixed font sizes) that can push the heading score below the 5.0 threshold for some pages, resulting in `body` style instead of `heading1`.

### 5B. Font family inconsistency: "HelveticaOblique" vs "Helvetica-Oblique"

The output contains both:
- `HelveticaOblique` (no dash): 21 occurrences
- `Helvetica-Oblique` (with dash): 54 occurrences

These refer to the same font but are rendered as different CSS font-family values.

**Root cause**: `extractor.py`, `FormattedSpan.font_family` property (line 53). The suffix stripping removes "-Italic" but not "-Oblique", so "Helvetica-Oblique" passes through unchanged. Meanwhile, some PDF fonts encode the name as "HelveticaOblique" (no dash), which also passes through. This creates inconsistent font-family CSS.

**Severity**: LOW -- browsers fall back to the same sans-serif font.

### 5C. Missing document-level HTML structure

The output is a bare `<div>` with no `<!DOCTYPE>`, `<html>`, `<head>`, or `<body>` wrapper:
```html
<div style="font-family:'Helvetica',sans-serif;font-size:11.0pt;color:#000000;line-height:1.4;">
```

The wrapper also lacks `max-width`, `margin: 0 auto`, and `padding` -- properties that the renderer's `__init__` configures but the actual output doesn't use (the output was generated with an older renderer version or `include_wrapper=True` but without the new max-width styling).

**Root cause**: `html_renderer.py`, `render()` method. The wrapper `<div>` is present but does not include `max-width:800px; margin:0 auto; padding:24px 32px` that the current code has (line 69). This suggests the output was generated with an older version of the renderer.

**Severity**: MEDIUM -- content renders but has no document-level constraints for readability.

---

## Category 6: Formula Rendering

**Severity: HIGH**

### 6A. Body text subscripts (8pt) NOT wrapped in `<sub>` tags

In the PDF, subscripts like AUC<sub>0-inf</sub>, C<sub>max</sub>, t<sub>1/2</sub> are represented as 8pt text alongside 10pt body text. In the HTML output, these are rendered as plain `<span style="font-size:8.0pt">0-inf</span>` with NO `<sub>` tag.

**245 spans at 8pt** in the output, representing subscript/superscript text, are rendered without semantic sub/sup tags.

Meanwhile, there are only **12 `<sub>` tags** for actual content (the rest of the 104 `<sub>` tags are the misclassified header/footer text).

**Root cause**: `extractor.py`, subscript detection (line ~337). The subscript detection requires `font_size < dominant_size * 0.80` AND a vertical position check. For body text lines where subscript text (8pt) follows normal text (10pt), the dominant size is 10pt, and 8 < 8.0 = 10*0.80 is exactly at the threshold boundary. The `<` (strict less than) comparison means 8pt text is NOT classified as subscript when dominant is 10pt, because 8 < 8.0 is False.

The 12 `<sub>` tags that DO exist are from 7.2pt spans (likely in table areas where the body is 9pt, making dominant_size=9, and 7.2 < 7.2 = 9*0.8 is also exactly at boundary -- these must have slightly different rounding).

### 6B. Formula enricher annotations are absent

The `formula_detector.py` module defines patterns for annotating formulas (CO2, HbA1c, AUC0-inf, etc.) with proper `<sub>`/`<sup>` HTML. However, the HTML output contains **zero** `class="formula"` annotations, suggesting the formula enricher was either not run on this document or its output was not integrated.

**Root cause**: The pipeline that generated this output likely did not invoke `FormulaDetector.annotate_html()`. The enricher exists but is not wired into the extraction-to-rendering pipeline for this specific conversion.

### 6C. Superscripts from PDF ARE correctly rendered

In contrast to subscripts, **superscripts** (PDF flag bit 0 = 1) ARE properly wrapped in `<sup>` tags. There are 58 `<sup>` occurrences:
- mg/m<sup>2</sup> (correct)
- Height (cm)<sup>0.725</sup> (correct)
- ×10<sup>9</sup>/L (correct)
- Na<sup>+</sup>, K<sup>+</sup>, Ca<sup>2+</sup> (correct)

This is because PyMuPDF's `flags & 1` correctly identifies superscript-flagged spans, and the extractor passes this through. The problem is exclusively with subscripts, which PyMuPDF does NOT flag -- they must be inferred from font size and position.

---

## Category 7: Images

**Severity: MEDIUM**

### 7A. Image captions appear BEFORE images (wrong order)

In the PDF, the visual order is: text -> image -> caption. In the HTML, captions render BEFORE their corresponding images. This affects all 13+ equation images.

Example: "Equation 1.1: Terminal half-life" (pos 12,049) appears before the `<img>` tag (pos 12,098).

**Root cause**: `extractor.py`, `_extract_images()` is called AFTER `_group_paragraphs()`. The caption text is part of the paragraph stream (extracted from text blocks), while images are appended separately. In the PDF, the image block (Block 6 on page 3) comes before the caption text block (Block 7). But since `_render_page()` renders all paragraphs first, then tables, images are interleaved based on their extraction order within the page's paragraph list. The caption text (being a small-font italic paragraph) gets extracted as a paragraph, and the image gets inserted at its Y position -- but both are at similar Y positions, and the sort order may not match visual order.

### 7B. One oversized image (1359x1677 px)

Image #14 has dimensions `width:1359px; height:1677px`, which is the full-page PK equation reference sheet from page 22 (Appendix D, Figure D.1). While the `max-width:100%` style prevents horizontal overflow, the image will be extremely tall in the rendered output.

**Root cause**: This is the actual pixel dimensions of the embedded image. The renderer uses the PDF's reported image dimensions directly. No downscaling is applied.

**Severity**: LOW -- `max-width:100%` handles the width; the height is just large.

### 7C. Images lack `alt` text and accessibility attributes

All 28 `<img>` tags use generic or empty `alt` attributes. The renderer does not extract caption text to use as alt text.

Note: The current renderer code (line 404) does add `alt="Embedded image"`, but the actual output has `alt=""` -- suggesting the output was generated with an older renderer version.

**Severity**: MEDIUM -- accessibility issue.

---

## Category 8: Layout

**Severity: MEDIUM**

### 8A. Page breaks are correctly placed

25 `<hr>` tags with `page-break-after:always` are present, one between each of the 26 pages. They appear at logical page boundaries.

**Status**: WORKING CORRECTLY.

### 8B. Wrapper div lacks proper document layout constraints

The output wrapper is:
```html
<div style="font-family:'Helvetica',sans-serif;font-size:11.0pt;color:#000000;line-height:1.4;">
```

Missing: `max-width`, `margin: 0 auto`, `padding`. Content stretches to full viewport width.

**Root cause**: The output was generated with a renderer that lacks the max-width/margin/padding properties that the current `html_renderer.py` code includes (lines 68-76). This is likely a version mismatch.

### 8C. Line height is 1.4 vs PDF's natural spacing

The wrapper sets `line-height:1.4` but the PDF uses variable line spacing (roughly 1.3-1.5x depending on section). This is a reasonable approximation.

**Severity**: LOW.

---

## Summary Table

| # | Category | Severity | Root Cause Module | Issue Count |
|---|----------|----------|-------------------|-------------|
| 1A | Table content duplication | CRITICAL | `extractor.py` `_filter_table_overlapping_lines()` | 7 tables x 2 = 14 renderings |
| 1B | Table headers as `<h4>` | HIGH | `extractor.py` `_classify_paragraph()` | 6 occurrences |
| 2A | Paragraph split mid-sentence | HIGH | `extractor.py` `_group_paragraphs()` | 22 splits |
| 2B | Missing inter-span spaces | HIGH | `extractor.py` space injection + `html_renderer.py` `"".join()` | 199 occurrences |
| 2C | Run-on words at line breaks | HIGH | `extractor.py` space injection | 27+ visible |
| 3A | Headers/footers as `<sub>` content | CRITICAL | `extractor.py` subscript detection + `html_renderer.py` no filter | 104 `<sub>` tags |
| 3B | Footer merged into `<h1>` | CRITICAL | `extractor.py` `_group_paragraphs()` negative Y gap | 16 pages |
| 4A | Table cells lose sub/sup formatting | MEDIUM | `extractor.py` `_extract_tables()` plain text only | All 7 tables |
| 4B | Table header color mismatch | LOW | `html_renderer.py` hardcoded `#1565C0` | All tables |
| 5A | Section 10 missing `<h1>` | HIGH | `extractor.py` `_classify_paragraph()` | 1 section |
| 5B | Font family inconsistency | LOW | `extractor.py` `font_family` property | 21+54 spans |
| 5C | No `<!DOCTYPE>`/`<html>` wrapper | MEDIUM | `html_renderer.py` `render()` | 1 doc |
| 6A | Subscripts not in `<sub>` tags | HIGH | `extractor.py` subscript threshold `< 0.80` too strict | 245 spans |
| 6B | Formula enricher not invoked | HIGH | Pipeline integration gap | 0 annotations |
| 6C | Superscripts correct | OK | -- | 58 `<sup>` tags |
| 7A | Caption before image (wrong order) | MEDIUM | `extractor.py` image/paragraph ordering | 13+ images |
| 7B | Oversized image 1359x1677 | LOW | `html_renderer.py` no size cap | 1 image |
| 7C | Missing `alt` text | MEDIUM | `html_renderer.py` / version mismatch | 28 images |
| 8A | Page breaks correct | OK | -- | 25 breaks |
| 8B | No max-width/padding | MEDIUM | Version mismatch or config | 1 doc |

---

## Recommended Fixes (Priority Order)

### P0 -- Must fix (CRITICAL)

1. **Fix header/footer merging into headings**: In `_group_paragraphs()`, handle negative Y gaps by treating them as absolute paragraph breaks. If `y_gap < 0`, it means the blocks are not in visual reading order (likely a footer-to-body transition). Add: `if y_gap < -10: is_new_para = True`.

2. **Suppress header/footer paragraphs in renderer**: In `_render_paragraph()`, add early return for `para.style in ("header", "footer")`. Also ensure that `_mark_headers_footers()` runs AFTER paragraph grouping to catch header/footer lines even when they're in their own paragraph.

3. **Fix table/paragraph deduplication**: The bounding-box overlap check in `_filter_table_overlapping_lines()` needs a larger tolerance, or should use an alternative strategy: after tables are extracted, remove any paragraph whose text content is a substring of any table cell text on the same page.

### P1 -- Should fix (HIGH)

4. **Fix subscript detection threshold**: Change `font_size < dominant_size * 0.80` to `font_size < dominant_size * 0.85` (or use `<= 0.80`). This will correctly flag 8pt text as subscript when body is 10pt (8/10 = 0.80).

5. **Wire formula enricher into pipeline**: Ensure `FormulaDetector` runs on extracted spans before rendering, so chemical/PK subscripts get `<sub>` annotation.

6. **Fix inter-span space injection**: In `_render_spans_html()`, add a space between adjacent spans where the first span's text ends with a letter/digit and the next span's text starts with a letter/digit. Alternatively, fix the extractor to always inject spaces at PDF line-break boundaries within the same block.

7. **Fix paragraph splitting threshold**: Tune `_group_paragraphs()` to use `y_gap > prev_size * 1.8` or add a heuristic: if the previous line doesn't end with a sentence-terminal character (`.`, `:`, `?`, `!`) and the next line starts lowercase, merge them.

### P2 -- Nice to fix (MEDIUM/LOW)

8. **Support rich text in table cells**: Extend `FormattedTableCell` to hold `spans` with formatting, not just plain `text`.

9. **Fix image/caption order**: Sort paragraphs and images by Y position before rendering, or extract images at their Y position and interleave them into the paragraph list.

10. **Add `<!DOCTYPE html>` wrapper**: When `include_wrapper=True`, emit a full HTML5 document structure.

11. **Add meaningful `alt` text to images**: Use adjacent caption text as the `alt` attribute.

12. **Prevent `<h4>` classification of table header rows**: In the heading classifier, add a negative signal for paragraphs that look like tabular data (multiple tab-separated or column-like tokens).

---

## Files Referenced

| File | Role |
|------|------|
| `src/formatter/extractor.py` | PDF text/table/image extraction, paragraph grouping, heading classification, header/footer detection, subscript detection |
| `src/formatter/render/html_renderer.py` | HTML generation from FormattedDocument IR |
| `src/formatter/formula_detector.py` | Formula pattern detection and HTML annotation (not invoked) |
