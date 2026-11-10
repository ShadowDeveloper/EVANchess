from __future__ import annotations

import chess
from pydantic import BaseModel, Field
from evan.engines.protocols import (
    EngineProtocol,
    comparable_mover_cp,
    format_mover_eval,
    is_confident_record,
)
from evan.engines.stockfish import build_board_with_history
from evan.pipeline.branch_search import BranchAnalysis


class ChallengeDefenseLine(BaseModel):
    defense_uci: str
    defense_san: str
    eval_cp_original_mover: int | None = None
    mate_original_mover: int | None = None
    pv_san: list[str] = Field(default_factory=list)


class ChallengeOutcome(BaseModel):
    query_id: str
    branch_id: str
    challenged_at_ply_offset: int
    opponent_punishing_move_san: str
    defenses_tested: list[ChallengeDefenseLine] = Field(default_factory=list)
    refutation_holds_across_top_defenses: bool = False
    evaluation_only_check: bool = True
    discovered_contradictions: list[str] = Field(default_factory=list)
    recommended_scope: str = "in_displayed_continuation"


def run_challenge_search_for_branch(
    root_board: chess.Board,
    branch: BranchAnalysis,
    engine: EngineProtocol,
    uci_history: list[str] | None = None,
    challenge_nodes: int = 60_000,
) -> ChallengeOutcome | None:
    pv_uci = branch.primary_record.pv_uci
    if len(pv_uci) < 2:
        return None

    board, hist = build_board_with_history(root_board, uci_history)

    try:
        move0 = chess.Move.from_uci(pv_uci[0])
    except ValueError:
        return None
    if move0 not in board.legal_moves:
        return None
    board.push(move0)
    hist.append(pv_uci[0])

    try:
        move1 = chess.Move.from_uci(pv_uci[1])
    except ValueError:
        return None
    if move1 not in board.legal_moves:
        return None
    punishing_san = board.san(move1)
    board.push(move1)
    hist.append(pv_uci[1])

    if board.is_game_over():
        is_mate = board.is_checkmate()
        return ChallengeOutcome(
            query_id=f"chal_{branch.branch_id}",
            branch_id=branch.branch_id,
            challenged_at_ply_offset=2,
            opponent_punishing_move_san=punishing_san,
            defenses_tested=[],
            refutation_holds_across_top_defenses=is_mate,
            evaluation_only_check=not is_mate,
            discovered_contradictions=[],
            recommended_scope="exact_rules_or_tablebase" if is_mate else "in_displayed_continuation",
        )

    recs = engine.analyze_root(
        board, uci_history=hist, nodes=challenge_nodes, multipv=3
    )
    if not recs:
        return None

    defenses: list[ChallengeDefenseLine] = []
    contradictions: list[str] = []
    all_confident = True

    for rec in recs:
        if not rec.pv_uci:
            continue
        def_uci = rec.pv_uci[0]
        def_san = rec.pv_san[0] if rec.pv_san else def_uci
        comp_sc = comparable_mover_cp(rec)
        if not is_confident_record(rec) or comp_sc is None:
            all_confident = False
        defenses.append(
            ChallengeDefenseLine(
                defense_uci=def_uci,
                defense_san=def_san,
                eval_cp_original_mover=rec.score_cp_mover,
                mate_original_mover=rec.mate_mover,
                pv_san=rec.pv_san[:5],
            )
        )
        if comp_sc is not None and comp_sc >= -60:
            contradictions.append(
                f"Defensive reply {def_san} holds the evaluation to {format_mover_eval(rec)} at {challenge_nodes} nodes."
            )

    holds = len(defenses) > 0 and all_confident and len(contradictions) == 0

    return ChallengeOutcome(
        query_id=f"chal_{branch.branch_id}",
        branch_id=branch.branch_id,
        challenged_at_ply_offset=2,
        opponent_punishing_move_san=punishing_san,
        defenses_tested=defenses,
        refutation_holds_across_top_defenses=holds,
        evaluation_only_check=True,
        discovered_contradictions=contradictions,
        recommended_scope="in_displayed_continuation",
    )
