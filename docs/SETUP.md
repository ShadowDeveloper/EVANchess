# EVAN Setup

EVAN is a local analysis workbench: a FastAPI backend, a React/Vite frontend, a user-supplied Stockfish UCI executable, and a live LLM provider. This guide covers a local Windows PowerShell setup first, with portable shell commands where they differ.

> **Local-only warning:** EVAN has no production authentication, no TLS, no user isolation, and no API rate limiting. Bind the backend to `127.0.0.1` and do not expose it to the internet or an untrusted network. API keys stay in the server-side `.env`; never put them in the UI, a PGN, a URL, or source control.

## 1. Prerequisites

| Requirement | Notes |
| --- | --- |
| Python 3.11+ | `pyproject.toml` requires `>=3.11`. `uv` can install and manage the interpreter. |
| [uv](https://docs.astral.sh/uv/) | Used for dependency sync and all backend commands. Tested here with uv 0.12.x. |
| Node.js 20 LTS+ and npm | No `engines` pin exists; this workspace was verified on Node 22. Use the lockfile with `npm ci`. |
| Stockfish UCI executable | A real engine binary, not a Python package. Set `STOCKFISH_PATH` or put `stockfish` on `PATH`. |
| Live LLM credentials | Required for the selected provider. `local` still requires a non-empty key value. |
| Git | Optional, only for source control. |

From the repository root in PowerShell:

```powershell
uv python install 3.11
uv sync --extra dev
```

If `uv` is unavailable, install it from the official Astral instructions. The project declares Python 3.11 as its minimum version.

## 2. Create the environment file

```powershell
Copy-Item .env.example .env
```

Edit `.env` in your editor. Do not print it, commit it, paste it into chat, or place live keys in frontend files. `.env` is ignored by git, along with `*.db` files.

The backend loads `.env` from the repository when it imports `evan.config`. A real process environment variable takes precedence over the same name in `.env`; restart the backend after editing either. Values should normally be unquoted and have no spaces around `=`.

### Required settings

| Variable | Purpose |
| --- | --- |
| `STOCKFISH_PATH` | Absolute path to the Stockfish UCI executable, or a command available on `PATH`. |
| `EVAN_DB_PATH` | SQLite file. Default `evan.db` is relative to the backend process working directory. Prefer an absolute path to avoid ambiguity. |
| `EVAN_LLM_PROVIDER` | `openrouter`, `openai`, `anthropic`, or `local`. |
| `EVAN_LLM_MODEL` | Provider-specific model ID. The default `openai/gpt-4o-mini` is an OpenRouter-style ID; change it for the other providers. |
| `EVAN_LLM_BASE_URL` | Optional override for cloud providers. Required for `local`. |
| `OPENROUTER_API_KEY` | Required when `EVAN_LLM_PROVIDER=openrouter`. |
| `OPENAI_API_KEY` | Required for `openai`; also required by `local` as the bearer token value. |
| `ANTHROPIC_API_KEY` | Required when `EVAN_LLM_PROVIDER=anthropic`. |

Engine budgets have validated defaults: `EVAN_ENGINE_THREADS=1`, `EVAN_ENGINE_HASH_MB=64`, `EVAN_COARSE_NODES=25000`, `EVAN_DEEP_NODES_TIER1=75000`, `EVAN_DEEP_NODES_PRIMARY=150000`, `EVAN_CHALLENGE_NODES=60000`, and `EVAN_CRITICAL_MOMENTS_COUNT=5` (allowed range 3-6). All numeric engine settings must be positive.

### Provider selection

| Provider | Key | Default base URL | Model ID to configure |
| --- | --- | --- | --- |
| `openrouter` | `OPENROUTER_API_KEY` | `https://openrouter.ai/api/v1` | A model available to your OpenRouter account, for example `openai/gpt-4o-mini`. |
| `openai` | `OPENAI_API_KEY` | `https://api.openai.com/v1` | An OpenAI model ID, for example `gpt-4o-mini`. Do not use the OpenRouter `vendor/model` form unless your gateway supports it. |
| `anthropic` | `ANTHROPIC_API_KEY` | `https://api.anthropic.com/v1` | An Anthropic model ID. EVAN uses the `/messages` API for this provider. |
| `local` | `OPENAI_API_KEY` | None; `EVAN_LLM_BASE_URL` is required | The model name served by the local endpoint, for example `local-model`. |

For `local`, the endpoint must be OpenAI-compatible and serve `POST {EVAN_LLM_BASE_URL}/chat/completions`, normally with a base such as `http://127.0.0.1:1234/v1`. `OPENAI_API_KEY` must be a non-empty value even if the local server ignores authorization; it is sent as `Authorization: Bearer <value>`. The local provider is not keyless.

The code sends `temperature: 0`, `max_tokens: 4096`, and for OpenAI-compatible providers requests a JSON object response. Select a model that supports those features. The Anthropic path does not use the OpenAI `response_format` field.

### Stockfish path

PowerShell example:

```powershell
$sf = "D:\Chess\Engines\Stockfish\stockfish-windows-x86-64-universal.exe"
Test-Path -LiteralPath $sf
"uci`nquit" | & $sf | Select-String "id name"
```

The output should include an engine identity line. If `STOCKFISH_PATH` is unset, EVAN tries `stockfish` on `PATH`, then the legacy default `D:\Chess\Engines\Stockfish\stockfish-windows-x86-64-universal.exe`. `SECONDARY_ENGINE_PATH` is parsed but no secondary engine is currently used.

## 3. Install frontend dependencies

From the repository root:

```powershell
npm --prefix frontend ci
```

`npm ci` uses `package-lock.json`. Use `npm install` only if you intentionally need to update the lockfile.

## 4. Verify configuration

Terminal 1, from the repository root:

```powershell
$env:PYTHONPATH = "backend"
uv run uvicorn evan.api.app:create_app --factory --host 127.0.0.1 --port 8000
```

Terminal 2:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/api/health | ConvertTo-Json -Depth 4
```

A resolved configuration reports `"configured": true`. This checks that settings and the engine path are present; it does not authenticate the key or start Stockfish. If it reports `false`, the `configuration_errors` array names the missing key, missing local base URL, or unresolved Stockfish path without exposing secret values.

The backend is not installed as a package. From the repository root, set `PYTHONPATH=backend` as above or pass `--app-dir backend` to Uvicorn, as in the [quick start](../README.md#quick-start). Running plain `uvicorn evan...` without either can fail with `ModuleNotFoundError: No module named 'evan'`.

Portable equivalent:

```bash
cd /path/to/ChessCommentator
export PYTHONPATH=backend
uv run uvicorn evan.api.app:create_app --factory --host 127.0.0.1 --port 8000
```

## 5. Run the development app

Use two terminals, each started from the repository root.

Backend terminal:

```powershell
$env:PYTHONPATH = "backend"
uv run uvicorn evan.api.app:create_app --factory --host 127.0.0.1 --port 8000 --reload
```

Frontend terminal:

```powershell
npm --prefix frontend run dev
```

Open `http://localhost:5173`. Vite proxies `/api` to `http://127.0.0.1:8000`; keep the backend on port 8000. The browser only talks to Vite, so this proxy avoids CORS during normal development.

The backend CORS allowlist contains only `http://localhost:5173` and `http://127.0.0.1:5173`. Calling the API directly from another origin is intentionally not configured.

## 6. Build and launch the full app

The backend serves the built frontend when `frontend/dist` exists at startup. Run these commands from the repository root.

```powershell
npm --prefix frontend run build
$env:PYTHONPATH = "backend"
uv run uvicorn evan.api.app:create_app --factory --host 127.0.0.1 --port 8000
```

Open `http://127.0.0.1:8000`. The API and static frontend are then same-origin, so the Vite proxy is not involved. Rebuild after frontend changes and restart the backend if `frontend/dist` did not exist when the server started.

Do not use `npm run preview` as the complete application: this project configures a proxy only under the Vite dev server, not under the preview server. Preview serves static assets without the `/api` proxy. Use Vite development mode or the backend static mount instead.

## 7. Persistence and restart behavior

- The SQLite path comes from `EVAN_DB_PATH`; without it, `evan.db` is relative to the process working directory. Running with `--directory backend` therefore places the default database under `backend\evan.db`. Set an absolute path in `.env` for predictable behavior.
- The database is created and migrated additively at backend startup. Existing games, ply analyses, and the engine cache are retained across restarts.
- Analysis is not resumed. At startup, games that were not `full_complete` or `failed` are marked failed with `Analysis interrupted by server shutdown. Import again to retry.` Running plies are also marked failed.
- The analysis queue is in memory only. Up to 20 games can be queued; queued work does not survive a restart. Priority boosts are stored in SQLite, but interrupted games are marked failed and cannot be resumed.
- To reset local state, stop the backend first and delete `evan.db`, `evan.db-wal`, and `evan.db-shm`. This permanently deletes game history and the engine cache.

## 8. Setup troubleshooting

| Symptom | Cause and fix |
| --- | --- |
| `ModuleNotFoundError: No module named 'evan'` | From the repository root, add `--app-dir backend` to Uvicorn or set `PYTHONPATH=backend`. |
| `/api/health` reports `configured: false` | Read `configuration_errors`: missing/blank provider key, missing `EVAN_LLM_BASE_URL` for `local`, or a Stockfish path that does not resolve. |
| Import returns HTTP 503 | The same configuration checks that feed health failed. Fix the key or engine path and restart. |
| `STOCKFISH_PATH ... does not exist or is not executable` | Use a full path to the actual binary, verify it launches and answers `uci`, or add it to `PATH`. |
| Provider HTTP 401/403 | The selected provider, model, and API key do not match, or the account lacks access. Check `EVAN_LLM_PROVIDER`, `EVAN_LLM_MODEL`, and the provider-specific key. |
| Provider HTTP 404 or model errors | Usually a wrong `EVAN_LLM_MODEL` or base URL. For local servers, confirm `/chat/completions` is supported at the configured base URL. |
| Provider timeout or malformed output | The LLM request has a 65-second overall limit. Generation failures fall back to deterministic audited templates for that ply; a 401/403 configuration failure fails the game. |
| Frontend says the backend is unreachable | Start the backend on `127.0.0.1:8000`; open the Vite dev URL, not the preview URL; verify `/api/health` directly. |
| Database is locked | Run only one backend worker/process against the same database. Prefer an absolute `EVAN_DB_PATH`. SQLite waits up to 30 seconds before failing. |
| `.env` changes have no effect | Restart the backend. A real environment variable with the same name overrides `.env`. |
| Python version rejected | `uv python install 3.11` and rerun `uv sync --extra dev`. |
| `npm ci` or build fails after switching Node versions | Confirm Node 20+ and rerun `npm ci` in `frontend`. |

## 9. Security and operational limits

- EVAN is a single-user local tool. There is no login, session authorization, CSRF protection, TLS termination, or per-user data separation.
- The API accepts unauthenticated local requests. Anyone who can reach the port can import games and consume engine/LLM resources.
- No application-level API rate limit or cost cap exists. The queue, 600-ply import limit, fixed node budgets, LLM timeout, and provider-side limits are the active controls.
- API keys are server-side only. The settings model hides them from its representation, and error messages are intentionally credential-free.
- `.env`, SQLite files, WAL files, and `frontend/dist` are ignored by git. Do not add live credentials to `.env.example` or documentation.
- PGN comments are quarantined as untrusted data. URL import is restricted to Lichess and Chess.com with host/path validation, but imported game text and generated prose are still untrusted content.
- Full state lives in `evan.db`; protect it as potentially sensitive user data.
