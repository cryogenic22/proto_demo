"""
OCR tool backends for Tier 4 image-based equation extraction.

All backends implement FormulaOCRTool and degrade gracefully when their
dependencies are not installed (return None, never crash).

Backends:
- PlaceholderOCR: stub that always returns None (fallback)
- ClaudeVisionOCR: uses Anthropic API to read equation images (VLM)
- LocalLaTeXOCR: wraps pix2tex / RapidLaTeXOCR if installed
"""

from __future__ import annotations

import base64
import logging
import os

from src.formatter.formula.base import (
    FormulaOCRTool,
    ToolMetadata,
    ToolSideEffect,
)
from src.formatter.formula.ir import (
    FormattedFormula,
    FormulaComplexity,
    FormulaSource,
    FormulaType,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# PlaceholderOCR — graceful degradation when no backend is installed
# ---------------------------------------------------------------------------

class PlaceholderOCR(FormulaOCRTool):
    """Stub OCR that always returns None.

    Ensures the system never crashes due to missing OCR dependencies.
    Registered as a low-priority fallback so real backends take precedence.
    """

    def metadata(self) -> ToolMetadata:
        return ToolMetadata(
            name="placeholder_ocr",
            version="1.0.0",
            description="Stub OCR backend — always returns None (no-op fallback)",
            side_effects=ToolSideEffect.NONE,
            supported_complexities=[FormulaComplexity.RENDERED],
            priority=1,  # Lowest priority — real backends override
            requires_gpu=False,
            requires_network=False,
            timeout_ms=10,
        )

    def recognize(self, image_bytes: bytes, width: int = 0, height: int = 0) -> FormattedFormula | None:
        """Always returns None — no OCR capability."""
        return None


# ---------------------------------------------------------------------------
# ClaudeVisionOCR — Anthropic API equation reader
# ---------------------------------------------------------------------------

class ClaudeVisionOCR(FormulaOCRTool):
    """Uses Claude Vision (Anthropic API) to convert equation images to LaTeX.

    Requires an API key (passed directly or via ANTHROPIC_API_KEY env var).
    Gracefully returns None if the key is missing or the API call fails.
    """

    def __init__(self, api_key: str = "", model: str = "claude-haiku-4-5-20251001"):
        self._api_key = api_key or os.environ.get("ANTHROPIC_API_KEY", "")
        self._model = model

    def metadata(self) -> ToolMetadata:
        return ToolMetadata(
            name="claude_vision_ocr",
            version="1.0.0",
            description="Converts equation images to LaTeX using Claude Vision API",
            side_effects=ToolSideEffect.EXTERNAL,
            supported_complexities=[FormulaComplexity.RENDERED],
            priority=80,  # High priority — good quality
            requires_gpu=False,
            requires_network=True,
            timeout_ms=15_000,
        )

    def recognize(self, image_bytes: bytes, width: int = 0, height: int = 0) -> FormattedFormula | None:
        """Send image to Claude Vision and extract LaTeX.

        Returns None if:
        - No API key is configured
        - The anthropic package is not installed
        - The API call fails for any reason
        """
        if not self._api_key:
            logger.debug("ClaudeVisionOCR: no API key, skipping")
            return None

        try:
            import anthropic  # noqa: F811
        except ImportError:
            logger.debug("ClaudeVisionOCR: anthropic package not installed")
            return None

        try:
            client = anthropic.Anthropic(api_key=self._api_key)

            # Encode image as base64
            img_b64 = base64.b64encode(image_bytes).decode("utf-8")

            # Detect media type from header bytes
            media_type = self._detect_media_type(image_bytes)

            response = client.messages.create(
                model=self._model,
                max_tokens=512,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image",
                                "source": {
                                    "type": "base64",
                                    "media_type": media_type,
                                    "data": img_b64,
                                },
                            },
                            {
                                "type": "text",
                                "text": "Convert this equation to LaTeX. Return ONLY the LaTeX, nothing else.",
                            },
                        ],
                    }
                ],
            )

            latex = response.content[0].text.strip()
            if not latex:
                return None

            # Strip wrapping $ or $$ delimiters if present
            latex = latex.strip("$").strip()

            return FormattedFormula(
                latex=latex,
                source=FormulaSource.VLM,
                complexity=FormulaComplexity.RENDERED,
                confidence=0.8,
                formula_type=FormulaType.MATHEMATICAL,
            )

        except Exception as e:
            logger.warning("ClaudeVisionOCR failed: %s", e)
            return None

    @staticmethod
    def _detect_media_type(image_bytes: bytes) -> str:
        """Detect image MIME type from magic bytes."""
        if image_bytes[:8] == b"\x89PNG\r\n\x1a\n":
            return "image/png"
        elif image_bytes[:2] == b"\xff\xd8":
            return "image/jpeg"
        elif image_bytes[:4] == b"GIF8":
            return "image/gif"
        elif image_bytes[:4] == b"RIFF" and image_bytes[8:12] == b"WEBP":
            return "image/webp"
        return "image/png"  # Default fallback


# ---------------------------------------------------------------------------
# LocalLaTeXOCR — pix2tex / RapidLaTeXOCR wrapper
# ---------------------------------------------------------------------------

class LocalLaTeXOCR(FormulaOCRTool):
    """Wraps local LaTeX OCR libraries (rapid_latex_ocr or pix2tex).

    Tries to import rapid_latex_ocr first (faster, lighter), then pix2tex.
    If neither is installed, gracefully returns None for all calls.
    """

    def __init__(self):
        self._available = False
        self._backend: str = ""
        self._engine = None

        # Try rapid_latex_ocr first
        try:
            from rapid_latex_ocr import LatexOCR  # noqa: F811
            self._engine = LatexOCR()
            self._backend = "rapid_latex_ocr"
            self._available = True
            logger.info("LocalLaTeXOCR: using rapid_latex_ocr backend")
        except (ImportError, Exception):
            pass

        # Fallback to pix2tex
        if not self._available:
            try:
                from pix2tex.cli import LatexOCR as Pix2TexOCR  # noqa: F811
                self._engine = Pix2TexOCR()
                self._backend = "pix2tex"
                self._available = True
                logger.info("LocalLaTeXOCR: using pix2tex backend")
            except (ImportError, Exception):
                pass

        if not self._available:
            logger.debug("LocalLaTeXOCR: no local OCR backend available")

    def metadata(self) -> ToolMetadata:
        return ToolMetadata(
            name="local_latex_ocr",
            version="1.0.0",
            description=f"Local LaTeX OCR via {self._backend or 'none (unavailable)'}",
            side_effects=ToolSideEffect.NONE,
            supported_complexities=[FormulaComplexity.RENDERED],
            priority=60,  # Preferred over placeholder, but below VLM
            requires_gpu=False,
            requires_network=False,
            timeout_ms=10_000,
        )

    def recognize(self, image_bytes: bytes, width: int = 0, height: int = 0) -> FormattedFormula | None:
        """Run local OCR on an equation image.

        Returns None if no backend is available or OCR fails.
        """
        if not self._available or self._engine is None:
            return None

        try:
            if self._backend == "rapid_latex_ocr":
                result, _ = self._engine(image_bytes)
                latex = result if isinstance(result, str) else str(result)
            elif self._backend == "pix2tex":
                # pix2tex expects a PIL Image
                try:
                    from PIL import Image  # noqa: F811
                    import io
                except ImportError:
                    logger.debug("LocalLaTeXOCR: pix2tex requires PIL")
                    return None
                img = Image.open(io.BytesIO(image_bytes))
                latex = self._engine(img)
            else:
                return None

            if not latex or not latex.strip():
                return None

            return FormattedFormula(
                latex=latex.strip(),
                source=FormulaSource.IMAGE_OCR,
                complexity=FormulaComplexity.RENDERED,
                confidence=0.7,
                formula_type=FormulaType.MATHEMATICAL,
            )

        except Exception as e:
            logger.warning("LocalLaTeXOCR (%s) failed: %s", self._backend, e)
            return None
