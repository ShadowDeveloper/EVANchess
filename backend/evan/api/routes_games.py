from __future__ import annotations

import asyncio
import json
from typing import Literal
from urllib.parse import urlparse

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from evan.chess_core.parser import GameParseError, parse_game_input
from evan.config import ConfigurationError, resolve_stockfish_path
from evan.importers.chesscom import fetch_chesscom_game_pgn, fetch_chesscom_user_games
from evan.importers.lichess import ImporterError, fetch_lichess_game_pgn, fetch_lichess_user_games

router = APIRouter(prefix="/api")


class ImportRequest(BaseModel):
    input: str = Field(min_length=1, max_length=200000)
    player_color: Literal["white", "black"] = "white"
    target_rating: int = Field(default=1500, ge=1200, le=2000)
    platform: Literal["lichess", "chesscom", "pgn", "fen", "other"] = "pgn"
    budget_profile: Literal["quick", "standard", "deep"] = "standard"
    username: str | None = Field(default=None, max_length=64)


@router.get("/games")
def list_games(request: Request):
    games = request.app.state.repository.list_games()
    for game in games:
        game.pop("untrusted_comments", None)
    return games


@router.post("/games/import", status_code=201)
async def import_game(body: ImportRequest, request: Request):
    settings = request.app.state.settings
    try:
        settings.require_llm_api_key()
        resolve_stockfish_path(settings.stockfish_path)
    except ConfigurationError as exc:
        raise HTTPException(503, str(exc)) from exc
    orchestrator = request.app.state.orchestrator
    if orchestrator.queue.full():
        raise HTTPException(429, "Analysis queue is full. Wait for existing games to finish.")
    text = body.input.strip()
    if text.lower().startswith(("http://", "https://")):
        host = (urlparse(text).hostname or "").lower()
        try:
            if host in {"lichess.org", "www.lichess.org"}:
                text = await fetch_lichess_game_pgn(text)
            elif host in {"chess.com", "www.chess.com"}:
                text = await fetch_chesscom_game_pgn(text, body.username or "")
            else:
                raise ImporterError("Only Lichess and Chess.com game URLs are supported.")
        except ImporterError as exc:
            raise HTTPException(422, str(exc)) from exc
    try:
        parsed = parse_game_input(text)
    except (GameParseError, ValueError) as exc:
        raise HTTPException(422, str(exc)) from exc
    if len(parsed.plies) > 600:
        raise HTTPException(422, "Games are limited to 600 half-moves per import.")
    if orchestrator.queue.full() or not orchestrator.accepting:
        raise HTTPException(429, "Analysis queue is full or shutting down.")
    repo = request.app.state.repository
    game_id = repo.create_game(
        pgn_text=parsed.clean_pgn, white=parsed.white, black=parsed.black,
        result=parsed.result, event=parsed.event, fen_root=parsed.fen_root,
        has_full_history=parsed.has_full_history, player_color=body.player_color,
        target_rating=body.target_rating, platform=body.platform,
        warnings=parsed.warnings, untrusted_comments=parsed.untrusted_comments,
    )
    repo.set_game_options(game_id, body.budget_profile)
    for item in parsed.plies:
        repo.upsert_ply_skeleton(game_id, item.ply, item.move_number, item.turn, item.uci, item.san,
                                item.state_before.fen, item.state_after.fen,
                                item.state_before.state_hash, item.state_after.state_hash)
    if not parsed.plies:
        from evan.chess_core.state import GameStateIdentity
        import chess
        board = chess.Board(parsed.fen_root)
        state = GameStateIdentity.from_board(board)
        repo.upsert_ply_skeleton(game_id, 0, board.fullmove_number, "white" if board.turn else "black", "", "Position", board.fen(), board.fen(), state.state_hash, state.state_hash)
    orchestrator.submit(game_id)
    return repo.get_game_detail(game_id)


@router.get("/importers/{platform}/{username}")
async def recent_games(platform: Literal["lichess", "chesscom"], username: str, max_games: int = Query(10, ge=1, le=25)):
    try:
        fetcher = fetch_lichess_user_games if platform == "lichess" else fetch_chesscom_user_games
        return await fetcher(username, max_games=max_games)
    except ImporterError as exc:
        raise HTTPException(422, str(exc)) from exc


@router.get("/games/{game_id}")
def get_game(game_id: str, request: Request):
    game = request.app.state.repository.get_game_detail(game_id)
    if game is None:
        raise HTTPException(404, "Game not found.")
    return game


@router.post("/games/{game_id}/plies/{ply}/prioritize")
def prioritize(game_id: str, ply: int, request: Request):
    game = get_game(game_id, request)
    if game["analysis_status"] in {"failed", "full_complete"}:
        if request.app.state.repository.get_ply_analysis(game_id, ply) is None:
            raise HTTPException(404, "Ply not found.")
        return {"prioritized": False}
    if not request.app.state.orchestrator.prioritize(game_id, ply):
        raise HTTPException(404, "Ply not found.")
    return {"prioritized": True}


@router.get("/games/{game_id}/events")
async def game_events(game_id: str, request: Request):
    get_game(game_id, request)
    orchestrator = request.app.state.orchestrator

    async def events():
        last_revision = -1
        ready_plies: set[int] = set()
        while not await request.is_disconnected():
            changed = orchestrator.changed.setdefault(game_id, asyncio.Event())
            changed.clear()
            game = request.app.state.repository.get_game_detail(game_id)
            if game is None:
                return
            revision = game.get("revision", 0)
            if revision != last_revision:
                yield f"id: {revision}\nevent: snapshot\ndata: {json.dumps(game)}\n\n"
                last_revision = revision
                for row in game["plies"]:
                    if row["deep_status"] in {"completed", "abstained"} and row["ply"] not in ready_plies:
                        yield f"event: moment_ready\ndata: {json.dumps(row)}\n\n"
                        ready_plies.add(row["ply"])
            if game["analysis_status"] in {"full_complete", "failed"}:
                event = "complete" if game["analysis_status"] == "full_complete" else "error"
                yield f"event: {event}\ndata: {json.dumps(game)}\n\n"
                return
            try:
                await asyncio.wait_for(changed.wait(), timeout=15)
            except TimeoutError:
                yield ": keepalive\n\n"

    return StreamingResponse(events(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})
