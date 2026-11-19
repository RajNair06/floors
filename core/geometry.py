"""Geometry helpers for axis-aligned rectangles.

All coordinates in metres. y grows downward in 2D view.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from core.config import EPS

if TYPE_CHECKING:
    from core.schema import Plan, Room


def overlap_area(r1: Room, r2: Room) -> float:
    """Area of intersection between two rooms' interiors."""
    x_overlap = max(
        0.0, min(r1.x + r1.w, r2.x + r2.w) - max(r1.x, r2.x)
    )
    y_overlap = max(
        0.0, min(r1.y + r1.h, r2.y + r2.h) - max(r1.y, r2.y)
    )
    return x_overlap * y_overlap


def room_rect(room: Room) -> dict:
    """Return {x, y, w, h} for a room."""
    return {"x": room.x, "y": room.y, "w": room.w, "h": room.h}


def wall_segment(room: Room, wall: str) -> tuple[float, float, float, float]:
    """Return (x1, y1, x2, y2) for a wall of a room.

    N = top edge, S = bottom edge, W = left edge, E = right edge.
    """
    if wall == "N":
        return (room.x, room.y, room.x + room.w, room.y)
    elif wall == "S":
        return (room.x, room.y + room.h, room.x + room.w, room.y + room.h)
    elif wall == "W":
        return (room.x, room.y, room.x, room.y + room.h)
    else:  # E
        return (room.x + room.w, room.y, room.x + room.w, room.y + room.h)


def shared_edge(r1: Room, r2: Room) -> list[tuple[str, str, float, float]]:
    """Find shared edges between two rooms.

    Returns list of (wall1, wall2, start, length) where wall1 is on r1 and wall2 is on r2.
    start is the coordinate along the shared edge where they touch.
    """
    edges = []
    # Check if r1's east wall touches r2's west wall.
    if abs((r1.x + r1.w) - r2.x) < EPS:
        y_start = max(r1.y, r2.y)
        y_end = min(r1.y + r1.h, r2.y + r2.h)
        if y_end - y_start > EPS:
            edges.append(("E", "W", y_start, y_end - y_start))
    # Check if r1's west wall touches r2's east wall.
    if abs(r1.x - (r2.x + r2.w)) < EPS:
        y_start = max(r1.y, r2.y)
        y_end = min(r1.y + r1.h, r2.y + r2.h)
        if y_end - y_start > EPS:
            edges.append(("W", "E", y_start, y_end - y_start))
    # Check if r1's south wall touches r2's north wall.
    if abs((r1.y + r1.h) - r2.y) < EPS:
        x_start = max(r1.x, r2.x)
        x_end = min(r1.x + r1.w, r2.x + r2.w)
        if x_end - x_start > EPS:
            edges.append(("S", "N", x_start, x_end - x_start))
    # Check if r1's north wall touches r2's south wall.
    if abs(r1.y - (r2.y + r2.h)) < EPS:
        x_start = max(r1.x, r2.x)
        x_end = min(r1.x + r1.w, r2.x + r2.w)
        if x_end - x_start > EPS:
            edges.append(("N", "S", x_start, x_end - x_start))
    return edges


def is_exterior_wall(room: Room, wall: str, all_rooms: list[Room]) -> bool:
    """Check if a wall of a room is exterior (not shared with another room)."""
    for other in all_rooms:
        if other.id == room.id:
            continue
        for wall1, wall2, _, length in shared_edge(room, other):
            if wall1 == wall and length > EPS:
                return False
    return True


def wall_length(room: Room, wall: str) -> float:
    """Length of a wall in metres."""
    if wall in ("N", "S"):
        return room.w
    else:
        return room.h
