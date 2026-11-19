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

mcp = MCPServer("Floors", version="0.1.0")


def _base_url() -> str:
    """Get the viewer base URL."""
    vercel_url = os.environ.get("VERCEL_URL", "")
    if vercel_url:
        if not vercel_url.startswith("http"):
            vercel_url = f"https://{vercel_url}"
        return vercel_url
    return "http://localhost:3000"


def _strip_ids(result_dict: dict) -> dict:
    """Strip internal rule IDs from violations for cleaner agent output."""
    if "violations" in result_dict:
        for v in result_dict["violations"]:
            v.pop("rule", None)
    return result_dict


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
    """Get the complete JSON Schema for floor plans and the validation rule catalogue.

    CALL THIS FIRST before generating or modifying any plan. It tells you:
    - The exact JSON structure a plan must follow (rooms, doors, windows arrays)
    - Every field name, type, and constraint
    - Valid room types: living, kitchen, dining, bedroom, bathroom, hallway, study, utility, storage
    - Valid wall sides: N (top), S (bottom), E (right), W (left)
    - The 10 validation rules with severity (error vs warning) and description

    Returns:
      schema: Full JSON Schema object for plan validation
      rules: Array of {severity, description} for each validation rule

    Coordinate system: origin (0,0) is top-left. X grows right, Y grows down.
    Rooms are axis-aligned rectangles defined by (x, y, w, h) in metres.
    """
    return {"schema": get_schema(), "rules": [{"severity": r["severity"], "description": r["description"]} for r in RULE_CATALOGUE]}


@mcp.tool(annotations={"readOnlyHint": True})
def validate_floorplan(plan: dict) -> dict:
    """Check a floor plan against all validation rules and return every problem found.

    This is the main tool for the repair loop: generate a plan, validate it,
    read the errors, fix them, validate again until passed=true.

    Input:
      plan: A floor plan JSON object (see get_schema_tool for the exact format)

    Returns on valid plan:
      passed: true if no errors exist (warnings alone still pass)
      errors: array of human-readable error strings, or null if none.
              Errors mean the plan cannot work (overlap, no entrance, unreachable rooms, etc.)
      warnings: array of human-readable warning strings, or null if none.
                Warnings mean the plan works but has design issues (small rooms, bad proportions, etc.)
      violations: array of detailed violation objects, each containing:
        severity: "error" or "warning"
        message: human-readable description of the problem
        suggested_fix: specific action to resolve the issue
        room_ids: array of room IDs involved
        region: {x, y, w, h} rectangle for SVG highlighting

    Returns on invalid plan (malformed JSON structure):
      error: {error: "schema", details: [{path, message}, ...]}
      Use the path and message to fix the structure, then retry.

    Workflow:
      1. Generate or receive a plan
      2. Call validate_floorplan
      3. If errors exist, read each message and suggested_fix
      4. Use update_room_tool, add_opening_tool, etc. to fix issues
      5. Re-validate until passed=true and errors=null
    """
    try:
        p = parse_plan(plan)
    except ValueError as e:
        detail = e.args[0] if e.args else {"error": "schema", "details": []}
        return {"error": detail}
    violations = validate(p)
    passed = all(v.severity != "error" for v in violations)
    errors = [v.message for v in violations if v.severity == "error"] or None
    warnings = [v.message for v in violations if v.severity == "warning"] or None
    return {"passed": passed, "errors": errors, "warnings": warnings, "violations": [v.model_dump() for v in violations]}


@mcp.tool(annotations={"readOnlyHint": True})
def score_floorplan(plan: dict) -> dict:
    """Score a floor plan from 0.0 (worst) to 1.0 (perfect) with full detail.

    Use this to rank plans, track improvement across repair iterations, or
    compare different designs. The score formula is:
      score = max(0, 1 - 0.25 * error_count - 0.05 * warning_count)

    Input:
      plan: A floor plan JSON object

    Returns:
      plan: The validated plan (echoed back)
      passed: true if no errors (same as validate_floorplan)
      score: float from 0.0 to 1.0
      errors: array of error strings or null
      warnings: array of warning strings or null
      breakdown: dict of {rule_name: count} showing which rules fired
      violations: full violation details (same as validate_floorplan)
      viewer_url: a URL that opens the plan in a browser with violations highlighted.
                  Share this with users to visualize the plan.

    Use score_floorplan when you need a single number to compare plans.
    Use validate_floorplan when you only need to know what to fix.
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
    """Render a floor plan as an SVG image with violation regions highlighted.

    Use this when you need a visual representation of the plan. The SVG shows:
    - Each room as a labelled rectangle with its name and dimensions
    - Doors as gaps in walls between rooms or on exterior walls
    - Windows as marks on walls
    - Violation regions highlighted in red (errors) or yellow (warnings)

    Input:
      plan: A floor plan JSON object

    Returns:
      svg: A complete SVG string that can be displayed as an image.
           Multimodal agents can analyze this image to understand the layout.
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
    """Batch evaluate up to 50 floor plans at once and return aggregate statistics.

    Use this to compare multiple plans, test a prompt or model across many examples,
    or measure improvement over iterations.

    Input:
      plans: Array of up to 50 floor plan JSON objects

    Returns:
      n: number of plans evaluated
      pass_rate: fraction of plans that passed (0.0 to 1.0)
      mean_score: average score across all plans (0.0 to 1.0)
      per_rule: dict of {rule_name: count} showing how many plans triggered each rule
      results: array of per-plan objects, each containing:
        plan_id: the plan's id field
        passed: true/false
        score: 0.0 to 1.0
        errors: array of error strings or null
        warnings: array of warning strings or null
        breakdown: per-rule counts for this plan
        violations: full violation details

    If any plan has a schema error, returns:
      {error: "schema", plan_index: N, details: [...]}
      Fix the plan at index N and retry.
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
    """Create a new empty floor plan ready for rooms to be added.

    This is always the first step when building a plan from scratch.
    The returned plan has empty rooms, doors, and windows arrays.

    Input:
      units: Must be "m" (metres). Other units are not supported.
      ceiling_height: Default ceiling height in metres (used for 3D view only, default 2.7)
      id: A unique identifier for this plan (default "plan_new")

    Returns:
      plan: The empty plan object
      passed: true (empty plan has no violations)
      score: 1.0
      errors: null
      warnings: null
      violations: []
      viewer_url: URL to view in browser

    Next step: Call add_room_tool to add the first room.
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
    """Add a rectangular room to a floor plan.

    Two placement modes:
    1. RELATIVE placement (recommended for most cases):
       - relative_to: ID of an existing room to snap against
       - side: which side of that room — "N" (above), "S" (below), "E" (right), "W" (left)
       - The new room's edge aligns exactly with the neighbour's edge so they share a wall
       - Example: relative_to="r1", side="E" places the new room to the right of room r1

    2. ABSOLUTE placement:
       - x: left edge coordinate in metres
       - y: top edge coordinate in metres
       - Use this when you need precise control over room position

    Input:
      plan: The current floor plan (pass the plan returned by previous tool calls)
      type: Room type — one of: living, kitchen, dining, bedroom, bathroom, hallway, study, utility, storage
      name: Human-readable name (e.g. "Master Bedroom", "Kitchen")
      w: Width in metres (must be positive)
      h: Height in metres (must be positive)
      x, y: Absolute position (use instead of relative_to/side)
      relative_to, side: Relative position (use instead of x/y)

    Returns the updated plan with score, errors, warnings, and viewer_url.

    Important:
    - Rooms must not overlap. If two rooms overlap, validation will report an error.
    - Rooms that share a wall (edges touch exactly) can be connected with connect_rooms_tool.
    - Minimum areas by type: bedroom 7m², living 10m², kitchen 4m², bathroom 2.5m², study 5m².
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

    The tool automatically finds the shared wall segment and places the door
    at its midpoint. The door width defaults to 0.9m (standard interior door).

    Input:
      plan: The current floor plan
      a: ID of the first room
      b: ID of the second room
      width: Door width in metres (default 0.9, valid range 0.7–1.2)

    Returns the updated plan with score, errors, warnings, and viewer_url.

    Errors if:
    - The two rooms do not share a wall. Fix: place them adjacent using
      add_room_tool with relative_to before connecting.
    - Either room ID does not exist.

    Important:
    - This tool only creates interior doors (room-to-room).
    - For exterior doors (to outside), use add_opening_tool with kind="entrance".
    - A plan must have at least one exterior door to pass validation.
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

    This tool is for openings that face outside — windows on exterior walls
    and exterior doors (entrances). For interior doors between rooms,
    use connect_rooms_tool instead.

    Input:
      plan: The current floor plan
      kind: "window" or "entrance"
      room: ID of the room to add the opening to
      wall: Which wall — "N" (top), "S" (bottom), "E" (right), "W" (left)
            The wall must be an exterior wall (not shared with another room).
      width: Opening width in metres (default 1.0)
      offset: Position along the wall in metres from the start of the wall.
              If omitted, the opening is centred on the wall.

    Returns the updated plan with score, errors, warnings, and viewer_url.

    Errors if:
    - The specified wall is interior (shared with another room).
      Fix: choose a different wall that faces outside.
    - The opening doesn't fit on the wall (offset + width > wall length).
    - The room ID does not exist.

    Important:
    - Every plan needs at least one exterior door (kind="entrance") to pass validation.
    - Bedrooms, living rooms, and studies need at least one window on an exterior wall.
    - Windows on interior walls will cause a validation error.
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
    """Update one or more properties of an existing room.

    Pass only the fields you want to change — all others remain unchanged.
    Useful for fixing validation errors (e.g. enlarging a room that's too small).

    Input:
      plan: The current floor plan
      id: ID of the room to update
      type: New room type (living, kitchen, dining, bedroom, bathroom, hallway, study, utility, storage)
      name: New human-readable name
      x: New left edge coordinate
      y: New top edge coordinate
      w: New width in metres
      h: New height in metres

    Returns the updated plan with score, errors, warnings, and viewer_url.

    Common uses:
    - Fix "room too small" warning: increase w and/or h
    - Fix "aspect ratio too high" warning: make w and h closer to equal
    - Fix overlap error: move the room (change x, y) or shrink it (reduce w, h)
    - Change room type to satisfy window requirements (e.g. study needs a window)
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
    """Remove a room, door, or window from a floor plan by its ID.

    When you remove a room, all doors and windows that reference that room
    are automatically removed as well.

    Input:
      plan: The current floor plan
      id: The ID of the room, door, or window to remove

    Returns the updated plan with score, errors, warnings, and viewer_url.

    Errors if the ID does not exist in the plan.

    Use this to:
    - Start over with a problematic room (remove it, then add a corrected version)
    - Simplify a plan that's too complex
    - Fix overlap errors by removing one of the overlapping rooms
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
    """Floor-plan validation rule catalogue."""
    lines = ["# Floor-Plan Validation Rules\n"]
    lines.append("Plans are checked against these 10 rules. Errors mean the plan cannot work.")
    lines.append("Warnings mean the plan works but has design issues.\n")
    for r in RULE_CATALOGUE:
        lines.append(f"- **{r['severity'].upper()}**: {r['description']}")
    return "\n".join(lines)
