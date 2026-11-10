from __future__ import annotations

import hashlib
import json
import chess
from pydantic import BaseModel, Field


class GameStateIdentity(BaseModel):
    """Rule-aware chess position identity that preserves repetition and 50-move rule context."""

    state_id: str
    state_hash: str
    fen: str
    board_fen: str
    turn: str  # "white" | "black"
    castling_rights: str
    ep_square: str | None
    halfmove_clock: int
    fullmove_number: int
    repetition_count: int
    uci_history_since_irreversible: list[str] = Field(default_factory=list)
    is_repetition_relevant: bool = False

    @classmethod
    def from_board(
        cls,
        board: chess.Board,
        uci_history: list[str] | None = None,
        state_id_prefix: str = "state",
    ) -> GameStateIdentity:
        raw_fen = board.fen()
        parts = raw_fen.split(" ")
        board_fen = parts[0]
        turn_str = "white" if board.turn == chess.WHITE else "black"
        castling = parts[2] if len(parts) > 2 else "-"
        ep_sq = None if (len(parts) <= 3 or parts[3] == "-") else parts[3]
        halfmove = board.halfmove_clock
        fullmove = board.fullmove_number

        # Compute repetition count and history since last irreversible move
        rep_count = 1
        for count in (3, 2):
            if board.is_repetition(count):
                rep_count = count
                break

        history_list = list(uci_history) if uci_history is not None else [m.uci() for m in board.move_stack]
        tail_len = min(len(history_list), halfmove)
        irreversible_tail = history_list[-tail_len:] if tail_len > 0 else []

        is_rep_relevant = rep_count >= 2 or halfmove > 0

        canonical_payload = json.dumps(
            {
                "board_fen": board_fen,
                "turn": turn_str,
                "castling": castling,
                "ep_square": ep_sq,
                "halfmove_clock": halfmove,
                "repetition_count": rep_count,
                "irreversible_tail": irreversible_tail,
            },
            sort_keys=True,
        )
        digest = hashlib.sha256(canonical_payload.encode("utf-8")).hexdigest()[:24]
        return cls(
            state_id=f"{state_id_prefix}_{digest[:12]}",
            state_hash=digest,
            fen=raw_fen,
            board_fen=board_fen,
            turn=turn_str,
            castling_rights=castling,
            ep_square=ep_sq,
            halfmove_clock=halfmove,
            fullmove_number=fullmove,
            repetition_count=rep_count,
            uci_history_since_irreversible=irreversible_tail,
            is_repetition_relevant=is_rep_relevant,
        )
