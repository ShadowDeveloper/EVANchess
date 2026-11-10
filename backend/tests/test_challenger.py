import chess
from evan.engines.protocols import EngineAnalysisRecord
from evan.evidence.challenger import run_challenge_search_for_branch
from evan.pipeline.branch_search import BranchAnalysis


class FakeChallengeEngine:
    def __init__(self, reply_scores: list[tuple[str, int]]) -> None:
        self.reply_scores = reply_scores

    def analyze_root(
        self,
        board: chess.Board,
        uci_history: list[str] | None = None,
        nodes: int = 60_000,
        multipv: int = 3,
        root_moves: list[str] | None = None,
    ) -> list[EngineAnalysisRecord]:
        recs = []
        for idx, (uci_mv, sc) in enumerate(self.reply_scores, start=1):
            mv_obj = chess.Move.from_uci(uci_mv)
            san_mv = board.san(mv_obj) if mv_obj in board.legal_moves else uci_mv
            recs.append(
                EngineAnalysisRecord(
                    engine_name="FakeSF",
                    engine_path="fake",
                    threads=1,
                    hash_mb=16,
                    root_fen=board.fen(),
                    root_state_hash="h",
                    multipv_index=idx,
                    node_limit=nodes,
                    score_cp_white=sc,
                    score_cp_mover=sc,
                    pv_uci=[uci_mv],
                    pv_san=[san_mv],
                )
            )
        return recs

    def close(self) -> None:
        pass


def test_challenge_search_identifies_refutation_holding_vs_contradiction():
    board = chess.Board()
    rec = EngineAnalysisRecord(
        engine_name="FakeSF",
        engine_path="fake",
        threads=1,
        hash_mb=16,
        root_fen=board.fen(),
        root_state_hash="h0",
        node_limit=150000,
        score_cp_white=-250,
        score_cp_mover=-250,
        pv_uci=["e2e4", "e7e5", "g1f3"],
        pv_san=["e4", "e5", "Nf3"],
    )
    branch = BranchAnalysis(
        branch_id="br_p0_played_e2e4",
        root_move_uci="e2e4",
        root_move_san="e4",
        role="played",
        nomination_source="game",
        tier1_record=rec,
        primary_record=rec,
    )

    outcome_holds = run_challenge_search_for_branch(
        board, branch, FakeChallengeEngine([("g1f3", -250), ("b1c3", -300)])
    )
    assert outcome_holds is not None
    assert outcome_holds.refutation_holds_across_top_defenses is True
    assert outcome_holds.evaluation_only_check is True
    assert outcome_holds.recommended_scope == "in_displayed_continuation"

    outcome_contra = run_challenge_search_for_branch(
        board, branch, FakeChallengeEngine([("g1f3", -250), ("d2d4", 0)])
    )
    assert outcome_contra is not None
    assert outcome_contra.refutation_holds_across_top_defenses is False
    assert len(outcome_contra.discovered_contradictions) == 1
    assert outcome_contra.recommended_scope == "in_displayed_continuation"
