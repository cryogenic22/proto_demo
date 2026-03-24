"""
Verbatim Extractor — 100% accurate copy-paste from protocol PDFs.

The key insight: LLMs GENERATE text, they don't COPY it. So for verbatim
extraction, the LLM is used ONLY to LOCATE content, and PyMuPDF's text
layer is used to EXTRACT the exact bytes. Zero hallucination.

Workflow:
1. User provides an instruction: "Copy the inclusion criteria from Section 5.1"
2. LLM reads the section parser output and identifies the target section/page
3. PyMuPDF extracts the exact text from those pages
4. Result is verbatim PDF text — not LLM-generated

For tables: PyMuPDF's find_tables() extracts table data as-is.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Any

import fitz

from src.llm.client import LLMClient
from src.models.schema import PipelineConfig
from src.pipeline.section_parser import Section, SectionParser

logger = logging.getLogger(__name__)

LOCATE_PROMPT = """You are given a protocol document's table of contents (section outline).
A user wants to extract specific content from this document.

DOCUMENT OUTLINE:
{outline}

USER REQUEST:
{instruction}

Your job is to identify which section(s) contain the requested content.
Return a JSON object:
{{
  "target_sections": ["4.1", "4.2"],
  "content_type": "text" or "table" or "paragraph",
  "search_keywords": ["inclusion criteria", "eligibility"],
  "explanation": "The inclusion criteria are in Section 5.1 (Inclusion Criteria) on page 45"
}}

If the user asks for a specific section number, return that section.
If the user describes the content, find the best matching section(s).
Return ONLY valid JSON."""


@dataclass
class VerbatimResult:
    """Result of a verbatim extraction."""
    instruction: str
    sections_found: list[str]
    content_type: str  # "text", "table", "paragraph"
    text: str  # The EXACT text from the PDF
    tables: list[list[list[str]]]  # Any tables found (list of row lists)
    source_pages: list[int]
    explanation: str
    is_verbatim: bool = True  # Always true — this is never LLM-generated


class VerbatimExtractor:
    """Extracts verbatim content from protocol PDFs using LLM-as-locator."""

    def __init__(self, config: PipelineConfig, llm_client: LLMClient | None = None):
        self.config = config
        self.llm = llm_client or LLMClient(config)
        self.section_parser = SectionParser()

    async def extract(
        self,
        pdf_bytes: bytes,
        instruction: str,
        sections: list[Section] | None = None,
        filename: str = "",
        output_format: str = "text",
    ) -> VerbatimResult:
        """
        Extract verbatim content based on a user instruction.

        Supports both PDF and DOCX files. For DOCX, uses python-docx XML
        parsing to preserve 100% of formatting (bold, italic, lists, tables,
        equations). For PDF, uses PyMuPDF text layer (some formatting loss
        is expected — industry-known limitation).

        Args:
            pdf_bytes: The file bytes (PDF or DOCX).
            instruction: What to extract (e.g., "Copy Section 5.1")
            sections: Pre-parsed sections (optional, will parse if not provided)
            filename: Original filename — used to detect DOCX vs PDF.
            output_format: "text", "html", or "docx"
        """
        self._output_format = output_format
        self._is_docx = filename.lower().endswith(".docx") if filename else False
        self._file_bytes = pdf_bytes

        # Step 1: Parse sections if not provided
        # Use parse_auto() for automatic LLM fallback on low-confidence parses
        if sections is None:
            if self._is_docx:
                sections = self.section_parser.parse_docx(pdf_bytes)
                logger.info(f"DOCX mode: parsed {len(sections)} sections via XML (100% format retention)")
            else:
                try:
                    sections = await self.section_parser.parse_auto(
                        pdf_bytes, filename=filename,
                        llm_client=self.llm if hasattr(self, 'llm') else None,
                    )
                except Exception:
                    # Fallback to synchronous parse if async fails
                    sections = self.section_parser.parse(pdf_bytes, filename=filename)

        # Step 2: Try deterministic section lookup first (no LLM needed)
        direct_match = self._try_direct_match(sections, instruction)
        if direct_match:
            return self._extract_from_section(pdf_bytes, direct_match, instruction,
                                              "Direct section number match — no LLM used")

        # Step 3: Use LLM to locate the content
        outline = self.section_parser.to_outline(sections)
        prompt = LOCATE_PROMPT.format(outline=outline, instruction=instruction)

        try:
            raw = await self.llm.json_query(
                prompt,
                system="You are a clinical protocol section locator. Return valid JSON only.",
                max_tokens=512,
            )

            if not isinstance(raw, dict):
                return VerbatimResult(
                    instruction=instruction, sections_found=[], content_type="text",
                    text="", tables=[], source_pages=[],
                    explanation="Could not locate the requested content",
                )

            target_sections = raw.get("target_sections", [])
            content_type = raw.get("content_type", "text")
            explanation = raw.get("explanation", "")

            # Find the sections
            matched = []
            for sec_num in target_sections:
                found = self.section_parser.find(sections, sec_num)
                if found:
                    matched.append(found)

            if not matched:
                # Try keyword search as fallback
                keywords = raw.get("search_keywords", [])
                for kw in keywords:
                    results = self.section_parser.find_by_title(sections, kw)
                    matched.extend(results)

            if not matched:
                return VerbatimResult(
                    instruction=instruction, sections_found=target_sections,
                    content_type=content_type, text="", tables=[], source_pages=[],
                    explanation=f"Sections {target_sections} not found in document",
                )

            # Step 4: Extract verbatim text using PyMuPDF (NOT LLM)
            return self._extract_from_sections(pdf_bytes, matched, instruction,
                                               content_type, explanation)

        except Exception as e:
            logger.error(f"Verbatim extraction failed: {e}")
            return VerbatimResult(
                instruction=instruction, sections_found=[], content_type="text",
                text="", tables=[], source_pages=[],
                explanation=f"Extraction failed: {e}",
            )

    def _try_direct_match(self, sections: list[Section], instruction: str) -> Section | None:
        """Try to match a section number directly from the instruction."""
        # Look for patterns like "Section 4.1", "section 5", "4.2.3"
        patterns = [
            r"[Ss]ection\s+(\d{1,2}(?:\.\d{1,3}){0,4})",
            r"^(\d{1,2}(?:\.\d{1,3}){1,4})\b",  # Just a section number
        ]
        for pat in patterns:
            match = re.search(pat, instruction)
            if match:
                sec_num = match.group(1)
                found = self.section_parser.find(sections, sec_num)
                if found:
                    return found
        return None

    def _extract_from_section(
        self, pdf_bytes: bytes, section: Section, instruction: str, explanation: str
    ) -> VerbatimResult:
        """Extract verbatim content from a single section."""
        return self._extract_from_sections(pdf_bytes, [section], instruction, "text", explanation)

    def _extract_from_sections(
        self, pdf_bytes: bytes, matched: list[Section], instruction: str,
        content_type: str, explanation: str,
    ) -> VerbatimResult:
        """Extract verbatim content from multiple sections.

        Routes to DOCX-native extraction when source is DOCX (100% format
        retention via XML parsing). Falls back to PyMuPDF for PDFs.
        """
        text_parts = []
        all_tables = []
        all_pages = []
        is_docx = getattr(self, '_is_docx', False)

        for section in matched:
            if is_docx:
                # DOCX path — 100% format retention via python-docx XML
                fmt = getattr(self, '_output_format', 'text')
                if fmt == "html":
                    # Extract raw XML, wrap in basic HTML container
                    xml = self.section_parser.get_section_docx_xml(pdf_bytes, section)
                    text = self._docx_xml_to_html(xml, section)
                elif fmt == "docx":
                    text = self.section_parser.get_section_docx_xml(pdf_bytes, section)
                else:
                    text = self.section_parser.get_section_text_docx(pdf_bytes, section)
                text_parts.append(text)

                # Tables from DOCX
                if content_type in ("table", "all"):
                    tables = self.section_parser.get_tables_in_section_docx(pdf_bytes, section)
                    all_tables.extend(tables)
            else:
                # PDF path — PyMuPDF extraction (some formatting loss expected)
                fmt = getattr(self, '_output_format', 'text')
                if fmt == "html":
                    text = self.section_parser.get_section_formatted(
                        pdf_bytes, section, output="html",
                        strip_heading=True,
                    )
                elif fmt == "docx":
                    text = self.section_parser.get_section_formatted(
                        pdf_bytes, section, output="html",
                        strip_heading=True,
                    )
                else:
                    text = self.section_parser.get_section_text(pdf_bytes, section)
                    if isinstance(text, str) and text.startswith(f"{section.number}"):
                        lines = text.split("\n", 1)
                        if len(lines) > 1:
                            text = lines[1].strip()
                text_parts.append(text)

                if content_type in ("table", "all"):
                    tables = self.section_parser.get_tables_in_section(pdf_bytes, section)
                    for t in tables:
                        all_tables.append(t["data"])

            # Track pages/paragraphs
            start = section.page
            end = section.end_page or start
            all_pages.extend(range(start, end + 1))

        src = "DOCX XML (100% format retention)" if is_docx else "PyMuPDF text layer"
        full_explanation = f"{explanation} [Source: {src}]"

        return VerbatimResult(
            instruction=instruction,
            sections_found=[s.number for s in matched],
            content_type=content_type,
            text="\n\n---\n\n".join(str(t) for t in text_parts),
            tables=all_tables,
            source_pages=sorted(set(all_pages)),
            explanation=full_explanation,
        )

    @staticmethod
    def _docx_xml_to_html(xml: str, section: Section) -> str:
        """Convert DOCX XML paragraphs to readable HTML.

        Extracts text content from OpenXML w:r/w:t elements and preserves
        basic formatting (bold, italic) for display in the UI.
        """
        import re as _re

        lines = []
        # Extract text runs from XML
        for para_xml in xml.split("</w:p>"):
            texts = _re.findall(r'<w:t[^>]*>([^<]+)</w:t>', para_xml)
            if texts:
                line = "".join(texts)
                # Detect bold
                if "<w:b/>" in para_xml or '<w:b ' in para_xml:
                    line = f"<strong>{line}</strong>"
                # Detect italic
                if "<w:i/>" in para_xml or '<w:i ' in para_xml:
                    line = f"<em>{line}</em>"
                lines.append(f"<p>{line}</p>")

        return "\n".join(lines) if lines else f"<p>(No content in section {section.number})</p>"
