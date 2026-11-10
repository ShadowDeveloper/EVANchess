import chess
from evan.engines.protocols import EngineAnalysisRecord
from evan.pipeline.alternatives import select_candidate_moves
from evan.pipeline.branch_search import run_deep_branch_search


class FakeStabilityEngine:
    def analyze_root(
        self,
        board: chess.Board,
        uci_history: list[str] | None = None,
        nodes: int = 25_000,
        multipv: int = 1,
        root_moves: list[str] | None = None,
    ) -> list[EngineAnalysisRecord]:
        mv = root_moves[0] if root_moves else "e2e4"
        # Simulate ranking reversal between tier1 (75k) and primary (150k)
        if mv == "e2e4":
            cp = 80 if nodes <= 75_000 else 10
        else:
            cp = 30 if nodes <= 75_000 else 95
        return [
            EngineAnalysisRecord(
                engine_name="FakeSF",
                engine_path="fake",
                threads=1,
                hash_mb=16,
                root_fen=board.fen(),
                root_state_hash="h0",
                allowed_root_moves=root_moves,
                node_limit=nodes,
                reported_nodes=nodes,
                depth=12 if nodes <= 75_000 else 16,
                seldepth=18,
                score_cp_white=cp,
                score_cp_mover=cp,
                pv_uci=[mv, "e7e5"],
                pv_san=[board.san(chess.Move.from_uci(mv)), "e5"],
            )
        ]

    def close(self) -> None:
        pass


def test_select_candidates_and_detect_budget_reversal():
    board = chess.Board()
    multipv = [
        EngineAnalysisRecord(
            engine_name="FakeSF",
            engine_path="fake",
            threads=1,
            hash_mb=16,
            root_fen=board.fen(),
            root_state_hash="h0",
            multipv_index=1,
            node_limit=25000,
            score_cp_white=40,
            score_cp_mover=40,
            pv_uci=["d2d4"],
            pv_san=["d4"],
        )
    ]
    cands = select_candidate_moves(board, played_uci="e2e4", multipv_records=multipv)
    assert [c.uci for c in cands] == ["e2e4", "d2d4"]

    bundle = run_deep_branch_search(
        ply=0,
        board=board,
        uci_history=[],
        candidates=cands,
        engine=FakeStabilityEngine(),
        tier1_nodes=75_000,
        primary_nodes=150_000,
    )
    assert bundle.ranking_reversed_across_budgets is True
    assert bundle.stability_status == "unstable_reversal"
    assert bundle.best_branch_id.endswith("d2d4")
