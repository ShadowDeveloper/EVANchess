from __future__ import annotations

import json
import re
from typing import Any
from urllib.parse import urlparse

import httpx


class ImporterError(RuntimeError):
    pass


_LICHESS_HOSTS = {"lichess.org", "www.lichess.org"}
_LICHESS_ID_RE = re.compile(r"^[A-Za-z0-9]{8}(?:[A-Za-z0-9]{4})?$")
_LICHESS_PATH_RE = re.compile(
    r"^/(?:game/export/|embed/)?([A-Za-z0-9]{8}(?:[A-Za-z0-9]{4})?)(?:/(?:white|black))?/?$",
    re.IGNORECASE,
)
_LICHESS_USERNAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{1,29}$")
_MIN_MAX_GAMES = 1
_MAX_MAX_GAMES = 25


def _validate_lichess_username(username: str) -> str:
    if not isinstance(username, str):
        raise ImporterError("Lichess username must be a string.")
    user_clean = username.strip()
    if not user_clean:
        raise ImporterError("Lichess username cannot be empty.")
    if not _LICHESS_USERNAME_RE.fullmatch(user_clean):
        raise ImporterError("Invalid Lichess username format.")
    return user_clean


def _validate_max_games(max_games: int) -> int:
    if (
        isinstance(max_games, bool)
        or not isinstance(max_games, int)
        or not (_MIN_MAX_GAMES <= max_games <= _MAX_MAX_GAMES)
    ):
        raise ImporterError(
            f"max_games must be an integer between {_MIN_MAX_GAMES} and {_MAX_MAX_GAMES}."
        )
    return max_games


def extract_lichess_game_id(url_or_id: str) -> str:
    if not isinstance(url_or_id, str):
        raise ImporterError("Lichess game URL or ID must be a string.")
    cleaned = url_or_id.strip()
    if not cleaned:
        raise ImporterError("Could not extract a valid Lichess game ID from empty input.")
    if _LICHESS_ID_RE.fullmatch(cleaned):
        return cleaned[:8]
    if "://" in cleaned:
        parsed = urlparse(cleaned)
    elif cleaned.lower().startswith(("lichess.org/", "www.lichess.org/")):
        parsed = urlparse(f"https://{cleaned}")
    else:
        raise ImporterError(f"Could not extract a valid Lichess game ID from '{url_or_id}'.")

    if parsed.scheme.lower() not in {"http", "https"}:
        raise ImporterError("Lichess URL must use HTTP or HTTPS.")
    if parsed.username is not None or parsed.password is not None or parsed.port is not None:
        raise ImporterError("Lichess URL must not contain credentials or a custom port.")
    host = (parsed.hostname or "").lower()
    if host not in _LICHESS_HOSTS or parsed.netloc.lower() not in _LICHESS_HOSTS:
        raise ImporterError("URL host must be lichess.org or www.lichess.org.")
    if parsed.params:
        raise ImporterError("Invalid Lichess game URL.")
    match = _LICHESS_PATH_RE.fullmatch(parsed.path)
    if not match:
        raise ImporterError(f"Could not extract a valid Lichess game ID from '{url_or_id}'.")
    return match.group(1)[:8]


async def fetch_lichess_game_pgn(
    url_or_id: str,
    client: httpx.AsyncClient | None = None,
) -> str:
    game_id = extract_lichess_game_id(url_or_id)
    export_url = f"https://lichess.org/game/export/{game_id}?clocks=false&evals=false"
    headers = {"Accept": "application/x-chess-pgn"}
    close_client = False
    if client is None:
        client = httpx.AsyncClient(timeout=15.0)
        close_client = True
    try:
        try:
            resp = await client.get(export_url, headers=headers)
        except httpx.HTTPError as exc:
            raise ImporterError(f"Network error while fetching Lichess game '{game_id}'.") from exc
        if resp.status_code != 200:
            raise ImporterError(
                f"Lichess returned HTTP {resp.status_code} for game '{game_id}'."
            )
        if not resp.text or not resp.text.strip():
            raise ImporterError(f"Lichess returned an empty PGN for game '{game_id}'.")
        return resp.text
    finally:
        if close_client:
            await client.aclose()


async def fetch_lichess_user_games(
    username: str,
    max_games: int = 10,
    client: httpx.AsyncClient | None = None,
) -> list[dict[str, Any]]:
    user_clean = _validate_lichess_username(username)
    _validate_max_games(max_games)
    url = f"https://lichess.org/api/games/user/{user_clean}?max={max_games}&pgnInJson=true&clocks=false&evals=false"
    headers = {"Accept": "application/x-ndjson"}
    close_client = False
    if client is None:
        client = httpx.AsyncClient(timeout=15.0)
        close_client = True
    try:
        try:
            resp = await client.get(url, headers=headers)
        except httpx.HTTPError as exc:
            raise ImporterError(
                f"Network error while fetching Lichess games for user '{user_clean}'."
            ) from exc
        if resp.status_code != 200:
            raise ImporterError(
                f"Lichess returned HTTP {resp.status_code} for user '{user_clean}'."
            )
        games: list[dict[str, Any]] = []
        for raw_line in resp.text.splitlines():
            line = raw_line.strip()
            if not line:
                continue
            try:
                item = json.loads(line)
            except ValueError as exc:
                raise ImporterError("Invalid JSON response from Lichess.") from exc
            if not isinstance(item, dict):
                raise ImporterError("Invalid game payload from Lichess.")
            players = item.get("players")
            if not isinstance(players, dict):
                players = {}
            white_info = players.get("white")
            black_info = players.get("black")
            white_user_obj = white_info.get("user") if isinstance(white_info, dict) else None
            black_user_obj = black_info.get("user") if isinstance(black_info, dict) else None
            white_user = (
                white_user_obj.get("name", "White")
                if isinstance(white_user_obj, dict)
                else "White"
            )
            black_user = (
                black_user_obj.get("name", "Black")
                if isinstance(black_user_obj, dict)
                else "Black"
            )
            games.append(
                {
                    "id": item.get("id", ""),
                    "white": white_user,
                    "black": black_user,
                    "speed": item.get("speed", ""),
                    "winner": item.get("winner"),
                    "pgn": item.get("pgn", ""),
                    "platform": "lichess",
                }
            )
            if len(games) >= max_games:
                break
        return games
    finally:
        if close_client:
            await client.aclose()
