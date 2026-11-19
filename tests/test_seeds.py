"""Tests that seed plans produce their expected_failures."""

import json
from pathlib import Path

from core.schema import Plan
from core.score import validate

SEEDS_DIR = Path(__file__).resolve().parent.parent / "data" / "seeds"


def _load_seeds():
    if not SEEDS_DIR.exists():
        return []
    seeds = []
    for p in sorted(SEEDS_DIR.glob("*.json")):
        with open(p) as f:
            seeds.append(json.load(f))
    return seeds


def test_seed_expected_failures():
    """Each seed's actual violations match its expected_failures exactly."""
    seeds = _load_seeds()
    assert len(seeds) > 0, "No seeds found"

    for seed in seeds:
        plan = Plan.model_validate(seed)
        violations = validate(plan)
        actual_rules = sorted(set(v.rule for v in violations))
        expected = sorted(seed.get("expected_failures", []))
        assert actual_rules == expected, (
            f"Seed {seed['id']} ({seed.get('title', '')}):\n"
            f"  expected: {expected}\n"
            f"  actual:   {actual_rules}\n"
            f"  violations: {[v.message for v in violations]}"
        )
