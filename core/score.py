"""Scoring: run rules, apply formula, build breakdown, batch evaluate."""

from __future__ import annotations

from typing import TYPE_CHECKING

from core.config import ERROR_PENALTY, WARNING_PENALTY
from core.rules import RULES
from core.schema import EvalReport, ScoreResult, Violation

if TYPE_CHECKING:
    from core.schema import Plan


def validate(plan: Plan) -> list[Violation]:
    """Run all rules and return sorted violations."""
    all_violations: list[Violation] = []
    for rule_fn in RULES:
        all_violations.extend(rule_fn(plan))

    # Sort: errors first, then by rule ID, then by room ID.
    severity_order = {"error": 0, "warning": 1}
    all_violations.sort(
        key=lambda v: (severity_order.get(v.severity, 2), v.rule, v.room_ids)
    )
    return all_violations


def score(plan: Plan) -> ScoreResult:
    """Score a plan: 0-1, where 1 is perfect."""
    violations = validate(plan)
    n_errors = sum(1 for v in violations if v.severity == "error")
    n_warnings = sum(1 for v in violations if v.severity == "warning")

    raw = 1.0 - ERROR_PENALTY * n_errors - WARNING_PENALTY * n_warnings
    final_score = max(0.0, raw)

    # Per-rule breakdown.
    breakdown: dict[str, int] = {}
    for v in violations:
        breakdown[v.rule] = breakdown.get(v.rule, 0) + 1

    # Plain-text error/warning arrays with rule prefix.
    errors_list = [f"{v.rule}: {v.message}" for v in violations if v.severity == "error"]
    warnings_list = [f"{v.rule}: {v.message}" for v in violations if v.severity == "warning"]

    return ScoreResult(
        passed=n_errors == 0,
        score=round(final_score, 3),
        errors=errors_list or None,
        warnings=warnings_list or None,
        breakdown=breakdown,
        violations=violations,
    )


def evaluate(plans: list[Plan]) -> EvalReport:
    """Batch evaluate a list of plans."""
    results = []
    per_rule: dict[str, int] = {}
    n_passed = 0
    total_score = 0.0

    for plan in plans:
        result = score(plan)
        results.append(
            {
                "plan_id": plan.id,
                "passed": result.passed,
                "score": result.score,
                "errors": result.errors,
                "warnings": result.warnings,
                "breakdown": result.breakdown,
                "violations": [v.model_dump() for v in result.violations],
            }
        )
        if result.passed:
            n_passed += 1
        total_score += result.score
        for rule_id, count in result.breakdown.items():
            per_rule[rule_id] = per_rule.get(rule_id, 0) + count

    n = len(plans)
    return EvalReport(
        n=n,
        pass_rate=round(n_passed / n, 3) if n else 0.0,
        mean_score=round(total_score / n, 3) if n else 0.0,
        per_rule=per_rule,
        results=results,
    )
