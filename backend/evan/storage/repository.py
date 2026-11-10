from __future__ import annotations

import json
import sqlite3
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SCHEMA_PATH = Path(__file__).parent / "schema.sql"


class EvanRepository:
    def __init__(self, db_path: str = "evan.db") -> None:
        self.db_path = db_path

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.db_path, timeout=30.0)
        conn.row_factory = sqlite3.Row
        try:
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.execute("PRAGMA foreign_keys=ON;")
            with conn:
                yield conn
        finally:
            conn.close()

    def init_db(self) -> None:
        schema_sql = SCHEMA_PATH.read_text(encoding="utf-8")
        with self._connect() as conn:
            conn.executescript(schema_sql)
            columns = {row[1] for row in conn.execute("PRAGMA table_info(games)")}
            for name, definition in {
                "error": "TEXT",
                "budget_profile": "TEXT NOT NULL DEFAULT 'standard'",
                "revision": "INTEGER NOT NULL DEFAULT 0",
            }.items():
                if name not in columns:
                    conn.execute(f"ALTER TABLE games ADD COLUMN {name} {definition}")

    def set_game_options(self, game_id: str, budget_profile: str) -> None:
        with self._connect() as conn:
            conn.execute("UPDATE games SET budget_profile = ? WHERE game_id = ?", (budget_profile, game_id))

    def record_error(self, game_id: str, error: str) -> None:
        with self._connect() as conn:
            conn.execute("UPDATE games SET analysis_status = 'failed', error = ? WHERE game_id = ?", (error, game_id))
            conn.execute("UPDATE ply_analyses SET deep_status = 'failed' WHERE game_id = ? AND deep_status = 'running'", (game_id,))

    def bump_revision(self, game_id: str) -> int:
        with self._connect() as conn:
            conn.execute("UPDATE games SET revision = revision + 1 WHERE game_id = ?", (game_id,))
            return int(conn.execute("SELECT revision FROM games WHERE game_id = ?", (game_id,)).fetchone()[0])

    def fail_interrupted(self) -> None:
        with self._connect() as conn:
            conn.execute("UPDATE games SET analysis_status = 'failed', error = 'Analysis interrupted by server shutdown. Import again to retry.', revision = revision + 1 WHERE analysis_status NOT IN ('full_complete', 'failed')")
            conn.execute("UPDATE ply_analyses SET deep_status = 'failed' WHERE deep_status = 'running'")

    def get_game_detail(self, game_id: str) -> dict[str, Any] | None:
        game = self.get_game(game_id)
        if game is None:
            return None
        game.pop("untrusted_comments", None)
        game["plies"] = self.list_ply_analyses(game_id)
        return game

    def create_game(
        self,
        pgn_text: str,
        white: str = "White",
        black: str = "Black",
        result: str = "*",
        event: str = "",
        fen_root: str = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
        has_full_history: bool = True,
        player_color: str = "white",
        target_rating: int = 1500,
        platform: str = "lichess",
        warnings: list[str] | None = None,
        untrusted_comments: dict[int, str] | None = None,
    ) -> str:
        game_id = f"game_{uuid.uuid4().hex[:12]}"
        now = datetime.now(timezone.utc).isoformat()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO games (
                    game_id, created_at, pgn_text, fen_root, has_full_history,
                    white, black, result, event, player_color, target_rating,
                    platform, analysis_status, critical_plies_json,
                    warnings_json, untrusted_comments_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending', '[]', ?, ?)
                """,
                (
                    game_id,
                    now,
                    pgn_text,
                    fen_root,
                    1 if has_full_history else 0,
                    white,
                    black,
                    result,
                    event,
                    player_color,
                    target_rating,
                    platform,
                    json.dumps(warnings or []),
                    json.dumps({str(k): v for k, v in (untrusted_comments or {}).items()}),
                ),
            )
        return game_id

    def get_game(self, game_id: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM games WHERE game_id = ?", (game_id,)).fetchone()
            if not row:
                return None
            data = dict(row)
            data["has_full_history"] = bool(data["has_full_history"])
            data["critical_plies"] = json.loads(data.pop("critical_plies_json", "[]"))
            data["warnings"] = json.loads(data.pop("warnings_json", "[]"))
            data["untrusted_comments"] = json.loads(data.pop("untrusted_comments_json", "{}"))
            return data

    def list_games(self, limit: int = 50) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM games ORDER BY created_at DESC LIMIT ?", (limit,)
            ).fetchall()
            results = []
            for row in rows:
                d = dict(row)
                d["has_full_history"] = bool(d["has_full_history"])
                d["critical_plies"] = json.loads(d.pop("critical_plies_json", "[]"))
                d["warnings"] = json.loads(d.pop("warnings_json", "[]"))
                d["untrusted_comments"] = json.loads(d.pop("untrusted_comments_json", "{}"))
                results.append(d)
            return results

    def update_game_status(
        self,
        game_id: str,
        analysis_status: str,
        critical_plies: list[int] | None = None,
    ) -> None:
        with self._connect() as conn:
            if critical_plies is not None:
                conn.execute(
                    "UPDATE games SET analysis_status = ?, critical_plies_json = ? WHERE game_id = ?",
                    (analysis_status, json.dumps(critical_plies), game_id),
                )
            else:
                conn.execute(
                    "UPDATE games SET analysis_status = ? WHERE game_id = ?",
                    (analysis_status, game_id),
                )

    def upsert_ply_skeleton(
        self,
        game_id: str,
        ply: int,
        move_number: int,
        turn: str,
        uci_move: str,
        san_move: str,
        fen_before: str,
        fen_after: str,
        state_before_hash: str,
        state_after_hash: str,
    ) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO ply_analyses (
                    game_id, ply, move_number, turn, uci_move, san_move,
                    fen_before, fen_after, state_before_hash, state_after_hash, deep_status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'queued')
                ON CONFLICT(game_id, ply) DO UPDATE SET
                    uci_move=excluded.uci_move,
                    san_move=excluded.san_move,
                    fen_before=excluded.fen_before,
                    fen_after=excluded.fen_after,
                    state_before_hash=excluded.state_before_hash,
                    state_after_hash=excluded.state_after_hash
                """,
                (
                    game_id,
                    ply,
                    move_number,
                    turn,
                    uci_move,
                    san_move,
                    fen_before,
                    fen_after,
                    state_before_hash,
                    state_after_hash,
                ),
            )

    def update_ply_coarse(
        self,
        game_id: str,
        ply: int,
        coarse_eval_cp_white: int | None,
        coarse_mate_white: int | None,
        coarse_eval_after_cp_white: int | None,
        coarse_mate_after_white: int | None,
        eval_swing_cp: int,
        critical_score: float = 0.0,
        critical_reason: dict[str, Any] | None = None,
        is_critical: bool = False,
    ) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE ply_analyses SET
                    coarse_eval_cp_white = ?,
                    coarse_mate_white = ?,
                    coarse_eval_after_cp_white = ?,
                    coarse_mate_after_white = ?,
                    eval_swing_cp = ?,
                    critical_score = ?,
                    critical_reason_json = ?,
                    is_critical = ?
                WHERE game_id = ? AND ply = ?
                """,
                (
                    coarse_eval_cp_white,
                    coarse_mate_white,
                    coarse_eval_after_cp_white,
                    coarse_mate_after_white,
                    eval_swing_cp,
                    critical_score,
                    json.dumps(critical_reason or {}),
                    1 if is_critical else 0,
                    game_id,
                    ply,
                ),
            )

    def update_ply_deep_result(
        self,
        game_id: str,
        ply: int,
        deep_status: str,
        ledger: dict[str, Any] | None = None,
        commentary: dict[str, Any] | None = None,
    ) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE ply_analyses SET
                    deep_status = ?,
                    ledger_json = ?,
                    commentary_json = ?
                WHERE game_id = ? AND ply = ?
                """,
                (
                    deep_status,
                    json.dumps(ledger) if ledger is not None else None,
                    json.dumps(commentary) if commentary is not None else None,
                    game_id,
                    ply,
                ),
            )

    def prioritize_ply(self, game_id: str, ply: int) -> bool:
        with self._connect() as conn:
            cur = conn.execute(
                """
                UPDATE ply_analyses
                SET priority_boost = priority_boost + 100
                WHERE game_id = ? AND ply = ?
                """,
                (game_id, ply),
            )
            return cur.rowcount > 0

    def get_ply_analysis(self, game_id: str, ply: int) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM ply_analyses WHERE game_id = ? AND ply = ?",
                (game_id, ply),
            ).fetchone()
            if not row:
                return None
            return self._deserialize_ply_row(row)

    def list_ply_analyses(self, game_id: str) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM ply_analyses WHERE game_id = ? ORDER BY ply ASC",
                (game_id,),
            ).fetchall()
            return [self._deserialize_ply_row(r) for r in rows]

    def _deserialize_ply_row(self, row: sqlite3.Row) -> dict[str, Any]:
        d = dict(row)
        d["is_critical"] = bool(d["is_critical"])
        d["critical_reason"] = json.loads(d.pop("critical_reason_json", "{}") or "{}")
        ledger_raw = d.pop("ledger_json", None)
        commentary_raw = d.pop("commentary_json", None)
        d["ledger"] = json.loads(ledger_raw) if ledger_raw else None
        d["commentary"] = json.loads(commentary_raw) if commentary_raw else None
        return d

    def get_engine_cache(self, cache_key: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT record_json FROM engine_cache WHERE cache_key = ?", (cache_key,)
            ).fetchone()
            if not row:
                return None
            return json.loads(row["record_json"])

    def set_engine_cache(self, cache_key: str, record_data: dict[str, Any]) -> None:
        now = datetime.now(timezone.utc).isoformat()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO engine_cache (cache_key, created_at, record_json)
                VALUES (?, ?, ?)
                ON CONFLICT(cache_key) DO UPDATE SET
                    created_at=excluded.created_at,
                    record_json=excluded.record_json
                """,
                (cache_key, now, json.dumps(record_data)),
            )
