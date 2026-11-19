"""Deterministic validation rules for floor plans.

Each rule is a pure function: (plan) -> list[Violation].
All rules run even when one fails, so an agent gets every problem in one pass.
"""

from __future__ import annotations

from collections import deque
from typing import TYPE_CHECKING

from core.config import (
    EPS,
    MAX_ASPECT_RATIO,
    MAX_INTERIOR_DOOR_WIDTH,
    MAX_TOTAL_AREA,
    MIN_EXTERIOR_DOOR_WIDTH,
    MIN_INTERIOR_DOOR_WIDTH,
    MIN_ROOM_AREA,
    MIN_SIDE,
    MIN_SIDE_HALLWAY,
    MIN_TOTAL_AREA,
)
from core.geometry import (
    is_exterior_wall,
    overlap_area,
    room_rect,
    shared_edge,
)
from core.schema import Violation

if TYPE_CHECKING:
    from core.schema import Plan


# ---------------------------------------------------------------------------
# R01: No overlap
# ---------------------------------------------------------------------------
def r01_no_overlap(plan: Plan) -> list[Violation]:
    """Interiors of any two rooms must not intersect by more than EPS²."""
    violations = []
    for i, r1 in enumerate(plan.rooms):
        for r2 in plan.rooms[i + 1 :]:
            area = overlap_area(r1, r2)
            if area > EPS * EPS:
                violations.append(
                    Violation(
                        rule="R01",
                        severity="error",
                        room_ids=[r1.id, r2.id],
                        message=f"'{r1.name}' and '{r2.name}' overlap by {area:.2f} m².",
                        suggested_fix="Move or shrink one room so the edges only touch.",
                        region=room_rect(r1),
                    )
                )
    return violations


# ---------------------------------------------------------------------------
# R02: Has entrance
# ---------------------------------------------------------------------------
def r02_has_entrance(plan: Plan) -> list[Violation]:
    """At least one door with to='outside'."""
    has_exterior_door = any(d.to == "outside" for d in plan.doors)
    if not has_exterior_door:
        return [
            Violation(
                rule="R02",
                severity="error",
                room_ids=[],
                message="The plan has no entrance. Add at least one exterior door.",
                suggested_fix="Add an exterior door to any room that has an exterior wall.",
            )
        ]
    return []


# ---------------------------------------------------------------------------
# R03: All rooms reachable
# ---------------------------------------------------------------------------
def r03_all_reachable(plan: Plan) -> list[Violation]:
    """BFS from entrance reaches every room."""
    if not plan.rooms:
        return []

    # Find entrance room.
    entrance_room_id = None
    for d in plan.doors:
        if d.to == "outside":
            entrance_room_id = d.from_
            break
    if entrance_room_id is None:
        return []  # R02 already catches this.

    # Build adjacency from doors.
    adj: dict[str, set[str]] = {r.id: set() for r in plan.rooms}
    for d in plan.doors:
        if d.to != "outside":
            adj.setdefault(d.from_, set()).add(d.to)
            adj.setdefault(d.to, set()).add(d.from_)

    # BFS.
    visited: set[str] = set()
    queue = deque([entrance_room_id])
    while queue:
        current = queue.popleft()
        if current in visited:
            continue
        visited.add(current)
        for neighbour in adj.get(current, []):
            if neighbour not in visited:
                queue.append(neighbour)

    unreachable = [r for r in plan.rooms if r.id not in visited]
    return [
        Violation(
            rule="R03",
            severity="error",
            room_ids=[r.id],
            message=f"'{r.name}' is not reachable from the entrance.",
            suggested_fix=f"Add a door linking '{r.name}' to an adjacent room.",
            region=room_rect(r),
        )
        for r in unreachable
    ]


# ---------------------------------------------------------------------------
# R04: Habitable rooms have a window
# ---------------------------------------------------------------------------
HABITABLE_TYPES = {"bedroom", "living", "study"}


def r04_habitable_window(plan: Plan) -> list[Violation]:
    """Every bedroom, living, and study must have a window on an exterior wall."""
    violations = []
    for room in plan.rooms:
        if room.type not in HABITABLE_TYPES:
            continue
        has_ext_window = any(
            w.room == room.id and is_exterior_wall(room, w.wall, plan.rooms)
            for w in plan.windows
        )
        if not has_ext_window:
            violations.append(
                Violation(
                    rule="R04",
                    severity="error",
                    room_ids=[room.id],
                    message=f"'{room.name}' ({room.type}) has no window on an exterior wall.",
                    suggested_fix=f"Add a window on an exterior wall of '{room.name}'.",
                    region=room_rect(room),
                )
            )
    return violations


# ---------------------------------------------------------------------------
# R05: Doors sit on real walls
# ---------------------------------------------------------------------------
def r05_doors_on_walls(plan: Plan) -> list[Violation]:
    """Room-to-room doors lie within a shared wall; exterior doors on an exterior wall."""
    violations = []
    room_map = {r.id: r for r in plan.rooms}
    for door in plan.doors:
        if door.from_ not in room_map:
            continue
        from_room = room_map[door.from_]
        if door.to == "outside":
            # Exterior door must be on an exterior wall.
            if not is_exterior_wall(from_room, door.wall, plan.rooms):
                violations.append(
                    Violation(
                        rule="R05",
                        severity="error",
                        room_ids=[door.from_],
                        message=f"Exterior door in '{from_room.name}' is on an interior wall (wall {door.wall}).",
                        suggested_fix=f"Move the exterior door in '{from_room.name}' to an exterior wall.",
                        region=room_rect(from_room),
                    )
                )
        else:
            if door.to not in room_map:
                continue
            to_room = room_map[door.to]
            edges = shared_edge(from_room, to_room)
            # Check that the door's wall is one of the shared walls.
            door_on_shared = any(w1 == door.wall for w1, w2, _, length in edges if length > EPS)
            if not door_on_shared:
                violations.append(
                    Violation(
                        rule="R05",
                        severity="error",
                        room_ids=[door.from_, door.to],
                        message=f"Door between '{from_room.name}' and '{to_room.name}' is on wall {door.wall}, which they do not share.",
                        suggested_fix=f"Move the door between '{from_room.name}' and '{to_room.name}' to the wall segment they share.",
                        region=room_rect(from_room),
                    )
                )
    return violations


# ---------------------------------------------------------------------------
# R06: Windows sit on exterior walls
# ---------------------------------------------------------------------------
def r06_windows_exterior(plan: Plan) -> list[Violation]:
    """Windows must lie within an exterior wall of their room."""
    violations = []
    room_map = {r.id: r for r in plan.rooms}
    for window in plan.windows:
        if window.room not in room_map:
            continue
        room = room_map[window.room]
        if not is_exterior_wall(room, window.wall, plan.rooms):
            violations.append(
                Violation(
                    rule="R06",
                    severity="error",
                    room_ids=[window.room],
                    message=f"Window in '{room.name}' is on an interior wall (wall {window.wall}).",
                    suggested_fix=f"Move the window in '{room.name}' to an exterior wall.",
                    region=room_rect(room),
                )
            )
    return violations


# ---------------------------------------------------------------------------
# R07: Minimum room areas
# ---------------------------------------------------------------------------
def r07_min_area(plan: Plan) -> list[Violation]:
    """Area below the minimum for its type."""
    violations = []
    for room in plan.rooms:
        area = room.w * room.h
        minimum = MIN_ROOM_AREA.get(room.type)
        if minimum and area < minimum:
            violations.append(
                Violation(
                    rule="R07",
                    severity="warning",
                    room_ids=[room.id],
                    message=f"'{room.name}' ({room.type}) is {area:.1f} m² — below the {minimum:.1f} m² minimum.",
                    suggested_fix=f"Enlarge '{room.name}' to at least {minimum:.1f} m².",
                    region=room_rect(room),
                )
            )
    return violations


# ---------------------------------------------------------------------------
# R08: Plausible proportions and size
# ---------------------------------------------------------------------------
def r08_proportions(plan: Plan) -> list[Violation]:
    """Aspect ratio above 4:1, any side under 1.2 m (hallway under 0.9 m), or total area outside 15-400 m²."""
    violations = []
    total_area = 0.0
    for room in plan.rooms:
        area = room.w * room.h
        total_area += area
        ratio = max(room.w, room.h) / max(min(room.w, room.h), 0.01)
        min_side = MIN_SIDE_HALLWAY if room.type == "hallway" else MIN_SIDE

        if ratio > MAX_ASPECT_RATIO:
            violations.append(
                Violation(
                    rule="R08",
                    severity="warning",
                    room_ids=[room.id],
                    message=f"'{room.name}' has an aspect ratio of {ratio:.1f}:1 (maximum {MAX_ASPECT_RATIO}:1).",
                    suggested_fix=f"Make '{room.name}' more square.",
                    region=room_rect(room),
                )
            )
        if min(room.w, room.h) < min_side:
            violations.append(
                Violation(
                    rule="R08",
                    severity="warning",
                    room_ids=[room.id],
                    message=f"'{room.name}' has a side shorter than {min_side} m.",
                    suggested_fix=f"Make the shortest side of '{room.name}' at least {min_side} m.",
                    region=room_rect(room),
                )
            )

    if total_area < MIN_TOTAL_AREA:
        violations.append(
            Violation(
                rule="R08",
                severity="warning",
                room_ids=[],
                message=f"Total plan area is {total_area:.1f} m² — below the {MIN_TOTAL_AREA} m² minimum.",
                suggested_fix="Enlarge the overall plan.",
            )
        )
    elif total_area > MAX_TOTAL_AREA:
        violations.append(
            Violation(
                rule="R08",
                severity="warning",
                room_ids=[],
                message=f"Total plan area is {total_area:.1f} m² — above the {MAX_TOTAL_AREA} m² maximum.",
                suggested_fix="Reduce the overall plan size.",
            )
        )
    return violations


# ---------------------------------------------------------------------------
# R09: Door widths
# ---------------------------------------------------------------------------
def r09_door_widths(plan: Plan) -> list[Violation]:
    """Interior doors outside 0.7-1.2 m, or exterior door under 0.9 m."""
    violations = []
    room_map = {r.id: r for r in plan.rooms}
    for door in plan.doors:
        from_name = room_map[door.from_].name if door.from_ in room_map else door.from_
        if door.to == "outside":
            if door.width < MIN_EXTERIOR_DOOR_WIDTH:
                violations.append(
                    Violation(
                        rule="R09",
                        severity="warning",
                        room_ids=[door.from_],
                        message=f"Exterior door in '{from_name}' is {door.width:.2f} m wide (minimum {MIN_EXTERIOR_DOOR_WIDTH} m).",
                        suggested_fix=f"Widen the exterior door in '{from_name}' to at least {MIN_EXTERIOR_DOOR_WIDTH} m.",
                    )
                )
        else:
            to_name = room_map[door.to].name if door.to in room_map else door.to
            if door.width < MIN_INTERIOR_DOOR_WIDTH or door.width > MAX_INTERIOR_DOOR_WIDTH:
                violations.append(
                    Violation(
                        rule="R09",
                        severity="warning",
                        room_ids=[door.from_],
                        message=f"Door between '{from_name}' and '{to_name}' is {door.width:.2f} m wide (expected {MIN_INTERIOR_DOOR_WIDTH}–{MAX_INTERIOR_DOOR_WIDTH} m).",
                        suggested_fix=f"Resize the door between '{from_name}' and '{to_name}' to {MIN_INTERIOR_DOOR_WIDTH}–{MAX_INTERIOR_DOOR_WIDTH} m.",
                    )
                )
    return violations


# ---------------------------------------------------------------------------
# R10: Bathroom privacy
# ---------------------------------------------------------------------------
PRIVACY_SENSITIVE = {"kitchen", "dining"}


def r10_bathroom_privacy(plan: Plan) -> list[Violation]:
    """A bathroom door should not open directly from a kitchen or dining room."""
    violations = []
    room_map = {r.id: r for r in plan.rooms}
    for door in plan.doors:
        if door.to == "outside":
            continue
        # Check if one side is a bathroom and the other is kitchen/dining.
        from_room = room_map.get(door.from_)
        to_room = room_map.get(door.to)
        if not from_room or not to_room:
            continue
        pairs = [(from_room, to_room), (to_room, from_room)]
        for bathroom, other in pairs:
            if bathroom.type == "bathroom" and other.type in PRIVACY_SENSITIVE:
                violations.append(
                    Violation(
                        rule="R10",
                        severity="warning",
                        room_ids=[bathroom.id, other.id],
                        message=f"'{bathroom.name}' opens directly into '{other.name}' ({other.type}).",
                        suggested_fix=f"Route the door to '{bathroom.name}' through a hallway or bedroom instead of '{other.name}'.",
                        region=room_rect(bathroom),
                    )
                )
                break  # One violation per door.
    return violations


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------
RULES = [
    r01_no_overlap,
    r02_has_entrance,
    r03_all_reachable,
    r04_habitable_window,
    r05_doors_on_walls,
    r06_windows_exterior,
    r07_min_area,
    r08_proportions,
    r09_door_widths,
    r10_bathroom_privacy,
]

RULE_CATALOGUE = [
    {"id": "R01", "severity": "error", "description": "No room overlap"},
    {"id": "R02", "severity": "error", "description": "Plan has an entrance"},
    {"id": "R03", "severity": "error", "description": "All rooms reachable"},
    {"id": "R04", "severity": "error", "description": "Habitable rooms have windows"},
    {"id": "R05", "severity": "error", "description": "Doors on real walls"},
    {"id": "R06", "severity": "error", "description": "Windows on exterior walls"},
    {"id": "R07", "severity": "warning", "description": "Minimum room areas"},
    {"id": "R08", "severity": "warning", "description": "Plausible proportions"},
    {"id": "R09", "severity": "warning", "description": "Door widths"},
    {"id": "R10", "severity": "warning", "description": "Bathroom privacy"},
]
