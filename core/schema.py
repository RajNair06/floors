"""Pydantic models for the floor-plan data model.

Structural validation: unique ids, valid references, positive sizes, openings within walls.
Exports JSON Schema for agents.
"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field, field_validator, model_validator

from core.config import ROOM_TYPES, WALLS


class Room(BaseModel):
    id: str
    type: str
    name: str
    x: float
    y: float
    w: float
    h: float

    @field_validator("type")
    @classmethod
    def check_type(cls, v: str) -> str:
        if v not in ROOM_TYPES:
            raise ValueError(f"unknown room type '{v}'")
        return v

    @field_validator("w", "h")
    @classmethod
    def positive(cls, v: float) -> float:
        if v <= 0:
            raise ValueError("must be positive")
        return v


class Door(BaseModel):
    id: str
    from_: str = Field(alias="from")
    to: str
    wall: str
    offset: float
    width: float

    model_config = {"populate_by_name": True}

    @field_validator("wall")
    @classmethod
    def check_wall(cls, v: str) -> str:
        if v not in WALLS:
            raise ValueError(f"unknown wall '{v}'")
        return v

    @field_validator("offset", "width")
    @classmethod
    def non_negative(cls, v: float) -> float:
        if v < 0:
            raise ValueError("must be non-negative")
        return v


class Window(BaseModel):
    id: str
    room: str
    wall: str
    offset: float
    width: float

    @field_validator("wall")
    @classmethod
    def check_wall(cls, v: str) -> str:
        if v not in WALLS:
            raise ValueError(f"unknown wall '{v}'")
        return v

    @field_validator("offset", "width")
    @classmethod
    def non_negative(cls, v: float) -> float:
        if v < 0:
            raise ValueError("must be non-negative")
        return v


class Plan(BaseModel):
    schema_version: str = "1.0"
    id: str
    units: str = "m"
    ceiling_height: float = 2.7
    rooms: list[Room] = []
    doors: list[Door] = []
    windows: list[Window] = []

    @field_validator("units")
    @classmethod
    def check_units(cls, v: str) -> str:
        if v != "m":
            raise ValueError("only 'm' (metres) is supported")
        return v

    @model_validator(mode="after")
    def validate_structure(self) -> "Plan":
        errors = []
        # Unique ids within each collection.
        for collection_name, collection in [
            ("rooms", self.rooms),
            ("doors", self.doors),
            ("windows", self.windows),
        ]:
            ids = [getattr(item, "id") for item in collection]
            if len(ids) != len(set(ids)):
                errors.append(
                    {"path": collection_name, "message": "duplicate ids"}
                )

        room_ids = {r.id for r in self.rooms}

        # Door references.
        for i, door in enumerate(self.doors):
            if door.from_ not in room_ids:
                errors.append(
                    {
                        "path": f"doors.{i}.from",
                        "message": f"unknown room id '{door.from_}'",
                    }
                )
            if door.to != "outside" and door.to not in room_ids:
                errors.append(
                    {
                        "path": f"doors.{i}.to",
                        "message": f"unknown room id '{door.to}'",
                    }
                )
            # Check door fits on wall.
            if door.from_ in room_ids:
                room = next(r for r in self.rooms if r.id == door.from_)
                wall_len = room.w if door.wall in ("N", "S") else room.h
                if door.offset + door.width > wall_len + 0.05:
                    errors.append(
                        {
                            "path": f"doors.{i}.offset",
                            "message": "door extends beyond wall",
                        }
                    )

        # Window references.
        for i, window in enumerate(self.windows):
            if window.room not in room_ids:
                errors.append(
                    {
                        "path": f"windows.{i}.room",
                        "message": f"unknown room id '{window.room}'",
                    }
                )
            if window.room in room_ids:
                room = next(r for r in self.rooms if r.id == window.room)
                wall_len = room.w if window.wall in ("N", "S") else room.h
                if window.offset + window.width > wall_len + 0.05:
                    errors.append(
                        {
                            "path": f"windows.{i}.offset",
                            "message": "window extends beyond wall",
                        }
                    )

        if errors:
            raise ValueError({"error": "schema", "details": errors})

        return self


class Violation(BaseModel):
    rule: str
    severity: str  # "error" or "warning"
    room_ids: list[str] = []
    message: str
    suggested_fix: str = ""
    region: Optional[dict] = None


class ScoreResult(BaseModel):
    passed: bool
    score: float
    errors: Optional[list[str]] = None
    warnings: Optional[list[str]] = None
    breakdown: dict[str, int]
    violations: list[Violation]


class EvalReport(BaseModel):
    n: int
    pass_rate: float
    mean_score: float
    per_rule: dict[str, int]
    results: list[dict]


def plan_to_dict(plan: Plan) -> dict:
    """Convert Plan back to JSON-friendly dict (handles 'from' alias)."""
    data = plan.model_dump(by_alias=True)
    return data


def get_schema() -> dict:
    """Return JSON Schema for Plan."""
    return Plan.model_json_schema()


def parse_plan(obj: dict) -> Plan:
    """Parse a raw dict into a Plan, raising ValueError on schema errors.

    The ValueError payload has {"error": "schema", "details": [...]} for API use.
    """
    try:
        return Plan.model_validate(obj)
    except Exception as e:
        # Extract structured errors.
        errors = _extract_errors(e)
        raise ValueError({"error": "schema", "details": errors}) from e


def _extract_errors(exc: Exception) -> list[dict]:
    """Extract {path, message} from a pydantic ValidationError or ValueError."""
    from pydantic import ValidationError

    if isinstance(exc, ValidationError):
        result = []
        for err in exc.errors():
            loc = err.get("loc", ())
            path = ".".join(str(part) for part in loc)
            result.append({"path": path, "message": err.get("msg", str(err))})
        return result
    # Nested ValueError from model_validator.
    if isinstance(exc, ValueError) and isinstance(exc.args[0] if exc.args else None, dict):
        return exc.args[0].get("details", [{"path": "", "message": str(exc)}])
    return [{"path": "", "message": str(exc)}]
