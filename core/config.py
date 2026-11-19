"""Configuration: thresholds and penalty weights.

All magic numbers live here. Every threshold is an assumption.
"""

# Tolerance for edge-sharing: two edges are "touching" if within this distance (metres).
EPS = 0.05

# Minimum room areas by type (m²).
MIN_ROOM_AREA = {
    "bedroom": 7.0,
    "living": 10.0,
    "kitchen": 4.0,
    "bathroom": 2.5,
    "study": 5.0,
    "dining": 5.0,
    "hallway": 1.5,
    "utility": 2.0,
    "storage": 1.0,
}

# Maximum aspect ratio (long side / short side).
MAX_ASPECT_RATIO = 4.0

# Minimum side length (metres). Hallways have a narrower threshold.
MIN_SIDE = 1.2
MIN_SIDE_HALLWAY = 0.9

# Total plan area bounds (m²).
MIN_TOTAL_AREA = 15.0
MAX_TOTAL_AREA = 400.0

# Door width bounds (metres).
MIN_INTERIOR_DOOR_WIDTH = 0.7
MAX_INTERIOR_DOOR_WIDTH = 1.2
MIN_EXTERIOR_DOOR_WIDTH = 0.9

# Scoring formula weights.
ERROR_PENALTY = 0.25
WARNING_PENALTY = 0.05

# Valid room types.
ROOM_TYPES = [
    "living",
    "kitchen",
    "dining",
    "bedroom",
    "bathroom",
    "hallway",
    "study",
    "utility",
    "storage",
]

# Valid wall identifiers.
WALLS = ["N", "S", "E", "W"]

# Maximum encoded plan length (characters).
MAX_ENCODED_LENGTH = 8000

# Maximum batch size for /api/eval.
MAX_BATCH_SIZE = 50
