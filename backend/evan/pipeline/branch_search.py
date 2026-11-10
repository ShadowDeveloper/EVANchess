from __future__ import annotations

import chess
from pydantic import BaseModel, Field
from evan.engines.protocols import EngineAnalysisRecord, EngineProtocol
from evan.pipeline.alternatives import CandidateMoveSpec


class BranchAnalysis(BaseModel):
    branch_id: str
    root_move_uci: str
    root_move_san: str
    role: str
    nomination_source: str
    tier1_record: EngineAnalysisRecord
    primary_record: EngineAnalysisRecord
    score_drift_cp: int = 0
    is_stable: bool = True


class MomentBranchBundle(BaseModel):
    ply: int
    root_fen: str
    turn: str
    branches: list[BranchAnalysis] = Field(default_factory=list)
    played_branch_id: str
    best_branch_id: str
    played_is_best: bool
    ranking_reversed_across_budgets: bool = False
    is_near_equal_top_choice: bool = False
    stability_status: str = "stable"  # "stable" | "unstable_reversal" | "near_equal"
    eval_gap_played_vs_best_cp: int = 0


def run_deep_branch_search(
    ply: int,
    board: chess.Board,
    uci_history: list[str],
    candidates: list[CandidateMoveSpec],
    engine: EngineProtocol,
    tier1_nodes: int = 75_000,
    primary_nodes: int = 150_000,
) -> MomentBranchBundle:
    """Step 5: Run root-restricted searches across two budget tiers and evaluate stability."""
    branches: list[BranchAnalysis] = []

    for idx, cand in enumerate(candidates):
        branch_id = f"br_p{ply}_{cand.role}_{cand.uci}"
        t1_recs = engine.analyze_root(
            board,
            uci_history=uci_history,
            nodes=tier1_nodes,
            multipv=1,
            root_moves=[cand.uci],
        )
        pri_recs = engine.analyze_root(
            board,
            uci_history=uci_history,
            nodes=primary_nodes,
            multipv=1,
            root_moves=[cand.uci],
        )
        if not t1_recs or not pri_recs:
            continue

        t1 = t1_recs[0]
        pri = pri_recs[0]

        s1 = t1.score_cp_mover if t1.score_cp_mover is not None else 0
        s2 = pri.score_cp_mover if pri.score_cp_mover is not None else 0
        drift = abs(s2 - s1)
        is_stable = drift <= 60

        branches.append(
            BranchAnalysis(
                branch_id=branch_id,
                root_move_uci=cand.uci,
                root_move_san=cand.san,
                role=cand.role,
                nomination_source=cand.nomination_source,
                tier1_record=t1,
                primary_record=pri,
                score_drift_cp=drift,
                is_stable=is_stable,
            )
        )

    played_br = next((b for b in branches if b.role == "played"), branches[0])
    sorted_pri = sorted(
        branches,
        key=lambda b: b.primary_record.score_cp_mover
        if b.primary_record.score_cp_mover is not None
        else -99999,
        reverse=True,
    )
    sorted_t1 = sorted(
        branches,
        key=lambda b: b.tier1_record.score_cp_mover
        if b.tier1_record.score_cp_mover is not None
        else -99999,
        reverse=True,
    )

    best_pri = sorted_pri[0]
    best_t1 = sorted_t1[0]

    best_score = best_pri.primary_record.score_cp_mover or 0
    played_score = played_br.primary_record.score_cp_mover or 0
    gap_cp = best_score - played_score

    played_is_best = best_pri.branch_id == played_br.branch_id or gap_cp <= 10
    ranking_reversed = best_pri.branch_id != best_t1.branch_id
    is_near_equal = False
    if len(sorted_pri) >= 2:
        sec_score = sorted_pri[1].primary_record.score_cp_mover or 0
        if abs(best_score - sec_score) <= 20:
            is_near_equal = True

    if ranking_reversed or any(not b.is_stable for b in branches):
        stability_status = "unstable_reversal" if ranking_reversed else "unstable_drift"
    elif is_near_equal:
        stability_status = "near_equal"
    else:
        stability_status = "stable"

    return MomentBranchBundle(
        ply=ply,
        root_fen=board.fen(),
        turn="white" if board.turn == chess.WHITE else "black",
        branches=branches,
        played_branch_id=played_br.branch_id,
        best_branch_id=best_pri.branch_id,
        played_is_best=played_is_best,
        ranking_reversed_across_budgets=ranking_reversed,
        is_near_equal_top_choice=is_near_equal,
        stability_status=stability_status,
        eval_gap_played_vs_best_cp=gap_cp,
    )
