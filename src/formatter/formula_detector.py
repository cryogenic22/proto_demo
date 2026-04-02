"""
Formula Detector — identifies and preserves formulas in pharma documents.

Detects 5 formula types common in clinical trial documents:
1. Chemical: CO2, H2O, HbA1c, Na+, PO4(3-)
2. Dosing: 10 mg/kg, 200 mg/m2, q3w
3. Statistical: p < 0.05, HR 0.67 (95% CI: 0.45-0.99)
4. Pharmacokinetic: AUC(0-inf), Cmax, t1/2, Vd/F
5. Mathematical: summation, integrals, fractions

Each detected formula is annotated with:
- Type classification
- Original text (as-extracted)
- HTML rendering (with proper sub/superscript tags)
- Position in document (page, paragraph)

Usage:
    detector = FormulaDetector()
    formulas = detector.detect(text)
    html = detector.annotate_html(text)
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class DetectedFormula:
    """A formula detected in the document text."""
    formula_type: str           # chemical, dosing, statistical, pk, mathematical
    original_text: str          # raw text as found
    html_text: str             # HTML-formatted with sub/sup tags
    start: int = 0             # position in source text
    end: int = 0
    confidence: float = 1.0


# ---------------------------------------------------------------------------
# Pattern definitions
# ---------------------------------------------------------------------------

# Chemical formulas
_CHEMICAL_PATTERNS: list[tuple[re.Pattern, str, str]] = [
    # CO2 → CO<sub>2</sub>
    (re.compile(r"\bCO2\b"), "CO<sub>2</sub>", "chemical"),
    # H2O → H<sub>2</sub>O
    (re.compile(r"\bH2O\b"), "H<sub>2</sub>O", "chemical"),
    # O2 (not part of larger word like CO2)
    (re.compile(r"(?<![A-Za-z])O2(?![A-Za-z0-9])"), "O<sub>2</sub>", "chemical"),
    # N2
    (re.compile(r"(?<![A-Za-z])N2(?![A-Za-z0-9])"), "N<sub>2</sub>", "chemical"),
    # HbA1c → HbA<sub>1c</sub>
    (re.compile(r"\bHbA1c\b"), "HbA<sub>1c</sub>", "chemical"),
    # PO4 → PO<sub>4</sub>
    (re.compile(r"\bPO4\b"), "PO<sub>4</sub>", "chemical"),
    # SO4 → SO<sub>4</sub>
    (re.compile(r"\bSO4\b"), "SO<sub>4</sub>", "chemical"),
    # NH4 → NH<sub>4</sub>
    (re.compile(r"\bNH4\b"), "NH<sub>4</sub>", "chemical"),
    # Ca2+ → Ca<sup>2+</sup>
    (re.compile(r"\bCa2\+"), "Ca<sup>2+</sup>", "chemical"),
    # Na+ → Na<sup>+</sup>
    (re.compile(r"\bNa\+"), "Na<sup>+</sup>", "chemical"),
    # K+ → K<sup>+</sup>
    (re.compile(r"(?<![A-Za-z])K\+"), "K<sup>+</sup>", "chemical"),
    # Fe2+ / Fe3+
    (re.compile(r"\bFe([23])\+"), r"Fe<sup>\1+</sup>", "chemical"),
]

# Dosing patterns with superscript
_DOSING_PATTERNS: list[tuple[re.Pattern, str, str]] = [
    # mg/m2 → mg/m<sup>2</sup>
    (re.compile(r"\bmg/m2\b"), "mg/m<sup>2</sup>", "dosing"),
    # mg/m² (already has Unicode superscript — preserve)
    (re.compile(r"\bmg/m\u00b2\b"), "mg/m<sup>2</sup>", "dosing"),
    # cells/mm3 → cells/mm<sup>3</sup>
    (re.compile(r"\bcells?/mm3\b"), lambda m: m.group().replace("mm3", "mm<sup>3</sup>"), "dosing"),
    # 10^6 cells → 10<sup>6</sup> cells
    (re.compile(r"\b10\^?(\d+)\s*cells?\b"), r"10<sup>\1</sup> cells", "dosing"),
    # x10^9/L → x10<sup>9</sup>/L
    (re.compile(r"[x\u00d7]10\^?(\d+)/([A-Za-z]+)"), r"\u00d710<sup>\1</sup>/\2", "dosing"),
]

# Statistical patterns
_STAT_PATTERNS: list[tuple[re.Pattern, str]] = [
    # p < 0.05, p = 0.001, p-value
    (re.compile(r"\bp\s*[<>=]\s*0\.\d+"), "statistical"),
    # HR 0.67, OR 1.23, RR 0.89
    (re.compile(r"\b(?:HR|OR|RR)\s+\d+\.\d+"), "statistical"),
    # 95% CI: 0.45-0.99 or (95% CI, 0.45–0.99)
    (re.compile(r"\d+%\s*CI[:\s,]+\d+\.\d+[\s\u2013\-]+\d+\.\d+"), "statistical"),
    # chi-squared, chi2
    (re.compile(r"\bchi[\-\s]?(?:squared|2)\b", re.IGNORECASE), "statistical"),
    # R-squared, R2
    (re.compile(r"\bR[\-\s]?(?:squared|2)\b"), "statistical"),
]

# Pharmacokinetic patterns
_PK_PATTERNS: list[tuple[re.Pattern, str, str]] = [
    # AUC0-inf → AUC<sub>0-\u221e</sub>
    (re.compile(r"\bAUC\s*0?\s*[-\u2013]\s*(?:inf|infinity|\u221e)\b", re.IGNORECASE),
     "AUC<sub>0-\u221e</sub>", "pk"),
    # AUC0-t → AUC<sub>0-t</sub>
    (re.compile(r"\bAUC\s*0?\s*[-\u2013]\s*t\b", re.IGNORECASE),
     "AUC<sub>0-t</sub>", "pk"),
    # AUC0-24 → AUC<sub>0-24</sub>
    (re.compile(r"\bAUC\s*0?\s*[-\u2013]\s*(\d+)\b"),
     r"AUC<sub>0-\1</sub>", "pk"),
    # Cmax, Cmin, Css
    (re.compile(r"\bC(max|min|ss|trough|peak)\b"),
     r"C<sub>\1</sub>", "pk"),
    # t1/2 → t<sub>1/2</sub>
    (re.compile(r"\bt1/2\b"), "t<sub>1/2</sub>", "pk"),
    # Vd/F → V<sub>d</sub>/F
    (re.compile(r"\bVd/F\b"), "V<sub>d</sub>/F", "pk"),
    # CL/F
    (re.compile(r"\bCL/F\b"), "CL/F", "pk"),
    # tmax → t<sub>max</sub>
    (re.compile(r"\bt(max|lag)\b"), r"t<sub>\1</sub>", "pk"),
]

# Exponent patterns
_EXPONENT_PATTERNS: list[tuple[re.Pattern, str, str]] = [
    # mm2, cm2, m2 (area units)
    (re.compile(r"\b(mm|cm|m|km)2\b"), r"\1<sup>2</sup>", "mathematical"),
    # mm3, cm3 (volume units)
    (re.compile(r"\b(mm|cm|m)3\b"), r"\1<sup>3</sup>", "mathematical"),
    # 10^6, 10^9 etc (generic exponents)
    (re.compile(r"\b10\^(\d+)\b"), r"10<sup>\1</sup>", "mathematical"),
]


class FormulaDetector:
    """Detects and annotates formulas in pharma document text."""

    def detect(self, text: str) -> list[DetectedFormula]:
        """Detect all formulas in a text string."""
        formulas: list[DetectedFormula] = []

        # Chemical
        for pattern, replacement, ftype in _CHEMICAL_PATTERNS:
            for match in pattern.finditer(text):
                if callable(replacement):
                    html = replacement(match)
                else:
                    html = pattern.sub(replacement, match.group())
                formulas.append(DetectedFormula(
                    formula_type=ftype,
                    original_text=match.group(),
                    html_text=html,
                    start=match.start(),
                    end=match.end(),
                ))

        # Dosing
        for pattern, replacement, ftype in _DOSING_PATTERNS:
            for match in pattern.finditer(text):
                if callable(replacement):
                    html = replacement(match)
                else:
                    html = pattern.sub(replacement, match.group())
                formulas.append(DetectedFormula(
                    formula_type=ftype,
                    original_text=match.group(),
                    html_text=html,
                    start=match.start(),
                    end=match.end(),
                ))

        # Statistical (detect only, no HTML transformation needed)
        for pattern, ftype in _STAT_PATTERNS:
            for match in pattern.finditer(text):
                formulas.append(DetectedFormula(
                    formula_type=ftype,
                    original_text=match.group(),
                    html_text=match.group(),  # preserve as-is
                    start=match.start(),
                    end=match.end(),
                ))

        # PK
        for pattern, replacement, ftype in _PK_PATTERNS:
            for match in pattern.finditer(text):
                if callable(replacement):
                    html = replacement(match)
                else:
                    html = pattern.sub(replacement, match.group())
                formulas.append(DetectedFormula(
                    formula_type=ftype,
                    original_text=match.group(),
                    html_text=html,
                    start=match.start(),
                    end=match.end(),
                ))

        # Exponents
        for pattern, replacement, ftype in _EXPONENT_PATTERNS:
            for match in pattern.finditer(text):
                html = pattern.sub(replacement, match.group())
                formulas.append(DetectedFormula(
                    formula_type=ftype,
                    original_text=match.group(),
                    html_text=html,
                    start=match.start(),
                    end=match.end(),
                ))

        # Deduplicate overlapping detections (keep longest match)
        formulas.sort(key=lambda f: (f.start, -(f.end - f.start)))
        deduped: list[DetectedFormula] = []
        last_end = -1
        for f in formulas:
            if f.start >= last_end:
                deduped.append(f)
                last_end = f.end

        return deduped

    def annotate_html(self, text: str) -> str:
        """Replace formulas in text with HTML-annotated versions.

        Returns the text with chemical subscripts, dosing superscripts,
        and PK parameter subscripts properly tagged.
        """
        formulas = self.detect(text)
        if not formulas:
            return text

        # Apply replacements in reverse order to preserve positions
        result = text
        for f in reversed(formulas):
            if f.html_text != f.original_text:
                result = result[:f.start] + f.html_text + result[f.end:]

        return result

    def detect_in_document(
        self, pages: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Detect formulas across all pages of a document.

        Args:
            pages: List of {"page": int, "paragraphs": [{"text": str}]}

        Returns:
            List of {"page": int, "paragraph": int, "formulas": [DetectedFormula]}
        """
        results = []
        for page_data in pages:
            page_num = page_data.get("page", 0)
            for para_idx, para in enumerate(page_data.get("paragraphs", [])):
                text = para.get("text", "")
                formulas = self.detect(text)
                if formulas:
                    results.append({
                        "page": page_num,
                        "paragraph": para_idx,
                        "formulas": [
                            {
                                "type": f.formula_type,
                                "original": f.original_text,
                                "html": f.html_text,
                                "start": f.start,
                                "end": f.end,
                            }
                            for f in formulas
                        ],
                    })
        return results
