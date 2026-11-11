# Implemented architecture

EVAN 0.1.0 is a local chess-review workbench: a Python/FastAPI backend runs bounded Stockfish searches, builds branch-specific evidence and claims, and uses an LLM to select supported commentary. A React frontend displays positions, explanations, provenance, and exports. Evidence links and automated audits reduce particular failure modes; **they do not guarantee perfect chess analysis, exhaustive defenses, or complete natural-language truth**.

See the [documentation index](README.md), [setup](SETUP.md), [development checks](DEVELOPMENT.md) and [HTTP API](API.md). Runtime behavior is defined by [backend code](../backend/evan/) and [tests](../backend/tests/), not [historical proposals](HISTORY.md).

## Components and boundaries

| Component | Responsibility and source |
| --- | --- |
| API/application | [app.py](../backend/evan/api/app.py), [game routes](../backend/evan/api/routes_games.py), [export routes](../backend/evan/api/routes_export.py): construct repository/orchestrator, configuration checks, imports, reads, priority, SSE, downloads; optionally serve `frontend/dist`. |
| Chess input/state | [parser.py](../backend/evan/chess_core/parser.py), [state.py](../backend/evan/chess_core/state.py): strict standard-chess parsing, legal replay, clean mainline PGN, history-aware state identities. |
| Platform importers | [importers](../backend/evan/importers/): public Lichess PGN/NDJSON and Chess.com monthly archives via `httpx`; no account login/OAuth. |
| Engine adapter | [stockfish.py](../backend/evan/engines/stockfish.py): local UCI process, bounded searches, normalized scores/PVs, binary/options metadata, persistent engine-result cache. |
| Scheduling/search | [pipeline](../backend/evan/pipeline/): coarse evaluation, critical-moment selection, legal candidates, two-budget root-restricted branch searches, serial background processing. |
| Evidence/claims | [evidence](../backend/evan/evidence/), [claims](../backend/evan/claims/): replay witnesses, limited defensive challenges, typed scopes, branch isolation, uncertainty/abstention. |
| Commentary/audit | [realizer](../backend/evan/realizer/), [prose_checker.py](../backend/evan/audit/prose_checker.py): constrained sentence selection, deterministic checks, one repair attempt, audited template fallback. |
| Storage/export | [repository.py](../backend/evan/storage/repository.py), [schema.sql](../backend/evan/storage/schema.sql), [pgn_exporter.py](../backend/evan/export/pgn_exporter.py): SQLite persistence, revisions, annotated PGN and JSON ledger. |
| Browser workbench | [App.tsx](../frontend/src/App.tsx), [client.ts](../frontend/src/api/client.ts), [components](../frontend/src/components/): health/library bootstrap, import, EventSource snapshots, board/branch previews, priority, claim/audit inspection and downloads. |

```text
PGN / FEN / supported public URL
  -> URL fetch if needed -> strict parser -> cleaned game + queued ply skeletons
  -> SQLite -> in-process game queue -> coarse Stockfish pass
  -> selected critical moments -> remaining queued plies
       -> legal candidate moves -> two-budget branch searches
       -> replay evidence + selected defensive challenges -> scoped claim ledger
       -> LLM sentence selection -> deterministic audit / repair / fallback
       -> persisted commentary, ledger, revision -> SSE snapshot -> React workbench
  -> annotated PGN / JSON ledger download at any stage
```

The LLM is not the engine, move generator, or source of new tactical explanations. The current prompt supplies already scoped, deterministic sentences; the model selects/orders them for a rating band rather than freely paraphrasing.

## Import and state identity

1. The import route checks provider credentials/base URL and Stockfish path, then queue capacity. These are presence/path checks, not live provider or UCI readiness tests.
2. Only an input starting with `http://` or `https://` enters URL dispatch. The host chooses Lichess or Chess.com independently of the request's `platform` metadata. Bare IDs and scheme-less URLs accepted by some internal helpers are not URL imports through this route.
3. The parser consumes one standard-chess game or a standalone FEN. It rejects unknown/trailing movetext, illegal SAN/variations, incorrect explicit check/mate suffixes, duplicate/malformed headers, inconsistent result declarations, incompatible `SetUp`/`FEN`, and unsupported variants. It validates variations but retains only mainline moves for analysis. A PGN result may represent resignation/agreement; it is not proof that the final board has that rules outcome.
4. Original mainline/root comments and column-one `%` escape-line text are quarantined as `untrusted_comments`. Clean PGN keeps selected header values and mainline moves, without imported comments, variations, or NAGs. Quarantined comments remain in SQLite but are omitted from public game responses and ledger exports. Player/header strings remain untrusted data, not instructions.
5. Each mainline move receives a zero-based `ply`, before/after FEN and state hash. Move-less custom positions receive synthetic ply `0`, SAN `Position`, empty UCI, and identical before/after states.

`GameStateIdentity` hashes a canonical payload containing raw-en-passant FEN, initial board, actual and supplied history, history-boundary FEN, repetition count and reversible tail. FEN includes turn, rights, en-passant target and both rule counters. Repetition comparison uses legally relevant en-passant availability. Equal piece layouts alone therefore need not share state hashes. This records available context; it cannot reconstruct unknown prior history.

### Input/platform limits

- Import JSON `input` is limited to 200,000 characters; accepted mainlines to 600 half-moves. The character field constraint is on submitted input, not a separate cap on fetched response bodies.
- Standard chess only: no Chess960, Atomic, Crazyhouse or other variants. Malformed input is rejected rather than silently repaired. Some otherwise permissive PGN dialects will not parse.
- Lichess game URLs use supported ID/export/embed forms; recent-game browsing is public and limited to 1–25 results per call.
- Chess.com direct URLs require a username. Fetching searches only the **12 most recent archive entries** for that user, not all historical games or necessarily the last twelve calendar months. Unsupported URL forms, unavailable/private games, rate limits and upstream failures can prevent import.
- Recent-game listings are not a standard-variant certification; the parser remains the import gate.
- Standalone FEN and setup-PGN explicitly set `has_full_history=false` and warn about unavailable repetition history, even for an explicit standard-start setup.
- **Setup-FEN with moves is not a reliable end-to-end path.** Parsing accepts it, but later evidence reconstruction can replay supplied history from the standard initial position and fail for a custom root (or lose context at an irreversible boundary). Parser acceptance is not a promise of successful analysis. Standalone FEN has no earlier history to recover either.

## Scheduling and bounded analysis

One `AnalysisOrchestrator` holds an `asyncio.Queue(maxsize=20)` of waiting game IDs and a single worker. Games run serially; Stockfish calls are offloaded to threads so HTTP/SSE can continue. Shutdown shields/awaits an active engine call before cleanup. This is not a durable distributed job queue or a multi-worker deployment design.

Normal game status progression:

```text
pending -> auto_analyzing -> auto_complete -> full_analyzing -> full_complete
                                  any worker failure -> failed
```

- The coarse pass searches each pre-move position with MultiPV 2, plus a final nonterminal position. White-perspective evaluations, mate values and mover-relative swings feed the timeline and selector.
- Critical selection combines evaluation/win-probability swing, top-two sharpness, captures/checks/mate indicators, chosen player color, phase diversity and spacing. Configured count is 3–6 (default 5), capped by game length. Selected moments are deep-analyzed in chronological order. A move-less position uses critical list `[0]`, without a normal coarse-selected `is_critical` row.
- `auto_complete` means selected moments finished, not all plies. It is transient and may not appear in every streamed snapshot.
- Deferred work picks the queued row with greatest `(priority_boost, abs(eval_swing_cp), -ply)`. Priority adds 100 to a queued row and affects this deferred phase; it does not preempt running searches, reorder the critical loop, or move a game ahead of other games.
- Ply states are `queued`, `running`, `completed`, `abstained`, `failed`. A commentary abstention notice makes a result `abstained`; individual abstaining claims can coexist with completed, supported commentary.
- An already-terminal board takes a special path: empty claims/sentences, a rules outcome in the ledger and a terminal notice, without LLM generation or the normal prose-audit pipeline.

Budgets are node limits, not latency or dollar limits. `quick`, `standard`, `deep` multiply configured coarse/tier-1/primary/challenge limits by 0.25, 1, 2, with each effective limit floored at 1,000. Default standard budgets are 25,000 / 75,000 / 150,000 / 60,000 nodes. Every candidate gets separate tier-1 and primary root-restricted searches; challenge calls and whole-game length add work.

Worker errors persist `analysis_status=failed`; the active running ply becomes failed, while other queued rows may remain queued. Startup marks all previously nonterminal games failed instead of resuming them. Retry means importing again; there is no resume, cancellation, deletion, deduplication or reanalysis endpoint.

## Branch search, provenance and evidence

Candidate selection always includes the played legal move, then unique legal MultiPV nominations, up to three candidates total by default. A legal fallback is possible when nominations provide no alternative. The orchestrator does not supply a human-policy model. For standalone FEN, the first nominated move occupies the comparison's `played` slot; no historical played move is inferred.

Each candidate has `branch_id = br_p{ply}_{role}_{uci}` and records its role, nomination source and root move. Tier-1 and primary searches restrict the same root move; recorded PVs are legally replayed. Missing score/PV, illegal/truncated PV or non-exact UCI score bounds reduce confidence. Engine `score_bound="exact"` means an engine search bound classification, **not a solved chess position**. Mate scores remain separate from centipawns; coarse ranking helpers use synthetic mate-comparison values, not measured centipawn evaluations.

The bundle records selected best/played branches, score gap, drift, ranking reversal, near equality and stability (`stable`, `near_equal`, `unstable_drift`, `unstable_reversal`, `incomplete`). “Best” is relative to the candidates/searches actually run, not every legal move at unlimited depth. The builder qualifies ranking reversals and abstains from confident preferences for incomplete searches; `unstable_drift`/`near_equal` remain visible metadata, not a universal suppression rule.

The evidence graph contains:

- Root observations of undefended/effectively unprotected pieces and absolute king pins.
- A replay trace per branch, limited to the first **eight half-moves**: root/post-move FENs, state IDs/hashes, SAN/UCI, captures, promotions, checks, checkmate, selected double attacks and early pins.
- Maps from evidence ID to owning branch and serialized witness. Engine records are witnesses too.

These are deliberately limited detectors. Attack/protection and fork classification are board-based heuristics, not complete tactical exchange analysis or strategic causation. Material changes in a PV are conditional events, not proof of forced profit.

For branches containing capture/double-attack/mate/promotion evidence, the challenger replays the first two PV moves and asks for up to three replies at that position. It records evaluation contradictions (including replies at least −60 comparable cp for the original mover). This is **evaluation-only checking of selected replies**, not independent validation of each tactical event or exhaustive adversarial proof. `refutation_holds_across_top_defenses=true` must not be read as “wins against every defense.” Except a rules-detected terminal mate, the challenger recommends `in_displayed_continuation`; it does not promote arbitrary claims to universal scope. The builder attaches relevant played-line contradictions to later played-line events; alternative-line claims are not all independently qualified by these challenge results.

## Claim scopes and validation

A `ClaimRecord` binds a proposition to root/branch/state identifiers, support evidence IDs, source, scope, status, preview FEN, arrows and unresolved/challenge information. Current builder behavior:

| Scope | Meaning and implementation |
| --- | --- |
| `current_board_only` | Root board observation, not a prediction. Builder emits selected attacked/unprotected-piece facts. |
| `in_displayed_continuation` | Capture/motif/check/promotion/mate event in a specific replayed line; other replies need not reproduce it. |
| `engine_preference_at_budget` | Search comparison at recorded node budgets; incomplete/non-exact results abstain, reversals qualify. |
| `heuristic_interpretation` | Tentative interpretation/notice that detectors cannot establish a concrete causal reason. Not invented strategic certainty. |
| `exact_rules_or_tablebase` | Builder uses this for checkmate replayed on the first move of a branch. The current implementation has no enabled tablebase probing. Later PV mates remain conditional. |
| `across_analyzed_defenses_at_budget` | Defined in schema/templates, but the current builder does not emit this scope. It would still be budget-limited, not all-defense proof. |

Statuses are `assert`, `qualify`, `abstain`. Validation rejects missing support for non-abstaining claims and unknown/mismatched evidence IDs. Root evidence is allowed for state facts; engine preferences may explicitly compare the played and best branches. Other claims cannot borrow evidence from another branch. `validation_results.scope_verified` stores the selected scope string; it is not a separate formal proof of that scope. Provenance IDs/hashes identify context, not cryptographic attestations of truth.

## Commentary audit and fallback

The provider receives allowed scope-prefixed sentences and a rating band, not raw imported PGN comments or arbitrary headers. Cloud requests use OpenRouter/OpenAI chat completions or Anthropic messages; `local` uses an OpenAI-compatible endpoint and still requires a nonempty key and base URL.

Generation must return only a `sentences` object. Schema/parsing rejects invalid citations, abstaining claims, duplicate sentence IDs and branch mismatch. The deterministic auditor additionally checks:

- Exactly one supported claim per sentence, with text equal to its scope-prefixed proposition after whitespace normalization; qualification prefixes are retained. Free paraphrases are intentionally rejected.
- SAN tokens and ordered PV sequences against replayed branch data; comparison claims have a narrow root-move exception.
- Disallowed forcing/universal language for non-exact claims, matching previews/arrows, valid preview boards and allowed abstention notices.

A failed audit requests one LLM repair and re-audits it. Generation/format/transport errors can go directly to deterministic templates. Templates use the same proposition projection and are audited; rejected sentences are dropped with an abstention notice, then empty abstention is attempted. An unusable ledger can still fail the job. Logs retain audit reports, generation failures and rejected repair output; provider-reported usage/cost is accumulated when available. `cost_usd=null` means cost was not fully reported, not zero cost.

Missing configuration or provider HTTP 401/403 raises `ConfigurationError` and fails rather than quietly disguising authentication failure as template success. A key is required even if a particular position ultimately abstains or falls back. There is no configuration-free template-only import mode. Ordinary audit success measures adherence to the ledger/checker; neither `audit_passed` nor fallback certifies the upstream claims or all implications of English text. The separate terminal-position path sets `audit_passed=true` without running these normal prose checks.

## Persistence, caching and updates

SQLite uses per-operation connections, WAL, foreign keys and transactions. Tables store games, per-ply skeleton/coarse/deep results and engine-cache JSON. Initialization creates tables and adds missing `error`, `budget_profile`, `revision` columns to games; this is a small ad hoc migration, not a general migration framework.

Engine cache keys fingerprint state history, binary SHA-256, options fingerprint, threads, hash memory/policy, node budget, MultiPV and sorted root restrictions. Cache reads/writes occur only under the default clear-hash policy; only nonempty complete, exact-bound search records are written. The engine is opened before a lookup to discover actual options/name. Hash is cleared before a new search when supported. Cached records preserve original timing metadata; there is no cache-hit flag, expiry, eviction, public cache management or prose cache. `network_hash` currently records `EvalFile`/`EvalFileSmall` option descriptors, **not a digest of external network file contents**; do not claim file-content verification from that field.

`notify()` increments a stored revision and signals an in-memory event. SSE sends a full game snapshot when revision differs, plus one ready-row event per completed/abstained ply per connection. There is a 15-second idle keepalive and terminal `complete`/`error`. It is a latest-state stream, not an event log: intermediate revisions may coalesce, reconnects resend ready rows, and `Last-Event-ID` is not used for replay. See [SSE details](API.md#server-sent-events).

The browser loads health/library together, fetches selected game details, and subscribes until terminal. It relies on full snapshots; although it registers `moment_ready`, its generic handler does not merge the standalone ply-row payload. Board previews use supplied branch FENs/arrows, not a new browser-side engine. Frontend interfaces omit some backend fields and still declare some fields that are not returned; backend serialization is the API authority.

## Security and deployment limits

**Keep both backend and frontend bound to loopback for personal use.** There is no application authentication, authorization, per-user isolation, TLS, API quota or production security boundary. The app itself does not enforce a localhost bind: server launch/network configuration controls exposure. Binding publicly exposes game data, local engine/path metadata, audit outputs and resource-consuming imports to reachable clients. CORS only allows the two port-5173 localhost origins for browser cross-origin access; it is not authentication and does not protect against direct HTTP clients or same-origin access. A 20-game queue is backpressure, not rate limiting.

Importer host/path/username checks and validated Chess.com archive URLs constrain outbound fetching; default clients do not follow redirects. These restrictions are not a general-purpose URL proxy or a complete hostile-input/resource-isolation guarantee. Provider base URLs and executable paths are operator-controlled settings, not request parameters; only trust local configuration and engine binaries.

Secrets are read from environment/`.env` and hidden from settings repr, not returned by API contracts. Provider prompts transmit supported chess explanations/rating information to the configured endpoint; audit records may persist provider output and usage locally. SQLite/quarantined comments and downloaded ledgers can contain sensitive game data. No encryption-at-rest, retention policy, secret scanner or backup service is implemented. Do not publish the database, `.env`, or unsanitized audit artifacts.

Use one backend process for the in-memory worker/notifications. Multiple processes sharing a database can mark one another's active games interrupted and do not share queue/SSE state. Reverse proxies must preserve streaming; `X-Accel-Buffering: no` is advisory, not a universal proxy setting.

## Unsupported/optional extension points and verification

`HumanPolicyProtocol`, `TablebaseProtocol`, policy/tablebase result models and `SECONDARY_ENGINE_PATH` exist, but the orchestrator does not integrate Maia, Lc0, a second-engine consensus pass or tablebases. Setting the secondary path does not enable them. There is no account sync, opening database, perfect strategic reasoner, exhaustive proof tree or guaranteed cost/latency bound.

Focused source-of-truth tests include [parser](../backend/tests/test_parser.py), [state/storage](../backend/tests/test_state_and_storage.py), [engine](../backend/tests/test_stockfish_engine.py), [branches](../backend/tests/test_branch_search.py), [claims](../backend/tests/test_claims_builder.py), [challenges](../backend/tests/test_challenger.py), [realizer/audit](../backend/tests/test_realizer_and_audit.py), [API/queue](../backend/tests/test_api_and_deferred_queue.py), [importers](../backend/tests/test_importers.py), [export](../backend/tests/test_exporter.py) and [frontend components](../frontend/src/__tests__/). Mocked provider tests do not establish that a chosen live model/key/endpoint works; real Stockfish tests require a usable executable. Treat tests as checked cases, not comprehensive safety or chess-quality certification.
