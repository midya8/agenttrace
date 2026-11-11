"""Local-first AI agent trace analysis."""

from .analysis import AnalysisResult, RunAnalysis, analyze_steps
from .parser import load_trace, parse_lines

__all__ = ["AnalysisResult", "RunAnalysis", "analyze_steps", "load_trace", "parse_lines"]
__version__ = "0.2.0"

from .capacity import capacity_report
__all__.append("capacity_report")
