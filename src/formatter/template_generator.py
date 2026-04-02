"""
Template-Guided Document Generator — applies a blueprint template's formatting
to the content extracted from a source PDF.

Uses FormattingExtractor to extract formatting specs from the template and
content from the source, then merges them into CKEditor-compatible HTML.
"""

from __future__ import annotations

import html as html_module
import logging
from collections import Counter
from dataclasses import dataclass, field
from typing import Any

from src.formatter.extractor import FormattingExtractor, FormattedDocument

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Template style profile
# ---------------------------------------------------------------------------

@dataclass
class TemplateStyleProfile:
    """Style profile extracted from a blueprint template."""
    body_font: str = "Arial"
    body_size: float = 10.0
    heading_fonts: dict[str, str] = field(default_factory=dict)   # heading1 -> font
    heading_sizes: dict[str, float] = field(default_factory=dict)  # heading1 -> size
    heading_colors: dict[str, str] = field(default_factory=dict)  # heading1 -> hex color
    heading_bold: dict[str, bool] = field(default_factory=dict)   # heading1 -> bold?
    margin_left: float = 72.0
    margin_right: float = 72.0
    margin_top: float = 72.0
    margin_bottom: float = 72.0
    line_spacing: float = 1.15
    paragraph_spacing: float = 6.0
    primary_color: str = "#000000"
    accent_color: str = "#000000"
    list_indent_px: int = 24

    def to_dict(self) -> dict[str, Any]:
        return {
            "body_font": self.body_font,
            "body_size": self.body_size,
            "heading_fonts": self.heading_fonts,
            "heading_sizes": self.heading_sizes,
            "heading_colors": self.heading_colors,
            "heading_bold": self.heading_bold,
            "margin_left": round(self.margin_left, 1),
            "margin_right": round(self.margin_right, 1),
            "margin_top": round(self.margin_top, 1),
            "margin_bottom": round(self.margin_bottom, 1),
            "line_spacing": round(self.line_spacing, 2),
            "paragraph_spacing": round(self.paragraph_spacing, 1),
            "primary_color": self.primary_color,
            "accent_color": self.accent_color,
            "list_indent_px": self.list_indent_px,
        }


# ---------------------------------------------------------------------------
# Template Conformer
# ---------------------------------------------------------------------------

class TemplateConformer:
    """Applies a template PDF's formatting to a source PDF's content."""

    def __init__(self) -> None:
        self.extractor = FormattingExtractor()

    # -- public API ----------------------------------------------------------

    def extract_style_profile(self, template_pdf: bytes) -> TemplateStyleProfile:
        """Extract formatting rules from a template PDF."""
        doc = self.extractor.extract(template_pdf, filename="template.pdf")
        return self._build_profile(doc)

    def conform(
        self, template_pdf: bytes, input_pdf: bytes,
    ) -> dict[str, Any]:
        """Generate a new document conforming input content to template format.

        Returns:
            dict with keys: html, style_profile, conformance_report
        """
        template_doc = self.extractor.extract(template_pdf, filename="template.pdf")
        input_doc = self.extractor.extract(input_pdf, filename="source.pdf")

        profile = self._build_profile(template_doc)
        styled_html = self._render_with_profile(input_doc, profile)
        report = self._build_conformance_report(template_doc, input_doc, profile)

        return {
            "html": styled_html,
            "style_profile": profile.to_dict(),
            "conformance_report": report,
        }

    # -- profile building ----------------------------------------------------

    def _build_profile(self, doc: FormattedDocument) -> TemplateStyleProfile:
        """Build a TemplateStyleProfile from a FormattedDocument."""
        profile = TemplateStyleProfile()

        # Collect per-style statistics
        body_fonts: Counter[str] = Counter()
        body_sizes: list[float] = []
        heading_fonts: dict[str, Counter[str]] = {}
        heading_sizes: dict[str, list[float]] = {}
        heading_colors_map: dict[str, Counter[str]] = {}
        heading_bold_counts: dict[str, Counter[bool]] = {}
        margins_left: list[float] = []
        margins_right: list[float] = []
        margins_top: list[float] = []
        margins_bottom: list[float] = []
        para_spacings: list[float] = []
        color_counts: Counter[str] = Counter()

        for page in doc.pages:
            margins_left.append(page.margin_left)
            margins_right.append(page.margin_right)
            margins_top.append(page.margin_top)
            margins_bottom.append(page.margin_bottom)

            for para in page.paragraphs:
                if para.spacing_before > 0:
                    para_spacings.append(para.spacing_before)

                for line in para.lines:
                    for span in line.spans:
                        if not span.text.strip():
                            continue

                        font_family = span.font_family
                        r, g, b = span.color_rgb
                        hex_color = f"#{r:02X}{g:02X}{b:02X}"

                        if para.style.startswith("heading"):
                            level = para.style  # e.g. heading1
                            if level not in heading_fonts:
                                heading_fonts[level] = Counter()
                                heading_sizes[level] = []
                                heading_colors_map[level] = Counter()
                                heading_bold_counts[level] = Counter()
                            heading_fonts[level][font_family] += 1
                            heading_sizes[level].append(span.size)
                            heading_colors_map[level][hex_color] += 1
                            heading_bold_counts[level][span.bold] += 1
                        else:
                            body_fonts[font_family] += 1
                            body_sizes.append(span.size)

                        color_counts[hex_color] += 1

        # Body font: most common
        if body_fonts:
            profile.body_font = body_fonts.most_common(1)[0][0]
        if body_sizes:
            # Use median body size
            sorted_sizes = sorted(body_sizes)
            profile.body_size = sorted_sizes[len(sorted_sizes) // 2]

        # Heading fonts/sizes
        for level in sorted(heading_fonts.keys()):
            profile.heading_fonts[level] = heading_fonts[level].most_common(1)[0][0]
            sizes = heading_sizes[level]
            profile.heading_sizes[level] = sorted(sizes)[len(sizes) // 2] if sizes else 14.0
            profile.heading_colors[level] = heading_colors_map[level].most_common(1)[0][0]
            if heading_bold_counts.get(level):
                profile.heading_bold[level] = heading_bold_counts[level].most_common(1)[0][0]

        # Margins (median)
        if margins_left:
            profile.margin_left = sorted(margins_left)[len(margins_left) // 2]
        if margins_right:
            profile.margin_right = sorted(margins_right)[len(margins_right) // 2]
        if margins_top:
            profile.margin_top = sorted(margins_top)[len(margins_top) // 2]
        if margins_bottom:
            profile.margin_bottom = sorted(margins_bottom)[len(margins_bottom) // 2]

        # Paragraph spacing (median)
        if para_spacings:
            sorted_sp = sorted(para_spacings)
            profile.paragraph_spacing = sorted_sp[len(sorted_sp) // 2]

        # Colors
        # Primary = most common; accent = second most common (if different from primary)
        if color_counts:
            ordered = color_counts.most_common(5)
            profile.primary_color = ordered[0][0]
            if len(ordered) > 1 and ordered[1][0] != profile.primary_color:
                profile.accent_color = ordered[1][0]
            else:
                profile.accent_color = profile.primary_color

        return profile

    # -- rendering -----------------------------------------------------------

    def _render_with_profile(
        self, input_doc: FormattedDocument, profile: TemplateStyleProfile,
    ) -> str:
        """Re-render the input document's content using the template's style profile."""
        html_parts: list[str] = []

        # Wrapper with page-level styles
        html_parts.append(
            f'<div style="'
            f"font-family:'{profile.body_font}',sans-serif;"
            f"font-size:{profile.body_size:.1f}pt;"
            f"color:{profile.primary_color};"
            f"line-height:{profile.line_spacing};"
            f"margin:{profile.margin_top:.0f}px {profile.margin_right:.0f}px "
            f"{profile.margin_bottom:.0f}px {profile.margin_left:.0f}px;"
            f'">'
        )

        for page in input_doc.pages:
            for para in page.paragraphs:
                text = self._extract_para_text(para)
                if not text.strip():
                    continue

                style = para.style
                tag, inline_style = self._style_for_paragraph(style, para, profile)

                # Spacing
                spacing_style = f"margin-bottom:{profile.paragraph_spacing:.0f}px;"
                if para.alignment and para.alignment != "left":
                    spacing_style += f"text-align:{para.alignment};"
                if para.indent_level:
                    spacing_style += f"margin-left:{para.indent_level * profile.list_indent_px}px;"

                full_style = f"{inline_style}{spacing_style}"
                style_attr = f' style="{full_style}"' if full_style else ""

                html_parts.append(f"<{tag}{style_attr}>{text}</{tag}>")

        html_parts.append("</div>")
        return "\n".join(html_parts)

    def _style_for_paragraph(
        self, style: str, para: Any, profile: TemplateStyleProfile,
    ) -> tuple[str, str]:
        """Return (html_tag, inline_css) for a paragraph style using the profile."""
        tag_map = {
            "heading1": "h1",
            "heading2": "h2",
            "heading3": "h3",
            "heading4": "h4",
            "list_bullet": "li",
            "list_number": "li",
        }
        tag = tag_map.get(style, "p")

        parts: list[str] = []

        if style.startswith("heading"):
            font = profile.heading_fonts.get(style, profile.body_font)
            size = profile.heading_sizes.get(style, profile.body_size + 4)
            color = profile.heading_colors.get(style, profile.primary_color)
            bold = profile.heading_bold.get(style, True)

            parts.append(f"font-family:'{font}',sans-serif")
            parts.append(f"font-size:{size:.1f}pt")
            parts.append(f"color:{color}")
            if bold:
                parts.append("font-weight:bold")
        else:
            # Body text inherits from the wrapper div
            pass

        return tag, ";".join(parts) + ";" if parts else ""

    def _extract_para_text(self, para: Any) -> str:
        """Extract HTML-escaped text from a paragraph, preserving inline formatting."""
        parts: list[str] = []

        for line in para.lines:
            for span in line.spans:
                text = html_module.escape(span.text)

                # Preserve inline formatting from source
                if span.bold:
                    text = f"<strong>{text}</strong>"
                if span.italic:
                    text = f"<em>{text}</em>"
                if span.underline:
                    text = f"<u>{text}</u>"
                if span.superscript:
                    text = f"<sup>{text}</sup>"
                if span.subscript:
                    text = f"<sub>{text}</sub>"

                parts.append(text)

        return "".join(parts)

    # -- conformance report --------------------------------------------------

    def _build_conformance_report(
        self,
        template_doc: FormattedDocument,
        input_doc: FormattedDocument,
        profile: TemplateStyleProfile,
    ) -> dict[str, Any]:
        """Build a conformance report describing what style rules were applied."""
        rules_applied: list[dict[str, str]] = []
        rules_skipped: list[dict[str, str]] = []

        # Body font
        rules_applied.append({
            "rule": "body_font",
            "description": f"Applied body font '{profile.body_font}' at {profile.body_size}pt",
        })

        # Heading styles
        for level in sorted(profile.heading_fonts.keys()):
            font = profile.heading_fonts[level]
            size = profile.heading_sizes.get(level, "?")
            color = profile.heading_colors.get(level, "?")
            rules_applied.append({
                "rule": f"{level}_style",
                "description": f"Applied {level}: '{font}' at {size}pt, color {color}",
            })

        # Margins
        rules_applied.append({
            "rule": "margins",
            "description": (
                f"Applied margins: "
                f"L={profile.margin_left:.0f} R={profile.margin_right:.0f} "
                f"T={profile.margin_top:.0f} B={profile.margin_bottom:.0f}"
            ),
        })

        # Spacing
        rules_applied.append({
            "rule": "paragraph_spacing",
            "description": f"Applied paragraph spacing: {profile.paragraph_spacing:.0f}px",
        })

        # Colors
        rules_applied.append({
            "rule": "primary_color",
            "description": f"Applied primary color: {profile.primary_color}",
        })

        # Input doc statistics
        input_paragraphs = sum(len(p.paragraphs) for p in input_doc.pages)
        input_pages = len(input_doc.pages)
        template_pages = len(template_doc.pages)

        return {
            "rules_applied": len(rules_applied),
            "rules_skipped": len(rules_skipped),
            "details": rules_applied,
            "skipped_details": rules_skipped,
            "source_stats": {
                "pages": input_pages,
                "paragraphs": input_paragraphs,
                "fonts_found": len(input_doc.font_inventory),
                "colors_found": len(input_doc.color_inventory),
            },
            "template_stats": {
                "pages": template_pages,
                "paragraphs": sum(len(p.paragraphs) for p in template_doc.pages),
                "fonts_found": len(template_doc.font_inventory),
                "colors_found": len(template_doc.color_inventory),
            },
        }
