"""
Tests for Tier 4 image equation detection and classification tools.

Covers:
- HeuristicImageClassifier: geometry heuristics, edge cases
- PlaceholderOCR: graceful no-op
- ClaudeVisionOCR: graceful degradation without API key
- LocalLaTeXOCR: graceful degradation without packages
- Factory integration: correct tool registration
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from src.formatter.formula.base import ClassificationResult, ToolSideEffect
from src.formatter.formula.ir import FormulaComplexity, FormulaSource
from src.formatter.formula.tools.image_classifier import HeuristicImageClassifier
from src.formatter.formula.tools.ocr_backends import (
    ClaudeVisionOCR,
    LocalLaTeXOCR,
    PlaceholderOCR,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# A 1x1 white PNG (minimal valid image for PIL tests)
_TINY_PNG = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01"
    b"\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00"
    b"\x00\x00\x0cIDATx\x9cc\xf8\x0f\x00\x00\x01\x01\x00"
    b"\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82"
)


# ---------------------------------------------------------------------------
# HeuristicImageClassifier
# ---------------------------------------------------------------------------

class TestHeuristicImageClassifier:
    """Tests for the heuristic image classifier."""

    def setup_method(self):
        self.classifier = HeuristicImageClassifier()

    def test_metadata_name(self):
        meta = self.classifier.metadata()
        assert meta.name == "heuristic_image_classifier"
        assert meta.side_effects == ToolSideEffect.NONE

    def test_metadata_complexity(self):
        meta = self.classifier.metadata()
        assert FormulaComplexity.RENDERED in meta.supported_complexities

    # -- Equation-like dimensions (wide, small) --

    def test_equation_like_wide_image(self):
        """A 400x80 image (5:1 aspect) in the right size range = equation."""
        result = self.classifier.classify(b"\x00" * 10, width=400, height=80)
        assert result.is_equation is True
        assert result.confidence >= 0.6

    def test_equation_like_narrow_display(self):
        """A 600x50 image (12:1 aspect) = display equation."""
        result = self.classifier.classify(b"\x00" * 10, width=600, height=50)
        assert result.is_equation is True
        assert result.equation_type == "display"

    def test_equation_inline_type(self):
        """A 300x100 image (3:1 aspect) = inline equation."""
        result = self.classifier.classify(b"\x00" * 10, width=300, height=100)
        assert result.is_equation is True
        assert result.equation_type == "inline"

    # -- Rejection cases --

    def test_reject_square_logo(self):
        """A 100x100 square image = logo, not an equation."""
        result = self.classifier.classify(b"\x00" * 10, width=100, height=100)
        assert result.is_equation is False

    def test_reject_very_large_photo(self):
        """A 1200x800 image = photo/chart, not an equation."""
        result = self.classifier.classify(b"\x00" * 10, width=1200, height=800)
        assert result.is_equation is False

    def test_reject_tiny_icon(self):
        """A 10x10 image = icon/bullet, not an equation."""
        result = self.classifier.classify(b"\x00" * 10, width=10, height=10)
        assert result.is_equation is False

    def test_reject_tall_narrow_image(self):
        """A 50x400 tall image = sidebar/column, not an equation."""
        result = self.classifier.classify(b"\x00" * 10, width=50, height=400)
        assert result.is_equation is False

    # -- Edge cases --

    def test_zero_dimensions(self):
        """Zero-size images should not crash."""
        result = self.classifier.classify(b"", width=0, height=0)
        assert result.is_equation is False
        assert result.confidence == 0.0

    def test_negative_dimensions(self):
        """Negative dimensions should not crash."""
        result = self.classifier.classify(b"", width=-1, height=-1)
        assert result.is_equation is False

    def test_zero_height(self):
        """Zero height (division by zero guard)."""
        result = self.classifier.classify(b"", width=400, height=0)
        assert result.is_equation is False

    def test_confidence_is_bounded(self):
        """Confidence should always be in [0, 1]."""
        # Test various sizes to ensure bounding
        for w, h in [(400, 80), (10, 10), (1200, 800), (100, 100)]:
            result = self.classifier.classify(b"\x00", width=w, height=h)
            assert 0.0 <= result.confidence <= 1.0, f"confidence out of bounds for {w}x{h}"

    # -- PIL monochrome check --

    def test_monochrome_check_without_pil(self):
        """When PIL is not available, classifier still works (geometry only)."""
        with patch.dict("sys.modules", {"PIL": None, "PIL.Image": None}):
            result = self.classifier._check_monochrome(b"\x00")
            # Should return None when PIL is unavailable
            assert result is None

    def test_monochrome_check_with_invalid_image(self):
        """Invalid image bytes should not crash the monochrome check."""
        # This will either return None (if PIL can't open it) or a score
        result = self.classifier._check_monochrome(b"not an image at all")
        # Should gracefully handle — either None or a float
        assert result is None or isinstance(result, float)


# ---------------------------------------------------------------------------
# PlaceholderOCR
# ---------------------------------------------------------------------------

class TestPlaceholderOCR:
    """Tests for the placeholder OCR stub."""

    def setup_method(self):
        self.ocr = PlaceholderOCR()

    def test_metadata_name(self):
        meta = self.ocr.metadata()
        assert meta.name == "placeholder_ocr"

    def test_metadata_low_priority(self):
        meta = self.ocr.metadata()
        assert meta.priority == 1  # Lowest

    def test_recognize_returns_none(self):
        """PlaceholderOCR always returns None."""
        result = self.ocr.recognize(b"\x89PNG...", width=400, height=80)
        assert result is None

    def test_recognize_empty_bytes(self):
        result = self.ocr.recognize(b"", width=0, height=0)
        assert result is None

    def test_side_effect_none(self):
        assert self.ocr.metadata().side_effects == ToolSideEffect.NONE


# ---------------------------------------------------------------------------
# ClaudeVisionOCR
# ---------------------------------------------------------------------------

class TestClaudeVisionOCR:
    """Tests for Claude Vision OCR backend."""

    def test_metadata_side_effect_external(self):
        ocr = ClaudeVisionOCR(api_key="test-key")
        assert ocr.metadata().side_effects == ToolSideEffect.EXTERNAL

    def test_metadata_requires_network(self):
        ocr = ClaudeVisionOCR(api_key="test-key")
        assert ocr.metadata().requires_network is True

    def test_no_api_key_returns_none(self):
        """Without an API key, recognize() should return None gracefully."""
        ocr = ClaudeVisionOCR(api_key="")
        with patch.dict("os.environ", {}, clear=True):
            # Re-init to clear any env-based key
            ocr._api_key = ""
            result = ocr.recognize(b"\x89PNG...", width=400, height=80)
            assert result is None

    def test_missing_anthropic_package_returns_none(self):
        """If anthropic is not installed, should return None."""
        ocr = ClaudeVisionOCR(api_key="test-key")
        with patch.dict("sys.modules", {"anthropic": None}):
            result = ocr.recognize(b"\x89PNG...", width=400, height=80)
            assert result is None

    def test_api_error_returns_none(self):
        """API errors should be caught and return None."""
        ocr = ClaudeVisionOCR(api_key="test-key")
        mock_anthropic = MagicMock()
        mock_anthropic.Anthropic.return_value.messages.create.side_effect = Exception("API error")

        with patch.dict("sys.modules", {"anthropic": mock_anthropic}):
            result = ocr.recognize(b"\x89PNG...", width=400, height=80)
            assert result is None

    def test_successful_recognition(self):
        """Successful API call should return a FormattedFormula."""
        ocr = ClaudeVisionOCR(api_key="test-key")

        mock_content = MagicMock()
        mock_content.text = r"\frac{a}{b}"

        mock_response = MagicMock()
        mock_response.content = [mock_content]

        mock_client = MagicMock()
        mock_client.messages.create.return_value = mock_response

        mock_anthropic = MagicMock()
        mock_anthropic.Anthropic.return_value = mock_client

        with patch.dict("sys.modules", {"anthropic": mock_anthropic}):
            result = ocr.recognize(_TINY_PNG, width=400, height=80)
            assert result is not None
            assert result.latex == r"\frac{a}{b}"
            assert result.source == FormulaSource.VLM
            assert result.complexity == FormulaComplexity.RENDERED

    def test_strips_dollar_delimiters(self):
        """LaTeX wrapped in $...$ should have delimiters stripped."""
        ocr = ClaudeVisionOCR(api_key="test-key")

        mock_content = MagicMock()
        mock_content.text = "$$\\sum_{i=1}^{n} x_i$$"

        mock_response = MagicMock()
        mock_response.content = [mock_content]

        mock_client = MagicMock()
        mock_client.messages.create.return_value = mock_response

        mock_anthropic = MagicMock()
        mock_anthropic.Anthropic.return_value = mock_client

        with patch.dict("sys.modules", {"anthropic": mock_anthropic}):
            result = ocr.recognize(_TINY_PNG, width=400, height=80)
            assert result is not None
            assert not result.latex.startswith("$")
            assert not result.latex.endswith("$")

    def test_detect_media_type_png(self):
        assert ClaudeVisionOCR._detect_media_type(b"\x89PNG\r\n\x1a\n") == "image/png"

    def test_detect_media_type_jpeg(self):
        assert ClaudeVisionOCR._detect_media_type(b"\xff\xd8\xff\xe0") == "image/jpeg"

    def test_detect_media_type_gif(self):
        assert ClaudeVisionOCR._detect_media_type(b"GIF89a") == "image/gif"

    def test_detect_media_type_unknown(self):
        assert ClaudeVisionOCR._detect_media_type(b"unknown") == "image/png"


# ---------------------------------------------------------------------------
# LocalLaTeXOCR
# ---------------------------------------------------------------------------

class TestLocalLaTeXOCR:
    """Tests for local LaTeX OCR backend."""

    def test_graceful_when_no_packages(self):
        """Should not crash when neither rapid_latex_ocr nor pix2tex is installed."""
        with patch.dict("sys.modules", {
            "rapid_latex_ocr": None,
            "pix2tex": None,
            "pix2tex.cli": None,
        }):
            ocr = LocalLaTeXOCR()
            assert ocr._available is False
            assert ocr.recognize(b"\x00", width=400, height=80) is None

    def test_metadata_side_effect_none(self):
        """LocalLaTeXOCR has no side effects."""
        with patch.dict("sys.modules", {
            "rapid_latex_ocr": None,
            "pix2tex": None,
            "pix2tex.cli": None,
        }):
            ocr = LocalLaTeXOCR()
            assert ocr.metadata().side_effects == ToolSideEffect.NONE

    def test_metadata_description_unavailable(self):
        """When no backend, description reflects that."""
        with patch.dict("sys.modules", {
            "rapid_latex_ocr": None,
            "pix2tex": None,
            "pix2tex.cli": None,
        }):
            ocr = LocalLaTeXOCR()
            assert "unavailable" in ocr.metadata().description.lower()

    def test_recognize_returns_none_when_unavailable(self):
        """recognize() returns None when no backend is installed."""
        with patch.dict("sys.modules", {
            "rapid_latex_ocr": None,
            "pix2tex": None,
            "pix2tex.cli": None,
        }):
            ocr = LocalLaTeXOCR()
            result = ocr.recognize(b"\x00" * 100, width=300, height=50)
            assert result is None


# ---------------------------------------------------------------------------
# Factory integration
# ---------------------------------------------------------------------------

class TestFactoryRegistration:
    """Tests that the factory correctly registers Tier 4 tools."""

    def test_factory_registers_classifier(self):
        """Factory should always register HeuristicImageClassifier."""
        from src.formatter.formula.factory import create_formula_system

        orchestrator = create_formula_system()
        classifiers = orchestrator._registry.get_classifiers()
        assert len(classifiers) >= 1
        names = [c.metadata().name for c in classifiers]
        assert "heuristic_image_classifier" in names

    def test_factory_registers_at_least_one_ocr(self):
        """Factory should always register at least PlaceholderOCR."""
        from src.formatter.formula.factory import create_formula_system

        orchestrator = create_formula_system()
        ocr_tools = orchestrator._registry.get_ocr_tools()
        assert len(ocr_tools) >= 1
        names = [t.metadata().name for t in ocr_tools]
        assert "placeholder_ocr" in names

    def test_factory_registers_claude_vision_with_key(self):
        """If ANTHROPIC_API_KEY is set, ClaudeVisionOCR should be registered."""
        from src.formatter.formula.factory import create_formula_system

        with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key-123"}):
            orchestrator = create_formula_system()
            ocr_tools = orchestrator._registry.get_ocr_tools()
            names = [t.metadata().name for t in ocr_tools]
            assert "claude_vision_ocr" in names

    def test_factory_skips_claude_vision_without_key(self):
        """Without ANTHROPIC_API_KEY, ClaudeVisionOCR should NOT be registered."""
        from src.formatter.formula.factory import create_formula_system

        with patch.dict("os.environ", {}, clear=True):
            orchestrator = create_formula_system()
            ocr_tools = orchestrator._registry.get_ocr_tools()
            names = [t.metadata().name for t in ocr_tools]
            assert "claude_vision_ocr" not in names

    def test_factory_total_tools_increased(self):
        """Factory should have more tools than before (detectors + renderers + classifier + OCR)."""
        from src.formatter.formula.factory import create_formula_system

        orchestrator = create_formula_system()
        # 2 detectors + 3 renderers + 1 classifier + at least 1 OCR = 7+
        assert orchestrator._registry.total_tools >= 7

    def test_factory_list_tools_includes_classifiers(self):
        """list_tools() should include classifiers category."""
        from src.formatter.formula.factory import create_formula_system

        orchestrator = create_formula_system()
        tool_list = orchestrator._registry.list_tools()
        assert "classifiers" in tool_list
        assert len(tool_list["classifiers"]) >= 1
