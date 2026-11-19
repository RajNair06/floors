"""Tests for core rules."""

import copy

from core.schema import Plan
from core.score import validate, score


def _plan(data: dict) -> Plan:
    return Plan.model_validate(data)


def _copy(data: dict) -> dict:
    return copy.deepcopy(data)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

VALID_PLAN = {
    "schema_version": "1.0",
    "id": "valid_01",
    "units": "m",
    "ceiling_height": 2.7,
    "rooms": [
        {"id": "r1", "type": "living", "name": "Living room", "x": 0, "y": 0, "w": 5.0, "h": 4.0},
        {"id": "r2", "type": "bedroom", "name": "Bedroom 1", "x": 5.0, "y": 0, "w": 3.5, "h": 4.0},
    ],
    "doors": [
        {"id": "d1", "from": "r1", "to": "outside", "wall": "S", "offset": 1.0, "width": 1.0},
        {"id": "d2", "from": "r1", "to": "r2", "wall": "E", "offset": 1.5, "width": 0.9},
    ],
    "windows": [
        {"id": "w1", "room": "r1", "wall": "N", "offset": 1.0, "width": 1.5},
        {"id": "w2", "room": "r2", "wall": "N", "offset": 0.5, "width": 1.2},
    ],
}


# ---------------------------------------------------------------------------
# R01: No overlap
# ---------------------------------------------------------------------------
def test_r01_pass():
    plan = _plan(VALID_PLAN)
    violations = [v for v in validate(plan) if v.rule == "R01"]
    assert len(violations) == 0


def test_r01_fail():
    data = dict(VALID_PLAN)
    data["rooms"] = [
        {"id": "r1", "type": "living", "name": "Living", "x": 0, "y": 0, "w": 5.0, "h": 4.0},
        {"id": "r2", "type": "bedroom", "name": "Bedroom", "x": 2.0, "y": 0, "w": 5.0, "h": 4.0},
    ]
    plan = _plan(data)
    violations = [v for v in validate(plan) if v.rule == "R01"]
    assert len(violations) > 0


# ---------------------------------------------------------------------------
# R02: Has entrance
# ---------------------------------------------------------------------------
def test_r02_pass():
    plan = _plan(VALID_PLAN)
    violations = [v for v in validate(plan) if v.rule == "R02"]
    assert len(violations) == 0


def test_r02_fail():
    data = dict(VALID_PLAN)
    data["doors"] = [d for d in data["doors"] if d["to"] != "outside"]
    plan = _plan(data)
    violations = [v for v in validate(plan) if v.rule == "R02"]
    assert len(violations) > 0


# ---------------------------------------------------------------------------
# R03: All rooms reachable
# ---------------------------------------------------------------------------
def test_r03_pass():
    plan = _plan(VALID_PLAN)
    violations = [v for v in validate(plan) if v.rule == "R03"]
    assert len(violations) == 0


def test_r03_fail():
    data = dict(VALID_PLAN)
    # Add an isolated room.
    data["rooms"] = list(data["rooms"]) + [
        {"id": "r3", "type": "bedroom", "name": "Isolated", "x": 20.0, "y": 0, "w": 3.0, "h": 3.0}
    ]
    data["windows"] = list(data["windows"]) + [
        {"id": "w3", "room": "r3", "wall": "N", "offset": 0.5, "width": 1.0}
    ]
    plan = _plan(data)
    violations = [v for v in validate(plan) if v.rule == "R03"]
    assert len(violations) > 0


# ---------------------------------------------------------------------------
# R04: Habitable rooms have a window
# ---------------------------------------------------------------------------
def test_r04_pass():
    plan = _plan(VALID_PLAN)
    violations = [v for v in validate(plan) if v.rule == "R04"]
    assert len(violations) == 0


def test_r04_fail():
    data = dict(VALID_PLAN)
    # Remove bedroom window.
    data["windows"] = [w for w in data["windows"] if w["room"] != "r2"]
    plan = _plan(data)
    violations = [v for v in validate(plan) if v.rule == "R04"]
    assert len(violations) > 0


# ---------------------------------------------------------------------------
# R05: Doors sit on real walls
# ---------------------------------------------------------------------------
def test_r05_pass():
    plan = _plan(VALID_PLAN)
    violations = [v for v in validate(plan) if v.rule == "R05"]
    assert len(violations) == 0


def test_r05_fail():
    data = dict(VALID_PLAN)
    # Door between r1 and r2 on wall N (not shared).
    data["doors"] = [
        {"id": "d1", "from": "r1", "to": "outside", "wall": "S", "offset": 1.0, "width": 1.0},
        {"id": "d2", "from": "r1", "to": "r2", "wall": "N", "offset": 1.0, "width": 0.9},
    ]
    plan = _plan(data)
    violations = [v for v in validate(plan) if v.rule == "R05"]
    assert len(violations) > 0


# ---------------------------------------------------------------------------
# R06: Windows sit on exterior walls
# ---------------------------------------------------------------------------
def test_r06_pass():
    plan = _plan(VALID_PLAN)
    violations = [v for v in validate(plan) if v.rule == "R06"]
    assert len(violations) == 0


def test_r06_fail():
    # r1 and r2 share the E/W wall. A window on that wall should fail.
    data = dict(VALID_PLAN)
    data["windows"] = [
        {"id": "w1", "room": "r1", "wall": "N", "offset": 1.0, "width": 1.5},
        {"id": "w2", "room": "r2", "wall": "N", "offset": 0.5, "width": 1.2},
        {"id": "w3", "room": "r1", "wall": "E", "offset": 1.0, "width": 1.0},  # interior wall
    ]
    plan = _plan(data)
    violations = [v for v in validate(plan) if v.rule == "R06"]
    assert len(violations) > 0


# ---------------------------------------------------------------------------
# R07: Minimum room areas
# ---------------------------------------------------------------------------
def test_r07_pass():
    plan = _plan(VALID_PLAN)
    violations = [v for v in validate(plan) if v.rule == "R07"]
    assert len(violations) == 0


def test_r07_fail():
    data = _copy(VALID_PLAN)
    data["rooms"][1] = {"id": "r2", "type": "bedroom", "name": "Tiny bedroom", "x": 5.0, "y": 0, "w": 2.0, "h": 2.0}
    plan = _plan(data)
    violations = [v for v in validate(plan) if v.rule == "R07"]
    assert len(violations) > 0


# ---------------------------------------------------------------------------
# R08: Plausible proportions
# ---------------------------------------------------------------------------
def test_r08_pass():
    plan = _plan(VALID_PLAN)
    violations = [v for v in validate(plan) if v.rule == "R08"]
    assert len(violations) == 0


def test_r08_fail_aspect():
    data = _copy(VALID_PLAN)
    data["rooms"][0] = {"id": "r1", "type": "living", "name": "Long room", "x": 0, "y": 0, "w": 10.0, "h": 1.5}
    # Fix doors to fit the new wall dimensions.
    data["doors"][0] = {"id": "d1", "from": "r1", "to": "outside", "wall": "N", "offset": 1.0, "width": 1.0}
    data["doors"][1] = {"id": "d2", "from": "r1", "to": "r2", "wall": "E", "offset": 0.2, "width": 0.9}
    plan = _plan(data)
    violations = [v for v in validate(plan) if v.rule == "R08"]
    assert len(violations) > 0


# ---------------------------------------------------------------------------
# R09: Door widths
# ---------------------------------------------------------------------------
def test_r09_pass():
    plan = _plan(VALID_PLAN)
    violations = [v for v in validate(plan) if v.rule == "R09"]
    assert len(violations) == 0


def test_r09_fail():
    data = _copy(VALID_PLAN)
    data["doors"][1] = {"id": "d2", "from": "r1", "to": "r2", "wall": "E", "offset": 1.5, "width": 0.5}
    plan = _plan(data)
    violations = [v for v in validate(plan) if v.rule == "R09"]
    assert len(violations) > 0


# ---------------------------------------------------------------------------
# R10: Bathroom privacy
# ---------------------------------------------------------------------------
def test_r10_pass():
    plan = _plan(VALID_PLAN)
    violations = [v for v in validate(plan) if v.rule == "R10"]
    assert len(violations) == 0


def test_r10_fail():
    data = {
        "schema_version": "1.0",
        "id": "r10_fail",
        "units": "m",
        "ceiling_height": 2.7,
        "rooms": [
            {"id": "r1", "type": "kitchen", "name": "Kitchen", "x": 0, "y": 0, "w": 4.0, "h": 4.0},
            {"id": "r2", "type": "bathroom", "name": "Bathroom", "x": 4.0, "y": 0, "w": 3.0, "h": 3.0},
        ],
        "doors": [
            {"id": "d1", "from": "r1", "to": "outside", "wall": "S", "offset": 1.0, "width": 1.0},
            {"id": "d2", "from": "r1", "to": "r2", "wall": "E", "offset": 0.5, "width": 0.8},
        ],
        "windows": [],
    }
    plan = _plan(data)
    violations = [v for v in validate(plan) if v.rule == "R10"]
    assert len(violations) > 0


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------
def test_score_valid_plan():
    plan = _plan(VALID_PLAN)
    result = score(plan)
    assert result.passed is True
    assert result.score == 1.0


def test_score_with_errors():
    data = dict(VALID_PLAN)
    data["doors"] = [d for d in data["doors"] if d["to"] != "outside"]  # no entrance
    plan = _plan(data)
    result = score(plan)
    assert result.passed is False
    assert result.score < 1.0


# ---------------------------------------------------------------------------
# Schema validation
# ---------------------------------------------------------------------------
def test_schema_rejects_unknown_room_in_door():
    from core.schema import parse_plan

    bad = {
        "schema_version": "1.0",
        "id": "bad",
        "units": "m",
        "rooms": [
            {"id": "r1", "type": "living", "name": "Living", "x": 0, "y": 0, "w": 5.0, "h": 4.0},
        ],
        "doors": [
            {"id": "d1", "from": "r1", "to": "r9", "wall": "S", "offset": 1.0, "width": 1.0},
        ],
        "windows": [],
    }
    try:
        parse_plan(bad)
        assert False, "should have raised"
    except ValueError as e:
        assert e.args[0]["error"] == "schema"
