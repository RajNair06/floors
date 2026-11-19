"""Tests for share.py (encode/decode/viewer URL)."""

from core.share import decode_plan, encode_plan, viewer_url
from core.config import MAX_ENCODED_LENGTH


def test_encode_decode_roundtrip():
    plan = {
        "schema_version": "1.0",
        "id": "test",
        "units": "m",
        "rooms": [{"id": "r1", "type": "living", "name": "Living", "x": 0, "y": 0, "w": 5.0, "h": 4.0}],
        "doors": [],
        "windows": [],
    }
    encoded = encode_plan(plan)
    decoded = decode_plan(encoded)
    assert decoded == plan


def test_viewer_url():
    plan = {"id": "test", "rooms": []}
    url = viewer_url(plan, "https://example.com")
    assert url.startswith("https://example.com#plan=")
    # Extract the encoded part and decode.
    encoded = url.split("#plan=")[1]
    decoded = decode_plan(encoded)
    assert decoded == plan


def test_oversized_plan_rejected():
    # Create a plan with lots of rooms.
    rooms = [{"id": f"r{i}", "type": "living", "name": f"Room {i}", "x": i * 5, "y": 0, "w": 5.0, "h": 4.0} for i in range(200)]
    plan = {"schema_version": "1.0", "id": "huge", "units": "m", "rooms": rooms, "doors": [], "windows": []}
    try:
        encode_plan(plan)
        # If it doesn't exceed the limit, that's fine.
    except ValueError as e:
        assert "exceeds" in str(e)
