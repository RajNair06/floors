# Decision Log

Running log of choices made during the build. Feeds the final write-up.

## Domain and format

- **Rectangular rooms only.** Axis-aligned rectangles in metres. An LLM can generate this reliably, and all rules reduce to plain arithmetic.
- **Wall thickness ignored.** Rooms share edges exactly; edges within 0.05 m (EPS) count as touching. Simplifies geometry and avoids an entire class of alignment bugs.
- **y grows downward** in 2D, matching SVG conventions. In 3D, y maps to Three.js Z.
- **Coordinates:** (x, y) is the room's top-left corner.
- **Only metres.** Other units rejected at schema validation.

## Rules and thresholds

- **Errors vs warnings.** Errors are structural problems that make the plan unusable (overlap, no entrance, unreachable rooms, missing windows in habitable rooms, doors/windows on wrong walls). Warnings are design-quality issues (small rooms, bad proportions, narrow doors, bathroom privacy). A plan with any error fails; warnings only affect the score.
- **Minimum areas:** bedroom 7 m², living 10 m², kitchen 4 m², bathroom 2.5 m², study 5 m², dining 5 m², hallway 1.5 m², utility 2 m², storage 1 m². Based on UK housing standards as a reasonable default.
- **Aspect ratio max 4:1.** Rooms above this look like corridors even when not typed as one.
- **Minimum side 1.2 m** (hallway 0.9 m). Below this, furniture placement becomes implausible.
- **Total plan area 15–400 m².** Below 15 is a hotel room; above 400 is beyond the scope of this tool.
- **Interior doors 0.7–1.2 m, exterior doors min 0.9 m.** Standard building practice.
- **Any exterior door counts as an entrance.** No distinction between front door, back door, and patio door.
- **Habitable rooms = bedroom, living, study.** Kitchen and dining are excluded from the window requirement because open-plan designs are common.

## Scoring

- **score = max(0, 1 - 0.25E - 0.05W)** where E = error count, W = warning count. The 5:1 ratio means 5 warnings equal 1 error in penalty, which feels right for ranking.
- **Pass/fail is separate from score.** A plan with 0 errors passes even with a score below 1.0. This avoids the common mistake of conflating pass/fail with a continuous metric.

## Architecture

- **core/ is pure.** No imports from api/, mcp_server/, or public/. No file or network I/O. Every rule is testable with a plain dict.
- **Two kinds of failure kept separate.** Schema errors (422) mean the plan is malformed and cannot be scored. Rule violations (200 with a list) mean the plan is valid but has design problems.
- **Stateless API.** No database, no module-level mutable state beyond the seed cache (which is a speed-up, not a store).
- **Seeds are bundled JSON.** Read at startup, cached at module level. Each carries `expected_failures` for regression testing.

## Frontend

- **No build step.** Plain HTML, CSS, ES modules. Three.js vendored (when added) to avoid CDN dependency.
- **Labels stored client-side only.** localStorage with try/catch wrapping, exported as JSONL via Blob. Nothing reaches the server.
- **Auto verdict shown after human label.** Prevents anchoring bias in the reviewer.
- **Agreement rate displayed.** The ratio of human-vs-auto agreement is the eval bench's main output.

## MCP

- **Streamable HTTP, stateless.** No per-session memory. Every tool is a pure function of its inputs.
- **Plan travels with every call.** No server-side storage needed. The viewer URL carries the whole plan in the fragment.
- **Authoring tools instead of raw JSON.** `add_room`, `connect_rooms`, `add_opening` let an agent build plans step by step with less chance of geometric errors.

## Deployment

- **Vercel, single function.** FastAPI app at api/index.py serves both /api/* and /mcp. Static files in public/.
- **Python 3.12 pinned.** Default on Vercel, matches local dev.
- **No secrets or environment variables.** The viewer URL base comes from the request host.

## Cut from v1

- Multi-storey plans.
- CAD/DXF/image import.
- Curved or non-rectangular rooms.
- LLM calls in the deployed app.
- Accounts, auth, multi-user collaboration.
- Legal building-code compliance claims.
