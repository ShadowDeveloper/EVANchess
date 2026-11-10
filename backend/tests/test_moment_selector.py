from evan.pipeline.coarse import CoarsePlySummary
from evan.pipeline.moment_selector import select_critical_moments


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
        # Ply 4: Quiet sharp find where player found the only move (swing=0, but top1-top2 gap=320cp)
        _make_summary(4, swing_cp=0, wp_delta=0.0, gap_cp=320, phase="opening"),
        # Ply 14 & 15: Consecutive blunders in middlegame
        _make_summary(14, swing_cp=-350, wp_delta=-0.42, gap_cp=200, phase="middlegame"),
        _make_summary(15, swing_cp=300, wp_delta=0.38, gap_cp=180, phase="middlegame", turn="black"),
        # Ply 30: Endgame mistake
        _make_summary(30, swing_cp=-220, wp_delta=-0.30, gap_cp=150, phase="endgame"),
    ]
    selected = select_critical_moments(summaries, count=3, player_color="white")
    selected_plies = [m.ply for m in selected]
    # Should pick ply 14 (biggest blunder), ply 30 (endgame blunder), and ply 4 (sharp opening resource)
    assert 14 in selected_plies
    assert 30 in selected_plies
    assert 4 in selected_plies
