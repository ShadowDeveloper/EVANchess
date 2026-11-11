# HTTP API

This documents the implemented EVAN 0.1.0 routes and serialized data, not proposed endpoints. See the [documentation index](README.md), [setup/configuration](SETUP.md) and [architecture and limitations](ARCHITECTURE.md). Route code, Pydantic models, repository serialization and [tests](../backend/tests/test_api_and_deferred_queue.py) are the source of truth; frontend TypeScript interfaces are not a complete wire schema.

## Connection and errors

Local examples use `http://127.0.0.1:8000`. The frontend calls relative `/api` URLs; Vite proxies them to that address in development. JSON requests use `Content-Type: application/json`; responses are JSON unless marked otherwise. There is **no authentication or user isolation**. Keep the server on loopback; CORS is not an access-control boundary. Imports can incur provider charges and consume local CPU/memory. Never send provider API keys as import fields.

Route-raised errors have `{"detail":"message"}`. FastAPI/Pydantic validation errors use `{"detail":[{"loc":[...],"msg":"...","type":"...",...}]}` with HTTP 422. Unexpected failures may return 500 rather than a normalized error. Analysis failures after an accepted import are stored in the game and sent over SSE; the original HTTP 201 does not mean analysis succeeded.

| Method/path | Success | Defined route-level failures |
| --- | --- | --- |
| `GET /api/health` | 200 `Health` | Configuration problems are in the body, not a 503. |
| `GET /api/games` | 200 `GameSummary[]` | No pagination/query contract. |
| `POST /api/games/import` | 201 `GameDetail` | 422 invalid input/import; 429 queue full/shutdown; 503 missing configuration. |
| `GET /api/importers/{platform}/{username}` | 200 remote-game array | 422 parameter validation, importer/network/upstream error. |
| `GET /api/games/{game_id}` | 200 `GameDetail` | 404 game absent. |
| `POST /api/games/{game_id}/plies/{ply}/prioritize` | 200 `{"prioritized":boolean}` | 404 game/ply absent; 422 malformed integer. |
| `GET /api/games/{game_id}/events` | 200 `text/event-stream` | 404 game absent before streaming. |
| `GET /api/games/{game_id}/export/pgn` | 200 `application/x-chess-pgn` | 404 game absent. |
| `GET /api/games/{game_id}/export/ledger` | 200 JSON export | 404 game absent. |

FastAPI also supplies `/docs`, `/redoc`, `/openapi.json`; most route responses are untyped dictionaries, so generated OpenAPI does not fully describe the payloads below. If `frontend/dist` exists at application creation, static frontend files are mounted at `/`; this is not an additional analysis API. There are no delete, cancel, resume, retry, reanalyze, single-ply retrieval, settings-update or cache-control endpoints.

## Health and configuration errors

`GET /api/health` returns:

```json
{"configured":true,"configuration_errors":[],"version":"0.1.0"}
```

`configured` checks only selected-provider key/base-URL presence and Stockfish path resolution. It does not call the provider, load the model or launch an engine. The app can start and existing games/exports remain readable when these checks fail. Invalid environment types/settings or an unusable database can instead prevent app creation.

Configuration checks use [config.py](../backend/evan/config.py):

| Selected provider | Required |
| --- | --- |
| `openrouter` (default) | Nonempty `OPENROUTER_API_KEY`. |
| `openai` | Nonempty `OPENAI_API_KEY`. |
| `anthropic` | Nonempty `ANTHROPIC_API_KEY`. |
| `local` | Nonempty `EVAN_LLM_BASE_URL` **and** `OPENAI_API_KEY`; there is no automatic dummy key. |

Model defaults to `openai/gpt-4o-mini`; set `EVAN_LLM_MODEL` to a model supported by the chosen provider. Base URL override is operator configuration, not an import option. Stockfish resolves explicit `STOCKFISH_PATH`, then `stockfish` on `PATH`, then the built-in Windows fallback if present. An explicit invalid path does not silently fall through.

Examples of exact configuration-error messages:

```json
{"configured":false,"configuration_errors":["OPENROUTER_API_KEY is required when EVAN_LLM_PROVIDER='openrouter'."],"version":"0.1.0"}
```

```json
{"detail":"Stockfish binary not found. Set STOCKFISH_PATH in .env or add 'stockfish' to system PATH."}
```

The second body is a possible HTTP 503 import response. Local-mode messages name the missing base URL/key. Health can list both a provider and an engine error; import stops at the first raised error. A provider authentication/access rejection (401/403) during background analysis fails the game with a configuration message; it is not an HTTP error on an already completed import request or a silent fallback. Transport/generation/audit failures may instead use audited templates. A nonempty configured key is still required before normal realization/abstention/fallback; health does not establish that it is live.

## Import a game or position

`POST /api/games/import`

```json
{
  "input":"1. e4 e5 2. Nf3 Nc6 *",
  "player_color":"white",
  "target_rating":1500,
  "platform":"pgn",
  "budget_profile":"quick"
}
```

| Field | Type, default and validation |
| --- | --- |
| `input` | Required string; 1–200,000 characters before trimming. Whitespace-only fails parsing. PGN, standalone FEN, or supported fully qualified HTTP(S) URL. |
| `player_color` | `"white"` or `"black"`; default `"white"`. Influences critical selection and frontend orientation. |
| `target_rating` | Integer 1200–2000 inclusive; default 1500. Passed as the commentary rating band; does not enable a human-policy engine. |
| `platform` | `"lichess"`, `"chesscom"`, `"pgn"`, `"fen"`, `"other"`; default `"pgn"`. Stored metadata, not parser dispatch or a platform authorization. |
| `budget_profile` | `"quick"`, `"standard"`, `"deep"`; default `"standard"`. Search factors 0.25 / 1 / 2 with 1,000-node minimum per configured budget; not time/cost caps. |
| `username` | Optional string or null; maximum 64 characters. Required by the Chess.com direct-URL importer, which applies stricter username rules. Not persisted as a game field. |

This model is not strict-extra-forbidden: unknown JSON keys are ignored by Pydantic, not new features. Do not rely on frontend's broader `platform: string` type to accept arbitrary values.

Processing checks configuration, queue capacity, fetches/parses, enforces the 600-half-move mainline limit, checks admission again, persists a game and queued skeletons, then submits it. It does not wait for analysis. Response is the full [GameDetail](#game-and-ply-response-shapes), normally `pending` with revision 1 and null ledgers/commentary. Read subsequent state rather than assuming exact timing. There is no import deduplication or idempotency key; repeating a request creates another game and job.

Explicit admission failures:

- 429 `Analysis queue is full. Wait for existing games to finish.`
- 429 `Analysis queue is full or shutting down.`
- 422 `Games are limited to 600 half-moves per import.`
- 422 `Only Lichess and Chess.com game URLs are supported.`
- Other 422 details come from strict parser/importer exceptions.

The 20-entry waiting queue is process-local, with one active worker; it is not a per-user quota. URL fetch failure is an importer error, generally mapped to 422 rather than upstream 4xx/5xx propagation.

### Supported inputs and caveats

- PGN: one standard-chess game. Unknown/trailing text, illegal moves/variations, unsupported variants, inconsistent result/setup headers and incorrect explicit `+`/`#` fail. Legal variations/comments/NAGs are validated or consumed but omitted from clean analysis PGN; imported comments are quarantined and excluded from public responses.
- FEN: a valid standard board, with a parser warning and `has_full_history=false`. Receives synthetic ply 0 (`san_move="Position"`, `uci_move=""`). Engine-nominated comparisons at that position are not historical played moves.
- Setup PGN: `SetUp "1"` and `FEN` must appear together. Parsing can succeed while downstream analysis fails because custom-root history reconstruction is limited; **setup-FEN with subsequent moves is not guaranteed end-to-end supported**. Earlier repetition history is unavailable for both standalone FEN and setup PGN.
- Lichess URL: HTTP(S), host `lichess.org` or `www.lichess.org`; path `/{id}`, `/game/export/{id}` or `/embed/{id}`, optionally `/white` or `/black`. IDs are 8 or 12 alphanumerics (first 8 identify the game). Credentials/custom ports are rejected. Fetching uses a fixed HTTPS export endpoint. Through this route, bare IDs and scheme-less URLs are parsed as chess text and fail, even though internal helper functions accept some of them.
- Chess.com URL: HTTP(S), host `chess.com` or `www.chess.com`; path `/(game/)?(live|daily)/{numeric_id}`. Requires `username` and searches up to 12 most recent archive entries for that user. Older/unpublished/private games and unsupported URL paths cannot be retrieved this way. Archive URLs must be validated HTTPS `api.chess.com` monthly paths for the requested user. Pasting PGN avoids archive discovery, not chess validation.

The route's `input` length constraint does not separately cap fetched PGN response size. Upstream availability, rate limits and changes remain external dependencies. Analysis is bounded evidence, not a correctness guarantee.

## List and retrieve games

`GET /api/games` returns at most the latest 50 `GameSummary` records by descending `created_at`. It has no implemented limit, page, search or status query parameter. Summaries include clean `pgn_text` but not `plies` or quarantined comments.

`GET /api/games/{game_id}` returns `GameDetail` (the same summary plus ascending-ply `plies`). Unknown ID: HTTP 404 `{"detail":"Game not found."}`. These reads do not require a configured provider/engine and do not trigger analysis.

### Game and ply response shapes

A `GameSummary` contains these wire fields (none of the internal `*_json` columns):

```json
{
  "game_id":"game_0123456789ab",
  "created_at":"2026-11-11T02:00:00+00:00",
  "pgn_text":"[Event \"?\"]\n\n1. e4 *",
  "fen_root":"rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
  "has_full_history":true,
  "white":"White",
  "black":"Black",
  "result":"*",
  "event":"?",
  "player_color":"white",
  "target_rating":1500,
  "platform":"pgn",
  "analysis_status":"pending",
  "critical_plies":[],
  "warnings":[],
  "error":null,
  "budget_profile":"standard",
  "revision":1
}
```

IDs/times above are illustrative; PGN header/default content varies with input. `critical_plies` and `warnings` are arrays, `error` is string or null, `revision` is a stored integer. `untrusted_comments` is intentionally **absent**, despite a legacy declaration in frontend types.

`GameDetail = GameSummary + {"plies": PlyAnalysis[]}`. A queued row has this complete shape:

```json
{
  "game_id":"game_0123456789ab",
  "ply":0,
  "move_number":1,
  "turn":"white",
  "uci_move":"e2e4",
  "san_move":"e4",
  "fen_before":"rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
  "fen_after":"rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq e3 0 1",
  "state_before_hash":"<SHA-256 hex>",
  "state_after_hash":"<SHA-256 hex>",
  "coarse_eval_cp_white":null,
  "coarse_mate_white":null,
  "coarse_eval_after_cp_white":null,
  "coarse_mate_after_white":null,
  "eval_swing_cp":0,
  "critical_score":0.0,
  "critical_reason":{},
  "is_critical":false,
  "deep_status":"queued",
  "priority_boost":0,
  "ledger":null,
  "commentary":null
}
```

Hashes above are descriptive placeholders, not real digests. `ply` is a zero-based half-move index, **not** a full move number. Analysis explains the choice from `fen_before`, even though the UI can display `fen_after`. Before/after cp and mate values are nullable integers with White's perspective. A mate result uses the separate mate field, not an artificial cp number. `eval_swing_cp` is mover-relative (after minus before; a loss is negative); zero can also reflect insufficient coarse confidence. `critical_reason` is `{}` or `{ply,total_score,eval_swing_score,sharpness_score,tactical_motif_bonus,phase_diversity_adjustment,primary_reason}`. Scores are numbers and reason is a string.

Game statuses: `pending`, `auto_analyzing`, `auto_complete`, `full_analyzing`, `full_complete`, `failed`. Ply statuses: `queued`, `running`, `completed`, `abstained`, `failed`. `auto_complete` is only selected-critical-moment completion. Failure can leave non-running rows queued. Startup marks interrupted nonterminal games failed; there is no durable resume endpoint.

### Deep ledger and commentary

`ledger` and `commentary` stay null until a result is written; clients must tolerate sparse/partial games. Normal deep results serialize [MomentClaimLedger](../backend/evan/claims/schema.py), with orchestrator additions:

| Ledger fields | Shape |
| --- | --- |
| `ply`, `move_number`, `turn`, `played_san`, `best_san`, `root_fen`, `root_state_id`, `root_state_hash`, `uci_history`, `stability_status` | Integers, color/string labels, FEN/state identifiers, string-array history. Stability is `stable`, `near_equal`, `unstable_drift`, `unstable_reversal`, `incomplete`. |
| `claims` | `ClaimRecord[]`, below. |
| `branch_pv_san_map`, `branch_legal_sans_map`, `branch_fens_map` | Object keyed by branch ID, values string arrays. PV/FEN traces cover at most eight half-moves plus root FEN; engine records may retain longer PVs. Legal-SAN map alone does not establish ordered PV validity. |
| `evidence_branch_map`, `evidence_witness_map` | Evidence ID → branch ID and evidence ID → serialized board observation/line event/engine record. |
| `challenge_outcomes` | Array of defensive-search outcomes, below. |
| `engine_metadata` | Primary `EngineAnalysisRecord[]`; not a separate engine consensus. |
| `audit_log` | Variable event dictionaries (`stage`, `event`, reports, failures, rejected repair output, usage as applicable); not a fixed event schema. |
| `evidence_graph` | Root FEN/state/history, root undefended/pin observations, `branch_traces`, evidence maps. See [graph.py](../backend/evan/evidence/graph.py) and [detector models](../backend/evan/evidence/detectors.py). |
| `branch_bundle` | Root position/history/turn, `branches`, played/best branch IDs, played-is-best/ranking-reversal/near-equal flags, stability and cp gap. Each branch has `branch_id`, `root_move_uci`, `root_move_san`, `role`, `nomination_source`, `tier1_record`, `primary_record`, `score_drift_cp`, `is_stable`. |
| `has_full_history` | Boolean; no reconstruction of missing pre-setup history. |
| `metrics` | `{elapsed_seconds:number,llm_usage:object,llm_cost_usd:number|null,node_budget_note:string}`. MultiPV rows may share reported node totals; do not sum identical totals from one search. |

A claim contains:

```text
claim_id, type, proposition, root_state_id, branch_id,
applicable_state_ids[], support_evidence_ids[], evidence_source, assertion_scope,
line_event_plies[], validation_results{}, challenge_queries[],
discovered_contradictions[], unresolved_questions[], status, preview_fen, arrows[]
```

`type`: `state_fact`, `conditional_line_event`, `engine_preference`, `motif`, `plan_interpretation`, `exact_outcome`. `status`: `assert`, `qualify`, `abstain`. Scope: `current_board_only`, `in_displayed_continuation`, `across_analyzed_defenses_at_budget`, `engine_preference_at_budget`, `heuristic_interpretation`, `exact_rules_or_tablebase`. Some enum values are extension vocabulary rather than currently emitted evidence: no enabled tablebase and no builder promotion to across-defense scope. See [scope semantics](ARCHITECTURE.md#claim-scopes-and-validation). Arrow shape: `{orig:string,dest:string,brush:string}` (algebraic squares, color name).

Engine records carry `evidence_id`, `engine_name`, `engine_path`, `binary_sha256`, `options_fingerprint`, `uci_options`, nullable `network_hash`, `threads`, `hash_mb`, `hash_policy`, `root_fen`, `root_state_hash`, `uci_history[]`, nullable `allowed_root_moves[]`, `multipv_index`, `node_limit`, `reported_nodes`, `depth`, `seldepth`, `wall_time_seconds`, nullable `score_cp_white`, `score_cp_mover`, `mate_white`, `mate_mover`, `wdl_white`, plus `score_bound`, `is_complete`, `pv_uci[]`, `pv_san[]`. WDL is null or a three-integer White win/draw/loss array. Score bounds are `exact`, `upperbound`, `lowerbound`; an exact engine bound is not a solved-game claim. `network_hash` is an option descriptor, not a file-content digest.

Challenge outcome fields: `query_id`, `branch_id`, `challenged_at_ply_offset`, `opponent_punishing_move_san`, `defenses_tested[]`, `refutation_holds_across_top_defenses`, `evaluation_only_check`, `discovered_contradictions[]`, `recommended_scope`. A defense has `defense_uci`, `defense_san`, nullable `eval_cp_original_mover`, nullable `mate_original_mover`, `pv_san[]`. These checks cover selected replies after the first two PV moves, not every legal defense or every event's semantic truth.

Normal commentary shape:

```json
{
  "sentences":[],
  "abstention_notice":"EVAN abstains: no independently supported coaching explanation is available at this analysis budget.",
  "provider":"openrouter",
  "model":"openai/gpt-4o-mini",
  "usage":{},
  "cost_usd":null,
  "used_fallback":false,
  "audit_passed":true
}
```

Each nonempty sentence is `{sentence_id:string,text:string,claim_ids:string[],branch_id:string,preview_fen:string,arrows:BoardArrow[]}`. Although the schema permits multiple claim IDs, the auditor currently requires exactly one supported claim and its scope-prefixed proposition. `abstention_notice` is null or the fixed notice in the normal audited path. `usage` can include `requests[]` with raw provider usage/cost plus accumulated token fields; it is **not** just `Record<string, number>`. `cost_usd=null` indicates unavailable/incompletely reported cost, not free use. `used_fallback` is the actual flag; the backend does not emit `used_template`.

**Terminal-board exception:** the worker writes only `ledger={claims:[],audit_log:[],root_fen:string,exact_outcome:string|null}` and `commentary={sentences:[],abstention_notice:"This position is already terminal under the applicable chess rules; no move comparison is available.",audit_passed:true}`. This sparse shape bypasses normal LLM/auditor processing and omits normal metadata. Do not assume every non-null ledger is a complete `MomentClaimLedger`.

## Browse public platform games

`GET /api/importers/{platform}/{username}?max_games=10`

- `platform`: `lichess` or `chesscom` only; literal `chess.com` is not the route value.
- `max_games`: integer 1–25 inclusive, default 10.
- Lichess username: trimmed, 2–30 characters matching `[A-Za-z0-9][A-Za-z0-9_-]{1,29}`.
- Chess.com username: trimmed/lowercased, 2–40 characters matching `[a-z0-9][a-z0-9_-]{1,39}`.

Lichess response entries:

```json
{"id":"abcdefgh","white":"PlayerA","black":"PlayerB","speed":"rapid","winner":null,"pgn":"1. e4 e5 *","platform":"lichess"}
```

Chess.com entries (no `winner`/`speed` field):

```json
{"id":"123456789","url":"https://www.chess.com/game/live/123456789","white":"playera","black":"playerb","time_class":"rapid","pgn":"1. e4 e5 *","platform":"chesscom"}
```

These are illustrative entries; fields come from upstream data, not a validated universal upstream schema. Empty available results return `[]`. Chess.com scans at most 12 most recent archive entries and skips games without nonempty PGN; Lichess reads an NDJSON public-game response. Results are not persisted or automatically analyzed, nor comprehensively filtered for standard variants. Pass a selected `pgn` to the import endpoint for validation/analysis. Missing users, upstream errors, invalid upstream JSON/archive destinations and network errors become HTTP 422 `detail` strings. Browsing does not require provider/Stockfish configuration.

## Prioritize deferred analysis

`POST /api/games/{game_id}/plies/{ply}/prioritize` has no request body.

```json
{"prioritized":true}
```

For a nonterminal game, an existing queued ply gets `priority_boost += 100` and a revision notification. Existing running/completed/abstained rows also return `true`, but receive no boost or new job. For `full_complete` or `failed`, an existing ply returns `{"prioritized":false}`. Missing ply returns 404 `{"detail":"Ply not found."}`. The response never includes a `game` field, despite the frontend's permissive response type.

Priority changes selection among deferred queued plies after critical analysis. It does not restart failed work, preempt a search, reorder critical moments, or promote a game in the global FIFO queue. Repeated requests can add repeated boosts to a queued row.

## Server-sent events

`GET /api/games/{game_id}/events`

Headers: `Content-Type: text/event-stream`, `Cache-Control: no-cache`, `X-Accel-Buffering: no`. Events carry JSON in one `data:` line, terminated by a blank line. There is no authentication token or body.

| Event | Data | Behavior |
| --- | --- | --- |
| `snapshot` | Full `GameDetail` | Immediately on connection, then when the observed revision changes; includes `id: {revision}`. |
| `moment_ready` | One complete `PlyAnalysis` row, **not** a `GameDetail` or `{game:...}` wrapper | After a snapshot, once per completed/abstained ply per connection. Includes deferred plies too, not just critical moments. No event ID of its own. |
| `complete` | Full `GameDetail`, status `full_complete` | Terminal; server closes stream after emitting. |
| `error` | Full `GameDetail`, status `failed`, including nullable `error` | Terminal analysis failure event over an HTTP 200 stream; not a `detail`-only HTTP error. Server closes after emitting. |

Illustrative framing (placeholders are explanatory, not literal JSON payloads):

```text
id: 7
event: snapshot
data: <GameDetail JSON>

event: moment_ready
data: <PlyAnalysis JSON>

: keepalive

```

Idle connections receive `: keepalive` after a 15-second wait without notification. Disconnect ends that subscription, not analysis. A terminal game still emits a snapshot, ready rows and the corresponding terminal event when newly subscribed.

This is **latest persisted state**, not guaranteed delivery of every status transition. Multiple revisions can coalesce; snapshot reads are not one atomic database-wide transaction. `Last-Event-ID` is allowed by CORS but is not read by the route, and there is no historical event replay. Reconnecting starts fresh and can resend all completed/abstained rows. Replace state by `game_id`/revision and upsert ready rows by `ply`; do not treat duplicate ready events as duplicate analyses. Browsers' transport-level EventSource `error` callbacks are distinct from a named error event with JSON data.

The current frontend updates from full snapshots. Its registered `moment_ready` listener sends the row to a generic game handler that does not merge standalone rows; snapshots supply the visible updates.

## Exports

Both routes work before full completion and export currently persisted results, including null ledgers/commentary. There is no “wait until complete” option. Unknown game is 404; neither export requires a working provider/engine configuration.

`GET /api/games/{game_id}/export/pgn`

- `Content-Type: application/x-chess-pgn`.
- `Content-Disposition: attachment; filename="{game_id}.pgn"`.
- Clean stored mainline PGN plus available commentary/abstention notes and `[%evan_claim_ids "..."]` comment tags.
- Alternative branch PVs are added as legal conditional variations (up to eight half-moves); original imported comments/variations are not restored. Generated comment text has braces/control characters sanitized.
- Claim-ID tags refer to IDs inspectable in the JSON ledger, not embedded proof objects. Conditional variations are not exhaustive proof trees.

`GET /api/games/{game_id}/export/ledger`

- `Content-Type: application/json`.
- `Content-Disposition: attachment; filename="{game_id}-ledger.json"`.
- Body:

```json
{
  "schema_version":"0.1.0",
  "game":{},
  "plies":[],
  "limitations":[
    "Engine variations are conditional examples, not exhaustive proof trees.",
    "Passing automated prose checks does not certify all natural-language implications.",
    "Optional Maia, Lc0 and tablebase interfaces are not enabled integrations."
  ]
}
```

Here `game` is the actual `GameSummary` and `plies` is the actual `PlyAnalysis[]`, not empty when records exist. Quarantined `untrusted_comments` is removed. Engine paths, provider output/audit data and other analysis metadata can still be present; review privacy before sharing. The schema version does not imply a formal compatibility/migration guarantee for every nested audit field.

## curl examples

Use a POSIX shell (or equivalent quoting in your shell); on Windows PowerShell invoke `curl.exe` and adapt multiline/JSON quoting as needed. No real credentials belong in these API requests. Configure the backend separately, then:

```sh
BASE=http://127.0.0.1:8000
curl -sS "$BASE/api/health"
curl -sS "$BASE/api/games"
curl -sS -X POST "$BASE/api/games/import" -H 'Content-Type: application/json' --data-raw '{"input":"1. e4 e5 2. Nf3 Nc6 *","player_color":"white","target_rating":1500,"platform":"pgn","budget_profile":"quick"}'
```

Copy `game_id` from the 201 response; the ID below is a placeholder:

```sh
GAME_ID=game_replace_with_returned_id
curl -sS "$BASE/api/games/$GAME_ID"
curl -N "$BASE/api/games/$GAME_ID/events"
curl -sS -X POST "$BASE/api/games/$GAME_ID/plies/0/prioritize"
curl -fS "$BASE/api/games/$GAME_ID/export/pgn" -o annotated.pgn
curl -fS "$BASE/api/games/$GAME_ID/export/ledger" -o ledger.json
```

`curl -N` disables client buffering. Run priority/downloads in another terminal if the stream is still open. Export files are created in your current directory.

```sh
curl -sS "$BASE/api/importers/lichess/DrNykterstein?max_games=3"
curl -sS -X POST "$BASE/api/games/import" -H 'Content-Type: application/json' --data-raw '{"input":"4k3/8/8/8/8/8/8/4K3 w - - 0 1","platform":"fen","budget_profile":"quick"}'
```

The FEN example is an insufficient-material terminal board and illustrates the sparse terminal-result path; it does not test live LLM generation. Public-user results/availability can change. For a local PGN file, encode its contents as the JSON `input` string; this API has no multipart/file-upload endpoint (the browser reads files and submits JSON).

## Contract checks

See [API/queue tests](../backend/tests/test_api_and_deferred_queue.py), [configuration tests](../backend/tests/test_config.py), [importer tests](../backend/tests/test_importers.py), [export tests](../backend/tests/test_exporter.py) and [realizer/audit tests](../backend/tests/test_realizer_and_audit.py). Source definitions: [game routes](../backend/evan/api/routes_games.py), [export routes](../backend/evan/api/routes_export.py), [repository serialization](../backend/evan/storage/repository.py), [claim models](../backend/evan/claims/schema.py), [commentary models](../backend/evan/realizer/schema.py), [engine models](../backend/evan/engines/protocols.py). Live providers, upstream platforms and arbitrary custom-setup histories are not guaranteed by mocked contract tests.
