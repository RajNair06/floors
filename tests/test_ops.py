"""Tests for ops.py."""

from core.ops import add_opening, add_room, connect_rooms, new_floorplan, remove_element, update_room
from core.score import score


def test_new_floorplan():
    plan = new_floorplan()
    assert len(plan.rooms) == 0
    assert plan.units == "m"


def test_add_room_absolute():
    plan = new_floorplan()
    plan = add_room(plan, type="living", name="Living", w=5.0, h=4.0, x=0, y=0)
    assert len(plan.rooms) == 1
    assert plan.rooms[0].id == "r1"


def test_add_room_relative():
    plan = new_floorplan()
    plan = add_room(plan, type="living", name="Living", w=5.0, h=4.0, x=0, y=0)
    plan = add_room(plan, type="bedroom", name="Bedroom", w=3.5, h=4.0, relative_to="r1", side="E")
    assert plan.rooms[1].x == 5.0  # flush with r1's east edge


def test_connect_rooms():
    plan = new_floorplan()
    plan = add_room(plan, type="living", name="Living", w=5.0, h=4.0, x=0, y=0)
    plan = add_room(plan, type="bedroom", name="Bedroom", w=3.5, h=4.0, relative_to="r1", side="E")
    plan = connect_rooms(plan, "r1", "r2")
    assert len(plan.doors) == 1
    assert plan.doors[0].from_ == "r1"
    assert plan.doors[0].to == "r2"


def test_connect_rooms_no_shared_wall():
    plan = new_floorplan()
    plan = add_room(plan, type="living", name="Living", w=5.0, h=4.0, x=0, y=0)
    plan = add_room(plan, type="bedroom", name="Bedroom", w=3.5, h=4.0, x=20.0, y=0)
    try:
        connect_rooms(plan, "r1", "r2")
        assert False, "should have raised"
    except ValueError as e:
        assert "share no wall" in str(e)


def test_add_opening_window():
    plan = new_floorplan()
    plan = add_room(plan, type="living", name="Living", w=5.0, h=4.0, x=0, y=0)
    plan = add_opening(plan, kind="window", room="r1", wall="N", width=1.5)
    assert len(plan.windows) == 1


def test_add_opening_entrance():
    plan = new_floorplan()
    plan = add_room(plan, type="living", name="Living", w=5.0, h=4.0, x=0, y=0)
    plan = add_opening(plan, kind="entrance", room="r1", wall="S", width=1.0)
    assert len(plan.doors) == 1
    assert plan.doors[0].to == "outside"


def test_update_room():
    plan = new_floorplan()
    plan = add_room(plan, type="living", name="Living", w=5.0, h=4.0, x=0, y=0)
    plan = update_room(plan, "r1", name="New Living", w=6.0)
    assert plan.rooms[0].name == "New Living"
    assert plan.rooms[0].w == 6.0


def test_remove_element():
    plan = new_floorplan()
    plan = add_room(plan, type="living", name="Living", w=5.0, h=4.0, x=0, y=0)
    plan = add_room(plan, type="bedroom", name="Bedroom", w=3.5, h=4.0, relative_to="r1", side="E")
    plan = connect_rooms(plan, "r1", "r2")
    plan = remove_element(plan, "r2")
    assert len(plan.rooms) == 1
    assert len(plan.doors) == 0  # cascaded


def test_full_build_passes():
    """Build a valid plan with ops and confirm it passes."""
    plan = new_floorplan(id="test_full")
    plan = add_room(plan, type="living", name="Living", w=5.0, h=4.0, x=0, y=0)
    plan = add_room(plan, type="bedroom", name="Bedroom", w=3.5, h=4.0, relative_to="r1", side="E")
    plan = connect_rooms(plan, "r1", "r2")
    plan = add_opening(plan, kind="entrance", room="r1", wall="S", width=1.0)
    plan = add_opening(plan, kind="window", room="r1", wall="N", width=1.5)
    plan = add_opening(plan, kind="window", room="r2", wall="N", width=1.2)
    result = score(plan)
    assert result.passed is True
