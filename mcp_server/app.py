"""MCP server: thin wrapper over core/ for agent interaction.

Uses MCP SDK v2 (MCPServer, formerly FastMCP).
"""

from __future__ import annotations

import json
import os
from typing import Any

from mcp.server import MCPServer

from core import get_schema, render_svg
from core.ops import (
    add_opening,
    add_room,
    connect_rooms,
    new_floorplan,
    remove_element,
    update_room,
)
from core.rules import RULE_CATALOGUE
from core.schema import parse_plan, plan_to_dict
from core.score import evaluate, score, validate
from core.share import viewer_url

mcp = MCPServer("Floor-Plan Checker", version="0.1.0")


def _base_url() -> str:
    """Get the viewer base URL."""
    vercel_url = os.environ.get("VERCEL_URL", "")
    if vercel_url:
        if not vercel_url.startswith("http"):
            vercel_url = f"https://{vercel_url}"
        return vercel_url
    return "http://localhost:3000"


def _wrap_result(plan):
    """Wrap a plan with score and viewer URL."""
    plan_dict = plan_to_dict(plan)
    score_result = score(plan)
    base = _base_url()
    try:
        return {
            "plan": plan_dict,
            "passed": score_result.passed,
            "score": score_result.score,
            "errors": score_result.errors,
            "warnings": score_result.warnings,
            "violations": [v.model_dump() for v in score_result.violations],
            "viewer_url": viewer_url(plan_dict, base),
        }
    except ValueError:
        # Plan too large to encode; omit viewer_url.
        return {
            "plan": plan_dict,
            "passed": score_result.passed,
            "score": score_result.score,
            "errors": score_result.errors,
            "warnings": score_result.warnings,
            "violations": [v.model_dump() for v in score_result.violations],
            "viewer_url": None,
        }


# ---------------------------------------------------------------------------
# Read tools
# ---------------------------------------------------------------------------
@mcp.tool(annotations={"readOnlyHint": True})
def get_schema_tool() -> dict:
    """Get the JSON Schema for floor plans, plus the rule catalogue.

    Call this first to learn the plan format before generating one.
    Returns: {"schema": {...}, "rules": [...]}
    """
    return {"schema": get_schema(), "rules": RULE_CATALOGUE}


@mcp.tool(annotations={"readOnlyHint": True})
def validate_floorplan(plan: dict) -> dict:
    """Validate a floor plan and return structured violations.

    The repair-loop workhorse. Returns passed (bool) and violations with
    suggested fixes and regions. A schema-invalid plan returns an error
    with path and message details so you can correct and retry.
    """
    try:
        p = parse_plan(plan)
    except ValueError as e:
        detail = e.args[0] if e.args else {"error": "schema", "details": []}
        return {"error": detail}
    violations = validate(p)
    passed = all(v.severity != "error" for v in violations)
    errors = [f"{v.rule}: {v.message}" for v in violations if v.severity == "error"] or None
    warnings = [f"{v.rule}: {v.message}" for v in violations if v.severity == "warning"] or None
    return {"passed": passed, "errors": errors, "warnings": warnings, "violations": [v.model_dump() for v in violations]}


@mcp.tool(annotations={"readOnlyHint": True})
def score_floorplan(plan: dict) -> dict:
    """Score a floor plan: returns passed, score (0-1), per-rule breakdown, and violations.

    Use for ranking and progress tracking. Also returns a viewer_url that
    opens the plan in a browser with violations highlighted.
    """
    try:
        p = parse_plan(plan)
    except ValueError as e:
        detail = e.args[0] if e.args else {"error": "schema", "details": []}
        return {"error": detail}
    result = score(p)
    plan_dict = plan_to_dict(p)
    base = _base_url()
    try:
        url = viewer_url(plan_dict, base)
    except ValueError:
        url = None
    return {
        "plan": plan_dict,
        "passed": result.passed,
        "score": result.score,
        "errors": result.errors,
        "warnings": result.warnings,
        "breakdown": result.breakdown,
        "violations": [v.model_dump() for v in result.violations],
        "viewer_url": url,
    }


@mcp.tool(annotations={"readOnlyHint": True})
def render_floorplan_svg(plan: dict) -> dict:
    """Render a floor plan to SVG with violation regions overlaid.

    Returns an SVG string that a multimodal agent can inspect.
    """
    try:
        p = parse_plan(plan)
    except ValueError as e:
        detail = e.args[0] if e.args else {"error": "schema", "details": []}
        return {"error": detail}
    violations = validate(p)
    svg = render_svg(p, violations)
    return {"svg": svg}


@mcp.tool(annotations={"readOnlyHint": True})
def run_eval(plans: list[dict]) -> dict:
    """Batch evaluate up to 50 plans.

    Returns pass_rate, mean_score, per_rule failure counts, and per-plan results.
    Use to compare models or prompts on a batch of plans.
    """
    if len(plans) > 50:
        return {"error": "Batch too large. Maximum is 50 plans."}
    parsed = []
    for i, raw in enumerate(plans):
        try:
            parsed.append(parse_plan(raw))
        except ValueError as e:
            detail = e.args[0] if e.args else {"error": "schema", "details": []}
            return {"error": "schema", "plan_index": i, "details": detail.get("details", [])}
    report = evaluate(parsed)
    return report.model_dump()


# ---------------------------------------------------------------------------
# Authoring tools
# ---------------------------------------------------------------------------
@mcp.tool(annotations={"readOnlyHint": True})
def new_floorplan_tool(
    units: str = "m",
    ceiling_height: float = 2.7,
    id: str = "plan_new",
) -> dict:
    """Create an empty floor plan.

    Returns an empty valid plan that you can add rooms to with add_room_tool.
    """
    plan = new_floorplan(id=id, units=units, ceiling_height=ceiling_height)
    return _wrap_result(plan)


@mcp.tool(annotations={"readOnlyHint": True})
def add_room_tool(
    plan: dict,
    type: str,
    name: str,
    w: float,
    h: float,
    x: float | None = None,
    y: float | None = None,
    relative_to: str | None = None,
    side: str | None = None,
) -> dict:
    """Add a room to a plan.

    With relative_to and side (N/S/E/W), the room snaps flush against that
    neighbour so edges touch exactly. With x and y, placed at absolute coords.
    Valid types: living, kitchen, dining, bedroom, bathroom, hallway, study, utility, storage.
    """
    try:
        p = parse_plan(plan)
        p = add_room(p, type=type, name=name, w=w, h=h, x=x, y=y, relative_to=relative_to, side=side)
    except ValueError as e:
        return {"error": str(e)}
    return _wrap_result(p)


@mcp.tool(annotations={"readOnlyHint": True})
def connect_rooms_tool(
    plan: dict,
    a: str,
    b: str,
    width: float = 0.9,
) -> dict:
    """Add a door between two rooms that share a wall.

    Finds the shared wall segment and places a door at its midpoint.
    Errors if the rooms share no wall — place them with relative_to first.
    """
    try:
        p = parse_plan(plan)
        p = connect_rooms(p, a=a, b=b, width=width)
    except ValueError as e:
        return {"error": str(e)}
    return _wrap_result(p)


@mcp.tool(annotations={"readOnlyHint": True})
def add_opening_tool(
    plan: dict,
    kind: str,
    room: str,
    wall: str,
    width: float = 1.0,
    offset: float | None = None,
) -> dict:
    """Add a window or an exterior door to a room.

    kind: 'window' or 'entrance'. Centred on the wall by default.
    The wall must be N, S, E, or W.
    """
    try:
        p = parse_plan(plan)
        p = add_opening(p, kind=kind, room=room, wall=wall, width=width, offset=offset)
    except ValueError as e:
        return {"error": str(e)}
    return _wrap_result(p)


@mcp.tool(annotations={"readOnlyHint": True})
def update_room_tool(
    plan: dict,
    id: str,
    type: str | None = None,
    name: str | None = None,
    x: float | None = None,
    y: float | None = None,
    w: float | None = None,
    h: float | None = None,
) -> dict:
    """Update a room's type, name, x, y, w, or h.

    Pass only the fields you want to change; others remain unchanged.
    """
    try:
        p = parse_plan(plan)
        fields = {}
        if type is not None:
            fields["type"] = type
        if name is not None:
            fields["name"] = name
        if x is not None:
            fields["x"] = x
        if y is not None:
            fields["y"] = y
        if w is not None:
            fields["w"] = w
        if h is not None:
            fields["h"] = h
        p = update_room(p, id=id, **fields)
    except ValueError as e:
        return {"error": str(e)}
    return _wrap_result(p)


@mcp.tool(annotations={"readOnlyHint": True})
def remove_element_tool(plan: dict, id: str) -> dict:
    """Remove a room, door, or window by id.

    Removing a room also removes doors and windows that reference it.
    """
    try:
        p = parse_plan(plan)
        p = remove_element(p, id=id)
    except ValueError as e:
        return {"error": str(e)}
    return _wrap_result(p)


# ---------------------------------------------------------------------------
# Resources
# ---------------------------------------------------------------------------
@mcp.resource("floorplan://rules")
def rules_resource() -> str:
    """Floor-plan rule catalogue."""
    lines = ["# Floor-Plan Rules\n"]
    for r in RULE_CATALOGUE:
        lines.append(f"- **{r['id']}** ({r['severity']}): {r['description']}")
    return "\n".join(lines)
