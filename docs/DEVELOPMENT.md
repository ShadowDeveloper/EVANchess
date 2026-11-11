# EVAN Development

This document describes the checked-in EVAN implementation: repository layout, backend and frontend commands, tests, configuration behavior, SQLite lifecycle, active limits, costs, and known non-goals. For first-time installation and provider/model selection, see [SETUP.md](./SETUP.md).

## Repository layout

| Path | Purpose |
| --- | --- |
| `backend/evan/api/` | FastAPI app factory, game/import routes, SSE events, exports. |
| `backend/evan/pipeline/` | Coarse game pass, moment selection, branch search, deferred analysis orchestrator. |
| `backend/evan/engines/` | Stockfish UCI adapter and engine protocol types. |
| `backend/evan/chess_core/` | Strict PGN/FEN parser and rule-aware position identity. |
| `backend/evan/evidence/`, `claims/`, `audit/`, `realizer/` | Detectors, claim construction, prose audit, and constrained LLM realization. |
| `backend/evan/storage/` | SQLite repository and schema. |
| `backend/evan/importers/` | Bounded Lichess and Chess.com fetchers. |
| `backend/evan/export/` | Annotated PGN and JSON ledger export. |
| `backend/tests/` | Backend unit and integration tests. |
| `frontend/src/` | React workbench, API client, components, and Vitest tests. |
| `frontend/vite.config.ts` | Vite dev server, `/api` proxy, and Vitest configuration. |
| `docs/` | Project design and setup/development documentation. |

There is no backend console-script entry point and no Docker or deployment configuration in this repository. The supported launch is the FastAPI app factory through Uvicorn.

## Backend commands

Run from the repository root unless noted.

| Task | Command |
| --- | --- |
| Install/sync dependencies | `uv sync --extra dev` |
| Start development server | `$env:PYTHONPATH = "backend"; uv run uvicorn evan.api.app:create_app --factory --host 127.0.0.1 --port 8000 --reload` |
| Portable server command | `PYTHONPATH=backend uv run uvicorn evan.api.app:create_app --factory --host 127.0.0.1 --port 8000` |
| Run all backend tests | `uv run pytest backend/tests -q` |
| Run one module | `uv run pytest backend/tests/test_api_and_deferred_queue.py -q` |
| Exclude real-engine test | `uv run pytest backend/tests -q -k "not real_stockfish"` |
| Lint | `uv run ruff check backend` |
| Typecheck | `uv run mypy` |

`uv run mypy` intentionally uses the `[tool.mypy]` settings in `pyproject.toml` (`files = ["backend/evan"]`). Running `uv run mypy backend` instead also checks tests and currently reports a pre-existing test-only union-attribute issue, so use the configured command.

`uv run` alone does not put `backend` on `sys.path` from the repository root. Set `PYTHONPATH=backend` or pass `--app-dir backend` to Uvicorn, as shown in the [quick start](../README.md#quick-start).

### Test prerequisites

Most backend tests use temporary SQLite files and fake engines or fake LLM clients. `backend/tests/test_stockfish_engine.py::test_real_stockfish_uci_analysis` launches the configured Stockfish binary. It fails if `STOCKFISH_PATH`/`PATH` does not resolve to a working UCI engine. `test_stage_order_and_user_priority_with_real_stockfish` also exercises the real engine while replacing LLM realization with fakes.

Tests do not require a live LLM key; fake clients and explicit test keys are used. They do not consume provider credits unless you alter them to use a real client.

## Frontend commands

Run from `frontend`:

| Task | Command | Notes |
| --- | --- | --- |
| Install from lockfile | `npm ci` | Uses `package-lock.json`. |
| Development server | `npm run dev` | Port 5173; proxies `/api` to `127.0.0.1:8000`. |
| Production build | `npm run build` | Runs `tsc -b && vite build`; outputs `frontend/dist`. |
| Typecheck | `npm run typecheck` | `tsc --noEmit` with strict and unused checks. |
| Lint | `npm run lint` | ESLint flat config. |
| Tests | `npm run test` | Vitest with jsdom; currently covers commentary, ledger, and import UI. |
| Watch tests | `npm run test:watch` | Vitest watch mode. |
| Preview static build | `npm run preview` | No API proxy in this repo; not a full-app launch. |

The production build was verified with Vite 6 and the current lockfile. Vite emits `frontend/dist`, which the FastAPI app mounts at `/` only if the directory exists when the app is created. In the full-app mode, open `http://127.0.0.1:8000`; in development, open `http://localhost:5173`.

### Vite proxy and CORS

`frontend/vite.config.ts` proxies `/api` to `http://127.0.0.1:8000` with `changeOrigin: true`. The frontend API client uses relative `/api` URLs, so no frontend environment variable is required. The backend CORS allowlist is fixed to the two localhost:5173 origins. If you change the backend port, update the proxy target; if you change the frontend development origin, update both the Vite port and backend CORS allowlist.

## Configuration behavior

Configuration is read from process environment variables, with `.env` loaded when the configuration module is imported. Existing process environment variables take precedence, followed by `.env`, then code defaults. Restart the backend after changing them. Numeric settings are validated when settings are constructed; `/api/health` and imports check for the required key, local base URL, and Stockfish path. These checks do not authenticate a key or start the engine.

- The selected provider has a non-empty key. `local` additionally requires a non-empty `EVAN_LLM_BASE_URL`.
- Engine budgets are positive.
- `EVAN_CRITICAL_MOMENTS_COUNT` is between 3 and 6 inclusive.
- Stockfish resolves when health/import configuration checks run.

The `/api/health` response reports `configured` and a list of configuration errors. It does not return key values. Import returns HTTP 503 when the same configuration checks fail.

Provider-specific behavior:

- `openrouter`, `openai`, and `local` call `POST {base}/chat/completions` with a JSON-object response request.
- `anthropic` calls `POST {base}/messages` with `anthropic-version: 2023-06-01`.
- Requests use temperature 0, a 4096 output-token cap, a 60-second HTTP timeout, and a 65-second overall generation timeout.
- A 401/403 is surfaced as a configuration error. Other HTTP/transport/JSON failures are generation failures that trigger deterministic audited fallback prose for that ply.
- There is one repair attempt after a prose-audit failure, not a general retry loop.
- `SECONDARY_ENGINE_PATH` is accepted by settings but is not used by the active pipeline.

## Analysis lifecycle

1. Import parses PGN/FEN or fetches a bounded Lichess/Chess.com game, creates a game row, creates one ply row per half-move, and enqueues the game.
2. The in-process worker runs one game at a time. It requires a valid provider key and Stockfish path.
3. A coarse pass analyzes every ply at the coarse node budget. Critical moments are selected (default 5, allowed 3-6).
4. Stage A deep-analyzes those critical moments and marks the game `auto_complete`.
5. Stage B deep-analyzes every remaining queued ply in priority order and marks the game `full_complete`.
6. A user can boost a queued ply through `POST /api/games/{game_id}/plies/{ply}/prioritize`.
7. SSE at `GET /api/games/{game_id}/events` sends snapshots, moment-ready events, keepalives, and a final complete/error event while analysis is active.
8. Exports are available at `/api/games/{game_id}/export/pgn` and `/api/games/{game_id}/export/ledger`.

Game statuses are `pending`, `auto_analyzing`, `auto_complete`, `full_analyzing`, `full_complete`, and `failed`. Ply deep statuses are `queued`, `running`, `completed`, `abstained`, and `failed`. Terminal positions abstain without an LLM call. A generation failure can produce deterministic fallback prose and still complete the ply; analysis-level configuration failure marks the game failed.

## SQLite lifecycle

- `EVAN_DB_PATH` defaults to `evan.db` relative to the backend process working directory. Use an absolute path when launching with different working directories.
- `create_app()` creates the repository and calls `init_db()`. The schema is applied idempotently from `backend/evan/storage/schema.sql`, with additive column additions for older databases. There is no separate migration command.
- Connections enable WAL mode and foreign keys and use a 30-second busy timeout.
- Tables are `games`, `ply_analyses`, and `engine_cache`. Game rows store the clean PGN, metadata, status, critical plies, warnings, and quarantined untrusted comments. Ply rows store engine summaries, evidence ledgers, commentary, and status. The engine cache stores complete exact engine records keyed by state, binary hash, options, node limit, MultiPV, and root-move restrictions.
- Completed history persists across restarts. On startup, games not already `full_complete` or `failed` are marked failed; running plies become failed. Analysis is not resumed, and re-import is the retry path.
- The queue and SSE change events are memory-only. Priority boosts are persisted in SQLite, but interrupted games are marked failed rather than resumed.
- To reset all local state, stop the backend and delete `evan.db`, `evan.db-wal`, and `evan.db-shm`. This destroys game history and the engine cache. Back up by stopping the backend and copying the database together with its WAL/SHM sidecars.

## Active limits and resource behavior

| Limit | Current behavior |
| --- | --- |
| Import size | 200,000 input characters; up to 600 half-moves per import. |
| Game queue | Up to 20 games; one worker processes games serially. |
| Critical moments | 3-6 moments; default 5. |
| Target rating | 1,200-2,000; default 1,500. |
| Platform input | Standard chess PGN, FEN, Lichess URL, or Chess.com URL. Variants are rejected. |
| Recent-game import | At most 25 games per request; Chess.com scans at most the 12 most recent monthly archives and direct Chess.com URLs require a username. |
| Game list | Most recent 50 games. |
| Node budgets | `quick` = 0.25x, `standard` = 1x, `deep` = 2x configured budgets, with a 1,000-node floor. |
| Analysis concurrency | Engine work is serialized through a single worker; LLM calls are also serialized per game. |
| LLM spend | No hard cost cap. Cost is bounded indirectly by up to 600 deep plies, fixed node budgets, one realization call per deep ply, at most one repair call, and the 65-second request timeout. |
| Provider/network timeouts | LLM 60 seconds HTTP / 65 seconds overall; Lichess/Chess.com 15 seconds per request. |
| API access | No authentication and no application-level rate limiting. Do not expose the service. |

Cost accounting depends on the provider response. Usage and reported cost are stored per ply in the ledger metrics/commentary fields. `cost_usd` is only populated when the provider supplies usable cost data for every recorded request; otherwise it can remain null even though token usage is present. OpenRouter commonly reports cost; OpenAI and Anthropic may not. There is no pricing table or local estimation.

The engine cache can make repeated identical searches effectively free in node terms, but it is keyed by exact state/configuration/budget and is not a general deduplication or cross-engine cache. Every imported game is a new game row; imports are not deduplicated.

## Optional or unimplemented features

These are not active despite being mentioned in design material or configuration:

- No production authentication, accounts, authorization roles, multi-tenant isolation, TLS, reverse-proxy configuration, or public deployment guidance.
- No API rate limiting, quotas, cost budget enforcement, or cancellation endpoint for a running analysis.
- No persistent job queue or automatic resume after a restart.
- No Lc0, Maia-2, Syzygy/tablebase, or secondary-engine integration is executed. `SECONDARY_ENGINE_PATH` is only parsed.
- No chess variants beyond standard chess.
- No database server, migrations framework, or cloud storage; SQLite is the only persistence layer.
- No token-by-token LLM streaming. SSE streams analysis snapshots and completed ply results.
- No game deletion endpoint and no import deduplication.
- No background scheduling outside the single in-process worker.
- No `npm run preview` API proxy and no separate frontend `.env` configuration.

## Development checks

Before handing off a change, run the checks relevant to the touched area:

```powershell
uv run ruff check backend
uv run mypy
uv run pytest backend/tests -q

npm --prefix frontend run typecheck
npm --prefix frontend run lint
npm --prefix frontend run test
npm --prefix frontend run build
```

The current checks include both a real Stockfish UCI test and an API/orchestration test that uses the real engine. If no engine is available, use the `-k "not real_stockfish"` filter for backend tests and treat those checks as environment-gated.

Do not commit `.env`, database files, WAL/SHM files, `node_modules`, or `frontend/dist`. These are already covered by `.gitignore`.
