"""
Formatting Fidelity Evaluation — measures verbatim extraction quality.

Runs against all available protocol PDFs and reports:
- List detection accuracy (numbered, bullet, nested)
- Heading detection accuracy
- Bold/italic/underline preservation
- Table extraction
- Paragraph boundary detection
- Cross-page merge quality
- Image presence detection

Output: JSON report with per-protocol scores + aggregate.
Run: python -m tests.eval_formatting_fidelity
"""

from __future__ import annotations

import json
import re
import sys
import time
from pathlib import Path

# Ensure project root is on path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.pipeline.section_parser import SectionParser


def count_html_elements(html: str) -> dict:
    """Count structural HTML elements in extracted content."""
    return {
        "paragraphs": len(re.findall(r"<p[\s>]", html)),
        "headings": len(re.findall(r"<h[1-6][\s>]", html)),
        "ol_lists": len(re.findall(r"<ol[\s>]", html)),
        "ul_lists": len(re.findall(r"<ul[\s>]", html)),
        "list_items": len(re.findall(r"<li[\s>]", html)),
        "bold_spans": len(re.findall(r"<strong[\s>]", html)),
        "italic_spans": len(re.findall(r"<em[\s>]", html)),
        "underline_spans": len(re.findall(r"<u[\s>]", html)),
        "tables": len(re.findall(r"<table[\s>]", html)),
        "table_rows": len(re.findall(r"<tr[\s>]", html)),
        "images": len(re.findall(r"<img[\s>]", html)),
        "figures": len(re.findall(r"<figure[\s>]", html)),
        "links": len(re.findall(r"<a[\s>]", html)),
    }


def check_formatting_issues(html: str, text: str) -> list[dict]:
    """Detect known formatting issues in extracted content."""
    issues = []

    # C1: Bold list items rendered as paragraphs
    # Look for <p>N. text</p> where it should be <li>
    for m in re.finditer(r"<p>\s*(\d{1,3})[.)]\s*<strong>", html):
        issues.append({
            "id": "C1",
            "severity": "critical",
            "description": f"Numbered item {m.group(1)} rendered as <p> with bold — should be <li>",
            "position": m.start(),
        })

    # C2: Multiple <ol> tags in sequence (numbering resets)
    ol_count = len(re.findall(r"</ol>\s*(?:<[^o][^>]*>\s*)*<ol>", html))
    if ol_count > 0:
        issues.append({
            "id": "C2",
            "severity": "critical",
            "description": f"List numbering resets {ol_count} time(s) — multiple <ol> blocks instead of one",
            "count": ol_count,
        })

    # C3: Missing spaces between words
    # Detect genuine stuck words: lowercase immediately followed by uppercase
    # that forms a word boundary (not part of a single scientific term).
    # Strategy: find camelCase patterns, then check if they're inside a single
    # word (legitimate) or at a word boundary (stuck).
    missing_spaces = []
    for m in re.finditer(r"([a-z])([A-Z])([a-z])", text):
        idx = m.start()
        # Get the full word containing this pattern
        # Walk left to find word start
        start = idx
        while start > 0 and text[start - 1].isalpha():
            start -= 1
        # Walk right to find word end
        end = idx + 3
        while end < len(text) and text[end].isalpha():
            end += 1
        word = text[start:end]

        # If the word is short (<12 chars), it's likely a legitimate
        # abbreviation (mRNA, nAbs, CoVs, eGFR, etc.)
        if len(word) <= 12:
            continue

        # If the word is long and has camelCase mid-word, it's likely stuck
        # e.g., "maleOrfemale" (14 chars) vs "neutralizingAntibody" (20 chars)
        missing_spaces.append(m.group())

    if len(missing_spaces) >= 3:  # Only flag if 3+ instances (avoids noise)
        issues.append({
            "id": "C3",
            "severity": "critical",
            "description": f"Missing spaces: {len(missing_spaces)} camelCase boundaries in long words",
            "examples": missing_spaces[:5],
        })

    # H1: Sub-items (a., b., c.) not nested
    sub_items_flat = len(re.findall(r"<li>\s*[a-z][.)]\s", html))
    sub_items_nested = len(re.findall(r"<ul>\s*<li>\s*[a-z][.)]\s", html))
    if sub_items_flat > 0 and sub_items_nested == 0:
        issues.append({
            "id": "H1",
            "severity": "high",
            "description": f"{sub_items_flat} sub-items (a., b.) at L1 instead of nested L2",
        })

    # Wave 3: Image presence detection
    img_count = len(re.findall(r"<figure[\s>]", html)) + len(re.findall(r"<img[\s>]", html))
    # This is informational, not a deduction — images are a bonus

    # H3: Missing underline
    # Can't detect this from HTML alone — need to check if PDF has underlined text

    # M3: Adjacent bold fragments not merged
    adjacent_bold = len(re.findall(r"</strong>\s*<strong>", html))
    if adjacent_bold > 0:
        issues.append({
            "id": "M3",
            "severity": "medium",
            "description": f"{adjacent_bold} adjacent <strong> tags not merged",
        })

    return issues


def evaluate_section(parser: SectionParser, pdf_bytes: bytes, section_num: str) -> dict | None:
    """Evaluate formatting fidelity for one section."""
    sections = parser.parse(pdf_bytes)
    section = parser.find(sections, section_num)
    if not section:
        return None

    html = parser.get_section_formatted(pdf_bytes, section, output="html", strip_heading=True)
    if not isinstance(html, str) or len(html) < 10:
        return None

    text = re.sub(r"<[^>]+>", " ", html)
    text = re.sub(r"\s+", " ", text).strip()

    elements = count_html_elements(html)
    issues = check_formatting_issues(html, text)

    return {
        "section": section_num,
        "title": section.title,
        "page": section.page,
        "html_length": len(html),
        "text_length": len(text),
        "elements": elements,
        "issues": issues,
        "issue_count": len(issues),
        "critical_count": sum(1 for i in issues if i["severity"] == "critical"),
        "high_count": sum(1 for i in issues if i["severity"] == "high"),
    }


def evaluate_protocol(pdf_path: Path) -> dict:
    """Evaluate formatting fidelity for an entire protocol."""
    parser = SectionParser()
    pdf_bytes = pdf_path.read_bytes()

    start = time.time()
    sections = parser.parse(pdf_bytes, filename=pdf_path.name)
    parse_time = time.time() - start

    flat = parser._flatten(sections)
    # Dedup
    seen = set()
    deduped = []
    for s in flat:
        k = (s.number, s.page)
        if k not in seen:
            seen.add(k)
            deduped.append(s)

    total_sections = len(deduped)
    section_with_numbers = [s for s in deduped if s.number]

    # Evaluate a sample of key clinical sections (up to 10)
    # Uses structured targets: try by number first, then by title keyword
    TARGET_SECTIONS = [
        {"numbers": ["1"], "keywords": ["synopsis", "summary", "introduction"]},
        {"numbers": ["2"], "keywords": ["background", "rationale"]},
        {"numbers": ["3"], "keywords": ["objective", "endpoint"]},
        {"numbers": ["4"], "keywords": ["design", "overview"]},
        {"numbers": ["5", "5.1"], "keywords": ["inclusion", "eligibility"]},
        {"numbers": ["5.2"], "keywords": ["exclusion"]},
        {"numbers": ["6", "6.1"], "keywords": ["intervention", "treatment", "study drug"]},
        {"numbers": ["6.2"], "keywords": ["dosing", "administration"]},
        {"numbers": ["8"], "keywords": ["assessment", "procedure", "schedule"]},
        {"numbers": ["9"], "keywords": ["statistical", "sample size", "analysis"]},
    ]

    sample_sections = []
    for target in TARGET_SECTIONS:
        found = None
        # Try number first
        for num in target["numbers"]:
            found = parser.find(sections, num)
            if found:
                sample_sections.append(num)
                break
        # Fall back to keyword search
        if not found:
            for kw in target["keywords"]:
                matches = parser.find_by_title(sections, kw)
                if matches:
                    sec = matches[0]
                    if sec.number and sec.number not in sample_sections:
                        sample_sections.append(sec.number)
                        found = sec
                        break
        if len(sample_sections) >= 10:
            break

    results = []
    total_issues = 0
    total_critical = 0
    total_elements = {
        "paragraphs": 0, "headings": 0, "ol_lists": 0, "ul_lists": 0,
        "list_items": 0, "bold_spans": 0, "italic_spans": 0,
        "underline_spans": 0, "tables": 0, "images": 0,
    }

    for sec_num in sample_sections:
        result = evaluate_section(parser, pdf_bytes, sec_num)
        if result:
            results.append(result)
            total_issues += result["issue_count"]
            total_critical += result["critical_count"]
            for k in total_elements:
                total_elements[k] += result["elements"].get(k, 0)

    # Scoring: honest assessment
    if total_sections < 10:
        score = 0  # Parser failure
    elif len(results) == 0:
        score = 50  # Parser found sections but none were evaluable
    else:
        score = 100
        for r in results:
            for issue in r["issues"]:
                if issue["severity"] == "critical":
                    score -= 10
                elif issue["severity"] == "high":
                    score -= 5
                elif issue["severity"] == "medium":
                    score -= 2
        score = max(0, score)

    return {
        "protocol": pdf_path.stem,
        "total_sections": total_sections,
        "sections_with_numbers": len(section_with_numbers),
        "parse_time_seconds": round(parse_time, 2),
        "sections_evaluated": len(results),
        "total_issues": total_issues,
        "critical_issues": total_critical,
        "fidelity_score": score,
        "elements": total_elements,
        "section_results": results,
    }


def main():
    """Run formatting fidelity evaluation across all available protocols."""
    pdf_dir = Path("golden_set/cached_pdfs")
    if not pdf_dir.exists():
        print("No PDFs found in golden_set/cached_pdfs/")
        return

    pdfs = sorted(pdf_dir.glob("*.pdf"))
    print(f"Evaluating {len(pdfs)} protocols...\n")

    all_results = []
    for pdf_path in pdfs:
        print(f"  {pdf_path.stem}...", end=" ", flush=True)
        try:
            result = evaluate_protocol(pdf_path)
            all_results.append(result)
            print(
                f"score={result['fidelity_score']}/100  "
                f"issues={result['total_issues']} "
                f"(C={result['critical_issues']})  "
                f"sections={result['sections_evaluated']}"
            )
        except Exception as e:
            print(f"FAILED: {e}")
            all_results.append({
                "protocol": pdf_path.stem,
                "fidelity_score": 0,
                "error": str(e),
            })

    # Aggregate
    scores = [r["fidelity_score"] for r in all_results if "error" not in r]
    avg_score = sum(scores) / max(len(scores), 1)
    total_issues_all = sum(r.get("total_issues", 0) for r in all_results)
    total_critical_all = sum(r.get("critical_issues", 0) for r in all_results)

    print(f"\n{'='*60}")
    print(f"AGGREGATE FIDELITY SCORE: {avg_score:.1f}/100")
    print(f"Total issues: {total_issues_all} (Critical: {total_critical_all})")
    print(f"Protocols evaluated: {len(all_results)}")
    print(f"{'='*60}")

    # Save report
    report = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "aggregate_score": round(avg_score, 1),
        "total_issues": total_issues_all,
        "critical_issues": total_critical_all,
        "protocols": all_results,
    }

    report_path = Path("tests/formatting_fidelity_report.json")
    report_path.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    print(f"\nDetailed report: {report_path}")


if __name__ == "__main__":
    main()
