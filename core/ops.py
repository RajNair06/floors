"""Pure editing operations for floor plans.

Every function takes a plan and returns a new plan. Never mutates input.
Generates deterministic ids (r1, d1, w1).
"""

from __future__ import annotations

import copy
from typing import Optional

from core.geometry import shared_edge, wall_length
from core.schema import Door, Plan, Room, Window


def _next_id(prefix: str, existing: list) -> str:
    """Generate next deterministic id like r1, r2, d1, w1."""
    nums = []
    for item in existing:
        item_id = item.get("id", "") if isinstance(item, dict) else getattr(item, "id", "")
        if item_id.startswith(prefix):
            try:
                nums.append(int(item_id[len(prefix):]))
            except ValueError:
                pass
    return f"{prefix}{max(nums, default=0) + 1}"


def _plan_to_raw(plan: Plan) -> dict:
    """Convert Plan to a plain dict for mutation."""
    return plan.model_dump(by_alias=True)


def _raw_to_plan(data: dict) -> Plan:
    """Convert a plain dict back to Plan."""
    return Plan.model_validate(data)


def new_floorplan(
    id: str = "plan_new",
    units: str = "m",
    ceiling_height: float = 2.7,
) -> Plan:
    """Return an empty valid plan."""
    return Plan(
        id=id,
        units=units,
        ceiling_height=ceiling_height,
        rooms=[],
        doors=[],
        windows=[],
    )


def add_room(
    plan: Plan,
    type: str,
    name: str,
    w: float,
    h: float,
    x: Optional[float] = None,
    y: Optional[float] = None,
    relative_to: Optional[str] = None,
    side: Optional[str] = None,
) -> Plan:
    """Add a room. With relative_to + side, snap flush against that room."""
    data = _plan_to_raw(plan)

    room_id = _next_id("r", data["rooms"])

    if relative_to and side:
        ref = next((r for r in data["rooms"] if r["id"] == relative_to), None)
        if ref is None:
            raise ValueError(f"Room '{relative_to}' not found")
        if side == "E":
            rx = ref["x"] + ref["w"]
            ry = ref["y"]
        elif side == "W":
            rx = ref["x"] - w
            ry = ref["y"]
        elif side == "S":
            rx = ref["x"]
            ry = ref["y"] + ref["h"]
        elif side == "N":
            rx = ref["x"]
            ry = ref["y"] - h
        else:
            raise ValueError(f"Unknown side '{side}', use N/S/E/W")
    elif x is not None and y is not None:
        rx, ry = x, y
    else:
        # Default: place at origin offset.
        rx = 0.0
        ry = 0.0

    data["rooms"].append(
        {"id": room_id, "type": type, "name": name, "x": rx, "y": ry, "w": w, "h": h}
    )
    return _raw_to_plan(data)


def connect_rooms(
    plan: Plan,
    a: str,
    b: str,
    width: float = 0.9,
) -> Plan:
    """Add a door between two rooms that share a wall. Errors if they share no wall."""
    data = _plan_to_raw(plan)

    room_a = next((r for r in data["rooms"] if r["id"] == a), None)
    room_b = next((r for r in data["rooms"] if r["id"] == b), None)
    if room_a is None:
        raise ValueError(f"Room '{a}' not found")
    if room_b is None:
        raise ValueError(f"Room '{b}' not found")

    ra = Room(**room_a)
    rb = Room(**room_b)
    edges = shared_edge(ra, rb)
    if not edges:
        raise ValueError(
            f"{a} and {b} share no wall; place {b} with `relative_to` {a}"
        )

    # Use the first shared edge.
    wall_a, wall_b, start, length = edges[0]
    # Place door at midpoint of shared segment.
    offset = start + length / 2 - width / 2
    if offset < 0:
        offset = 0.0
    # Clamp so door fits.
    if offset + width > length + 0.01:
        offset = max(0.0, length - width)

    door_id = _next_id("d", data["doors"])
    data["doors"].append(
        {
            "id": door_id,
            "from": a,
            "to": b,
            "wall": wall_a,
            "offset": round(offset, 2),
            "width": width,
        }
    )
    return _raw_to_plan(data)


def add_opening(
    plan: Plan,
    kind: str,
    room: str,
    wall: str,
    width: float = 1.0,
    offset: Optional[float] = None,
) -> Plan:
    """Add a window or an exterior door, centred on the wall by default."""
    data = _plan_to_raw(plan)

    room_data = next((r for r in data["rooms"] if r["id"] == room), None)
    if room_data is None:
        raise ValueError(f"Room '{room}' not found")

    wl = wall_length(Room(**room_data), wall)
    if offset is None:
        offset = max(0.0, (wl - width) / 2)

    if kind == "window":
        oid = _next_id("w", data["windows"])
        data["windows"].append(
            {"id": oid, "room": room, "wall": wall, "offset": round(offset, 2), "width": width}
        )
    elif kind == "entrance":
        oid = _next_id("d", data["doors"])
        data["doors"].append(
            {
                "id": oid,
                "from": room,
                "to": "outside",
                "wall": wall,
                "offset": round(offset, 2),
                "width": width,
            }
        )
    else:
        raise ValueError(f"Unknown kind '{kind}', use 'window' or 'entrance'")

    return _raw_to_plan(data)


def update_room(plan: Plan, id: str, **fields) -> Plan:
    """Change type, name, size or position of a room."""
    data = _plan_to_raw(plan)
    room = next((r for r in data["rooms"] if r["id"] == id), None)
    if room is None:
        raise ValueError(f"Room '{id}' not found")
    allowed = {"type", "name", "x", "y", "w", "h"}
    for key, value in fields.items():
        if key in allowed:
            room[key] = value
    return _raw_to_plan(data)


def remove_element(plan: Plan, id: str) -> Plan:
    """Remove a room, door or window. Cascades references."""
    data = _plan_to_raw(plan)

    # Try rooms.
    before = len(data["rooms"])
    data["rooms"] = [r for r in data["rooms"] if r["id"] != id]
    if len(data["rooms"]) < before:
        # Cascade: remove doors and windows referencing this room.
        data["doors"] = [
            d for d in data["doors"] if d["from"] != id and d["to"] != id
        ]
        data["windows"] = [w for w in data["windows"] if w["room"] != id]
        return _raw_to_plan(data)

    # Try doors.
    data["doors"] = [d for d in data["doors"] if d["id"] != id]
    # Try windows.
    data["windows"] = [w for w in data["windows"] if w["id"] != id]

    return _raw_to_plan(data)
