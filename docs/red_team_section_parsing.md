# Red Team Assessment: Section Parsing & Verbatim Extraction

**Date:** 22 March 2026
**Scope:** 24 sections across 5 protocols (Pfizer, P-01, P-09, P-14, P-27)

---

## FINDING 1: CRITICAL — Each Numbered List Item Gets Its Own `<ol>` Wrapper

**Severity: HIGH**

Every numbered list item emits a separate `<ol><li>...</li></ol>` block instead of grouping consecutive items under a single `<ol>`. There are 113 `<ol>` tags in the report, nearly all wrapping a single `<li>`.

```html
<!-- CURRENT (wrong) -->
<ol><li>Male or female participants...</li></ol>
<p>some body text</p>
<ol><li>Participants who are willing...</li></ol>

<!-- SHOULD BE -->
<ol>
  <li>Male or female participants...</li>
  <li>Participants who are willing...</li>
</ol>
```

**Root cause:** `_paragraphs_to_html` calls `_close_lists_to(0)` at the start of every `LIST_ITEM` before opening a new list. Combined with `_reconstruct_paragraphs` which forces `start_new = True` for every line matching the numbered pattern, consecutive items never group.

**Impact:** Invalid HTML semantics. Screen readers announce "list of 1 item" repeatedly. Copy-paste to Word produces broken numbering.

**Fix:** Track current list type and only close/reopen when list type changes or a non-list paragraph intervenes.

---

## FINDING 2: CRITICAL — Table Content Duplicated as Flattened Paragraphs

**Severity: HIGH**

Every table appears twice: once as a proper `<table>` (from `find_tables()`), and again as flattened `<p>` tags from the text-block extraction running over the same Y-range. Column headers get misclassified as `<h4><strong>` subheadings.

**Root cause:** The text-block loop (lines 939-995) doesn't check whether text falls inside a detected table's bounding box. Both the structured table and raw text from the same region end up in `raw_lines`.

**Impact:** Output is roughly double the correct size for table-heavy sections.

**Fix:** After `find_tables()`, collect all table bounding boxes and skip text blocks whose Y-coordinates fall within any table bbox.

---

## FINDING 3: HIGH — P-01 Watermark/DRM Noise Corruption

**Severity: HIGH**

P-01 has a heavily watermarked PDF. Extracted text is massively corrupted: `"to re to re extensions"`, `"ana ana alyly"`, `"e su e s subj ub ject"`. Tables filled with gibberish.

**Root cause:** No watermark/overlay detection. PyMuPDF extracts all text layers including repeated watermark fragments.

**Impact:** P-01 sections are ~30-40% watermark noise — largely unusable.

**Fix:** Detect and filter duplicate/near-duplicate text spans at the same (x,y) positions.

---

## FINDING 4: HIGH — Equation Detection Massive False Positives

**Severity: HIGH**

19/24 sections flagged as having equations. P-01 Section 7.10 (randomization): EQ:31. BNT162 Section 8.16.4 (phone call): EQ:30. These sections have zero actual equations.

**Root cause:** `_looks_like_equation` triggers on `n =` (sample sizes), `p <` (p-values), `≥` (eligibility criteria). A line like "≥12 years (Phase 2/3)" matches 2+ patterns.

**Impact:** If used to route content to LaTeX rendering, vast majority of flagged content is not equations.

**Fix:** Require `math_count >= 3` AND `pattern_matches >= 3` (currently >= 2 for either). Exclude common clinical patterns like `n = <number>`.

---

## FINDING 5: HIGH — P-01 Has Only L2 Sections (No L1)

**Severity: MEDIUM-HIGH**

All 63 P-01 sections detected at level 2. Parent sections ("2. BACKGROUND", "3. OBJECTIVES") completely missing. The hierarchy is flat with empty `children` arrays.

**Root cause:** P-01's PDF lacks bookmarks and the watermark noise prevents the header scan from finding parent-level headings.

---

## Summary

| Finding | Severity | Fixable Without Re-Extraction |
|---|---|---|
| Single-item `<ol>` wrappers | CRITICAL | Yes — HTML generation logic only |
| Table content duplication | CRITICAL | Yes — skip text blocks inside table bboxes |
| P-01 watermark corruption | HIGH | Partially — duplicate span filtering |
| Equation false positives | HIGH | Yes — tighten thresholds |
| P-01 flat hierarchy | MEDIUM-HIGH | Requires watermark fix first |

**Overall verdict:** The section parsing architecture is sound. Y-coordinate clipping, paragraph reconstruction, and DOCX generation work correctly for clean PDFs (Pfizer, P-09, P-14, P-27). The two critical bugs (single-item lists, table duplication) are HTML generation issues — easy to fix. The P-01 watermark problem is a separate challenge requiring PDF pre-processing.
