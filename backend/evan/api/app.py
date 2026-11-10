from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from evan.api.routes_export import router as export_router
from evan.api.routes_games import router as games_router
from evan.config import ConfigurationError, EvanSettings, resolve_stockfish_path
from evan.pipeline.orchestrator import AnalysisOrchestrator
from evan.storage.repository import EvanRepository


def configuration_errors(settings: EvanSettings) -> list[str]:
    errors = []
    try:
        settings.require_llm_api_key()
    except ConfigurationError as exc:
        errors.append(str(exc))
    try:
        resolve_stockfish_path(settings.stockfish_path)
    except ConfigurationError as exc:
        errors.append(str(exc))
    return errors


def create_app(settings: EvanSettings | None = None, orchestrator_factory: Any = AnalysisOrchestrator) -> FastAPI:
    config = settings or EvanSettings()
    repository = EvanRepository(config.sqlite_path)
    repository.init_db()
    orchestrator = orchestrator_factory(config, repository)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        repository.fail_interrupted()
        orchestrator.start()
        yield
        await orchestrator.close()

    app = FastAPI(title="EVAN · Evidence-Verified Chess Analysis", lifespan=lifespan)
    app.state.settings = config
    app.state.repository = repository
    app.state.orchestrator = orchestrator
    app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"], allow_methods=["GET", "POST"], allow_headers=["Content-Type", "Last-Event-ID"])

    @app.get("/api/health")
    def health():
        errors = configuration_errors(config)
        return {"configured": not errors, "configuration_errors": errors, "version": "0.1.0"}

    app.include_router(games_router)
    app.include_router(export_router)
    static_path = Path(__file__).resolve().parents[3] / "frontend" / "dist"
    if static_path.is_dir():
        app.mount("/", StaticFiles(directory=static_path, html=True), name="frontend")
    return app
