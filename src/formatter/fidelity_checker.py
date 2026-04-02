"""
Document Fidelity Checker — compares two documents for formatting conformance.

Addresses the 3 core client issues:
1. Formatting alignment with blueprint template (spacing, fonts, alignment)
2. Run-on words detection and repair
3. Unnecessary strikethrough detection (same-word redlines)

Usage:
    checker = DocumentFidelityChecker()
    report = checker.check(pdf_bytes)
    # or compare against a template:
    report = checker.compare(template_pdf_bytes, generated_pdf_bytes)
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from typing import Any

from src.formatter.extractor import (
    FormattedDocument,
    FormattedPage,
    FormattedParagraph,
    FormattedSpan,
    FormattingExtractor,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Fidelity issue models
# ---------------------------------------------------------------------------

@dataclass
class FidelityIssue:
    """A single formatting fidelity issue found in the document."""
    category: str       # runon_word, spacing, alignment, font, color, strikethrough, template_mismatch
    severity: str       # critical, high, medium, low
    page: int
    location: str       # human-readable location (e.g., "Paragraph 3, line 2")
    description: str
    original_text: str = ""
    suggested_fix: str = ""
    auto_fixable: bool = False


@dataclass
class FidelityReport:
    """Complete fidelity check report for a document."""
    document_name: str = ""
    total_issues: int = 0
    critical_count: int = 0
    high_count: int = 0
    medium_count: int = 0
    low_count: int = 0
    issues: list[FidelityIssue] = field(default_factory=list)
    formatting_summary: dict[str, Any] = field(default_factory=dict)
    score: float = 100.0  # 0-100 fidelity score

    def add_issue(self, issue: FidelityIssue) -> None:
        self.issues.append(issue)
        self.total_issues += 1
        if issue.severity == "critical":
            self.critical_count += 1
        elif issue.severity == "high":
            self.high_count += 1
        elif issue.severity == "medium":
            self.medium_count += 1
        else:
            self.low_count += 1

    def compute_score(self) -> float:
        """Compute a fidelity score: 100 = perfect, 0 = unusable."""
        penalty = (
            self.critical_count * 10
            + self.high_count * 5
            + self.medium_count * 2
            + self.low_count * 0.5
        )
        self.score = max(0.0, 100.0 - penalty)
        return self.score


# ---------------------------------------------------------------------------
# Run-on word detector
# ---------------------------------------------------------------------------

# Common clinical/pharma words that appear concatenated
_WORD_BOUNDARY_RE = re.compile(
    r"[a-z][A-Z]"   # camelCase boundary (lowercase→uppercase)
)

_RUNON_PATTERNS = [
    # Long words (>15 chars) with internal capital
    re.compile(r"\b[a-z]+[A-Z][a-z]{3,}\b"),
    # Known clinical concatenation patterns
    re.compile(r"(?:the|and|for|with|from|this|that|will|shall|must|each|been|have|were|are|was|not|all|may|can|any)"
               r"(?:the|and|for|with|from|this|that|will|shall|must|each|been|have|were|are|was|not|all|may|can|any)", re.IGNORECASE),
]


def detect_runon_words(text: str) -> list[tuple[str, int, str]]:
    """Detect run-on words in text.

    Returns list of (word, position, suggested_fix).
    """
    issues = []

    # Method 1: Words > 15 chars with internal uppercase
    words = text.split()
    pos = 0
    for word in words:
        clean = re.sub(r"[^\w]", "", word)
        if len(clean) > 15:
            # Check for camelCase-like boundaries
            boundaries = list(_WORD_BOUNDARY_RE.finditer(clean))
            if boundaries:
                # Split at boundaries
                parts = []
                last = 0
                for m in boundaries:
                    parts.append(clean[last:m.start() + 1])
                    last = m.start() + 1
                parts.append(clean[last:])
                fix = " ".join(parts)
                issues.append((word, pos, fix))

        pos += len(word) + 1

    # Method 2: Common word concatenations
    for pattern in _RUNON_PATTERNS:
        for match in pattern.finditer(text):
            matched = match.group()
            # Try to split into two real words
            for split_point in range(3, len(matched) - 2):
                left = matched[:split_point].lower()
                right = matched[split_point:].lower()
                if left in _COMMON_WORDS and right in _COMMON_WORDS:
                    fix = f"{matched[:split_point]} {matched[split_point:]}"
                    issues.append((matched, match.start(), fix))
                    break

    return issues


_COMMON_WORDS = {
    "the", "and", "for", "with", "from", "this", "that", "will", "shall",
    "must", "each", "been", "have", "were", "are", "was", "not", "all",
    "may", "can", "any", "but", "has", "had", "its", "per", "via", "use",
    "who", "how", "our", "one", "two", "new", "also", "only", "such",
    "more", "most", "some", "very", "just", "than", "then", "when",
    "both", "well", "much", "many", "made", "does", "done", "used",
    "same", "need", "into", "over", "upon", "time", "days", "week",
    "year", "site", "dose", "drug", "test", "data", "form", "part",
    "study", "trial", "subject", "patient", "visit", "protocol",
    "information", "should", "would", "could", "during", "after",
    "before", "between", "within", "through", "about", "other",
}


# ---------------------------------------------------------------------------
# Strikethrough analyzer
# ---------------------------------------------------------------------------

def detect_unnecessary_strikethroughs(
    old_text: str, new_text: str, threshold: float = 0.95,
) -> list[tuple[str, str, float]]:
    """Detect strikethroughs where old and new text are essentially identical.

    Returns list of (old_word, new_word, similarity) where similarity > threshold.
    """
    issues = []
    old_words = old_text.split()
    new_words = new_text.split()

    matcher = SequenceMatcher(None, old_words, new_words)
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "replace":
            # Words being "replaced" — check if they're actually the same
            for k in range(min(i2 - i1, j2 - j1)):
                old_w = old_words[i1 + k]
                new_w = new_words[j1 + k]
                # Normalize for comparison
                old_norm = re.sub(r"[^\w]", "", old_w).lower()
                new_norm = re.sub(r"[^\w]", "", new_w).lower()
                if old_norm == new_norm:
                    issues.append((old_w, new_w, 1.0))
                else:
                    sim = SequenceMatcher(None, old_norm, new_norm).ratio()
                    if sim >= threshold:
                        issues.append((old_w, new_w, sim))

    return issues


# ---------------------------------------------------------------------------
# Main fidelity checker
# ---------------------------------------------------------------------------

class DocumentFidelityChecker:
    """Checks document formatting fidelity and identifies issues."""

    def __init__(self):
        self.extractor = FormattingExtractor()

    def check(self, pdf_bytes: bytes, filename: str = "") -> FidelityReport:
        """Check a single document for formatting issues."""
        doc = self.extractor.extract(pdf_bytes, filename)
        report = FidelityReport(document_name=filename)

        # Check 1: Run-on words
        self._check_runon_words(doc, report)

        # Check 2: Spacing consistency
        self._check_spacing(doc, report)

        # Check 3: Font consistency
        self._check_font_consistency(doc, report)

        # Check 4: Alignment issues
        self._check_alignment(doc, report)

        # Check 5: Color usage
        self._check_color_usage(doc, report)

        # Build summary
        report.formatting_summary = {
            "total_pages": len(doc.pages),
            "total_paragraphs": doc.total_paragraphs,
            "fonts_used": dict(sorted(doc.font_inventory.items(), key=lambda x: -x[1])[:10]),
            "colors_used": dict(sorted(doc.color_inventory.items(), key=lambda x: -x[1])[:10]),
            "styles_used": doc.style_inventory,
        }

        report.compute_score()
        return report

    def compare(
        self,
        template_pdf: bytes,
        generated_pdf: bytes,
        template_name: str = "template",
        generated_name: str = "generated",
    ) -> FidelityReport:
        """Compare a generated document against a template for conformance."""
        template = self.extractor.extract(template_pdf, template_name)
        generated = self.extractor.extract(generated_pdf, generated_name)
        report = FidelityReport(document_name=generated_name)

        # All single-doc checks
        self._check_runon_words(generated, report)
        self._check_spacing(generated, report)
        self._check_alignment(generated, report)

        # Template comparison checks
        self._compare_fonts(template, generated, report)
        self._compare_margins(template, generated, report)
        self._compare_spacing_patterns(template, generated, report)

        report.formatting_summary = {
            "template_fonts": dict(sorted(template.font_inventory.items(), key=lambda x: -x[1])[:5]),
            "generated_fonts": dict(sorted(generated.font_inventory.items(), key=lambda x: -x[1])[:5]),
            "template_pages": len(template.pages),
            "generated_pages": len(generated.pages),
            "font_match": self._font_match_score(template, generated),
        }

        report.compute_score()
        return report

    # ── Single-document checks ──────────────────────────────────────────

    def _check_runon_words(self, doc: FormattedDocument, report: FidelityReport) -> None:
        """Detect run-on words throughout the document."""
        for page in doc.pages:
            for para_idx, para in enumerate(page.paragraphs):
                text = para.text
                runons = detect_runon_words(text)
                for word, pos, fix in runons:
                    report.add_issue(FidelityIssue(
                        category="runon_word",
                        severity="high",
                        page=page.page_number + 1,
                        location=f"Paragraph {para_idx + 1}",
                        description=f"Run-on word detected: '{word}'",
                        original_text=word,
                        suggested_fix=fix,
                        auto_fixable=True,
                    ))

    def _check_spacing(self, doc: FormattedDocument, report: FidelityReport) -> None:
        """Check for spacing inconsistencies."""
        for page in doc.pages:
            for para_idx, para in enumerate(page.paragraphs):
                # Check for double spaces
                text = para.text
                double_spaces = [m.start() for m in re.finditer(r"  +", text)]
                if len(double_spaces) > 2:
                    report.add_issue(FidelityIssue(
                        category="spacing",
                        severity="medium",
                        page=page.page_number + 1,
                        location=f"Paragraph {para_idx + 1}",
                        description=f"Multiple double-spaces found ({len(double_spaces)} instances)",
                        auto_fixable=True,
                    ))

                # Check for missing space after period
                missing_space = re.findall(r"\.[A-Z]", text)
                for ms in missing_space:
                    report.add_issue(FidelityIssue(
                        category="runon_word",
                        severity="high",
                        page=page.page_number + 1,
                        location=f"Paragraph {para_idx + 1}",
                        description=f"Missing space after period: '...{ms}...'",
                        original_text=ms,
                        suggested_fix=f"{ms[0]} {ms[1]}",
                        auto_fixable=True,
                    ))

    def _check_font_consistency(self, doc: FormattedDocument, report: FidelityReport) -> None:
        """Check for unexpected font changes within paragraphs."""
        for page in doc.pages:
            for para_idx, para in enumerate(page.paragraphs):
                fonts_in_para = set()
                for line in para.lines:
                    for span in line.spans:
                        if span.text.strip():
                            fonts_in_para.add(span.font_family)

                # More than 2 font families in one paragraph is suspicious
                if len(fonts_in_para) > 2:
                    report.add_issue(FidelityIssue(
                        category="font",
                        severity="medium",
                        page=page.page_number + 1,
                        location=f"Paragraph {para_idx + 1}",
                        description=f"Mixed fonts in paragraph: {', '.join(fonts_in_para)}",
                    ))

    def _check_alignment(self, doc: FormattedDocument, report: FidelityReport) -> None:
        """Check for alignment inconsistencies."""
        for page in doc.pages:
            # Check if body text indents are consistent
            body_indents = [
                para.lines[0].indent
                for para in page.paragraphs
                if para.style == "body" and para.lines
            ]
            if len(body_indents) > 3:
                unique_indents = set(round(i, 0) for i in body_indents)
                if len(unique_indents) > 3:
                    report.add_issue(FidelityIssue(
                        category="alignment",
                        severity="medium",
                        page=page.page_number + 1,
                        location="Page body text",
                        description=f"Inconsistent body text indentation: {len(unique_indents)} different indent levels",
                    ))

    def _check_color_usage(self, doc: FormattedDocument, report: FidelityReport) -> None:
        """Flag unexpected colors (not black, not standard blue links)."""
        standard_colors = {"#000000", "#0000FF", "#0563C1", "#FFFFFF"}
        for hex_color, count in doc.color_inventory.items():
            if hex_color not in standard_colors and count > 5:
                report.add_issue(FidelityIssue(
                    category="color",
                    severity="low",
                    page=0,
                    location="Document-wide",
                    description=f"Non-standard color {hex_color} used {count} times",
                ))

    # ── Template comparison checks ──────────────────────────────────────

    def _compare_fonts(
        self, template: FormattedDocument, generated: FormattedDocument,
        report: FidelityReport,
    ) -> None:
        """Compare font usage between template and generated."""
        template_fonts = set(template.font_inventory.keys())
        generated_fonts = set(generated.font_inventory.keys())

        unexpected = generated_fonts - template_fonts
        for font in unexpected:
            count = generated.font_inventory[font]
            if count > 10:
                report.add_issue(FidelityIssue(
                    category="template_mismatch",
                    severity="high",
                    page=0,
                    location="Document-wide",
                    description=f"Font '{font}' not in template (used {count} times)",
                ))

        missing = template_fonts - generated_fonts
        for font in missing:
            count = template.font_inventory[font]
            if count > 10:
                report.add_issue(FidelityIssue(
                    category="template_mismatch",
                    severity="medium",
                    page=0,
                    location="Document-wide",
                    description=f"Template font '{font}' missing from generated document",
                ))

    def _compare_margins(
        self, template: FormattedDocument, generated: FormattedDocument,
        report: FidelityReport,
    ) -> None:
        """Compare page margins between template and generated."""
        if not template.pages or not generated.pages:
            return

        tp = template.pages[0]
        gp = generated.pages[0]

        for attr, label in [
            ("margin_left", "Left margin"),
            ("margin_right", "Right margin"),
            ("margin_top", "Top margin"),
        ]:
            t_val = getattr(tp, attr)
            g_val = getattr(gp, attr)
            diff = abs(t_val - g_val)
            if diff > 10:  # more than 10pt difference
                report.add_issue(FidelityIssue(
                    category="template_mismatch",
                    severity="high",
                    page=1,
                    location="Page layout",
                    description=f"{label} differs: template={t_val:.0f}pt, generated={g_val:.0f}pt (diff={diff:.0f}pt)",
                ))

    def _compare_spacing_patterns(
        self, template: FormattedDocument, generated: FormattedDocument,
        report: FidelityReport,
    ) -> None:
        """Compare paragraph spacing patterns."""
        def get_spacing_stats(doc: FormattedDocument) -> dict[str, float]:
            spacings = [
                p.spacing_before for page in doc.pages
                for p in page.paragraphs if p.spacing_before > 0
            ]
            if not spacings:
                return {"avg": 0, "median": 0}
            spacings.sort()
            return {
                "avg": sum(spacings) / len(spacings),
                "median": spacings[len(spacings) // 2],
            }

        t_stats = get_spacing_stats(template)
        g_stats = get_spacing_stats(generated)

        if t_stats["avg"] > 0 and g_stats["avg"] > 0:
            ratio = g_stats["avg"] / t_stats["avg"]
            if ratio < 0.7 or ratio > 1.3:
                report.add_issue(FidelityIssue(
                    category="template_mismatch",
                    severity="high",
                    page=0,
                    location="Document-wide",
                    description=(
                        f"Paragraph spacing differs significantly: "
                        f"template avg={t_stats['avg']:.1f}pt, "
                        f"generated avg={g_stats['avg']:.1f}pt"
                    ),
                ))

    def _font_match_score(
        self, template: FormattedDocument, generated: FormattedDocument,
    ) -> float:
        """Compute font match score (0-1) between template and generated."""
        t_fonts = set(template.font_inventory.keys())
        g_fonts = set(generated.font_inventory.keys())
        if not t_fonts:
            return 1.0
        overlap = t_fonts & g_fonts
        return len(overlap) / len(t_fonts)
