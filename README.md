# Floor Plan Checker

A deterministic floor plan validation tool that checks architectural layouts against 10 design rules. Built as an evaluation benchmark for testing LLM-generated floor plans.

**Live Demo:** [Deploy to Vercel to get your URL]

## Features

- **10 Validation Rules**: Overlap detection, entrance requirements, room connectivity, window placement, door positioning, minimum areas, proportions, door widths, and bathroom privacy
- **Scoring System**: 0-1 score based on errors (0.25 penalty) and warnings (0.05 penalty)
- **REST API**: Validate, score, render SVG, and batch evaluate plans
- **MCP Server**: Authoring tools for building plans step-by-step with automatic validation
- **Web UI**: Interactive editor with 2D visualization, reviewer interface, and batch evaluation
- **25 Seed Plans**: Test cases covering all rules and edge cases
- **Share Links**: Encode plans in URL fragments for easy sharing

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

### Read Operations

- `GET /api/health` - Health check
- `GET /api/schema` - JSON Schema for plan format + rule catalogue
- `GET /api/seeds` - List all seed plans
- `GET /api/seeds/{id}` - Get one seed plan
- `POST /api/validate` - Validate a plan (returns violations)
- `POST /api/score` - Score a plan (returns score + violations)
- `POST /api/render` - Render plan as SVG
- `POST /api/eval` - Batch evaluate up to 50 plans

### Example

```bash
curl -X POST http://localhost:8000/api/score \
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
  "breakdown": {},
  "violations": []
}
```

## MCP Server

Connect an MCP client to build plans interactively:

### Tools (11 total)

**Read Tools:**
- `get_schema` - Learn the plan format
- `validate_floorplan` - Check for violations
- `score_floorplan` - Get score and breakdown
- `render_floorplan_svg` - Visualize the plan
- `run_eval` - Batch evaluate multiple plans

**Authoring Tools:**
- `new_floorplan` - Create empty plan
- `add_room` - Add a room (absolute or relative positioning)
- `connect_rooms` - Add door between adjacent rooms
- `add_opening` - Add window or exterior door
- `update_room` - Modify room properties
- `remove_element` - Remove room/door/window

### MCP Client Configuration

```json
{
  "mcpServers": {
    "floor-plan-checker": {
      "url": "https://your-deployment.vercel.app/mcp"
    }
  }
}
```

### Local MCP (stdio)

```bash
uv run python -m mcp_server
```

## Validation Rules

| ID  | Rule                              | Severity |
|-----|-----------------------------------|----------|
| R01 | No room overlap                   | error    |
| R02 | Has entrance (exterior door)      | error    |
| R03 | All rooms reachable               | error    |
| R04 | Habitable rooms have windows      | error    |
| R05 | Doors on shared/exterior walls    | error    |
| R06 | Windows on exterior walls only    | error    |
| R07 | Minimum room areas                | warning  |
| R08 | Plausible proportions (4:1 max)   | warning  |
| R09 | Door widths (0.7-1.2m)            | warning  |
| R10 | Bathroom privacy                  | warning  |

See `DECISIONS.md` for rule thresholds and assumptions.

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
│   ├── svg.py             # SVG rendering
│   ├── ops.py             # Authoring operations
│   └── share.py           # Encode/decode plans
├── mcp_server/            # MCP tool definitions
│   ├── app.py             # 11 MCP tools
│   └── __main__.py        # stdio entrypoint
├── public/                # Static web UI
│   ├── index.html
│   ├── css/style.css
│   └── js/app.js
├── data/seeds/            # 25 test plans
├── tests/                 # pytest suite (44 tests)
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
3. **Dataset Curation**: Use seed plans as training data or benchmarks
4. **Rule Exploration**: Understand architectural constraints through violation messages

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
