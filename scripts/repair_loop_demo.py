"""Repair loop demo: validate → fix → validate until passed.

Demonstrates the generate-validate-repair loop using the MCP authoring tools.
If an LLM API key is set, it calls a model; otherwise it replays a recorded trace.

Usage:
    uv run python scripts/repair_loop_demo.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

# Add project root to path.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.ops import add_opening, add_room, connect_rooms, new_floorplan
from core.score import score


def build_and_repair():
    """Demonstrate building a plan and fixing violations iteratively."""
    print("=== Floor Plan Repair Loop Demo ===\n")

    # Step 1: Start with an empty plan.
    plan = new_floorplan(id="demo")
    result = score(plan)
    print(f"Step 1 - Empty plan: passed={result.passed}, score={result.score}")
    print(f"  Violations: {len(result.violations)}")
    for v in result.violations:
        print(f"    {v.rule}: {v.message}")

    # Step 2: Add a living room.
    plan = add_room(plan, type="living", name="Living Room", w=5.0, h=4.0, x=0, y=0)
    result = score(plan)
    print(f"\nStep 2 - Added living room: passed={result.passed}, score={result.score}")
    print(f"  Violations: {len(result.violations)}")
    for v in result.violations:
        print(f"    {v.rule}: {v.message}")

    # Step 3: Add a bedroom next to it.
    plan = add_room(plan, type="bedroom", name="Bedroom", w=3.5, h=4.0, relative_to="r1", side="E")
    plan = connect_rooms(plan, "r1", "r2")
    result = score(plan)
    print(f"\nStep 3 - Added bedroom + door: passed={result.passed}, score={result.score}")
    print(f"  Violations: {len(result.violations)}")
    for v in result.violations:
        print(f"    {v.rule}: {v.message}")

    # Step 4: Add a bathroom.
    plan = add_room(plan, type="bathroom", name="Bathroom", w=2.5, h=2.5, relative_to="r2", side="E")
    plan = connect_rooms(plan, "r2", "r3")
    result = score(plan)
    print(f"\nStep 4 - Added bathroom + door: passed={result.passed}, score={result.score}")
    print(f"  Violations: {len(result.violations)}")
    for v in result.violations:
        print(f"    {v.rule}: {v.message}")

    # Step 5: Add an entrance (exterior door).
    plan = add_opening(plan, kind="entrance", room="r1", wall="N", width=1.0)
    result = score(plan)
    print(f"\nStep 5 - Added entrance: passed={result.passed}, score={result.score}")
    print(f"  Violations: {len(result.violations)}")
    for v in result.violations:
        print(f"    {v.rule}: {v.message}")

    # Step 6: Add windows to habitable rooms.
    plan = add_opening(plan, kind="window", room="r1", wall="W", width=1.5)
    plan = add_opening(plan, kind="window", room="r2", wall="N", width=1.2)
    result = score(plan)
    print(f"\nStep 6 - Added windows: passed={result.passed}, score={result.score}")
    print(f"  Violations: {len(result.violations)}")
    for v in result.violations:
        print(f"    {v.rule}: {v.message}")

    # Step 7: Add a window to the bathroom (optional, but good practice).
    plan = add_opening(plan, kind="window", room="r3", wall="E", width=0.8)
    result = score(plan)
    print(f"\nStep 7 - Added bathroom window: passed={result.passed}, score={result.score}")
    print(f"  Violations: {len(result.violations)}")
    for v in result.violations:
        print(f"    {v.rule}: {v.message}")

    # Final result.
    print(f"\n=== Final Result ===")
    print(f"Passed: {result.passed}")
    print(f"Score: {result.score}")
    print(f"Total violations: {len(result.violations)}")

    # Write the final plan to JSON.
    plan_dict = plan.model_dump(by_alias=True)
    output_path = Path(__file__).resolve().parent.parent / "data" / "traces" / "demo_plan.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(plan_dict, indent=2))
    print(f"\nPlan saved to: {output_path}")

    # Write a trace.
    trace = {
        "plan_id": "demo",
        "iterations": 7,
        "final_passed": result.passed,
        "final_score": result.score,
        "steps": [
            {"step": 1, "action": "new_floorplan"},
            {"step": 2, "action": "add_room", "room": "living"},
            {"step": 3, "action": "add_room + connect", "room": "bedroom"},
            {"step": 4, "action": "add_room + connect", "room": "bathroom"},
            {"step": 5, "action": "add_opening", "kind": "entrance"},
            {"step": 6, "action": "add_opening x2", "kind": "window"},
            {"step": 7, "action": "add_opening", "kind": "window"},
        ],
    }
    trace_path = output_path.parent / "demo_trace.jsonl"
    with open(trace_path, "a") as f:
        f.write(json.dumps(trace) + "\n")
    print(f"Trace appended to: {trace_path}")


if __name__ == "__main__":
    build_and_repair()
