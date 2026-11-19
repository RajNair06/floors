"""FastAPI app: /api/* routes, mounts /mcp, exports `app`."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, RedirectResponse

from core import get_schema, render_svg
from core.config import MAX_BATCH_SIZE
from core.rules import RULE_CATALOGUE
from core.schema import EvalReport, Plan, ScoreResult, Violation, parse_plan, plan_to_dict
from core.score import evaluate, score, validate
from core.share import viewer_url


# ---------------------------------------------------------------------------
# Seed loader (read-only, cached at module level).
# ---------------------------------------------------------------------------
_SEEDS: list[dict] | None = None


def _load_seeds() -> list[dict]:
    global _SEEDS
    if _SEEDS is not None:
        return _SEEDS
    seeds_dir = Path(__file__).resolve().parent.parent / "data" / "seeds"
    if not seeds_dir.exists():
        _SEEDS = []
        return _SEEDS
    seeds = []
    for p in sorted(seeds_dir.glob("*.json")):
        with open(p) as f:
            data = json.load(f)
        seeds.append(data)
    _SEEDS = seeds
    return seeds


# ---------------------------------------------------------------------------
# MCP setup (imported here so we can wire its lifespan into FastAPI).
# ---------------------------------------------------------------------------
_mcp = None
_mcp_app = None

try:
    from mcp_server.app import mcp as _mcp
    from mcp.server.transport_security import TransportSecuritySettings

    # Allow all hosts for deployment; localhost-only is too restrictive for Vercel.
    security = TransportSecuritySettings(
        allowed_hosts=["*"],
        allowed_origins=["*"],
    )
    _mcp_app = _mcp.streamable_http_app(
        stateless_http=True,
        transport_security=security,
    )
except Exception:
    _mcp = None
    _mcp_app = None


# ---------------------------------------------------------------------------
# FastAPI app with lifespan that also runs MCP session manager.
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    if _mcp is not None and _mcp_app is not None:
        async with _mcp.session_manager.run():
            yield
    else:
        yield


app = FastAPI(title="Floor-Plan Checker", version="0.1.0", lifespan=lifespan)

# Mount MCP if available.
if _mcp_app is not None:
    app.mount("/mcp", _mcp_app)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
@app.get("/api/health")
async def health():
    return {"status": "ok", "version": "0.1.0"}


@app.get("/api/schema")
async def schema_route():
    return {"schema": get_schema(), "rules": RULE_CATALOGUE}


@app.post("/api/validate")
async def validate_route(request: Request):
    body = await request.json()
    try:
        plan = parse_plan(body)
    except ValueError as e:
        detail = e.args[0] if e.args else {"error": "schema", "details": []}
        return JSONResponse(status_code=422, content=detail)
    violations = validate(plan)
    passed = all(v.severity != "error" for v in violations)
    errors = [f"{v.rule}: {v.message}" for v in violations if v.severity == "error"] or None
    warnings = [f"{v.rule}: {v.message}" for v in violations if v.severity == "warning"] or None
    return {"passed": passed, "errors": errors, "warnings": warnings, "violations": [v.model_dump() for v in violations]}


@app.post("/api/score")
async def score_route(request: Request):
    body = await request.json()
    try:
        plan = parse_plan(body)
    except ValueError as e:
        detail = e.args[0] if e.args else {"error": "schema", "details": []}
        return JSONResponse(status_code=422, content=detail)
    result = score(plan)
    return {
        "passed": result.passed,
        "score": result.score,
        "errors": result.errors,
        "warnings": result.warnings,
        "breakdown": result.breakdown,
        "violations": [v.model_dump() for v in result.violations],
    }


@app.post("/api/render")
async def render_route(request: Request):
    body = await request.json()
    try:
        plan = parse_plan(body)
    except ValueError as e:
        detail = e.args[0] if e.args else {"error": "schema", "details": []}
        return JSONResponse(status_code=422, content=detail)
    violations = validate(plan)
    svg = render_svg(plan, violations)
    return {"svg": svg}


@app.post("/api/eval")
async def eval_route(request: Request):
    body = await request.json()
    raw_plans = body.get("plans", [])
    if len(raw_plans) > MAX_BATCH_SIZE:
        return JSONResponse(
            status_code=413,
            content={"error": f"Batch too large. Maximum is {MAX_BATCH_SIZE} plans."},
        )
    parsed = []
    for i, raw in enumerate(raw_plans):
        try:
            parsed.append(parse_plan(raw))
        except ValueError as e:
            detail = e.args[0] if e.args else {"error": "schema", "details": []}
            return JSONResponse(
                status_code=422,
                content={"error": "schema", "plan_index": i, "details": detail.get("details", [])},
            )
    report = evaluate(parsed)
    return report.model_dump()


@app.get("/api/seeds")
async def seeds_list():
    seeds = _load_seeds()
    return [
        {"id": s.get("id", ""), "title": s.get("title", ""), "expected_failures": s.get("expected_failures", [])}
        for s in seeds
    ]


@app.get("/api/seeds/{seed_id}")
async def seeds_detail(seed_id: str):
    seeds = _load_seeds()
    for s in seeds:
        if s.get("id") == seed_id:
            # Return plan fields only; strip test metadata.
            plan = {k: v for k, v in s.items() if k != "expected_failures"}
            return plan
    raise HTTPException(status_code=404, detail="Seed not found")


@app.get("/")
async def root():
    """Redirect to the static index.html."""
    return RedirectResponse(url="/index.html")
