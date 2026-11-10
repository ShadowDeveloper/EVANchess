import json
import httpx
import pytest
from evan.importers import ImporterError
from evan.importers.lichess import (
    extract_lichess_game_id,
    fetch_lichess_game_pgn,
    fetch_lichess_user_games,
)
from evan.importers.chesscom import (
    extract_chesscom_game_id,
    fetch_chesscom_game_pgn,
    fetch_chesscom_user_games,
)


def test_extract_lichess_game_id():
    assert extract_lichess_game_id("https://lichess.org/abcdefgh/black") == "abcdefgh"
    assert extract_lichess_game_id("https://lichess.org/abcdefgh1234") == "abcdefgh"
    assert extract_lichess_game_id("https://www.lichess.org/game/export/abcdefgh") == "abcdefgh"
    assert extract_lichess_game_id("https://lichess.org/embed/abcdefgh1234/white") == "abcdefgh"
    assert extract_lichess_game_id("abcdefgh") == "abcdefgh"
    assert extract_lichess_game_id("abcdefgh1234") == "abcdefgh"


@pytest.mark.parametrize(
    "bad_input",
    [
        "",
        "   ",
        "abcdefg",
        "abcdefghi",
        "abcdefgh12",
        "abcdefgh123",
        "abcdefgh12345",
        "https://lichess.org/abcdefgh12",
        "https://evil.com/lichess.org/abcdefgh",
        "https://lichess.org.evil.com/abcdefgh",
        "https://notlichess.org/abcdefgh",
        "ftp://lichess.org/abcdefgh",
        "https://user:pass@lichess.org/abcdefgh",
        "https://lichess.org:8080/abcdefgh",
        "https://lichess.org/abcdefgh/extra",
        "https://lichess.org/training/abcdefgh",
    ],
)
def test_extract_lichess_game_id_rejects_invalid_urls_and_ids(bad_input: str):
    with pytest.raises(ImporterError):
        extract_lichess_game_id(bad_input)


def test_extract_chesscom_game_id():
    assert (
        extract_chesscom_game_id("https://www.chess.com/game/live/123456789")
        == "123456789"
    )
    assert (
        extract_chesscom_game_id("https://chess.com/daily/987654")
        == "987654"
    )


@pytest.mark.parametrize(
    "bad_url",
    [
        "",
        "123456789",
        "https://evil.com/chess.com/game/live/123456789",
        "https://chess.com.evil.com/game/live/123456789",
        "https://api.chess.com/game/live/123456789",
        "ftp://www.chess.com/game/live/123456789",
        "https://user@www.chess.com/game/live/123456789",
        "https://www.chess.com:8443/game/live/123456789",
        "https://www.chess.com/game/live/123456789/extra",
        "https://www.chess.com/game/computer/123456789",
        "https://www.chess.com/game/live/notdigits",
    ],
)
def test_extract_chesscom_game_id_rejects_invalid_urls_and_hosts(bad_url: str):
    with pytest.raises(ImporterError):
        extract_chesscom_game_id(bad_url)


@pytest.mark.parametrize(
    "bad_username",
    [
        "",
        "   ",
        "a",
        "-alice",
        "_alice",
        "alice/../bob",
        "alice?max=100",
        "alice bob",
        "a" * 45,
    ],
)
async def test_username_validation_rejects_invalid_usernames(bad_username: str):
    with pytest.raises(ImporterError):
        await fetch_lichess_user_games(bad_username)
    with pytest.raises(ImporterError):
        await fetch_chesscom_user_games(bad_username)


@pytest.mark.parametrize("bad_max", [0, -5, 26, 100, True])
async def test_max_games_bounds_validation(bad_max):
    with pytest.raises(ImporterError):
        await fetch_lichess_user_games("Alice", max_games=bad_max)
    with pytest.raises(ImporterError):
        await fetch_chesscom_user_games("Alice", max_games=bad_max)


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


async def test_fetch_chesscom_user_games_multi_month_traversal_and_direct_url():
    def handler(request: httpx.Request) -> httpx.Response:
        url_str = str(request.url)
        if url_str == "https://api.chess.com/pub/player/alice/games/archives":
            return httpx.Response(
                200,
                json={
                    "archives": [
                        "https://api.chess.com/pub/player/alice/games/2025/09",
                        "https://api.chess.com/pub/player/alice/games/2025/10",
                        "https://api.chess.com/pub/player/alice/games/2025/11",
                        "https://api.chess.com/pub/player/alice/games/2025/12",
                        "https://api.chess.com/pub/player/alice/games/2026/01",
                        "https://api.chess.com/pub/player/alice/games/2026/02",
                        "https://api.chess.com/pub/player/alice/games/2026/03",
                        "https://api.chess.com/pub/player/alice/games/2026/04",
                        "https://api.chess.com/pub/player/alice/games/2026/05",
                        "https://api.chess.com/pub/player/alice/games/2026/06",
                        "https://api.chess.com/pub/player/alice/games/2026/07",
                        "https://api.chess.com/pub/player/alice/games/2026/08",
                        "https://api.chess.com/pub/player/alice/games/2026/09",
                        "https://api.chess.com/pub/player/alice/games/2026/10",
                        "https://api.chess.com/pub/player/alice/games/2026/11",
                    ]
                },
            )
        if url_str.endswith("/2026/11"):
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
        if url_str.endswith("/2026/10"):
            return httpx.Response(
                200,
                json={
                    "games": [
                        {
                            "url": "https://www.chess.com/game/live/888",
                            "pgn": "1. e4 c5 *",
                            "time_class": "blitz",
                            "white": {"username": "Carol"},
                            "black": {"username": "Alice"},
                        }
                    ]
                },
            )
        if url_str.endswith("/2025/09"):
            return httpx.Response(
                200,
                json={
                    "games": [
                        {
                            "url": "https://www.chess.com/game/live/111",
                            "pgn": "1. c4 e5 *",
                            "time_class": "bullet",
                            "white": {"username": "Alice"},
                            "black": {"username": "Dave"},
                        }
                    ]
                },
            )
        return httpx.Response(200, json={"games": []})

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        games = await fetch_chesscom_user_games("Alice", max_games=2, client=client)
        assert len(games) == 2
        assert [g["id"] for g in games] == ["999", "888"]
        assert games[0]["pgn"] == "1. d4 d5 *"
        assert games[1]["pgn"] == "1. e4 c5 *"

        pgn_older_month = await fetch_chesscom_game_pgn(
            "https://www.chess.com/game/live/888",
            "Alice",
            client=client,
        )
        assert pgn_older_month == "1. e4 c5 *"

        with pytest.raises(ImporterError, match="12 monthly archives"):
            await fetch_chesscom_game_pgn(
                "https://www.chess.com/game/live/111",
                "Alice",
                client=client,
            )


async def test_fetch_chesscom_game_pgn_requires_username():
    with pytest.raises(ImporterError, match="username is required"):
        await fetch_chesscom_game_pgn("https://www.chess.com/game/live/999")
    with pytest.raises(ImporterError, match="username is required"):
        await fetch_chesscom_game_pgn("https://www.chess.com/game/live/999", "")
    with pytest.raises(ImporterError, match="username is required"):
        await fetch_chesscom_game_pgn("https://www.chess.com/game/live/999", "   ")


@pytest.mark.parametrize(
    "hostile_archive_url",
    [
        "http://169.254.169.254/latest/meta-data/",
        "https://evil.com/pub/player/alice/games/2026/11",
        "http://api.chess.com/pub/player/alice/games/2026/11",
        "https://api.chess.com:8443/pub/player/alice/games/2026/11",
        "https://api.chess.com/pub/player/bob/games/2026/11",
        "https://api.chess.com/pub/player/alice/games/2026/13",
        "https://api.chess.com/pub/player/alice/games/2026/11?redirect=http://evil.com",
        "https://api.chess.com/pub/player/alice/games/2026/11/../../secret",
    ],
)
async def test_chesscom_rejects_ssrf_hostile_archive_urls(hostile_archive_url: str):
    called_urls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        called_urls.append(str(request.url))
        if str(request.url).endswith("/games/archives"):
            return httpx.Response(200, json={"archives": [hostile_archive_url]})
        return httpx.Response(200, json={"games": []})

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        with pytest.raises(ImporterError):
            await fetch_chesscom_user_games("Alice", max_games=5, client=client)
        assert called_urls == ["https://api.chess.com/pub/player/alice/games/archives"]


async def test_network_and_json_errors_normalized_to_importer_error():
    def failing_network_handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("Connection refused (secret-token-xyz)")

    net_transport = httpx.MockTransport(failing_network_handler)
    async with httpx.AsyncClient(transport=net_transport) as client:
        with pytest.raises(ImporterError) as exc_info:
            await fetch_lichess_game_pgn("https://lichess.org/abcdefgh", client=client)
        assert "secret-token-xyz" not in str(exc_info.value)

        with pytest.raises(ImporterError):
            await fetch_lichess_user_games("Alice", client=client)

        with pytest.raises(ImporterError):
            await fetch_chesscom_user_games("Alice", client=client)

        with pytest.raises(ImporterError):
            await fetch_chesscom_game_pgn(
                "https://www.chess.com/game/live/999",
                "Alice",
                client=client,
            )

    def bad_json_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="not-valid-json{{{")

    json_transport = httpx.MockTransport(bad_json_handler)
    async with httpx.AsyncClient(transport=json_transport) as client:
        with pytest.raises(ImporterError):
            await fetch_lichess_user_games("Alice", client=client)
        with pytest.raises(ImporterError):
            await fetch_chesscom_user_games("Alice", client=client)
