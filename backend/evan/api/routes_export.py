from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse, Response

from evan.export.pgn_exporter import export_annotated_pgn, export_ledger

router = APIRouter(prefix="/api/games")


def _records(request: Request, game_id: str):
    repo = request.app.state.repository
    game = repo.get_game(game_id)
    if game is None:
        raise HTTPException(404, "Game not found.")
    return game, repo.list_ply_analyses(game_id)


@router.get("/{game_id}/export/pgn")
def pgn(game_id: str, request: Request):
    game, plies = _records(request, game_id)
    return Response(export_annotated_pgn(game, plies), media_type="application/x-chess-pgn", headers={"Content-Disposition": f'attachment; filename="{game_id}.pgn"'})


@router.get("/{game_id}/export/ledger")
def ledger(game_id: str, request: Request):
    game, plies = _records(request, game_id)
    return JSONResponse(export_ledger(game, plies), headers={"Content-Disposition": f'attachment; filename="{game_id}-ledger.json"'})
