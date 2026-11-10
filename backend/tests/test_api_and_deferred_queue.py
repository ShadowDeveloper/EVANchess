import io
from functools import partial

import chess
import chess.pgn
import pytest
from fastapi.testclient import TestClient

from evan.api.app import create_app
from evan.config import EvanSettings
from evan.pipeline.orchestrator import AnalysisOrchestrator
from evan.realizer.realizer import RealizedCommentary
from evan.storage.repository import EvanRepository


class ControlledOrchestrator(AnalysisOrchestrator):
    def start(self):
        pass


@pytest.fixture
def settings(tmp_path):
    return EvanSettings(sqlite_path=str(tmp_path / "api.db"), openrouter_api_key="test-not-a-real-key")


def test_api_import_validation_exports_and_priority(settings):
    app = create_app(settings, ControlledOrchestrator)
    with TestClient(app) as client:
        response = client.post("/api/games/import", json={"input": "1. e4 e5 2. Nf3 Nc6 *"})
        assert response.status_code == 201
        game = response.json()
        game_id = game["game_id"]
        assert len(game["plies"]) == 4
        assert client.post(f"/api/games/{game_id}/plies/2/prioritize").status_code == 200
        assert client.get(f"/api/games/{game_id}").json()["plies"][2]["priority_boost"] == 100
        assert client.post(f"/api/games/{game_id}/plies/77/prioritize").status_code == 404
        assert client.get("/api/games/missing").status_code == 404
        exported = client.get(f"/api/games/{game_id}/export/pgn")
        assert exported.status_code == 200
        assert chess.pgn.read_game(io.StringIO(exported.text)) is not None
        ledger = client.get(f"/api/games/{game_id}/export/ledger").json()
        assert len(ledger["plies"]) == 4
        assert "untrusted_comments" not in ledger["game"]
        assert client.post("/api/games/import", json={"input": "not chess"}).status_code == 422
        assert client.post("/api/games/import", json={"input": "1. e4", "target_rating": 900}).status_code == 422


def test_api_requires_live_key(tmp_path):
    settings = EvanSettings(sqlite_path=str(tmp_path / "empty.db"), openrouter_api_key=None)
    with TestClient(create_app(settings, ControlledOrchestrator)) as client:
        assert client.get("/api/health").json()["configured"] is False
        assert client.post("/api/games/import", json={"input": "1. e4 e5"}).status_code == 503
        assert client.get("/api/games").json() == []


def test_fen_has_position_ply_and_missing_history(settings):
    with TestClient(create_app(settings, ControlledOrchestrator)) as client:
        response = client.post("/api/games/import", json={"input": chess.STARTING_FEN})
        assert response.status_code == 201
        game = response.json()
        assert game["has_full_history"] is False
        assert game["plies"][0]["san_move"] == "Position"
        assert game["warnings"]


class FakeRealizer:
    async def realize(self, ledger, rating_band=1500):
        return RealizedCommentary(sentences=[], abstention_notice="Test abstention")


class FakeAuditor:
    async def verify_or_repair(self, commentary, ledger, rating_band=1500):
        return commentary


async def test_stage_order_and_user_priority_with_real_stockfish(settings):
    settings.coarse_nodes = 1000
    settings.deep_nodes_tier1 = 1000
    settings.deep_nodes_primary = 2000
    settings.challenge_nodes = 1000
    settings.critical_moments_count = 1
    app = create_app(settings, partial(ControlledOrchestrator, realizer=FakeRealizer(), auditor=FakeAuditor()))
    orchestrator = app.state.orchestrator
    repo = app.state.repository
    from evan.chess_core.parser import parse_game_input
    parsed = parse_game_input("1. e4 e5 2. Nf3 Nc6 3. Bb5 a6 *")
    game_id = repo.create_game(pgn_text=parsed.clean_pgn)
    for item in parsed.plies:
        repo.upsert_ply_skeleton(game_id, item.ply, item.move_number, item.turn, item.uci, item.san, item.state_before.fen, item.state_after.fen, item.state_before.state_hash, item.state_after.state_hash)
    seen = []
    original_deep = orchestrator._deep

    async def observe(*args, **kwargs):
        seen.append(args[1])
        if len(seen) == 1:
            boost = next(p for p in reversed(range(len(parsed.plies))) if p != args[1])
            orchestrator.prioritize(game_id, boost)
            seen.append(("boost", boost))
        await original_deep(*args, **kwargs)

    orchestrator._deep = observe
    await orchestrator.analyze_game(game_id)
    assert repo.get_game(game_id)["analysis_status"] == "full_complete"
    assert seen[0] == repo.get_game(game_id)["critical_plies"][0]
    assert seen[2] == seen[1][1]
    assert all(row["deep_status"] == "abstained" for row in repo.list_ply_analyses(game_id))


def test_terminal_sse_snapshot(settings):
    app = create_app(settings, ControlledOrchestrator)
    with TestClient(app) as client:
        game_id = app.state.repository.create_game("1. e4 e5 *")
        app.state.repository.update_game_status(game_id, "full_complete")
        response = client.get(f"/api/games/{game_id}/events")
        assert "event: snapshot" in response.text
        assert "event: complete" in response.text


def test_restart_marks_interrupted_games_failed(settings):
    repo = EvanRepository(settings.sqlite_path)
    repo.init_db()
    game_id = repo.create_game("1. e4 e5 *")
    with TestClient(create_app(settings, ControlledOrchestrator)) as client:
        assert client.get(f"/api/games/{game_id}").json()["analysis_status"] == "failed"
