import chess
from evan.chess_core.parser import parse_game_input
from evan.engines.protocols import EngineAnalysisRecord
from evan.pipeline.coarse import CoarsePlySummary, run_coarse_game_pass
from evan.pipeline.moment_selector import select_critical_moments


class FakeMateAndBoundEngine:
    def analyze_root(
        self,
        board: chess.Board,
        uci_history: list[str] | None = None,
        nodes: int = 25_000,
        multipv: int = 1,
        root_moves: list[str] | None = None,
    ) -> list[EngineAnalysisRecord]:
        mv = next(iter(board.legal_moves))
        if len(uci_history or []) == 0:
            return [
                EngineAnalysisRecord(
                    engine_name="FakeSF",
                    engine_path="fake",
                    threads=1,
                    hash_mb=16,
                    root_fen=board.fen(),
                    root_state_hash="h0",
                    node_limit=nodes,
                    score_cp_white=None,
                    score_cp_mover=None,
                    mate_white=2,
                    mate_mover=2,
                    pv_uci=[mv.uci()],
                    pv_san=[board.san(mv)],
                )
            ]
        return [
            EngineAnalysisRecord(
                engine_name="FakeSF",
                engine_path="fake",
                threads=1,
                hash_mb=16,
                root_fen=board.fen(),
                root_state_hash="h1",
                node_limit=nodes,
                score_cp_white=50,
                score_cp_mover=-50,
                score_bound="upperbound",
                pv_uci=[mv.uci()],
                pv_san=[board.san(mv)],
            )
        ]

    def close(self) -> None:
        pass


def _make_summary(
    ply: int,
    swing_cp: int,
    wp_delta: float,
    gap_cp: int = 20,
    phase: str = "middlegame",
    turn: str = "white",
) -> CoarsePlySummary:
    return CoarsePlySummary(
        ply=ply,
        move_number=(ply // 2) + 1,
        turn=turn,
        uci="e2e4",
        san="e4",
        fen_before="8/8/8/8/8/8/8/8 w - - 0 1",
        fen_after="8/8/8/8/8/8/8/8 b - - 0 1",
        state_before_hash=f"h_pre_{ply}",
        state_after_hash=f"h_post_{ply}",
        eval_swing_cp_mover=swing_cp,
        win_prob_delta_mover=wp_delta,
        top1_top2_gap_cp=gap_cp,
        phase=phase,
    )


def test_moment_selector_surfaces_blunders_and_sharp_finds_with_diversity():
    summaries = [
        _make_summary(0, swing_cp=-10, wp_delta=-0.01, gap_cp=15, phase="opening"),
        _make_summary(4, swing_cp=0, wp_delta=0.0, gap_cp=320, phase="opening"),
        _make_summary(14, swing_cp=-350, wp_delta=-0.42, gap_cp=200, phase="middlegame"),
        _make_summary(15, swing_cp=300, wp_delta=0.38, gap_cp=180, phase="middlegame", turn="black"),
        _make_summary(30, swing_cp=-220, wp_delta=-0.30, gap_cp=150, phase="endgame"),
    ]
    selected = select_critical_moments(summaries, count=3, player_color="white")
    selected_plies = [m.ply for m in selected]
    assert 14 in selected_plies
    assert 30 in selected_plies
    assert 4 in selected_plies


def test_coarse_pass_handles_mate_and_excludes_bound_records_from_confident_comparison():
    parsed = parse_game_input("1. e4 e5")
    summaries = run_coarse_game_pass(parsed, FakeMateAndBoundEngine(), coarse_nodes=1000)
    assert len(summaries) == 2
    assert summaries[0].mate_before_white == 2
    assert summaries[0].eval_before_cp_white is None
    assert summaries[0].is_confident is False
    assert summaries[0].eval_swing_cp_mover == 0
