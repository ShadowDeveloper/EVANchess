from __future__ import annotations

import math
import chess
from pydantic import BaseModel, Field
from evan.chess_core.parser import ParsedGame
from evan.engines.protocols import EngineAnalysisRecord, EngineProtocol


def cp_to_win_prob(cp: int | None) -> float:
    """Lichess-style empirical centipawn to win-probability mapping [0.0, 1.0]."""
    if cp is None:
        return 0.5
    clamped = max(-4000, min(4000, cp))
    return 1.0 / (1.0 + math.exp(-0.00368208 * clamped))


class CoarsePlySummary(BaseModel):
    ply: int
    move_number: int
    turn: str  # "white" | "black"
    uci: str
    san: str
    fen_before: str
    fen_after: str
    state_before_hash: str
    state_after_hash: str
    eval_before_cp_white: int = 0
    mate_before_white: int | None = None
    eval_after_cp_white: int = 0
    mate_after_white: int | None = None
    eval_swing_cp_mover: int = 0
    win_prob_delta_mover: float = 0.0
    top1_top2_gap_cp: int = 0
    best_move_uci: str | None = None
    best_move_san: str | None = None
    played_matches_best: bool = False
    is_capture: bool = False
    gives_check: bool = False
    phase: str = "opening"  # "opening" | "middlegame" | "endgame"
    multipv_before: list[EngineAnalysisRecord] = Field(default_factory=list)


def classify_phase(board: chess.Board, ply: int) -> str:
    non_pawn_material = 0
    values = {chess.KNIGHT: 3, chess.BISHOP: 3, chess.ROOK: 5, chess.QUEEN: 9}
    for pt, val in values.items():
        non_pawn_material += (
            len(board.pieces(pt, chess.WHITE)) + len(board.pieces(pt, chess.BLACK))
        ) * val
    if ply < 14 and non_pawn_material >= 44:
        return "opening"
    if non_pawn_material <= 20:
        return "endgame"
    return "middlegame"


def run_coarse_game_pass(
    parsed_game: ParsedGame,
    engine: EngineProtocol,
    coarse_nodes: int = 25_000,
) -> list[CoarsePlySummary]:
    """Run Step 2 coarse engine pass across all game plies."""
    summaries: list[CoarsePlySummary] = []
    board = chess.Board(parsed_game.fen_root)
    uci_history: list[str] = []

    cached_records: dict[int, list[EngineAnalysisRecord]] = {}
    for ply_obj in parsed_game.plies:
        recs = engine.analyze_root(
            board, uci_history=uci_history, nodes=coarse_nodes, multipv=2
        )
        cached_records[ply_obj.ply] = recs
        move = chess.Move.from_uci(ply_obj.uci)
        board.push(move)
        uci_history.append(ply_obj.uci)

    # Also evaluate terminal position if not game over
    terminal_recs = (
        engine.analyze_root(board, uci_history=uci_history, nodes=coarse_nodes, multipv=1)
        if not board.is_game_over()
        else []
    )

    sim_board = chess.Board(parsed_game.fen_root)
    for idx, ply_obj in enumerate(parsed_game.plies):
        recs_before = cached_records.get(ply_obj.ply, [])
        recs_after = (
            cached_records.get(ply_obj.ply + 1, [])
            if idx + 1 < len(parsed_game.plies)
            else terminal_recs
        )

        top1 = recs_before[0] if recs_before else None
        top2 = recs_before[1] if len(recs_before) > 1 else None
        after1 = recs_after[0] if recs_after else None

        eval_before = top1.score_cp_white if (top1 and top1.score_cp_white is not None) else 0
        mate_before = top1.mate_white if top1 else None

        move = chess.Move.from_uci(ply_obj.uci)
        is_cap = sim_board.is_capture(move)
        phase = classify_phase(sim_board, ply_obj.ply)
        sim_board.push(move)
        gives_chk = sim_board.is_check()

        if sim_board.is_checkmate():
            eval_after = 10000 if ply_obj.turn == "white" else -10000
            mate_after = 0
        elif sim_board.is_game_over():
            eval_after = 0
            mate_after = None
        else:
            eval_after = (
                after1.score_cp_white if (after1 and after1.score_cp_white is not None) else eval_before
            )
            mate_after = after1.mate_white if after1 else None

        sign = 1 if ply_obj.turn == "white" else -1
        mover_before = eval_before * sign
        mover_after = eval_after * sign
        swing_cp_mover = mover_after - mover_before

        wp_before = cp_to_win_prob(mover_before)
        wp_after = cp_to_win_prob(mover_after)
        wp_delta = wp_after - wp_before

        gap_cp = 0
        if top1 and top2 and top1.score_cp_mover is not None and top2.score_cp_mover is not None:
            gap_cp = abs(top1.score_cp_mover - top2.score_cp_mover)

        best_uci = top1.pv_uci[0] if (top1 and top1.pv_uci) else None
        best_san = top1.pv_san[0] if (top1 and top1.pv_san) else None

        summaries.append(
            CoarsePlySummary(
                ply=ply_obj.ply,
                move_number=ply_obj.move_number,
                turn=ply_obj.turn,
                uci=ply_obj.uci,
                san=ply_obj.san,
                fen_before=ply_obj.state_before.fen,
                fen_after=ply_obj.state_after.fen,
                state_before_hash=ply_obj.state_before.state_hash,
                state_after_hash=ply_obj.state_after.state_hash,
                eval_before_cp_white=eval_before,
                mate_before_white=mate_before,
                eval_after_cp_white=eval_after,
                mate_after_white=mate_after,
                eval_swing_cp_mover=swing_cp_mover,
                win_prob_delta_mover=wp_delta,
                top1_top2_gap_cp=gap_cp,
                best_move_uci=best_uci,
                best_move_san=best_san,
                played_matches_best=(best_uci == ply_obj.uci),
                is_capture=is_cap,
                gives_check=gives_chk,
                phase=phase,
                multipv_before=recs_before,
            )
        )

    return summaries
