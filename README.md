# Floors

A deterministic floor plan validation tool that checks architectural layouts against 10 design rules. Built for evaluating LLM-generated floor plans with interactive editing and 3D visualization.

**Live Demo:** https://floors-sigma.vercel.app  
**MCP Endpoint:** https://floors-sigma.vercel.app/mcp/

## Features

### Core Validation
- **10 Validation Rules**: Overlap detection, entrance requirements, room connectivity, window placement, door positioning, minimum areas, proportions, door widths, and bathroom privacy
- **Scoring System**: 0-1 score based on errors (0.25 penalty) and warnings (0.05 penalty)
- **25 Seed Plans**: Test cases covering all rules and edge cases

### Visualization & Export
- **2D SVG Rendering**: Clean vector graphics with violation highlighting
- **3D GLB Export**: Generate binary glTF models with rooms, walls, doors, and windows
- **Share Links**: Encode plans in URL fragments for easy sharing

### Interfaces
- **REST API**: Validate, score, render SVG/GLB, and batch evaluate plans
- **MCP Server**: 12 tools for building plans step-by-step with automatic validation
- **Web UI**: Interactive editor with 2D/3D views, batch evaluation, and documentation

### Batch Processing
- Evaluate up to 50 plans in a single API call
- Aggregate pass rates and violation statistics
- Export results as JSON reports

## Quick Start

### Prerequisites

- Python 3.12+
- [uv](https://docs.astral.sh/uv/) package manager

### Local Development

```bash
# Install dependencies
uv sync

# Run tests
uv run pytest

# Start dev server
uv run vercel dev

# Or run FastAPI directly
uv run uvicorn api.index:app --reload --port 8000
```

Open http://localhost:8000 (or the Vercel dev URL) in your browser.

### Deployment

```bash
# Deploy to Vercel
vercel

# Deploy to production
vercel --prod
```

## API Endpoints

Base URL: `https://floors-sigma.vercel.app`

### Read Operations

- `GET /api/health` - Health check
- `GET /api/schema` - JSON Schema for plan format + rule catalogue
- `GET /api/seeds` - List all seed plans
- `GET /api/seeds/{id}` - Get one seed plan
- `POST /api/validate` - Validate a plan (returns violations)
- `POST /api/score` - Score a plan (returns score + violations)
- `POST /api/render` - Render plan as 2D SVG
- `POST /api/render3d` - Render plan as 3D GLB (base64-encoded)
- `POST /api/eval` - Batch evaluate up to 50 plans

### Example: Score a Plan

```bash
curl -X POST https://floors-sigma.vercel.app/api/score \
  -H "Content-Type: application/json" \
  -d '{
    "schema_version": "1.0",
    "id": "test",
    "units": "m",
    "rooms": [
      {"id": "r1", "type": "living", "name": "Living", "x": 0, "y": 0, "w": 5, "h": 4}
    ],
    "doors": [
      {"id": "d1", "from": "r1", "to": "outside", "wall": "S", "offset": 1, "width": 1}
    ],
    "windows": [
      {"id": "w1", "room": "r1", "wall": "N", "offset": 1, "width": 1.5}
    ]
  }'
```

Response:
```json
{
  "passed": true,
  "score": 1.0,
  "errors": null,
  "warnings": null,
  "breakdown": {},
  "violations": []
}
```

### Example: Export 3D Model

```bash
curl -X POST https://floors-sigma.vercel.app/api/render3d \
  -H "Content-Type: application/json" \
  -d '{...plan JSON...}' \
  | jq -r .glb | base64 -d > plan.glb
```

The GLB file can be opened in:
- **Blender** (File → Import → glTF 2.0)
- **Windows 3D Viewer** (drag and drop)
- **Web viewers** (three.js, Babylon.js, model-viewer)
- **macOS Preview** (Quick Look)

## MCP Server

Connect an MCP client to build plans interactively with real-time validation.

**Endpoint:** `https://floors-sigma.vercel.app/mcp/`

### Tools (12 total)

**Read Tools:**
- `get_schema_tool` - Learn the plan format and validation rules
- `validate_floorplan` - Check for violations
- `score_floorplan` - Get score and breakdown
- `render_floorplan_svg` - Visualize the plan as 2D SVG
- `render_3d_model` - Generate 3D GLB model (base64-encoded)
- `run_eval` - Batch evaluate multiple plans

**Authoring Tools:**
- `new_floorplan_tool` - Create empty plan
- `add_room_tool` - Add a room (absolute or relative positioning)
- `connect_rooms_tool` - Add door between adjacent rooms
- `add_opening_tool` - Add window or exterior door
- `update_room_tool` - Modify room properties
- `remove_element_tool` - Remove room/door/window

All authoring tools automatically validate the plan after each operation and return the updated plan with score and violations.

### MCP Client Configuration

```json
{
  "mcpServers": {
    "floors": {
      "url": "https://floors-sigma.vercel.app/mcp/"
    }
  }
}
```

### Example: Building a Plan via MCP

```python
# 1. Create empty plan
plan = new_floorplan_tool(id="my_apartment")

# 2. Add rooms
plan = add_room_tool(plan, type="living", name="Living Room", w=5, h=4, x=0, y=0)
plan = add_room_tool(plan, type="bedroom", name="Bedroom", w=4, h=4, relative_to="living", side="E")

# 3. Connect rooms with doors
plan = connect_rooms_tool(plan, a="living", b="bedroom", width=0.9)

# 4. Add exterior door
plan = add_opening_tool(plan, kind="door", room="living", wall="S", width=1.0)

# 5. Add windows
plan = add_opening_tool(plan, kind="window", room="living", wall="N", width=1.5)
plan = add_opening_tool(plan, kind="window", room="bedroom", wall="N", width=1.2)

# 6. Check final score
result = score_floorplan(plan)
print(f"Score: {result['score']}, Passed: {result['passed']}")

# 7. Export 3D model
glb_data = render_3d_model(plan)
# Save base64-decoded GLB to file
```

### Local MCP (stdio)

```bash
uv run python -m mcp_server
```

## Validation Rules

The system checks floor plans against 10 design rules. **Errors** mean the plan cannot work. **Warnings** mean the plan works but has design issues.

| ID  | Rule | Severity | What It Checks |
|-----|------|----------|----------------|
| R01 | **No room overlap** | error | Rooms must not intersect. Tolerance: 0.05m. Adjacent rooms may share walls exactly. |
| R02 | **Has entrance** | error | Plan must have at least one exterior door (door to "outside"). |
| R03 | **All rooms reachable** | error | Every room must be reachable from the entrance via interior doors. Uses flood-fill algorithm. |
| R04 | **Windows in habitable rooms** | error | Living, bedroom, dining, study, and kitchen rooms must have at least one window. Bathrooms, hallways, utility, and storage are exempt. |
| R05 | **Doors on walls** | error | Interior doors must be on shared walls between two rooms. Exterior doors must be on exterior walls. Door position must fit within wall bounds. |
| R06 | **Windows on exterior walls** | error | Windows can only be placed on exterior walls (walls not shared with another room). Window position must fit within wall bounds. |
| R07 | **Minimum room areas** | warning | Living: ≥12m², Bedroom: ≥7m², Kitchen: ≥5m², Dining: ≥6m², Bathroom: ≥3m², Hallway: ≥3m², Study: ≥5m², Utility: ≥3m², Storage: ≥2m² |
| R08 | **Plausible proportions** | warning | Room aspect ratio (longer side / shorter side) must be ≤4:1. Prevents impossibly narrow rooms. |
| R09 | **Door widths** | warning | All doors must be 0.7m–1.2m wide. Narrower doors are impractical; wider doors are unusual. |
| R10 | **Bathroom privacy** | warning | Bathrooms should not have direct doors to kitchens or dining rooms. Prefer hallway or bedroom access. |

**Scoring formula:** `score = max(0, 1 - 0.25 * error_count - 0.05 * warning_count)`

A plan with 0 errors and 0 warnings scores 1.0. A plan with 2 errors scores 0.5. A plan with 4+ errors scores 0.

See `DECISIONS.md` for rule thresholds, rationale, and edge cases.

## Plan Format

```json
{
  "schema_version": "1.0",
  "id": "plan_001",
  "units": "m",
  "ceiling_height": 2.7,
  "rooms": [
    {"id": "r1", "type": "living", "name": "Living room", "x": 0, "y": 0, "w": 5.0, "h": 4.0}
  ],
  "doors": [
    {"id": "d1", "from": "r1", "to": "outside", "wall": "S", "offset": 1.0, "width": 1.0}
  ],
  "windows": [
    {"id": "w1", "room": "r1", "wall": "N", "offset": 1.0, "width": 1.5}
  ]
}
```

**Conventions:**
- Coordinates: x right, y down (top-left origin)
- Units: metres only
- Walls: N/S/E/W relative to room
- Wall thickness: ignored (rooms share edges exactly)
- Tolerance: 0.05m (EPS)

## Project Structure

```
floors/
├── api/index.py           # FastAPI app + MCP mount
├── core/                  # Pure validation logic
│   ├── config.py          # Thresholds and constants
│   ├── schema.py          # Pydantic models
│   ├── geometry.py        # Rectangle operations
│   ├── rules.py           # 10 validation rules
│   ├── score.py           # Scoring + evaluation
│   ├── svg.py             # 2D SVG rendering
│   ├── render3d.py        # 3D GLB rendering
│   ├── ops.py             # Authoring operations
│   └── share.py           # Encode/decode plans
├── mcp_server/            # MCP tool definitions
│   ├── app.py             # 12 MCP tools
│   └── __main__.py        # stdio entrypoint
├── public/                # Static web UI
│   ├── index.html
│   ├── css/style.css
│   ├── js/app.js
│   └── js/viewer3d.js     # Three.js 3D viewer
├── data/seeds/            # 25 test plans
├── tests/                 # pytest suite (52 tests)
├── vercel.json            # Deployment config
└── DECISIONS.md           # Design decisions
```

## Testing

```bash
# Run all tests
uv run pytest

# Run with coverage
uv run pytest --cov=core --cov=api

# Run specific test file
uv run pytest tests/test_rules.py -v

# Test a specific rule
uv run pytest tests/test_rules.py::test_r01_no_overlap -v
```

## Use Cases

1. **LLM Evaluation**: Generate floor plans with an LLM, validate them, measure pass rates
2. **Design Assistance**: Build plans interactively via MCP with real-time feedback
3. **3D Visualization**: Export GLB models for review in Blender, 3D viewers, or AR applications
4. **Dataset Curation**: Use seed plans as training data or benchmarks
5. **Rule Exploration**: Understand architectural constraints through violation messages
6. **Batch Testing**: Evaluate multiple plans at once to compare designs or test model outputs

## Limitations

- Rectangular rooms only (no L-shapes, curves)
- Single-floor plans only
- No furniture or fixtures
- No CAD/DXF import
- No multi-user collaboration
- No authentication or persistence

See `DECISIONS.md` for full scope.

## License

MIT

## Contributing

This is an evaluation benchmark project. To add a new rule:

1. Add rule function in `core/rules.py`
2. Add test in `tests/test_rules.py`
3. Add seed plans demonstrating the rule
4. Update `RULE_CATALOGUE` in `core/rules.py`
5. Document threshold in `DECISIONS.md`
