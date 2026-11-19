"""Core package for floor-plan validation and scoring."""

from core.schema import Plan, Violation, ScoreResult, EvalReport, parse_plan, get_schema
from core.score import validate, score, evaluate
from core.svg import render_svg
from core.render3d import render_glb, render_glb_base64

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
    "render_glb",
    "render_glb_base64",
]
