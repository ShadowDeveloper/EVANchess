from __future__ import annotations

import re
from typing import Any
import httpx
from evan.importers.lichess import ImporterError


_CHESSCOM_GAME_URL_RE = re.compile(
    r"(?:https?://)?(?:www\.)?chess\.com/(?:game/)?(?:live|daily)/(\d+)",
    re.IGNORECASE,
)


def extract_chesscom_game_id(url: str) -> str:
    match = _CHESSCOM_GAME_URL_RE.search(url.strip())
    if not match:
        raise ImporterError(f"Could not extract Chess.com game ID from '{url}'.")
    return match.group(1)


async def fetch_chesscom_user_games(
    username: str,
    max_games: int = 10,
    client: httpx.AsyncClient | None = None,
) -> list[dict[str, Any]]:
    user_clean = username.strip().lower()
    if not user_clean:
        raise ImporterError("Chess.com username cannot be empty.")

    headers = {"User-Agent": "EVANChessCoach/0.1 (https://github.com/ShadowDeveloper/EVANchess)"}
    close_client = False
    if client is None:
        client = httpx.AsyncClient(timeout=15.0, headers=headers)
        close_client = True

    try:
        arch_resp = await client.get(
            f"https://api.chess.com/pub/player/{user_clean}/games/archives",
            headers=headers,
        )
        if arch_resp.status_code != 200:
            raise ImporterError(
                f"Chess.com returned HTTP {arch_resp.status_code} for user '{username}'."
            )
        archives = arch_resp.json().get("archives", [])
        if not archives:
            return []

        latest_archive_url = archives[-1]
        games_resp = await client.get(latest_archive_url, headers=headers)
        if games_resp.status_code != 200:
            raise ImporterError(
                f"Chess.com archive returned HTTP {games_resp.status_code}."
            )
        raw_games = games_resp.json().get("games", [])
        results: list[dict[str, Any]] = []
        for g in reversed(raw_games):
            pgn = g.get("pgn")
            if not pgn:
                continue
            url = g.get("url", "")
            game_id = url.rstrip("/").split("/")[-1] if url else ""
            results.append(
                {
                    "id": game_id,
                    "url": url,
                    "white": g.get("white", {}).get("username", "White"),
                    "black": g.get("black", {}).get("username", "Black"),
                    "time_class": g.get("time_class", ""),
                    "pgn": pgn,
                    "platform": "chesscom",
                }
            )
            if len(results) >= max_games:
                break
        return results
    finally:
        if close_client:
            await client.aclose()
