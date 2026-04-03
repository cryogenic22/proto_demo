"""
Formula processing module — modular, registry-based architecture.

Follows the harness pattern from rough_notes.md:
- Tool registry with metadata-first design
- Typed tools with explicit input/output contracts
- Pluggable backends (swap OCR, renderers, validators)
- Orchestrator selects tools per formula complexity
- No hardcoded workflows — configurable strategy
"""

from src.formatter.formula.ir import FormattedFormula
from src.formatter.formula.registry import FormulaToolRegistry
from src.formatter.formula.orchestrator import FormulaOrchestrator

__all__ = [
    "FormattedFormula",
    "FormulaToolRegistry",
    "FormulaOrchestrator",
]
