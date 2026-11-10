from __future__ import annotations

import json
import re
from typing import Any
import httpx


class ImporterError(RuntimeError):
    """Raised when fetching a game from Lichess or Chess.com fails."""


_LICHESS_URL_RE = re.compile(
    r"(?:https?://)?(?:www\.)?lichess\.org/(?:game/export/|embed/)?([A-Za-z0-9]{8,12})(?:/(?:white|black))?",
    re.IGNORECASE,
)


def extract_lichess_game_id(url_or_id: str) -> str:
    cleaned = url_or_id.strip()
    match = _LICHESS_URL_RE.search(cleaned)
    if match:
        raw_id = match.group(1)
        return raw_id[:8]
    if re.fullmatch(r"[A-Za-z0-9]{8,12}", cleaned):
        return cleaned[:8]
    raise ImporterError(f"Could not extract a valid Lichess game ID from '{url_or_id}'.")


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
        resp = await client.get(export_url, headers=headers)
        if resp.status_code != 200:
            raise ImporterError(
                f"Lichess returned HTTP {resp.status_code} for game '{game_id}'."
            )
        return resp.text
    finally:
        if close_client:
            await client.aclose()


async def fetch_lichess_user_games(
    username: str,
    max_games: int = 10,
    client: httpx.AsyncClient | None = None,
) -> list[dict[str, Any]]:
    user_clean = username.strip()
    if not user_clean:
        raise ImporterError("Lichess username cannot be empty.")
    url = f"https://lichess.org/api/games/user/{user_clean}?max={max_games}&pgnInJson=true&clocks=false&evals=false"
    headers = {"Accept": "application/x-ndjson"}
    close_client = False
    if client is None:
        client = httpx.AsyncClient(timeout=15.0)
        close_client = True
    try:
        resp = await client.get(url, headers=headers)
        if resp.status_code != 200:
            raise ImporterError(
                f"Lichess returned HTTP {resp.status_code} for user '{user_clean}'."
            )
        games: list[dict[str, Any]] = []
        for line in resp.text.splitlines():
            line = line.strip()
            if not line:
                continue
            item = json.loads(line)
            players = item.get("players", {})
            white_user = players.get("white", {}).get("user", {}).get("name", "White")
            black_user = players.get("black", {}).get("user", {}).get("name", "Black")
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
        return games
    finally:
        if close_client:
            await client.aclose()
