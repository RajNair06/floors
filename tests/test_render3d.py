"""Tests for 3D rendering (core/render3d.py)."""

import base64
import struct

import pygltflib
import pytest

from core.render3d import render_glb, render_glb_base64
from core.schema import parse_plan


@pytest.fixture
def simple_plan_dict():
    return {
        "id": "test",
        "rooms": [
            {"id": "r1", "type": "living", "name": "Living", "x": 0, "y": 0, "w": 5.0, "h": 4.0},
        ],
        "doors": [
            {"id": "d1", "from": "r1", "wall": "S", "offset": 1.0, "width": 0.9, "to": "outside"},
        ],
        "windows": [
            {"id": "w1", "room": "r1", "wall": "N", "offset": 1.0, "width": 1.5},
        ],
    }


def test_render_glb_valid_format(simple_plan_dict):
    plan = parse_plan(simple_plan_dict)
    glb = render_glb(plan)

    # Check GLB header
    assert glb[:4] == b"glTF"
    version = struct.unpack_from("<I", glb, 4)[0]
    assert version == 2
    total_length = struct.unpack_from("<I", glb, 8)[0]
    assert total_length == len(glb)


def test_render_glb_box_count(simple_plan_dict):
    plan = parse_plan(simple_plan_dict)
    glb = render_glb(plan)

    # Write to temp file and reload
    import tempfile
    with tempfile.NamedTemporaryFile(suffix=".glb", delete=False) as f:
        f.write(glb)
        path = f.name

    gltf = pygltflib.GLTF2().load(path)

    # 1 room: floor + 4 walls = 5
    # 1 door = 1
    # 1 window = 1
    # Total: 7
    assert len(gltf.meshes) == 7
    assert len(gltf.materials) == 7
    assert len(gltf.nodes) == 8  # 7 mesh nodes + 1 root


def test_render_glb_empty_plan():
    plan = parse_plan({"id": "empty", "rooms": [], "doors": [], "windows": []})
    glb = render_glb(plan)
    assert glb[:4] == b"glTF"
    total_length = struct.unpack_from("<I", glb, 8)[0]
    assert total_length == len(glb)


def test_render_glb_base64(simple_plan_dict):
    plan = parse_plan(simple_plan_dict)
    b64 = render_glb_base64(plan)

    # Should be valid base64
    decoded = base64.b64decode(b64)
    assert decoded[:4] == b"glTF"


def test_render_glb_multi_room():
    plan = parse_plan({
        "id": "multi",
        "rooms": [
            {"id": "r1", "type": "living", "name": "Living", "x": 0, "y": 0, "w": 5.0, "h": 4.0},
            {"id": "r2", "type": "bedroom", "name": "Bedroom", "x": 5, "y": 0, "w": 4.0, "h": 4.0},
        ],
        "doors": [
            {"id": "d1", "from": "r1", "wall": "S", "offset": 1.0, "width": 0.9, "to": "outside"},
            {"id": "d2", "from": "r1", "wall": "E", "offset": 1.5, "width": 0.9, "to": "r2"},
        ],
        "windows": [
            {"id": "w1", "room": "r1", "wall": "N", "offset": 1.0, "width": 1.5},
            {"id": "w2", "room": "r2", "wall": "N", "offset": 1.0, "width": 1.2},
        ],
    })
    glb = render_glb(plan)
    assert glb[:4] == b"glTF"

    # 2 rooms * (1 floor + 4 walls) + 2 doors + 2 windows = 14
    import tempfile
    with tempfile.NamedTemporaryFile(suffix=".glb", delete=False) as f:
        f.write(glb)
        path = f.name

    gltf = pygltflib.GLTF2().load(path)
    assert len(gltf.meshes) == 14


def test_render_glb_custom_ceiling_height(simple_plan_dict):
    plan = parse_plan(simple_plan_dict)
    glb_default = render_glb(plan)
    glb_tall = render_glb(plan, ceiling_height=3.5)

    # Both should be valid GLB
    assert glb_default[:4] == b"glTF"
    assert glb_tall[:4] == b"glTF"

    # Both should have the same number of meshes (same plan structure)
    import tempfile
    with tempfile.NamedTemporaryFile(suffix=".glb", delete=False) as f:
        f.write(glb_default)
        gltf_default = pygltflib.GLTF2().load(f.name)

    with tempfile.NamedTemporaryFile(suffix=".glb", delete=False) as f:
        f.write(glb_tall)
        gltf_tall = pygltflib.GLTF2().load(f.name)

    assert len(gltf_default.meshes) == len(gltf_tall.meshes)
