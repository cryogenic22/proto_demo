"""
Heuristic image classifier — determines if a PDF image is likely an equation.

Uses lightweight heuristics (aspect ratio, size, pixel histogram) to classify
images without requiring any ML model. This is the first gate in the Tier 4
pipeline: only images that pass classification are sent to OCR.

Heuristics:
- Aspect ratio: equations are typically wider than tall (2:1 to 15:1)
- Size: equation images are small (height < 200px, width 100-800px)
- Near-monochrome: equations are black text on white background
- Rejection: very large (photo/chart), very small (icon/bullet), square (logo)
"""

from __future__ import annotations

import logging

from src.formatter.formula.base import (
    ClassificationResult,
    FormulaClassifierTool,
    ToolMetadata,
    ToolSideEffect,
)
from src.formatter.formula.ir import FormulaComplexity

logger = logging.getLogger(__name__)


class HeuristicImageClassifier(FormulaClassifierTool):
    """Classifies images as equation vs. non-equation using heuristics.

    No external dependencies required. PIL is used opportunistically for
    pixel-level analysis when available, but the classifier still works
    without it (using only geometry).
    """

    # -- Geometry thresholds --
    MIN_WIDTH = 100
    MAX_WIDTH = 800
    MAX_HEIGHT = 200
    MIN_ASPECT_RATIO = 2.0    # width / height
    MAX_ASPECT_RATIO = 15.0

    # -- Size rejection thresholds --
    MIN_AREA = 500            # Below this = icon/bullet
    MAX_AREA = 200_000        # Above this = photo/chart
    MAX_SQUARE_RATIO = 1.5    # Below this = too square (logo-like)

    # -- Pixel histogram thresholds --
    MONOCHROME_THRESHOLD = 0.85   # Fraction of pixels that must be near-white or near-black

    def metadata(self) -> ToolMetadata:
        return ToolMetadata(
            name="heuristic_image_classifier",
            version="1.0.0",
            description="Classifies PDF images as equation vs. non-equation using aspect ratio, size, and pixel heuristics",
            side_effects=ToolSideEffect.NONE,
            supported_complexities=[FormulaComplexity.RENDERED],
            priority=50,
            requires_gpu=False,
            requires_network=False,
            timeout_ms=100,
        )

    def classify(self, image_bytes: bytes, width: int, height: int) -> ClassificationResult:
        """Determine if an image contains a mathematical equation.

        Returns ClassificationResult with confidence based on how many
        heuristic checks pass.
        """
        if width <= 0 or height <= 0:
            return ClassificationResult(is_equation=False, confidence=0.0)

        score = 0.0
        max_score = 0.0

        # --- Check 1: Aspect ratio (equations are wide, not tall) ---
        max_score += 1.0
        aspect_ratio = width / height
        if self.MIN_ASPECT_RATIO <= aspect_ratio <= self.MAX_ASPECT_RATIO:
            score += 1.0
        elif aspect_ratio < self.MAX_SQUARE_RATIO:
            # Too square -- strong signal against equation
            score -= 0.5

        # --- Check 2: Absolute size ---
        max_score += 1.0
        area = width * height
        if area < self.MIN_AREA:
            # Too small (icon/bullet)
            score -= 0.5
        elif area > self.MAX_AREA:
            # Too large (photo/chart)
            score -= 0.5
        else:
            score += 1.0

        # --- Check 3: Width and height in expected range ---
        max_score += 1.0
        if self.MIN_WIDTH <= width <= self.MAX_WIDTH and height <= self.MAX_HEIGHT:
            score += 1.0

        # --- Check 4: Pixel histogram (monochrome check) ---
        monochrome_score = self._check_monochrome(image_bytes)
        if monochrome_score is not None:
            max_score += 1.0
            score += monochrome_score

        # Normalize confidence to [0, 1]
        if max_score <= 0:
            return ClassificationResult(is_equation=False, confidence=0.0)

        confidence = max(0.0, min(1.0, score / max_score))
        is_equation = confidence >= 0.6

        equation_type = ""
        if is_equation:
            equation_type = "display" if aspect_ratio > 4.0 else "inline"

        return ClassificationResult(
            is_equation=is_equation,
            confidence=round(confidence, 3),
            equation_type=equation_type,
        )

    def _check_monochrome(self, image_bytes: bytes) -> float | None:
        """Analyze pixel histogram to check if image is near-monochrome.

        Returns a score 0.0-1.0 if PIL is available, None otherwise.
        PIL is NOT imported at module level -- only checked at runtime.
        """
        try:
            from PIL import Image  # noqa: F811
            import io
        except ImportError:
            return None

        try:
            img = Image.open(io.BytesIO(image_bytes)).convert("L")  # Grayscale
            histogram = img.histogram()
            total_pixels = sum(histogram)
            if total_pixels == 0:
                return None

            # Count near-black (0-30) and near-white (225-255) pixels
            near_black = sum(histogram[:31])
            near_white = sum(histogram[225:])
            monochrome_fraction = (near_black + near_white) / total_pixels

            if monochrome_fraction >= self.MONOCHROME_THRESHOLD:
                return 1.0
            elif monochrome_fraction >= 0.6:
                return 0.5
            else:
                return 0.0
        except Exception:
            logger.debug("PIL histogram analysis failed", exc_info=True)
            return None
