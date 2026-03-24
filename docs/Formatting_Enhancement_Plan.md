# Formatting Enhancement Plan — Verbatim Extraction Fidelity

## Baseline (2026-03-24)

**Aggregate fidelity score: 52.6/100** across 10 protocols.

| Protocol | Score | Issues | Critical | Notes |
|----------|-------|--------|----------|-------|
| P-01 | 60 | 4 | 4 | Bold list items misclassified |
| P-03 | 100 | 0 | 0 | Low-confidence parse (only 8 sections found) — no sections to evaluate |
| P-05 | 30 | 7 | 7 | Heavy list formatting, multiple resets |
| P-09 | 0 | 10 | 10 | Worst case — many stuck words, list issues |
| P-14 | 70 | 3 | 3 | Moderna — relatively clean |
| P-24 | 100 | 0 | 0 | Low-confidence parse — no sections to evaluate |
| P-27 | 10 | 9 | 9 | Many stuck words |
| P-32 | 0 | 17 | 9 | Worst protocol — complex formatting |
| P-33 | 56 | 6 | 4 | Mixed results |
| P-34 | 100 | 0 | 0 | Clean — no issues detected |

### Issue distribution
| ID | Count | Severity | Description |
|----|-------|----------|-------------|
| C3 | 46 | Critical | Missing spaces between merged words ("maleOrfemale") |
| M3 | 10 | Medium | Adjacent `<strong>` tags not merged |

### Target: 85/100 by Wave 1 completion

---

## Wave 1: Critical Fixes (target: 75/100)

### C3: Missing Spaces in Merged Text (46 occurrences — #1 priority)
**Root cause**: When PyMuPDF splits text into spans at line/page boundaries, the trailing/leading whitespace is lost. The merge logic adds a space but doesn't handle cases where the span itself drops the space.

**Fix in** `section_parser.py` `_reconstruct_paragraphs()`:
```python
# Before merging, check span-level whitespace
prev_text = current["text"]
# Check if the last span of previous line ends with space
last_span_text = current["spans_data"][-1][-1]["text"] if current["spans_data"] else ""
next_span_text = line["spans"][0]["text"] if line["spans"] else text

# Smart join: always add space unless hyphenation or already spaced
if prev_text.endswith("-"):
    current["text"] = prev_text[:-1] + text
elif prev_text.endswith((" ", "\n")) or text.startswith((" ", "\n")):
    current["text"] += text
else:
    # Check character boundary — don't join if both sides are letters
    if prev_text and prev_text[-1].isalpha() and text and text[0].isalpha():
        current["text"] += " " + text
    else:
        current["text"] += text
```

**Also fix** `_format_inline_html()` line 1504-1510 — the inter-line space logic.

**Eval**: Run `eval_formatting_fidelity.py` → C3 count should drop from 46 to <5.

### C1: Bold List Items Misclassified as Paragraphs
**Root cause**: `is_numbered_list` requires `not line["bold"]`. But criteria like "4. **Phase 2/3 only:** Participants who..." are bold in the first span but not-bold in the continuation.

**Fix**: Change bold detection to check if the **majority** of the line's text content is bold, not any-span:
```python
# Replace: line["bold"]  (any-span bold)
# With: _is_majority_bold(line["spans"])
def _is_majority_bold(spans):
    bold_chars = sum(len(s["text"]) for s in spans if s["flags"] & 16 or "Bold" in s.get("font", ""))
    total_chars = sum(len(s["text"]) for s in spans)
    return bold_chars > total_chars * 0.6  # >60% bold = bold line
```

Then allow numbered list items even when the prefix is bold:
```python
is_numbered_list = bool(numbered_list_re.match(text) and not is_section_heading)
# Remove: `and not line["bold"]`
```

**Eval**: P-01 Section 5.1 inclusion criteria → items 4, 5 should render as `<li>` not `<p>`.

### C2: List Numbering Resets Per Item
**Root cause**: Subheadings between list items close the `<ol>` context. Item 1 → subheading → item 2 = two `<ol>` blocks.

**Fix**: In `_paragraphs_to_html()`, track the running list counter and use `<ol start="N">`:
```python
# When a non-list element (subheading) appears between list items:
# Don't close the list — instead, inject the subheading inside the list context
# OR: close and reopen with start="N"
last_list_number = 0
```

**Eval**: Section 5.1 → one continuous `<ol>` or `<ol start="N">` blocks.

### M3: Adjacent Bold Fragments Not Merged
**Root cause**: Separate spans with identical formatting produce `</strong><strong>` in HTML.

**Fix**: Post-process HTML to merge adjacent same-tag elements:
```python
def _merge_adjacent_tags(html: str) -> str:
    # Merge: </strong><strong> → (remove)
    # Merge: </em><em> → (remove)
    html = re.sub(r'</strong>\s*<strong>', '', html)
    html = re.sub(r'</em>\s*<em>', '', html)
    html = re.sub(r'</u>\s*<u>', '', html)
    return html
```

**Eval**: M3 count should drop from 10 to 0.

---

## Wave 2: High-Priority Formatting (target: 85/100)

### H1: Sub-Item Nesting (a., b., c.)
**Root cause**: L2 detection requires `indent_level >= 3`. Many protocols use indent level 2 for sub-items.

**Fix**: Reduce L2 threshold and add letter-list detection:
```python
letter_list_re = re.compile(r"^[a-z][.)]\s")

# Sub-item detection:
is_sub_item = (
    letter_list_re.match(text)
    or (is_bullet and indent_level >= 2)  # Was >= 3
)
```

### H3: Underline Detection
**Fix**: Add flag check in `_format_inline_html()`:
```python
is_underline = flags & 4
if is_underline:
    text = f"<u>{text}</u>"
```

### H4: Cross-Page Merge Validation
**Fix**: Before merging across pages, validate Y-position continuity:
```python
# Last line Y on previous page should be near bottom of page
# First line Y on next page should be near top
if line["page"] != current.get("last_page"):
    prev_y = current.get("last_y", 0)
    # If previous line was above page midpoint, it's unlikely a continuation
    if prev_y < 400:  # ~middle of standard page
        start_new = True
```

### C4: Auto LLM Fallback for Low-Confidence Parse
**Fix**: When parse score < threshold, automatically invoke LLM-assisted parsing:
```python
if best_score < 30 and len(best_sections) < 20:
    logger.warning("Low-confidence parse — invoking LLM fallback")
    llm_sections = await self.parse_with_llm(pdf_bytes)
    if len(llm_sections) > len(best_sections):
        best_sections = llm_sections
```

### M4: Generalize Header/Footer Stripping
**Fix**: Auto-detect repeated text in top/bottom margins:
```python
def _detect_headers_footers(self, doc) -> tuple[list[re.Pattern], list[re.Pattern]]:
    """Detect repeated text in page margins across 5+ pages."""
    top_texts = Counter()
    bottom_texts = Counter()
    for page in doc[:min(20, len(doc))]:
        blocks = page.get_text("dict")["blocks"]
        for block in blocks:
            for line in block.get("lines", []):
                y = line["spans"][0]["origin"][1]
                text = "".join(s["text"] for s in line["spans"]).strip()
                if y < 80:  # Top margin
                    top_texts[text] += 1
                elif y > page.rect.height - 80:  # Bottom margin
                    bottom_texts[text] += 1
    # Patterns appearing on 5+ pages are headers/footers
    patterns = []
    for text, count in {**top_texts, **bottom_texts}.items():
        if count >= 5 and len(text) > 3:
            patterns.append(re.compile(re.escape(text), re.IGNORECASE))
    return patterns
```

---

## Wave 3: Polish & New Capabilities (target: 90/100)

### M1: Hyperlink Preservation
```python
# In get_section_formatted(), after text extraction:
links = page.get_links()
for link in links:
    if link["kind"] == 2:  # URI link
        # Find text at link rect position, wrap in <a>
```

### M2: Text Color Preservation
```python
color = span.get("color", 0)
if color and color != 0:
    r, g, b = (color >> 16) & 0xFF, (color >> 8) & 0xFF, color & 0xFF
    text = f'<span style="color:rgb({r},{g},{b})">{text}</span>'
```

### Image Extraction (from rough notes Phase 1-2)
- Extract embedded images via `page.get_images()`
- Position-aware interleaving with text via Y-coordinate
- Base64 inline for HTML, `add_picture()` for DOCX
- Region capture fallback via `get_pixmap(clip=rect)`

### Formula Handling (from rough notes Phase 3-5)
- Unicode formula → LaTeX conversion
- Image formula → LaTeX via VLM
- OMML extraction from DOCX
- KaTeX rendering in UI

---

## Evaluation Framework

### How to run
```bash
python -m tests.eval_formatting_fidelity
```

### What it measures
| Metric | Method |
|--------|--------|
| C1: Bold list items | Count `<p>N.<strong>` patterns |
| C2: List resets | Count `</ol>...<ol>` sequences |
| C3: Missing spaces | Detect camelCase and stuck-word patterns |
| H1: Sub-item nesting | Count flat `<li>a.` vs nested `<ul><li>a.` |
| M3: Bold fragments | Count `</strong><strong>` sequences |
| Fidelity score | Start at 100, deduct per issue (C=-10, H=-5, M=-2) |

### Targets
| Wave | Target Score | Timeline |
|------|-------------|----------|
| Baseline | 52.6/100 | Current |
| Wave 1 | 75/100 | C3 + C1 + C2 + M3 fixes |
| Wave 2 | 85/100 | H1 + H3 + H4 + C4 + M4 fixes |
| Wave 3 | 90/100 | M1 + M2 + images + formulas |

### Progress tracking
After each fix, run the eval and record:
```bash
python -m tests.eval_formatting_fidelity
# Output saved to tests/formatting_fidelity_report.json
```

Compare `aggregate_score` and per-protocol breakdown against baseline.

---

## Files to Modify

| File | Wave | Changes |
|------|------|---------|
| `src/pipeline/section_parser.py` | 1-2 | C1, C2, C3, H1, H3, H4, M3, M4 |
| `web/src/app/globals.css` | 1 | List styling for `<ol start="N">` |
| `api/main.py` | 2 | Auto-LLM fallback endpoint |
| `src/pipeline/verbatim_extractor.py` | 3 | Image + formula extraction |
| `web/src/app/tools/verbatim/page.tsx` | 3 | Formula rendering (KaTeX) |
| `tests/eval_formatting_fidelity.py` | All | Updated checks per wave |
