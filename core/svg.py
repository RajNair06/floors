"""Render a floor plan to SVG.

Optionally overlay violation regions tinted by severity.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.schema import Plan, Violation


# Colour palette.
ROOM_COLOURS = {
    "living": "#e8f4f8",
    "kitchen": "#fef3c7",
    "dining": "#fde8e8",
    "bedroom": "#e0e7ff",
    "bathroom": "#d1fae5",
    "hallway": "#f3f4f6",
    "study": "#fef9c3",
    "utility": "#e5e7eb",
    "storage": "#d6d3d1",
}

ERROR_COLOUR = "rgba(239, 68, 68, 0.25)"
WARNING_COLOUR = "rgba(251, 191, 36, 0.25)"

SCALE = 40  # pixels per metre.
MARGIN = 20  # pixels.


def render_svg(plan: Plan, violations: list[Violation] | None = None) -> str:
    """Render a plan to an SVG string."""
    if not plan.rooms:
        return '<svg xmlns="http://www.w3.org/2000/svg" width="200" height="100"><text x="10" y="50">Empty plan</text></svg>'

    # Compute bounds.
    min_x = min(r.x for r in plan.rooms)
    min_y = min(r.y for r in plan.rooms)
    max_x = max(r.x + r.w for r in plan.rooms)
    max_y = max(r.y + r.h for r in plan.rooms)

    width_px = int((max_x - min_x) * SCALE) + 2 * MARGIN
    height_px = int((max_y - min_y) * SCALE) + 2 * MARGIN

    def tx(x: float) -> float:
        return (x - min_x) * SCALE + MARGIN

    def ty(y: float) -> float:
        return (y - min_y) * SCALE + MARGIN

    parts: list[str] = []
    parts.append(
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width_px}" height="{height_px}" '
        f'viewBox="0 0 {width_px} {height_px}">'
    )

    # Background.
    parts.append(
        f'<rect width="{width_px}" height="{height_px}" fill="#fafafa"/>'
    )

    # Draw rooms.
    for room in plan.rooms:
        colour = ROOM_COLOURS.get(room.type, "#f5f5f5")
        x = tx(room.x)
        y = ty(room.y)
        w = room.w * SCALE
        h = room.h * SCALE
        parts.append(
            f'<rect x="{x}" y="{y}" width="{w}" height="{h}" '
            f'fill="{colour}" stroke="#374151" stroke-width="2" rx="2"/>'
        )
        # Room label.
        cx = x + w / 2
        cy = y + h / 2
        parts.append(
            f'<text x="{cx}" y="{cy}" text-anchor="middle" dominant-baseline="middle" '
            f'font-size="12" font-family="system-ui" fill="#1f2937">{room.name}</text>'
        )
        # Area label.
        area = room.w * room.h
        parts.append(
            f'<text x="{cx}" y="{cy + 14}" text-anchor="middle" '
            f'font-size="10" font-family="system-ui" fill="#6b7280">{area:.1f} m²</text>'
        )

    # Draw doors.
    for door in plan.doors:
        # Find the room.
        room = next((r for r in plan.rooms if r.id == door.from_), None)
        if not room:
            continue
        # Compute door position on wall.
        if door.wall == "N":
            dx = tx(room.x + door.offset)
            dy = ty(room.y)
            dw = door.width * SCALE
            dh = 4
        elif door.wall == "S":
            dx = tx(room.x + door.offset)
            dy = ty(room.y + room.h) - 2
            dw = door.width * SCALE
            dh = 4
        elif door.wall == "W":
            dx = tx(room.x)
            dy = ty(room.y + door.offset)
            dw = 4
            dh = door.width * SCALE
        else:  # E
            dx = tx(room.x + room.w) - 2
            dy = ty(room.y + door.offset)
            dw = 4
            dh = door.width * SCALE
        colour = "#059669" if door.to == "outside" else "#2563eb"
        parts.append(
            f'<rect x="{dx}" y="{dy}" width="{dw}" height="{dh}" fill="{colour}"/>'
        )

    # Draw windows.
    for window in plan.windows:
        room = next((r for r in plan.rooms if r.id == window.room), None)
        if not room:
            continue
        if window.wall == "N":
            wx = tx(room.x + window.offset)
            wy = ty(room.y) - 2
            ww = window.width * SCALE
            wh = 4
        elif window.wall == "S":
            wx = tx(room.x + window.offset)
            wy = ty(room.y + room.h) - 2
            ww = window.width * SCALE
            wh = 4
        elif window.wall == "W":
            wx = tx(room.x) - 2
            wy = ty(room.y + window.offset)
            ww = 4
            wh = window.width * SCALE
        else:  # E
            wx = tx(room.x + room.w) - 2
            wy = ty(room.y + window.offset)
            ww = 4
            wh = window.width * SCALE
        parts.append(
            f'<rect x="{wx}" y="{wy}" width="{ww}" height="{wh}" fill="#7dd3fc"/>'
        )

    # Violation overlays.
    if violations:
        for v in violations:
            if not v.region:
                continue
            colour = ERROR_COLOUR if v.severity == "error" else WARNING_COLOUR
            rx = tx(v.region["x"])
            ry = ty(v.region["y"])
            rw = v.region["w"] * SCALE
            rh = v.region["h"] * SCALE
            parts.append(
                f'<rect x="{rx}" y="{ry}" width="{rw}" height="{rh}" '
                f'fill="{colour}" stroke="#dc2626" stroke-width="1" stroke-dasharray="4"/>'
            )

    parts.append("</svg>")
    return "\n".join(parts)
