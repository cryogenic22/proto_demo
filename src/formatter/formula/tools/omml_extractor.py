"""
OMML Equation Extractor — extracts Office MathML equations from DOCX XML elements.

DOCX files embed equations as OMML (Office Math Markup Language) inside paragraph
XML. This tool walks <m:oMath> elements and converts them to:
  - plain_text: human-readable string ("a/b", "x^2", "sqrt(x)")
  - LaTeX: canonical internal format (r"\\frac{a}{b}", "x^{2}", r"\\sqrt{x}")

OMML reference elements handled:
  m:r/m:t    — text runs (literal characters)
  m:f        — fractions (m:num / m:den)
  m:sSup     — superscript
  m:sSub     — subscript
  m:rad      — radical / sqrt
  m:nary     — n-ary operators (sum, integral, product)
  m:d        — delimiters (parentheses, brackets)
"""

from __future__ import annotations

import logging
from typing import Any

from lxml import etree

from src.formatter.formula.ir import (
    FormattedFormula,
    FormulaComplexity,
    FormulaSource,
    FormulaType,
)

logger = logging.getLogger(__name__)

# OMML namespace
_OMML_NS = "http://schemas.openxmlformats.org/officeDocument/2006/math"
_NS = {"m": _OMML_NS}


class OmmlExtractor:
    """Extracts OMML equations from DOCX paragraph XML elements."""

    OMML_NS = _OMML_NS

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def extract_from_element(self, element: Any) -> list[FormattedFormula]:
        """Find all oMath elements inside *element* and return FormattedFormulas.

        Parameters
        ----------
        element : lxml.etree._Element
            A DOCX paragraph (w:p) or body element that may contain <m:oMath>.

        Returns
        -------
        list[FormattedFormula]
            One FormattedFormula per <m:oMath> found.
        """
        results: list[FormattedFormula] = []
        try:
            omath_elements = element.findall(f".//{{{_OMML_NS}}}oMath")
            if not omath_elements:
                # Also try without namespace prefix in case namespace is default
                omath_elements = element.findall(".//oMath")
        except Exception as exc:
            logger.debug("Failed to search for oMath elements: %s", exc)
            return results

        for omath in omath_elements:
            try:
                plain = self.omml_to_plain_text(omath)
                latex = self.omml_to_latex(omath)

                # Determine complexity from structure
                complexity = self._classify_complexity(omath)

                formula = FormattedFormula(
                    latex=latex,
                    plain_text=plain,
                    omml=etree.tostring(omath, encoding="unicode"),
                    source=FormulaSource.OMML,
                    complexity=complexity,
                    formula_type=FormulaType.MATHEMATICAL,
                    confidence=0.95,
                )
                results.append(formula)
            except Exception as exc:
                logger.warning("Failed to convert oMath element: %s", exc)

        return results

    # ------------------------------------------------------------------
    # Plain-text conversion
    # ------------------------------------------------------------------

    def omml_to_plain_text(self, omath: Any) -> str:
        """Walk OMML XML tree and produce a human-readable plain-text string.

        Conversion rules:
          m:f         → "num/den"
          m:sSup      → "base^{exp}"
          m:sSub      → "base_{sub}"
          m:rad       → "sqrt(radicand)"
          m:nary      → "op_{lower}^{upper}(body)"  (e.g. "sum_{i=1}^{n}(x)")
          m:d         → "(content)"
          m:r/m:t     → literal text
        """
        try:
            return self._walk_plain(omath).strip()
        except Exception as exc:
            logger.debug("Plain text conversion failed: %s", exc)
            return self._fallback_text(omath)

    def _walk_plain(self, node: Any) -> str:
        """Recursively walk an OMML node and produce plain text."""
        tag = _local_name(node)

        # Fraction: m:f → num/den
        if tag == "f":
            num = self._get_child_plain(node, "num")
            den = self._get_child_plain(node, "den")
            return f"{num}/{den}"

        # Superscript: m:sSup → base^{exp}
        if tag == "sSup":
            base = self._get_child_plain(node, "e")
            exp = self._get_child_plain(node, "sup")
            return f"{base}^{exp}"

        # Subscript: m:sSub → base_{sub}
        if tag == "sSub":
            base = self._get_child_plain(node, "e")
            sub = self._get_child_plain(node, "sub")
            return f"{base}_{sub}"

        # Radical: m:rad → sqrt(radicand)
        if tag == "rad":
            # m:deg may contain the degree (e.g. cube root)
            deg = self._get_child_plain(node, "deg")
            radicand = self._get_child_plain(node, "e")
            if deg:
                return f"root({deg}, {radicand})"
            return f"sqrt({radicand})"

        # N-ary: m:nary → sum/int/prod with limits
        if tag == "nary":
            operator = self._get_nary_char(node)
            lower = self._get_child_plain(node, "sub")
            upper = self._get_child_plain(node, "sup")
            body = self._get_child_plain(node, "e")
            parts = [operator]
            if lower:
                parts.append(f"_{lower}")
            if upper:
                parts.append(f"^{upper}")
            if body:
                parts.append(f"({body})")
            return "".join(parts)

        # Delimiter: m:d → (content)
        if tag == "d":
            beg_chr, end_chr = self._get_delimiter_chars(node)
            inner = self._collect_children_plain(node, "e")
            return f"{beg_chr}{inner}{end_chr}"

        # Text run: m:r → extract m:t text
        if tag == "r":
            return self._get_text_content(node)

        # Text node: m:t
        if tag == "t":
            return node.text or ""

        # For everything else (including oMath root), walk children
        parts = []
        for child in node:
            parts.append(self._walk_plain(child))
        return "".join(parts)

    def _get_child_plain(self, node: Any, child_local: str) -> str:
        """Get plain text of a specific child element by local name."""
        child = node.find(f"{{{_OMML_NS}}}{child_local}")
        if child is None:
            # Fallback: try without namespace
            child = node.find(child_local)
        if child is None:
            return ""
        return self._walk_plain(child).strip()

    def _collect_children_plain(self, node: Any, child_local: str) -> str:
        """Collect plain text from all children with a given local name."""
        parts = []
        for child in node:
            if _local_name(child) == child_local:
                parts.append(self._walk_plain(child).strip())
        # If no specific children found, walk all children
        if not parts:
            for child in node:
                if _local_name(child) not in ("dPr",):
                    parts.append(self._walk_plain(child).strip())
        return ", ".join(parts) if len(parts) > 1 else "".join(parts)

    # ------------------------------------------------------------------
    # LaTeX conversion
    # ------------------------------------------------------------------

    def omml_to_latex(self, omath: Any) -> str:
        r"""Walk OMML XML tree and produce a LaTeX string.

        Conversion rules:
          m:f         → \frac{num}{den}
          m:sSup      → base^{exp}
          m:sSub      → base_{sub}
          m:rad       → \sqrt{radicand} or \sqrt[deg]{radicand}
          m:nary      → \sum_{lower}^{upper} body  (or \int, \prod)
          m:d         → \left( content \right)
          m:r/m:t     → literal text
        """
        try:
            return self._walk_latex(omath).strip()
        except Exception as exc:
            logger.debug("LaTeX conversion failed: %s", exc)
            return self._fallback_text(omath)

    def _walk_latex(self, node: Any) -> str:
        """Recursively walk an OMML node and produce LaTeX."""
        tag = _local_name(node)

        # Fraction
        if tag == "f":
            num = self._get_child_latex(node, "num")
            den = self._get_child_latex(node, "den")
            return f"\\frac{{{num}}}{{{den}}}"

        # Superscript
        if tag == "sSup":
            base = self._get_child_latex(node, "e")
            exp = self._get_child_latex(node, "sup")
            return f"{base}^{{{exp}}}"

        # Subscript
        if tag == "sSub":
            base = self._get_child_latex(node, "e")
            sub = self._get_child_latex(node, "sub")
            return f"{base}_{{{sub}}}"

        # Radical
        if tag == "rad":
            deg = self._get_child_latex(node, "deg")
            radicand = self._get_child_latex(node, "e")
            if deg:
                return f"\\sqrt[{deg}]{{{radicand}}}"
            return f"\\sqrt{{{radicand}}}"

        # N-ary operator
        if tag == "nary":
            operator = self._get_nary_char(node)
            latex_op = _NARY_LATEX_MAP.get(operator, operator)
            lower = self._get_child_latex(node, "sub")
            upper = self._get_child_latex(node, "sup")
            body = self._get_child_latex(node, "e")
            parts = [latex_op]
            if lower:
                parts.append(f"_{{{lower}}}")
            if upper:
                parts.append(f"^{{{upper}}}")
            if body:
                parts.append(f" {body}")
            return "".join(parts)

        # Delimiter
        if tag == "d":
            beg_chr, end_chr = self._get_delimiter_chars(node)
            beg_latex = _DELIM_LATEX_MAP.get(beg_chr, beg_chr)
            end_latex = _DELIM_LATEX_MAP.get(end_chr, end_chr)
            inner = self._collect_children_latex(node, "e")
            return f"\\left{beg_latex}{inner}\\right{end_latex}"

        # Text run
        if tag == "r":
            return self._get_text_content(node)

        # Text node
        if tag == "t":
            return node.text or ""

        # Default: walk children
        parts = []
        for child in node:
            parts.append(self._walk_latex(child))
        return "".join(parts)

    def _get_child_latex(self, node: Any, child_local: str) -> str:
        """Get LaTeX of a specific child element by local name."""
        child = node.find(f"{{{_OMML_NS}}}{child_local}")
        if child is None:
            child = node.find(child_local)
        if child is None:
            return ""
        return self._walk_latex(child).strip()

    def _collect_children_latex(self, node: Any, child_local: str) -> str:
        """Collect LaTeX from all children with a given local name."""
        parts = []
        for child in node:
            if _local_name(child) == child_local:
                parts.append(self._walk_latex(child).strip())
        if not parts:
            for child in node:
                if _local_name(child) not in ("dPr",):
                    parts.append(self._walk_latex(child).strip())
        return ", ".join(parts) if len(parts) > 1 else "".join(parts)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _get_text_content(self, run_node: Any) -> str:
        """Extract text from an m:r element (looks for m:t children)."""
        parts = []
        for child in run_node:
            if _local_name(child) == "t":
                parts.append(child.text or "")
        return "".join(parts)

    def _get_nary_char(self, nary_node: Any) -> str:
        """Get the operator character from an m:nary properties element.

        Looks for <m:naryPr><m:chr m:val="..."/></m:naryPr>.
        Defaults to summation if not specified.
        """
        pr = nary_node.find(f"{{{_OMML_NS}}}naryPr")
        if pr is not None:
            chr_elem = pr.find(f"{{{_OMML_NS}}}chr")
            if chr_elem is not None:
                val = chr_elem.get(f"{{{_OMML_NS}}}val")
                if val is None:
                    # Try without namespace on attribute
                    val = chr_elem.get("val")
                if val:
                    return val
        # Default: summation
        return "\u2211"

    def _get_delimiter_chars(self, d_node: Any) -> tuple[str, str]:
        """Get opening and closing delimiter characters from m:d properties.

        Looks for <m:dPr><m:begChr m:val="..."/><m:endChr m:val="..."/></m:dPr>.
        Defaults to parentheses.
        """
        beg = "("
        end = ")"
        pr = d_node.find(f"{{{_OMML_NS}}}dPr")
        if pr is not None:
            beg_elem = pr.find(f"{{{_OMML_NS}}}begChr")
            if beg_elem is not None:
                val = beg_elem.get(f"{{{_OMML_NS}}}val") or beg_elem.get("val")
                if val is not None:
                    beg = val
            end_elem = pr.find(f"{{{_OMML_NS}}}endChr")
            if end_elem is not None:
                val = end_elem.get(f"{{{_OMML_NS}}}val") or end_elem.get("val")
                if val is not None:
                    end = val
        return beg, end

    def _classify_complexity(self, omath: Any) -> FormulaComplexity:
        """Classify the complexity tier of an oMath element."""
        # Structured if it contains fractions, radicals, or n-ary operators
        structured_tags = ("f", "rad", "nary")
        for tag in structured_tags:
            if omath.findall(f".//{{{_OMML_NS}}}{tag}"):
                return FormulaComplexity.STRUCTURED
        # Otherwise inline (sub/sup only)
        return FormulaComplexity.INLINE

    def _fallback_text(self, node: Any) -> str:
        """Last-resort: extract all text content from an element."""
        try:
            return "".join(node.itertext()).strip()
        except Exception:
            return ""


# ---------------------------------------------------------------------------
# Module-level helpers
# ---------------------------------------------------------------------------

def _local_name(node: Any) -> str:
    """Get the local tag name, stripping any namespace."""
    tag = node.tag if isinstance(node.tag, str) else ""
    if "}" in tag:
        return tag.split("}", 1)[1]
    return tag


# Mapping from Unicode n-ary characters to LaTeX commands
_NARY_LATEX_MAP: dict[str, str] = {
    "\u2211": "\\sum",       # ∑
    "\u220F": "\\prod",      # ∏
    "\u222B": "\\int",       # ∫
    "\u222C": "\\iint",      # ∬
    "\u222D": "\\iiint",     # ∭
    "\u2210": "\\coprod",    # ∐
    "\u22C0": "\\bigwedge",  # ⋀
    "\u22C1": "\\bigvee",    # ⋁
    "\u22C2": "\\bigcap",    # ⋂
    "\u22C3": "\\bigcup",    # ⋃
}

# Mapping from delimiter chars to LaTeX
_DELIM_LATEX_MAP: dict[str, str] = {
    "(": "(",
    ")": ")",
    "[": "[",
    "]": "]",
    "{": "\\{",
    "}": "\\}",
    "|": "|",
    "\u2016": "\\|",  # ‖ double vertical
}
