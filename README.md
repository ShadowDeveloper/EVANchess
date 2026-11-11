# EVAN Chess

**EVAN** (Evidence-Verified Analysis & Narration) is a local chess review application. It analyzes standard-chess PGN games or FEN positions with Stockfish and presents commentary linked to engine searches, replayed lines, and an inspectable claim ledger.

## Quick start

Requirements: Python 3.11+, [uv](https://docs.astral.sh/uv/), Node.js and npm, a UCI-compatible Stockfish executable, and credentials for the configured LLM provider. Analysis requires a provider key; the application can start without one to report configuration errors.

From the repository root in PowerShell:

```powershell
uv sync --extra dev
npm --prefix frontend ci
npm --prefix frontend run build
Copy-Item .env.example .env
```

Edit `.env`: set `STOCKFISH_PATH` to your Stockfish executable and set `OPENROUTER_API_KEY` for the default OpenRouter provider. Do not commit credentials. The example's engine path is specific to its original Windows machine; adjust it or clear it to use `stockfish` from `PATH`. Other providers require matching provider, model, and credentials; see [setup and configuration](docs/SETUP.md).

Start the backend from the repository root:

```powershell
uv run uvicorn evan.api.app:create_app --factory --app-dir backend --host 127.0.0.1 --port 8000
```

Open [http://127.0.0.1:8000](http://127.0.0.1:8000). The backend serves the production frontend built above. Import a PGN, FEN, Lichess game, or Chess.com game and select moves to inspect commentary and evidence. Chess.com game URLs require the player's username to search its public archives.

## What to expect

- A coarse engine pass selects critical moments for deeper analysis; remaining moves are queued and can be prioritized from the interface.
- Commentary is restricted to supported claim records. The ledger exposes engine metadata, conditional variations, audit results, and explicit abstentions; PGN and JSON exports are available.
- Standalone FENs and games starting from a custom position lack earlier repetition history. Engine evaluations are budget-dependent, not mathematical proofs; the prose audit is not a guarantee that every chess implication is correct.
- Maia, secondary-engine, and tablebase integrations mentioned in the historical plan are not active production integrations. Cloud requests may incur provider charges.
- EVAN has no built-in authentication. Keep the service bound to localhost; do not expose it to an untrusted network.

## Documentation

Start at [docs/README.md](docs/README.md) for installation, development, architecture, API, and the archived original materials. The original idea, proposal, and plan are historical context, not a description of the current implementation.
