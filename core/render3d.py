"""Server-side 3D rendering: generate GLB files from floor plans."""

from __future__ import annotations

import base64
import struct
from dataclasses import dataclass, field

import pygltflib

from core.schema import Plan, plan_to_dict

WALL_THICKNESS = 0.08
DOOR_HEIGHT = 2.1
WINDOW_BOTTOM = 0.9
WINDOW_HEIGHT = 1.2

ROOM_COLOURS = {
    "living": (0.910, 0.957, 0.973),
    "kitchen": (0.996, 0.953, 0.780),
    "dining": (0.992, 0.910, 0.910),
    "bedroom": (0.878, 0.906, 1.000),
    "bathroom": (0.820, 0.980, 0.898),
    "hallway": (0.953, 0.957, 0.965),
    "study": (0.996, 0.976, 0.765),
    "utility": (0.898, 0.906, 0.922),
    "storage": (0.839, 0.827, 0.820),
}

WALL_COLOUR = (0.961, 0.961, 0.941)
DOOR_COLOUR = (0.145, 0.388, 0.922)
EXTERIOR_DOOR_COLOUR = (0.020, 0.588, 0.412)
WINDOW_COLOUR = (0.490, 0.827, 0.988)

_DEFAULT_ROOM_COLOUR = (0.961, 0.961, 0.961)


@dataclass
class _BoxSpec:
    cx: float
    cy: float
    cz: float
    w: float
    h: float
    d: float
    colour: tuple[float, float, float]
    opacity: float = 1.0


def _box_geometry(w: float, h: float, d: float) -> tuple[bytes, bytes, bytes]:
    """Generate index, position, and normal data for an axis-aligned box."""
    hw, hh, hd = w / 2, h / 2, d / 2

    vertices = [
        (-hw, -hh, hd), (hw, -hh, hd), (hw, hh, hd), (-hw, hh, hd),          # front
        (hw, -hh, -hd), (-hw, -hh, -hd), (-hw, hh, -hd), (hw, hh, -hd),      # back
        (-hw, hh, hd), (hw, hh, hd), (hw, hh, -hd), (-hw, hh, -hd),          # top
        (-hw, -hh, -hd), (hw, -hh, -hd), (hw, -hh, hd), (-hw, -hh, hd),      # bottom
        (hw, -hh, hd), (hw, -hh, -hd), (hw, hh, -hd), (hw, hh, hd),          # right
        (-hw, -hh, -hd), (-hw, -hh, hd), (-hw, hh, hd), (-hw, hh, -hd),      # left
    ]
    normals = (
        [(0, 0, 1)] * 4 + [(0, 0, -1)] * 4 + [(0, 1, 0)] * 4
        + [(0, -1, 0)] * 4 + [(1, 0, 0)] * 4 + [(-1, 0, 0)] * 4
    )
    indices = []
    for face in range(6):
        base = face * 4
        indices.extend([base, base + 1, base + 2, base, base + 2, base + 3])

    index_data = struct.pack(f"<{len(indices)}H", *indices)
    pos_data = struct.pack(f"<{len(vertices) * 3}f", *(c for v in vertices for c in v))
    norm_data = struct.pack(f"<{len(normals) * 3}f", *(c for n in normals for c in n))

    return index_data, pos_data, norm_data


def _pad4(data: bytes) -> bytes:
    """Pad data to 4-byte alignment."""
    remainder = len(data) % 4
    if remainder:
        data += b"\x00" * (4 - remainder)
    return data


def render_glb(plan: Plan, ceiling_height: float = 2.7) -> bytes:
    """Render a floor plan as a GLB file.

    Args:
        plan: The parsed floor plan.
        ceiling_height: Height of walls in metres.

    Returns:
        GLB file as bytes.
    """
    plan_dict = plan_to_dict(plan)

    # Compute scene center
    if not plan.rooms:
        cx, cz = 0.0, 0.0
    else:
        min_x = min(r.x for r in plan.rooms)
        max_x = max(r.x + r.w for r in plan.rooms)
        min_y = min(r.y for r in plan.rooms)
        max_y = max(r.y + r.h for r in plan.rooms)
        cx = (min_x + max_x) / 2
        cz = (min_y + max_y) / 2

    def map_x(x: float) -> float:
        return x - cx

    def map_z(y: float) -> float:
        return -(y - cz)

    # Collect all box specs
    boxes: list[_BoxSpec] = []

    # Rooms: floor + 4 walls
    for room in plan.rooms:
        px = map_x(room.x + room.w / 2)
        pz = map_z(room.y + room.h / 2)
        colour = ROOM_COLOURS.get(room.type, _DEFAULT_ROOM_COLOUR)

        # Floor
        boxes.append(_BoxSpec(px, 0.025, pz, room.w, 0.05, room.h, colour))

        # Walls
        wh = ceiling_height
        boxes.append(_BoxSpec(px, wh / 2, pz + room.h / 2, room.w, wh, WALL_THICKNESS, WALL_COLOUR))
        boxes.append(_BoxSpec(px, wh / 2, pz - room.h / 2, room.w, wh, WALL_THICKNESS, WALL_COLOUR))
        boxes.append(_BoxSpec(px - room.w / 2, wh / 2, pz, WALL_THICKNESS, wh, room.h, WALL_COLOUR))
        boxes.append(_BoxSpec(px + room.w / 2, wh / 2, pz, WALL_THICKNESS, wh, room.h, WALL_COLOUR))

    # Doors
    for door in plan.doors:
        from_room = next((r for r in plan.rooms if r.id == door.from_), None)
        if not from_room:
            continue
        px = map_x(from_room.x)
        pz = map_z(from_room.y)
        is_exterior = door.to == "outside"
        colour = EXTERIOR_DOOR_COLOUR if is_exterior else DOOR_COLOUR
        dh = min(DOOR_HEIGHT, ceiling_height)

        if door.wall == "N":
            dx, dz = px + door.offset + door.width / 2, pz + from_room.h / 2
            dw, dd = door.width, WALL_THICKNESS + 0.02
        elif door.wall == "S":
            dx, dz = px + door.offset + door.width / 2, pz - from_room.h / 2
            dw, dd = door.width, WALL_THICKNESS + 0.02
        elif door.wall == "W":
            dx, dz = px - from_room.w / 2, pz - (door.offset + door.width / 2 - from_room.h / 2)
            dw, dd = WALL_THICKNESS + 0.02, door.width
        else:  # E
            dx, dz = px + from_room.w / 2, pz - (door.offset + door.width / 2 - from_room.h / 2)
            dw, dd = WALL_THICKNESS + 0.02, door.width

        boxes.append(_BoxSpec(dx, dh / 2, dz, dw, dh, dd, colour))

    # Windows
    for window in plan.windows:
        room = next((r for r in plan.rooms if r.id == window.room), None)
        if not room:
            continue
        px = map_x(room.x)
        pz = map_z(room.y)
        wb = min(WINDOW_BOTTOM, ceiling_height - WINDOW_HEIGHT)
        wh = min(WINDOW_HEIGHT, ceiling_height - wb)

        if window.wall == "N":
            wx, wz = px + window.offset + window.width / 2, pz + room.h / 2
            ww, wd = window.width, WALL_THICKNESS + 0.03
        elif window.wall == "S":
            wx, wz = px + window.offset + window.width / 2, pz - room.h / 2
            ww, wd = window.width, WALL_THICKNESS + 0.03
        elif window.wall == "W":
            wx, wz = px - room.w / 2, pz - (window.offset + window.width / 2 - room.h / 2)
            ww, wd = WALL_THICKNESS + 0.03, window.width
        else:  # E
            wx, wz = px + room.w / 2, pz - (window.offset + window.width / 2 - room.h / 2)
            ww, wd = WALL_THICKNESS + 0.03, window.width

        boxes.append(_BoxSpec(wx, wb + wh / 2, wz, ww, wh, wd, WINDOW_COLOUR, 0.6))

    if not boxes:
        # Empty plan — return a minimal valid GLB
        return _build_glb([])

    return _build_glb(boxes)


def _build_glb(boxes: list[_BoxSpec]) -> bytes:
    """Build a GLB file from a list of box specifications."""
    gltf = pygltflib.GLTF2()
    gltf.scenes.append(pygltflib.Scene(nodes=[0]))
    gltf.scene = 0

    # Root node; children will be added below.
    root = pygltflib.Node(children=[])
    gltf.nodes.append(root)

    # Single buffer; all data concatenated.
    gltf.buffers.append(pygltflib.Buffer(byteLength=0))  # updated at end

    blob = b""
    children: list[int] = []

    for box in boxes:
        idx_data, pos_data, norm_data = _box_geometry(box.w, box.h, box.d)

        # Align each chunk to 4 bytes
        idx_data = _pad4(idx_data)
        pos_data = _pad4(pos_data)
        norm_data = _pad4(norm_data)

        idx_offset = len(blob)
        blob += idx_data
        pos_offset = len(blob)
        blob += pos_data
        norm_offset = len(blob)
        blob += norm_data

        # Buffer views
        idx_view = len(gltf.bufferViews)
        gltf.bufferViews.append(pygltflib.BufferView(
            buffer=0, byteOffset=idx_offset, byteLength=len(idx_data),
            target=pygltflib.ELEMENT_ARRAY_BUFFER,
        ))
        pos_view = idx_view + 1
        gltf.bufferViews.append(pygltflib.BufferView(
            buffer=0, byteOffset=pos_offset, byteLength=len(pos_data),
            target=pygltflib.ARRAY_BUFFER,
        ))
        norm_view = pos_view + 1
        gltf.bufferViews.append(pygltflib.BufferView(
            buffer=0, byteOffset=norm_offset, byteLength=len(norm_data),
            target=pygltflib.ARRAY_BUFFER,
        ))

        # Compute bounding box
        n_verts = len(pos_data) // (4 * 3)
        floats = struct.unpack_from(f"<{n_verts * 3}f", pos_data)
        xs = [floats[i * 3] for i in range(n_verts)]
        ys = [floats[i * 3 + 1] for i in range(n_verts)]
        zs = [floats[i * 3 + 2] for i in range(n_verts)]

        # Accessors
        idx_acc = len(gltf.accessors)
        gltf.accessors.append(pygltflib.Accessor(
            bufferView=idx_view,
            componentType=pygltflib.UNSIGNED_SHORT,
            count=len(idx_data) // 2,  # 2 bytes per unsigned short (before padding)
            type=pygltflib.SCALAR,
            max=[23], min=[0],  # box always has 24 vertices (0-23)
        ))
        pos_acc = idx_acc + 1
        gltf.accessors.append(pygltflib.Accessor(
            bufferView=pos_view,
            componentType=pygltflib.FLOAT,
            count=n_verts,
            type=pygltflib.VEC3,
            max=[max(xs), max(ys), max(zs)],
            min=[min(xs), min(ys), min(zs)],
        ))
        norm_acc = pos_acc + 1
        n_norms = len(norm_data) // (4 * 3)
        gltf.accessors.append(pygltflib.Accessor(
            bufferView=norm_view,
            componentType=pygltflib.FLOAT,
            count=n_norms,
            type=pygltflib.VEC3,
        ))

        # Material
        mat_idx = len(gltf.materials)
        alpha_mode = pygltflib.OPAQUE if box.opacity >= 1.0 else pygltflib.BLEND
        gltf.materials.append(pygltflib.Material(
            pbrMetallicRoughness=pygltflib.PbrMetallicRoughness(
                baseColorFactor=[*box.colour, box.opacity],
                metallicFactor=0.0,
                roughnessFactor=0.6,
            ),
            alphaMode=alpha_mode,
            doubleSided=True,
        ))

        # Mesh + node
        mesh_idx = len(gltf.meshes)
        # Use the unpadded index count (36 indices per box = 12 triangles)
        gltf.meshes.append(pygltflib.Mesh(
            primitives=[pygltflib.Primitive(
                attributes={"POSITION": pos_acc, "NORMAL": norm_acc},
                indices=idx_acc,
                mode=pygltflib.TRIANGLES,
                material=mat_idx,
            )]
        ))

        node_idx = len(gltf.nodes)
        gltf.nodes.append(pygltflib.Node(
            mesh=mesh_idx,
            translation=[box.cx, box.cy, box.cz],
        ))
        children.append(node_idx)

    root.children = children

    # Update buffer length
    gltf.buffers[0].byteLength = len(blob)

    # Set binary blob and export
    gltf.set_binary_blob(blob)
    chunks = gltf.save_to_bytes()
    return b"".join(chunks)


def render_glb_base64(plan: Plan, ceiling_height: float = 2.7) -> str:
    """Render a floor plan as a base64-encoded GLB file."""
    glb_bytes = render_glb(plan, ceiling_height)
    return base64.b64encode(glb_bytes).decode("ascii")
