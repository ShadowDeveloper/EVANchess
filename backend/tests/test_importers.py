import json
import httpx
import pytest
from evan.importers.lichess import (
    extract_lichess_game_id,
    fetch_lichess_game_pgn,
    fetch_lichess_user_games,
)
from evan.importers.chesscom import (
    extract_chesscom_game_id,
    fetch_chesscom_user_games,
)


def test_extract_lichess_game_id():
    assert extract_lichess_game_id("https://lichess.org/abcdefgh/black") == "abcdefgh"
    assert extract_lichess_game_id("https://lichess.org/abcdefgh1234") == "abcdefgh"
    assert extract_lichess_game_id("abcdefgh") == "abcdefgh"


def test_extract_chesscom_game_id():
    assert (
        extract_chesscom_game_id("https://www.chess.com/game/live/123456789")
        == "123456789"
    )


async def test_fetch_lichess_game_pgn_and_user_games():
    sample_pgn = '[White "Alice"]\n[Black "Bob"]\n\n1. e4 e5 *'
    ndjson_line = json.dumps(
        {
            "id": "abcdefgh",
            "speed": "rapid",
            "players": {
                "white": {"user": {"name": "Alice"}},
                "black": {"user": {"name": "Bob"}},
            },
            "pgn": sample_pgn,
        }
    )

    def handler(request: httpx.Request) -> httpx.Response:
        if "/game/export/abcdefgh" in str(request.url):
            return httpx.Response(200, text=sample_pgn)
        if "/api/games/user/Alice" in str(request.url):
            return httpx.Response(200, text=ndjson_line + "\n")
        return httpx.Response(404)

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        pgn = await fetch_lichess_game_pgn("https://lichess.org/abcdefgh", client=client)
        assert "1. e4 e5" in pgn

        games = await fetch_lichess_user_games("Alice", max_games=5, client=client)
        assert len(games) == 1
        assert games[0]["white"] == "Alice"
        assert games[0]["id"] == "abcdefgh"


async def test_fetch_chesscom_user_games():
    def handler(request: httpx.Request) -> httpx.Response:
        if str(request.url).endswith("/games/archives"):
            return httpx.Response(
                200,
                json={"archives": ["https://api.chess.com/pub/player/alice/games/2026/11"]},
            )
        if str(request.url).endswith("/2026/11"):
            return httpx.Response(
                200,
                json={
                    "games": [
                        {
                            "url": "https://www.chess.com/game/live/999",
                            "pgn": "1. d4 d5 *",
                            "time_class": "rapid",
                            "white": {"username": "Alice"},
                            "black": {"username": "Bob"},
                        }
                    ]
                },
            )
        return httpx.Response(404)

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        games = await fetch_chesscom_user_games("Alice", max_games=5, client=client)
        assert len(games) == 1
        assert games[0]["id"] == "999"
        assert games[0]["pgn"] == "1. d4 d5 *"
