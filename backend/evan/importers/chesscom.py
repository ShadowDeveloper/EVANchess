from __future__ import annotations

import re
from typing import Any
from urllib.parse import urlparse

import httpx

from evan.importers.lichess import ImporterError, _validate_max_games

_CHESSCOM_HOSTS = {"chess.com", "www.chess.com"}
_CHESSCOM_API_HOST = "api.chess.com"
_CHESSCOM_GAME_PATH_RE = re.compile(
    r"^/(?:game/)?(?:live|daily)/(\d{1,20})/?$",
    re.IGNORECASE,
)
_CHESSCOM_USERNAME_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{1,39}$")
_CHESSCOM_ARCHIVE_PATH_RE = re.compile(
    r"^/pub/player/([a-z0-9][a-z0-9_-]{1,39})/games/(\d{4})/(0[1-9]|1[0-2])/?$",
    re.IGNORECASE,
)
_MAX_ARCHIVE_MONTHS = 12
_DEFAULT_HEADERS = {
    "User-Agent": "EVANChessCoach/0.1 (https://github.com/ShadowDeveloper/EVANchess)"
}


def _validate_chesscom_username(
    username: str | None,
    *,
    for_direct_url: bool = False,
) -> str:
    if username is None or not isinstance(username, str) or not username.strip():
        if for_direct_url:
            raise ImporterError(
                "Chess.com username is required to fetch a game by direct URL."
            )
        raise ImporterError("Chess.com username cannot be empty.")
    user_clean = username.strip().lower()
    if not _CHESSCOM_USERNAME_RE.fullmatch(user_clean):
        raise ImporterError("Invalid Chess.com username format.")
    return user_clean


def _validate_chesscom_archive_url(archive_url: Any, expected_username: str) -> str:
    if not isinstance(archive_url, str) or not archive_url.strip():
        raise ImporterError("Invalid Chess.com archive URL.")
    parsed = urlparse(archive_url.strip())
    if parsed.scheme.lower() != "https":
        raise ImporterError("Chess.com archive URL must use HTTPS.")
    if parsed.username is not None or parsed.password is not None or parsed.port is not None:
        raise ImporterError("Chess.com archive URL must not contain credentials or a custom port.")
    host = (parsed.hostname or "").lower()
    if host != _CHESSCOM_API_HOST or parsed.netloc.lower() != _CHESSCOM_API_HOST:
        raise ImporterError("Chess.com archive URL must use host api.chess.com.")
    if parsed.params or parsed.query or parsed.fragment:
        raise ImporterError("Chess.com archive URL must not contain query or fragment parts.")
    match = _CHESSCOM_ARCHIVE_PATH_RE.fullmatch(parsed.path)
    if not match:
        raise ImporterError("Invalid Chess.com archive URL path.")
    archive_user = match.group(1).lower()
    if archive_user != expected_username.lower():
        raise ImporterError("Chess.com archive URL does not match requested username.")
    return f"https://api.chess.com/pub/player/{archive_user}/games/{match.group(2)}/{match.group(3)}"


def extract_chesscom_game_id(url: str) -> str:
    if not isinstance(url, str):
        raise ImporterError("Chess.com game URL must be a string.")
    cleaned = url.strip()
    if not cleaned:
        raise ImporterError("Could not extract Chess.com game ID from empty URL.")
    if "://" in cleaned:
        parsed = urlparse(cleaned)
    elif cleaned.lower().startswith(("chess.com/", "www.chess.com/")):
        parsed = urlparse(f"https://{cleaned}")
    else:
        raise ImporterError(f"Could not extract Chess.com game ID from '{url}'.")

    if parsed.scheme.lower() not in {"http", "https"}:
        raise ImporterError("Chess.com URL must use HTTP or HTTPS.")
    if parsed.username is not None or parsed.password is not None or parsed.port is not None:
        raise ImporterError("Chess.com URL must not contain credentials or a custom port.")
    host = (parsed.hostname or "").lower()
    if host not in _CHESSCOM_HOSTS or parsed.netloc.lower() not in _CHESSCOM_HOSTS:
        raise ImporterError("URL host must be chess.com or www.chess.com.")
    if parsed.params:
        raise ImporterError(f"Could not extract Chess.com game ID from '{url}'.")
    match = _CHESSCOM_GAME_PATH_RE.fullmatch(parsed.path)
    if not match:
        raise ImporterError(f"Could not extract Chess.com game ID from '{url}'.")
    return match.group(1)


async def _fetch_recent_archive_urls(
    client: httpx.AsyncClient,
    user_clean: str,
) -> list[str]:
    archives_endpoint = f"https://api.chess.com/pub/player/{user_clean}/games/archives"
    try:
        arch_resp = await client.get(archives_endpoint, headers=_DEFAULT_HEADERS)
    except httpx.HTTPError as exc:
        raise ImporterError(
            f"Network error while fetching Chess.com archives for user '{user_clean}'."
        ) from exc
    if arch_resp.status_code != 200:
        raise ImporterError(
            f"Chess.com returned HTTP {arch_resp.status_code} for user '{user_clean}'."
        )
    try:
        payload = arch_resp.json()
    except ValueError as exc:
        raise ImporterError("Invalid JSON response from Chess.com archives.") from exc
    if not isinstance(payload, dict):
        raise ImporterError("Invalid Chess.com archives payload.")
    archives = payload.get("archives", [])
    if not isinstance(archives, list):
        raise ImporterError("Invalid Chess.com archives list.")
    recent_raw = list(reversed(archives[-_MAX_ARCHIVE_MONTHS:]))
    return [_validate_chesscom_archive_url(u, user_clean) for u in recent_raw]


async def _fetch_archive_games(
    client: httpx.AsyncClient,
    archive_url: str,
    user_clean: str,
) -> list[dict[str, Any]]:
    safe_url = _validate_chesscom_archive_url(archive_url, user_clean)
    try:
        games_resp = await client.get(safe_url, headers=_DEFAULT_HEADERS)
    except httpx.HTTPError as exc:
        raise ImporterError("Network error while fetching Chess.com monthly archive.") from exc
    if games_resp.status_code != 200:
        raise ImporterError(f"Chess.com archive returned HTTP {games_resp.status_code}.")
    try:
        payload = games_resp.json()
    except ValueError as exc:
        raise ImporterError("Invalid JSON response from Chess.com monthly archive.") from exc
    if not isinstance(payload, dict):
        raise ImporterError("Invalid Chess.com monthly archive payload.")
    raw_games = payload.get("games", [])
    if not isinstance(raw_games, list):
        raise ImporterError("Invalid Chess.com monthly archive games list.")
    return [g for g in raw_games if isinstance(g, dict)]


async def fetch_chesscom_game_pgn(
    url: str,
    username: str | None = None,
    client: httpx.AsyncClient | None = None,
) -> str:
    game_id = extract_chesscom_game_id(url)
    user_clean = _validate_chesscom_username(username, for_direct_url=True)

    close_client = False
    if client is None:
        client = httpx.AsyncClient(timeout=15.0, headers=_DEFAULT_HEADERS)
        close_client = True

    try:
        archive_urls = await _fetch_recent_archive_urls(client, user_clean)
        for archive_url in archive_urls:
            raw_games = await _fetch_archive_games(client, archive_url, user_clean)
            for g in reversed(raw_games):
                raw_game_url = g.get("url", "")
                candidate_id = ""
                if isinstance(raw_game_url, str) and raw_game_url.strip():
                    try:
                        candidate_id = extract_chesscom_game_id(raw_game_url)
                    except ImporterError:
                        candidate_id = ""
                if candidate_id == game_id:
                    pgn = g.get("pgn")
                    if isinstance(pgn, str) and pgn.strip():
                        return pgn
                    raise ImporterError(f"Chess.com game '{game_id}' does not contain PGN data.")
        raise ImporterError(
            f"Chess.com game '{game_id}' was not found in the last {_MAX_ARCHIVE_MONTHS} monthly archives for user '{user_clean}'."
        )
    finally:
        if close_client:
            await client.aclose()


async def fetch_chesscom_user_games(
    username: str,
    max_games: int = 10,
    client: httpx.AsyncClient | None = None,
) -> list[dict[str, Any]]:
    user_clean = _validate_chesscom_username(username)
    _validate_max_games(max_games)

    close_client = False
    if client is None:
        client = httpx.AsyncClient(timeout=15.0, headers=_DEFAULT_HEADERS)
        close_client = True

    try:
        archive_urls = await _fetch_recent_archive_urls(client, user_clean)
        if not archive_urls:
            return []

        results: list[dict[str, Any]] = []
        for archive_url in archive_urls:
            raw_games = await _fetch_archive_games(client, archive_url, user_clean)
            for g in reversed(raw_games):
                pgn = g.get("pgn")
                if not isinstance(pgn, str) or not pgn.strip():
                    continue
                raw_url = g.get("url", "")
                game_id = ""
                if isinstance(raw_url, str) and raw_url.strip():
                    try:
                        game_id = extract_chesscom_game_id(raw_url)
                    except ImporterError:
                        game_id = raw_url.rstrip("/").split("/")[-1]
                white_obj = g.get("white")
                black_obj = g.get("black")
                white_name = (
                    white_obj.get("username", "White")
                    if isinstance(white_obj, dict)
                    else "White"
                )
                black_name = (
                    black_obj.get("username", "Black")
                    if isinstance(black_obj, dict)
                    else "Black"
                )
                time_class = g.get("time_class", "")
                results.append(
                    {
                        "id": game_id,
                        "url": raw_url if isinstance(raw_url, str) else "",
                        "white": white_name,
                        "black": black_name,
                        "time_class": time_class if isinstance(time_class, str) else "",
                        "pgn": pgn,
                        "platform": "chesscom",
                    }
                )
                if len(results) >= max_games:
                    break
            if len(results) >= max_games:
                break
        return results
    finally:
        if close_client:
            await client.aclose()
