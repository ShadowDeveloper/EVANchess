from __future__ import annotations

import chess
from pydantic import BaseModel, Field
from evan.engines.protocols import (
    EngineAnalysisRecord,
    EngineProtocol,
    comparable_mover_cp,
    is_confident_record,
    mover_sort_key,
)
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
    uci_history: list[str] = Field(default_factory=list)
    turn: str
    branches: list[BranchAnalysis] = Field(default_factory=list)
    played_branch_id: str = ""
    best_branch_id: str = ""
    played_is_best: bool = False
    ranking_reversed_across_budgets: bool = False
    is_near_equal_top_choice: bool = False
    stability_status: str = "stable"
    eval_gap_played_vs_best_cp: int = 0


def _check_branch_stability(
    t1: EngineAnalysisRecord,
    pri: EngineAnalysisRecord,
) -> tuple[int, bool]:
    if not is_confident_record(t1) or not is_confident_record(pri):
        return 0, False
    if t1.mate_mover is not None or pri.mate_mover is not None:
        if t1.mate_mover is not None and pri.mate_mover is not None:
            same_sign = (t1.mate_mover > 0 and pri.mate_mover > 0) or (
                t1.mate_mover < 0 and pri.mate_mover < 0
            ) or (t1.mate_mover == 0 and pri.mate_mover == 0)
            drift_plies = abs(pri.mate_mover - t1.mate_mover)
            return drift_plies * 50, same_sign
        return 1000, False
    if t1.score_cp_mover is None or pri.score_cp_mover is None:
        return 0, False
    drift = abs(pri.score_cp_mover - t1.score_cp_mover)
    return drift, drift <= 60


def run_deep_branch_search(
    ply: int,
    board: chess.Board,
    uci_history: list[str],
    candidates: list[CandidateMoveSpec],
    engine: EngineProtocol,
    tier1_nodes: int = 75_000,
    primary_nodes: int = 150_000,
) -> MomentBranchBundle:
    branches: list[BranchAnalysis] = []

    for cand in candidates:
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
        drift, is_stable = _check_branch_stability(t1, pri)

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

    turn_str = "white" if board.turn == chess.WHITE else "black"
    if not branches:
        return MomentBranchBundle(
            ply=ply,
            root_fen=board.fen(),
            uci_history=list(uci_history),
            turn=turn_str,
            branches=[],
            played_branch_id="",
            best_branch_id="",
            played_is_best=False,
            ranking_reversed_across_budgets=False,
            is_near_equal_top_choice=False,
            stability_status="incomplete",
            eval_gap_played_vs_best_cp=0,
        )

    played_br = next((b for b in branches if b.role == "played"), branches[0])
    sorted_pri = sorted(
        branches,
        key=lambda b: mover_sort_key(b.primary_record),
        reverse=True,
    )
    sorted_t1 = sorted(
        branches,
        key=lambda b: mover_sort_key(b.tier1_record),
        reverse=True,
    )

    best_pri = sorted_pri[0]
    best_t1 = sorted_t1[0]

    any_unconfident = any(
        not is_confident_record(b.primary_record) or not is_confident_record(b.tier1_record)
        for b in branches
    )

    best_comp = comparable_mover_cp(best_pri.primary_record)
    played_comp = comparable_mover_cp(played_br.primary_record)
    if best_comp is not None and played_comp is not None:
        gap_cp = max(0, best_comp - played_comp)
    else:
        gap_cp = 0

    if best_pri.branch_id == played_br.branch_id:
        played_is_best = True
    elif (
        is_confident_record(best_pri.primary_record)
        and is_confident_record(played_br.primary_record)
        and best_pri.primary_record.mate_mover is None
        and played_br.primary_record.mate_mover is None
        and gap_cp <= 10
    ):
        played_is_best = True
    elif (
        is_confident_record(best_pri.primary_record)
        and is_confident_record(played_br.primary_record)
        and best_pri.primary_record.mate_mover is not None
        and best_pri.primary_record.mate_mover == played_br.primary_record.mate_mover
    ):
        played_is_best = True
    else:
        played_is_best = False

    ranking_reversed = best_pri.branch_id != best_t1.branch_id
    is_near_equal = False
    if len(sorted_pri) >= 2:
        sec_rec = sorted_pri[1].primary_record
        if (
            is_confident_record(best_pri.primary_record)
            and is_confident_record(sec_rec)
            and best_pri.primary_record.mate_mover is None
            and sec_rec.mate_mover is None
            and best_pri.primary_record.score_cp_mover is not None
            and sec_rec.score_cp_mover is not None
        ):
            if abs(best_pri.primary_record.score_cp_mover - sec_rec.score_cp_mover) <= 20:
                is_near_equal = True

    if any_unconfident:
        stability_status = "incomplete"
    elif ranking_reversed or any(not b.is_stable for b in branches):
        stability_status = "unstable_reversal" if ranking_reversed else "unstable_drift"
    elif is_near_equal:
        stability_status = "near_equal"
    else:
        stability_status = "stable"

    return MomentBranchBundle(
        ply=ply,
        root_fen=board.fen(),
        uci_history=list(uci_history),
        turn=turn_str,
        branches=branches,
        played_branch_id=played_br.branch_id,
        best_branch_id=best_pri.branch_id,
        played_is_best=played_is_best,
        ranking_reversed_across_budgets=ranking_reversed,
        is_near_equal_top_choice=is_near_equal,
        stability_status=stability_status,
        eval_gap_played_vs_best_cp=gap_cp,
    )
