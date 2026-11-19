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
    # Use raw deflate (wbits=-15) for browser DecompressionStream compatibility
    compressor = zlib.compressobj(level=9, wbits=-15)
    compressed = compressor.compress(raw.encode("utf-8")) + compressor.flush()
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
    # Try raw deflate first (wbits=-15), fall back to zlib format (wbits=15)
    try:
        raw = zlib.decompress(compressed, wbits=-15)
    except zlib.error:
        raw = zlib.decompress(compressed)
    return json.loads(raw)


def viewer_url(plan_dict: dict, base_url: str = "http://localhost:3000") -> str:
    """Build a URL that opens the plan in the viewer."""
    encoded = encode_plan(plan_dict)
    # Strip trailing slash from base_url, then use /index.html to avoid redirects.
    base = base_url.rstrip("/")
    return f"{base}/index.html#plan={encoded}"
