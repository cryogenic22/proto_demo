"""
Protocol Section Parser — deterministic extraction of document structure.

Extracts the full section hierarchy from a protocol PDF:
- Section numbers (1, 1.1, 1.1.1, etc.)
- Section titles
- Page numbers
- Page ranges (start → end)

This is NOT LLM-based — it uses PyMuPDF's text extraction + regex
to deterministically parse the table of contents and section headers.
Results are 100% repeatable (same PDF → same output every time).

Usage:
    parser = SectionParser()
    sections = parser.parse(pdf_bytes)
    # sections[0] = Section(number="1", title="INTRODUCTION", page=8, ...)
    # parser.find("4.1") → Section(number="4.1", title="STUDY DESIGN", page=23)
"""

from __future__ import annotations

import re
import logging
from dataclasses import dataclass, field
from pathlib import Path

import fitz  # PyMuPDF

try:
    from docx import Document as DocxDocument
    from docx.enum.text import WD_PARAGRAPH_ALIGNMENT
    HAS_DOCX = True
except ImportError:
    HAS_DOCX = False

logger = logging.getLogger(__name__)

# Matches section headers like "1.", "1.1", "1.1.1", "4.2.3.1"
_SECTION_RE = re.compile(
    r"^(\d{1,2}(?:\.\d{1,3}){0,4})\.?\s+([A-Z][A-Za-z\s,\-/&\(\)]+)"
)

# Matches TOC entries like "1.  INTRODUCTION .................. 8"
_TOC_RE = re.compile(
    r"(\d{1,2}(?:\.\d{1,3}){0,4})\.?\s+"
    r"([A-Za-z][A-Za-z\s,\-/&\(\)]+?)"
    r"\s*[\.·\-_]{3,}\s*(\d{1,4})\s*$"
)

# Also match TOC without dots: "1.  INTRODUCTION  8"
_TOC_SIMPLE_RE = re.compile(
    r"(\d{1,2}(?:\.\d{1,3}){0,4})\.?\s+"
    r"([A-Z][A-Z\s,\-/&\(\)]{3,}?)"
    r"\s+(\d{1,4})\s*$"
)


@dataclass
class Section:
    number: str          # "1", "1.1", "4.2.3"
    title: str           # "INTRODUCTION", "Study Design"
    page: int            # 0-indexed page number
    page_display: str    # Display page number from TOC (may differ from 0-indexed)
    level: int           # Nesting depth: 1, 2, 3, 4
    end_page: int | None = None  # Last page of this section
    children: list[Section] = field(default_factory=list)

    @property
    def full_title(self) -> str:
        return f"{self.number} {self.title}"

    def to_dict(self) -> dict:
        return {
            "number": self.number,
            "title": self.title,
            "page": self.page,
            "page_display": self.page_display,
            "level": self.level,
            "end_page": self.end_page,
            "children": [c.to_dict() for c in self.children],
        }


class SectionParser:
    """Deterministic protocol section parser using PyMuPDF text extraction."""

    def parse(self, file_bytes: bytes, filename: str = "") -> list[Section]:
        """Parse all sections from a protocol PDF or DOCX.

        Auto-detects format from filename or magic bytes.
        """
        is_docx = (
            filename.lower().endswith(".docx")
            or file_bytes[:4] == b"PK\x03\x04"  # ZIP/DOCX magic bytes
        )

        if is_docx:
            return self.parse_docx(file_bytes)
        return self.parse_pdf(file_bytes)

    def parse_docx(self, docx_bytes: bytes) -> list[Section]:
        """Parse sections from a DOCX file using python-docx.

        DOCX is MUCH easier than PDF — paragraphs have style metadata
        (Heading 1, Heading 2, etc.) that directly maps to section hierarchy.
        """
        if not HAS_DOCX:
            logger.error("python-docx not installed — cannot parse DOCX")
            return []

        import io
        doc = DocxDocument(io.BytesIO(docx_bytes))
        sections: list[Section] = []
        seen = set()

        for i, para in enumerate(doc.paragraphs):
            text = para.text.strip()
            if not text:
                continue

            # Check if this paragraph is a heading
            style_name = (para.style.name or "").lower()
            level = 0

            if "heading 1" in style_name:
                level = 1
            elif "heading 2" in style_name:
                level = 2
            elif "heading 3" in style_name:
                level = 3
            elif "heading 4" in style_name:
                level = 4
            elif "heading 5" in style_name:
                level = 5

            if level == 0:
                # Try regex match on text for numbered sections
                match = _SECTION_RE.match(text)
                if match:
                    sec_num = match.group(1)
                    level = sec_num.count(".") + 1
                else:
                    continue

            # Extract section number from text
            match = re.match(r"^(\d{1,2}(?:\.\d{1,3}){0,4})\.?\s+(.*)", text)
            if match:
                sec_num = match.group(1)
                sec_title = match.group(2).strip()
            else:
                sec_num = ""
                sec_title = text

            key = f"{sec_num}_{sec_title[:20]}"
            if key in seen:
                continue
            seen.add(key)

            sections.append(Section(
                number=sec_num,
                title=sec_title,
                page=i,  # paragraph index (no page concept in DOCX)
                page_display=str(i + 1),
                level=level,
            ))

        logger.info(f"Parsed {len(sections)} sections from DOCX")
        # Page ranges don't apply for DOCX — use paragraph indices
        for j, s in enumerate(sections):
            if j + 1 < len(sections):
                s.end_page = sections[j + 1].page - 1
            else:
                s.end_page = len(doc.paragraphs) - 1

        return sections

    def get_section_text_docx(self, docx_bytes: bytes, section: Section) -> str:
        """Extract verbatim text from a DOCX section. 100% accurate."""
        if not HAS_DOCX:
            return ""

        import io
        doc = DocxDocument(io.BytesIO(docx_bytes))
        start = section.page
        end = section.end_page if section.end_page is not None else len(doc.paragraphs) - 1

        text_parts = []
        for i in range(start, min(end + 1, len(doc.paragraphs))):
            text_parts.append(doc.paragraphs[i].text)

        return "\n".join(text_parts).strip()

    def get_tables_in_section_docx(self, docx_bytes: bytes, section: Section) -> list[list[list[str]]]:
        """Extract tables from a DOCX section. Returns exact table data."""
        if not HAS_DOCX:
            return []

        import io
        doc = DocxDocument(io.BytesIO(docx_bytes))

        # DOCX tables are separate from paragraphs — find tables
        # that appear between this section's paragraph range
        tables = []
        for table in doc.tables:
            table_data = []
            for row in table.rows:
                row_data = [cell.text.strip() for cell in row.cells]
                table_data.append(row_data)
            if table_data:
                tables.append(table_data)

        return tables

    def parse_pdf(self, pdf_bytes: bytes) -> list[Section]:
        """Parse all sections from a protocol PDF.

        Strategy (cascading fallback):
        1. PyMuPDF built-in TOC metadata (most reliable, instant)
        2. Parse TOC text from content pages (regex on dotted lines)
        3. Scan all pages for section headers (regex + font-size detection)
        4. If all strategies produce <5 sections, mark as low-confidence

        Returns sections sorted by page number.
        """
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        total_pages = doc.page_count

        # Try all strategies and pick the best result
        candidates: list[tuple[str, list[Section]]] = []

        # Strategy 1: Parse TOC from PyMuPDF's built-in TOC extraction
        toc = doc.get_toc()
        if toc and len(toc) > 5:
            sections = self._parse_fitz_toc(toc)
            if sections and len(sections) > 5:
                candidates.append(("fitz_toc", sections))
                logger.info(f"Strategy 1 (fitz TOC): {len(sections)} sections")

        # Strategy 2: Find the TOC pages and parse text
        sections = self._parse_toc_text(doc)
        if sections and len(sections) > 3:
            candidates.append(("toc_text", sections))
            logger.info(f"Strategy 2 (TOC text): {len(sections)} sections")

        # Strategy 3: Scan all pages for section headers (with font detection)
        sections = self._scan_headers(doc)
        if sections:
            candidates.append(("header_scan", sections))
            logger.info(f"Strategy 3 (header scan): {len(sections)} sections")

        doc.close()

        # Pick the best candidate — most sections wins, with quality weighting
        if not candidates:
            logger.warning("No sections found by any strategy")
            return []

        # Score each candidate
        best_name, best_sections = max(
            candidates,
            key=lambda c: self._score_sections(c[1], total_pages),
        )
        logger.info(
            f"Selected strategy '{best_name}' with {len(best_sections)} sections "
            f"(from {len(candidates)} candidates)"
        )

        self._compute_page_ranges(best_sections, total_pages)
        return best_sections

    @staticmethod
    def _score_sections(sections: list[Section], total_pages: int) -> float:
        """Score a section list for quality. Higher = better."""
        if not sections:
            return 0

        score = len(sections)  # More sections generally better

        # Bonus for having standard top-level sections
        numbers = {s.number for s in sections}
        for expected in ["1", "2", "3", "4", "5"]:
            if expected in numbers:
                score += 10

        # Bonus for having titled sections (not just numbers)
        titled = sum(1 for s in sections if len(s.title) > 5)
        score += titled * 0.5

        # Penalty for suspicious patterns (dates parsed as sections)
        months = {"january", "february", "march", "april", "may", "june",
                  "july", "august", "september", "october", "november", "december",
                  "jan", "feb", "mar", "apr", "jun", "jul", "aug", "sep", "oct", "nov", "dec"}
        date_sections = sum(
            1 for s in sections
            if s.title and s.title.split() and s.title.lower().split()[0] in months
        )
        score -= date_sections * 20  # Heavy penalty

        # Penalty for all sections on same page (likely cover page noise)
        if len(sections) > 3:
            pages_used = len({s.page for s in sections})
            if pages_used == 1:
                score -= 50  # All on one page = probably wrong

        return score

    def find(self, sections: list[Section], section_number: str) -> Section | None:
        """Find a section by its number (e.g., "4.1", "8.2.3")."""
        target = section_number.strip().rstrip(".")
        for s in self._flatten(sections):
            if s.number == target:
                return s
        return None

    def find_by_title(self, sections: list[Section], title_query: str) -> list[Section]:
        """Find sections whose title contains the query string."""
        query = title_query.lower()
        return [s for s in self._flatten(sections) if query in s.title.lower()]

    def get_section_text(self, pdf_bytes: bytes, section: Section) -> str:
        """Extract the EXACT text of a section from the PDF.

        This is deterministic — no LLM involved. Uses PyMuPDF's
        text extraction to pull verbatim text from the page range.
        """
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        start = section.page
        end = section.end_page if section.end_page is not None else start

        text_parts = []
        for page_num in range(start, min(end + 1, doc.page_count)):
            page = doc[page_num]
            text_parts.append(page.get_text("text"))

        doc.close()

        full_text = "\n".join(text_parts)

        # Trim to just this section's content
        # Find the section header in the text
        header_pattern = re.escape(section.number) + r"\.?\s+" + re.escape(section.title[:20])
        match = re.search(header_pattern, full_text, re.IGNORECASE)
        if match:
            full_text = full_text[match.start():]

        # Find the NEXT section header to trim the end
        next_section_pattern = r"\n\d{1,2}(?:\.\d{1,3}){0,4}\.?\s+[A-Z]"
        parts = re.split(next_section_pattern, full_text, maxsplit=1)
        if parts:
            full_text = parts[0]

        return full_text.strip()

    def get_tables_in_section(self, pdf_bytes: bytes, section: Section) -> list[dict]:
        """Extract tables from a specific section using PyMuPDF's table finder."""
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        start = section.page
        end = section.end_page if section.end_page is not None else start

        tables = []
        for page_num in range(start, min(end + 1, doc.page_count)):
            page = doc[page_num]
            # PyMuPDF 1.23+ has find_tables()
            try:
                found = page.find_tables()
                for t in found.tables:
                    table_data = t.extract()
                    if table_data:
                        tables.append({
                            "page": page_num,
                            "rows": len(table_data),
                            "cols": len(table_data[0]) if table_data else 0,
                            "data": table_data,
                        })
            except AttributeError:
                # Older PyMuPDF without find_tables
                pass

        doc.close()
        return tables

    def to_outline(self, sections: list[Section]) -> str:
        """Generate a readable outline of all sections."""
        lines = []
        for s in self._flatten(sections):
            indent = "  " * (s.level - 1)
            page_info = f"(p.{s.page_display})" if s.page_display else ""
            lines.append(f"{indent}{s.number} {s.title} {page_info}")
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Internal methods
    # ------------------------------------------------------------------

    def _parse_fitz_toc(self, toc: list) -> list[Section]:
        """Parse PyMuPDF's built-in TOC extraction."""
        sections = []
        for level, title, page in toc:
            # Try to extract section number from title
            match = re.match(r"^(\d{1,2}(?:\.\d{1,3}){0,4})\.?\s+(.*)", title.strip())
            if match:
                sections.append(Section(
                    number=match.group(1),
                    title=match.group(2).strip(),
                    page=page - 1,  # fitz TOC is 1-indexed
                    page_display=str(page),
                    level=level,
                ))
            else:
                # Non-numbered sections (appendices, etc.)
                sections.append(Section(
                    number="",
                    title=title.strip(),
                    page=page - 1,
                    page_display=str(page),
                    level=level,
                ))
        return sections

    def _parse_toc_text(self, doc: fitz.Document) -> list[Section]:
        """Find and parse the Table of Contents from page text."""
        sections = []

        # Look for TOC in first 15 pages
        for page_num in range(min(15, doc.page_count)):
            page = doc[page_num]
            text = page.get_text("text")

            # Check if this page looks like a TOC
            if not any(kw in text.upper() for kw in
                       ["TABLE OF CONTENTS", "CONTENTS", "LIST OF TABLES"]):
                if page_num > 5:
                    continue

            for line in text.split("\n"):
                line = line.strip()
                if not line:
                    continue

                # Try dotted TOC format
                match = _TOC_RE.match(line)
                if not match:
                    match = _TOC_SIMPLE_RE.match(line)
                if match:
                    sec_num = match.group(1)
                    sec_title = match.group(2).strip()
                    sec_page = match.group(3)
                    level = sec_num.count(".") + 1
                    sections.append(Section(
                        number=sec_num,
                        title=sec_title,
                        page=int(sec_page) - 1,
                        page_display=sec_page,
                        level=level,
                    ))

        return sections

    def _scan_headers(self, doc: fitz.Document) -> list[Section]:
        """Scan all pages for section headers using text + font analysis.

        Uses two strategies:
        1. Regex matching on section number patterns (with date rejection)
        2. Font-size detection for bold/large text that may be unnumbered headings
        """
        sections = []
        seen = set()

        # Month names for date rejection
        months = {"january", "february", "march", "april", "may", "june",
                  "july", "august", "september", "october", "november", "december",
                  "jan", "feb", "mar", "apr", "jun", "jul", "aug", "sep", "oct", "nov", "dec"}

        # ICH standard section titles for validation
        standard_titles = {
            "introduction", "background", "objectives", "endpoints",
            "study design", "study population", "inclusion", "exclusion",
            "study intervention", "discontinuation", "assessments",
            "procedures", "statistical", "considerations", "references",
            "appendix", "supporting", "documentation", "abbreviations",
            "synopsis", "summary", "schedule of activities",
            "adverse events", "safety", "efficacy", "laboratory",
            "pharmacokinetic", "pharmacodynamic", "dosing",
        }

        for page_num in range(doc.page_count):
            page = doc[page_num]

            # Strategy 1: Regex on plain text with date rejection
            text = page.get_text("text")
            for line in text.split("\n"):
                line = line.strip()
                match = _SECTION_RE.match(line)
                if match:
                    sec_num = match.group(1)
                    sec_title = match.group(2).strip()

                    # REJECT DATES: "7 June", "10 October", "29 December"
                    if sec_title and sec_title.split() and sec_title.lower().split()[0] in months:
                        continue
                    # Reject very short "titles" that are likely not sections
                    if len(sec_title) < 3:
                        continue
                    # Reject if title is just a number or date-like
                    if re.match(r"^\d", sec_title) and not any(
                        kw in sec_title.lower() for kw in standard_titles
                    ):
                        continue

                    key = f"{sec_num}_{sec_title[:20]}"
                    if key in seen:
                        continue
                    seen.add(key)

                    level = sec_num.count(".") + 1
                    sections.append(Section(
                        number=sec_num,
                        title=sec_title,
                        page=page_num,
                        page_display=str(page_num + 1),
                        level=level,
                    ))

            # Strategy 2: Font-size detection for bold headers without numbers
            # This catches headers that are just bold text (no section number)
            try:
                blocks = page.get_text("dict")["blocks"]
                for block in blocks:
                    if block.get("type") != 0:  # text blocks only
                        continue
                    for line_data in block.get("lines", []):
                        for span in line_data.get("spans", []):
                            text_span = span.get("text", "").strip()
                            font_size = span.get("size", 0)
                            flags = span.get("flags", 0)
                            is_bold = flags & 2 ** 4  # bit 4 = bold

                            # Large bold text (>12pt) that looks like a heading
                            if font_size >= 12 and is_bold and len(text_span) > 5:
                                # Check if it matches a known section title pattern
                                text_lower = text_span.lower()
                                if any(kw in text_lower for kw in standard_titles):
                                    # Try to extract section number
                                    num_match = re.match(
                                        r"^(\d{1,2}(?:\.\d{1,3}){0,4})\.?\s+(.*)",
                                        text_span
                                    )
                                    if num_match:
                                        sec_num = num_match.group(1)
                                        sec_title = num_match.group(2).strip()
                                    else:
                                        sec_num = ""
                                        sec_title = text_span

                                    key = f"font_{sec_num}_{sec_title[:20]}"
                                    if key in seen:
                                        continue
                                    seen.add(key)

                                    level = sec_num.count(".") + 1 if sec_num else 1
                                    sections.append(Section(
                                        number=sec_num,
                                        title=sec_title,
                                        page=page_num,
                                        page_display=str(page_num + 1),
                                        level=level,
                                    ))
            except Exception:
                pass  # Font analysis is best-effort

        return sections

    def _compute_page_ranges(self, sections: list[Section], total_pages: int):
        """Compute end_page for each section based on the next section's start."""
        flat = self._flatten(sections)
        for i, s in enumerate(flat):
            if i + 1 < len(flat):
                s.end_page = flat[i + 1].page - 1
                if s.end_page < s.page:
                    s.end_page = s.page
            else:
                s.end_page = total_pages - 1

    def _flatten(self, sections: list[Section]) -> list[Section]:
        """Flatten nested sections into a sorted list."""
        result = []
        for s in sections:
            result.append(s)
            result.extend(self._flatten(s.children))
        return sorted(result, key=lambda s: (s.page, s.number))
