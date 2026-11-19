"""Encode, decode and build viewer URLs for floor plans.

Encoding: compact JSON → zlib → base64url.
The whole plan travels in the URL fragment, never reaching the server.
"""

from __future__ import annotations

import base64
import json
import zlib

from core.config import MAX_ENCODED_LENGTH


def encode_plan(plan_dict: dict) -> str:
    """Encode a plan dict to a compact base64url string."""
    raw = json.dumps(plan_dict, separators=(",", ":"))
    compressed = zlib.compress(raw.encode("utf-8"))
    encoded = base64.urlsafe_b64encode(compressed).decode("ascii")
    if len(encoded) > MAX_ENCODED_LENGTH:
        raise ValueError(
            f"Encoded plan is {len(encoded)} characters, exceeds {MAX_ENCODED_LENGTH}. "
            "Simplify the plan."
        )
    return encoded


def decode_plan(s: str) -> dict:
    """Decode a base64url string back to a plan dict."""
    # Add padding if needed.
    padding = 4 - len(s) % 4
    if padding != 4:
        s += "=" * padding
    compressed = base64.urlsafe_b64decode(s)
    raw = zlib.decompress(compressed)
    return json.loads(raw)


def viewer_url(plan_dict: dict, base_url: str = "http://localhost:3000") -> str:
    """Build a URL that opens the plan in the viewer."""
    encoded = encode_plan(plan_dict)
    # Strip trailing slash from base_url, then use /index.html to avoid redirects.
    base = base_url.rstrip("/")
    return f"{base}/index.html#plan={encoded}"
