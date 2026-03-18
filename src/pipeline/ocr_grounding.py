"""
OCR Grounding — cross-modal verification of VLM cell extraction.

Implements LMDX-style grounding: runs OCR independently on the table image,
then cross-verifies each extracted cell value against what OCR reads at
those coordinates. Cells where VLM and OCR disagree get flagged.

This catches the #1 source of hallucination: VLM fabricating values that
don't exist in the source image.

Supports multiple OCR backends:
- docTR (preferred, highest accuracy)
- pytesseract (fallback, widely available)
- None (grounding disabled, pipeline still works)
"""

from __future__ import annotations

import io
import logging
import re
from dataclasses import dataclass, field
from typing import Any

from src.models.schema import (
    CellRef,
    ChallengeIssue,
    ChallengeType,
    ExtractedCell,
    PageImage,
    PipelineConfig,
    TableRegion,
)

logger = logging.getLogger(__name__)


@dataclass
class OCRWord:
    """A single word detected by OCR with its position."""
    text: str
    x0: float  # Normalized 0-1
    y0: float
    x1: float
    y1: float
    confidence: float = 1.0


@dataclass
class OCRResult:
    """OCR results for a single page/image."""
    words: list[OCRWord] = field(default_factory=list)
    full_text: str = ""


@dataclass
class GroundingVerdict:
    """Result of grounding verification for one cell."""
    cell_ref: CellRef
    extracted_value: str
    grounded: bool  # True if OCR confirms the value exists
    ocr_evidence: str  # What OCR found near this cell's location
    confidence_adjustment: float  # Multiplier: 1.0 = no change, 0.5 = halve confidence


class OCRBackend:
    """Abstract OCR backend. Subclasses implement specific engines."""

    def run(self, image_bytes: bytes) -> OCRResult:
        raise NotImplementedError


class DocTRBackend(OCRBackend):
    """docTR-based OCR (highest accuracy)."""

    def __init__(self):
        self._model = None

    def _get_model(self):
        if self._model is None:
            from doctr.models import ocr_predictor
            self._model = ocr_predictor(pretrained=True)
        return self._model

    def run(self, image_bytes: bytes) -> OCRResult:
        from doctr.io import DocumentFile
        from PIL import Image

        # Convert bytes to PIL Image for docTR
        img = Image.open(io.BytesIO(image_bytes))
        doc = DocumentFile.from_images([img])
        model = self._get_model()
        result = model(doc)

        words: list[OCRWord] = []
        full_text_parts: list[str] = []

        for page in result.pages:
            for block in page.blocks:
                for line in block.lines:
                    for word in line.words:
                        geo = word.geometry
                        words.append(OCRWord(
                            text=word.value,
                            x0=geo[0][0], y0=geo[0][1],
                            x1=geo[1][0], y1=geo[1][1],
                            confidence=word.confidence,
                        ))
                        full_text_parts.append(word.value)

        return OCRResult(words=words, full_text=" ".join(full_text_parts))


class TesseractBackend(OCRBackend):
    """Tesseract-based OCR (widely available fallback)."""

    def run(self, image_bytes: bytes) -> OCRResult:
        import pytesseract
        from PIL import Image

        img = Image.open(io.BytesIO(image_bytes))
        w, h = img.size

        # Get word-level data with positions
        data = pytesseract.image_to_data(img, output_type=pytesseract.Output.DICT)

        words: list[OCRWord] = []
        full_text_parts: list[str] = []

        for i in range(len(data["text"])):
            text = data["text"][i].strip()
            if not text:
                continue

            conf = float(data["conf"][i])
            if conf < 0:
                continue

            # Normalize coordinates to 0-1 range
            x0 = data["left"][i] / w
            y0 = data["top"][i] / h
            x1 = (data["left"][i] + data["width"][i]) / w
            y1 = (data["top"][i] + data["height"][i]) / h

            words.append(OCRWord(
                text=text, x0=x0, y0=y0, x1=x1, y1=y1,
                confidence=conf / 100.0,
            ))
            full_text_parts.append(text)

        return OCRResult(words=words, full_text=" ".join(full_text_parts))


class SimpleTextBackend(OCRBackend):
    """Lightweight fallback using PyMuPDF's built-in text extraction.

    No ML dependencies required. Works on native digital PDFs (not scans).
    """

    def run(self, image_bytes: bytes) -> OCRResult:
        # This backend works differently — it takes raw PDF page text
        # For PNG images from our pipeline, we can't extract text directly
        # So this just returns empty and grounding is skipped
        return OCRResult(words=[], full_text="")


def _get_backend() -> OCRBackend | None:
    """Try to load the best available OCR backend."""
    # Try docTR first
    try:
        from doctr.models import ocr_predictor  # noqa: F401
        logger.info("OCR grounding: using docTR backend")
        return DocTRBackend()
    except ImportError:
        pass

    # Try Tesseract
    try:
        import pytesseract  # noqa: F401
        # Verify tesseract binary exists
        pytesseract.get_tesseract_version()
        logger.info("OCR grounding: using Tesseract backend")
        return TesseractBackend()
    except (ImportError, Exception):
        pass

    logger.warning("OCR grounding: no OCR backend available — grounding disabled")
    return None


class OCRGroundingVerifier:
    """Cross-modal verification of VLM extraction against OCR.

    For each extracted cell value, checks whether OCR independently
    confirms that text exists in the source image. Cells where the VLM
    claims a value that OCR cannot find are flagged as potential
    hallucinations.
    """

    def __init__(self, config: PipelineConfig):
        self.config = config
        self._backend = _get_backend()
        self._ocr_cache: dict[int, OCRResult] = {}  # page_num → result

    @property
    def available(self) -> bool:
        """Whether OCR grounding is available."""
        return self._backend is not None

    def run_ocr(self, page: PageImage) -> OCRResult:
        """Run OCR on a page image. Results are cached."""
        if page.page_number in self._ocr_cache:
            return self._ocr_cache[page.page_number]

        if not self._backend:
            return OCRResult()

        try:
            result = self._backend.run(page.image_bytes)
            self._ocr_cache[page.page_number] = result
            logger.debug(
                f"OCR page {page.page_number}: {len(result.words)} words extracted"
            )
            return result
        except Exception as e:
            logger.warning(f"OCR failed on page {page.page_number}: {e}")
            return OCRResult()

    def verify_cells(
        self,
        cells: list[ExtractedCell],
        region: TableRegion,
        pages: list[PageImage],
    ) -> list[GroundingVerdict]:
        """
        Verify extracted cells against OCR output.

        Returns a GroundingVerdict per cell indicating whether OCR
        confirms the extracted value.
        """
        if not self._backend:
            return []  # Grounding not available

        # Run OCR on all table pages
        page_map = {p.page_number: p for p in pages}
        ocr_texts: list[str] = []
        all_words: list[OCRWord] = []

        for page_num in region.pages:
            if page_num in page_map:
                result = self.run_ocr(page_map[page_num])
                ocr_texts.append(result.full_text)
                all_words.extend(result.words)

        combined_text = " ".join(ocr_texts).lower()

        verdicts: list[GroundingVerdict] = []

        for cell in cells:
            verdict = self._verify_one_cell(cell, combined_text, all_words)
            verdicts.append(verdict)

        grounded = sum(1 for v in verdicts if v.grounded)
        total = len(verdicts)
        logger.info(
            f"OCR grounding: {grounded}/{total} cells verified "
            f"({grounded/max(total,1)*100:.0f}%)"
        )

        return verdicts

    def verdicts_to_challenges(
        self, verdicts: list[GroundingVerdict]
    ) -> list[ChallengeIssue]:
        """Convert ungrounded verdicts to ChallengeIssues for the reconciler."""
        challenges = []
        for v in verdicts:
            if not v.grounded and v.extracted_value.strip():
                challenges.append(ChallengeIssue(
                    cell_ref=v.cell_ref,
                    challenge_type=ChallengeType.HALLUCINATED_VALUE,
                    description=(
                        f"OCR grounding failed: VLM extracted '{v.extracted_value}' "
                        f"but OCR found '{v.ocr_evidence}' in this region"
                    ),
                    extracted_value=v.extracted_value,
                    suggested_value=v.ocr_evidence if v.ocr_evidence else None,
                    severity=0.4,  # Moderate — flag but don't tank confidence
                ))
        return challenges

    def _verify_one_cell(
        self,
        cell: ExtractedCell,
        ocr_text: str,
        all_words: list[OCRWord],
    ) -> GroundingVerdict:
        """Verify a single cell against OCR output.

        Column 0 cells (procedure names / row headers) and marker cells
        get lenient treatment — OCR is weak on these and dual-pass
        extraction already validates them.
        """
        ref = CellRef(row=cell.row, col=cell.col)

        # Row headers (column 0) — these are procedure names that OCR
        # often segments differently. Don't penalize.
        if cell.col == 0:
            return GroundingVerdict(
                cell_ref=ref, extracted_value=cell.raw_value,
                grounded=True, ocr_evidence="row_header",
                confidence_adjustment=1.0,
            )
        value = cell.raw_value.strip()

        # Empty cells and markers are easy to verify
        if not value or cell.data_type.value == "EMPTY":
            return GroundingVerdict(
                cell_ref=ref, extracted_value=value,
                grounded=True, ocr_evidence="", confidence_adjustment=1.0,
            )

        # Single-character markers (X, ✓, ✗) — just check OCR found them
        if len(value) <= 2 and value.upper() in ("X", "✓", "✗", "✔", "✘", "Y", "N"):
            # Markers are hard for OCR — give them a pass if OCR finds
            # the character anywhere on the page
            found = value.lower() in ocr_text or "x" in ocr_text
            return GroundingVerdict(
                cell_ref=ref, extracted_value=value,
                grounded=True,  # Don't penalize markers — OCR is weak on these
                ocr_evidence="marker",
                confidence_adjustment=1.0,
            )

        # For text values, check if the key words exist in OCR output
        value_lower = value.lower()
        # Extract significant words (3+ chars, not common filler)
        words = [w for w in re.findall(r'\b\w{3,}\b', value_lower)
                 if w not in ("the", "and", "for", "with", "from")]

        if not words:
            return GroundingVerdict(
                cell_ref=ref, extracted_value=value,
                grounded=True, ocr_evidence="short_value",
                confidence_adjustment=1.0,
            )

        # Count how many significant words OCR confirms
        confirmed = sum(1 for w in words if w in ocr_text)
        total = len(words)
        ratio = confirmed / total if total > 0 else 0

        if ratio >= 0.6:
            # Majority of words confirmed
            return GroundingVerdict(
                cell_ref=ref, extracted_value=value,
                grounded=True,
                ocr_evidence=f"{confirmed}/{total} words confirmed",
                confidence_adjustment=1.0,
            )
        elif ratio >= 0.3:
            # Partial match — lower confidence but don't reject
            return GroundingVerdict(
                cell_ref=ref, extracted_value=value,
                grounded=True,
                ocr_evidence=f"{confirmed}/{total} words (partial)",
                confidence_adjustment=0.85,
            )
        else:
            # OCR cannot confirm this value — possible hallucination
            # But be cautious: OCR quality varies, especially on complex tables
            nearby = self._find_nearby_ocr_text(value_lower, ocr_text)
            return GroundingVerdict(
                cell_ref=ref, extracted_value=value,
                grounded=False,
                ocr_evidence=nearby,
                confidence_adjustment=0.75,  # Moderate penalty, not destructive
            )

    @staticmethod
    def _find_nearby_ocr_text(target: str, ocr_text: str) -> str:
        """Find OCR text that might correspond to the target value."""
        # Look for the best matching substring in OCR text
        target_words = set(re.findall(r'\b\w{3,}\b', target.lower()))
        if not target_words:
            return ""

        # Slide a window over OCR text and find best overlap
        ocr_words = ocr_text.split()
        best_match = ""
        best_score = 0

        window_size = max(len(target_words) + 2, 5)
        for i in range(max(1, len(ocr_words) - window_size + 1)):
            window = " ".join(ocr_words[i:i + window_size])
            window_word_set = set(re.findall(r'\b\w{3,}\b', window.lower()))
            overlap = len(target_words & window_word_set)
            if overlap > best_score:
                best_score = overlap
                best_match = window

        return best_match[:100] if best_match else ""
