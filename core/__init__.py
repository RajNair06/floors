"""Core package for floor-plan validation and scoring."""

from core.schema import Plan, Violation, ScoreResult, EvalReport, parse_plan, get_schema
from core.score import validate, score, evaluate
from core.svg import render_svg

__all__ = [
    "Plan",
    "Violation",
    "ScoreResult",
    "EvalReport",
    "parse_plan",
    "get_schema",
    "validate",
    "score",
    "evaluate",
    "render_svg",
]
