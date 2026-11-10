from __future__ import annotations

import hashlib
import json

import chess
from pydantic import BaseModel, Field


class GameStateIdentity(BaseModel):
    state_id: str
    state_hash: str
    fen: str
    board_fen: str
    turn: str
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
        raw_fen = board.fen(en_passant="fen")
        parts = raw_fen.split()
        turn_str = "white" if board.turn == chess.WHITE else "black"
        stack_history = [move.uci() for move in board.move_stack]
        history_list = list(uci_history) if uci_history is not None else stack_history
        repetition_key = board.fen(en_passant="legal").split()[:4]
        cursor = board.copy()
        rep_count = 1
        reversible_tail: list[str] = []
        while cursor.move_stack:
            move = cursor.pop()
            if cursor.is_irreversible(move):
                cursor.push(move)
                break
            reversible_tail.append(move.uci())
            if cursor.fen(en_passant="legal").split()[:4] == repetition_key:
                rep_count += 1
        reversible_tail.reverse()

        canonical_payload = json.dumps(
            {
                "fen": raw_fen,
                "starting_fen": board.root().fen(en_passant="fen"),
                "board_history": stack_history,
                "supplied_history": history_list,
                "history_boundary_fen": cursor.fen(en_passant="fen"),
                "repetition_count": rep_count,
                "irreversible_tail": reversible_tail,
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        digest = hashlib.sha256(canonical_payload.encode("utf-8")).hexdigest()
        return cls(
            state_id=f"{state_id_prefix}_{digest}",
            state_hash=digest,
            fen=raw_fen,
            board_fen=parts[0],
            turn=turn_str,
            castling_rights=parts[2],
            ep_square=None if parts[3] == "-" else parts[3],
            halfmove_clock=board.halfmove_clock,
            fullmove_number=board.fullmove_number,
            repetition_count=rep_count,
            uci_history_since_irreversible=reversible_tail,
            is_repetition_relevant=rep_count >= 2 or board.halfmove_clock > 0,
        )
