import chess
import pytest
from evan.evidence.detectors import (
    detect_double_attacks,
    detect_undefended_pieces,
    detect_pins,
    trace_line_events,
)


def test_undefended_distinguishes_pinned_defender():
    board = chess.Board("6r1/7k/8/8/8/5N2/6P1/6K1 w - - 0 1")
    undefended = detect_undefended_pieces(board, chess.WHITE)
    f3_items = [u for u in undefended if u.square == "f3"]
    assert len(f3_items) == 1
    assert f3_items[0].protection_status == "pinned_defender_only"
    assert f3_items[0].evidence_id == "ev_root_undef_white_f3"

    pins = detect_pins(board, chess.WHITE)
    assert any(p.pinned_square == "g2" and p.pinner_square == "g8" for p in pins)


def test_double_attack_and_material_gain_in_pv():
    board = chess.Board("r3kbnr/pp3ppp/8/3N4/8/8/PPPPPPPP/R1BQKBNR w KQkq - 0 1")
    pv_uci = ["d5c7", "e8d8", "c7a8"]
    trace = trace_line_events(board, branch_id="br_best", pv_uci=pv_uci)
    assert any(e.event_type == "double_attack" and e.ply_offset == 1 for e in trace.events)
    assert trace.net_material_delta_mover == 500
    assert len(trace.state_hashes) == 4
    assert trace.root_state_hash == trace.state_hashes[0]


def test_pinned_attacker_does_not_create_false_double_attack():
    board = chess.Board("4r2k/8/8/8/8/8/q3R2r/4K3 b - - 0 1")
    assert board.is_pinned(chess.WHITE, chess.E2)
    assert detect_double_attacks(board, chess.E2) is None


def test_trace_line_events_rejects_illegal_or_malformed_pv():
    board = chess.Board()
    with pytest.raises(ValueError, match="Illegal PV move"):
        trace_line_events(board, branch_id="br_bad", pv_uci=["e2e4", "e2e5"])
    with pytest.raises(ValueError, match="Malformed UCI move"):
        trace_line_events(board, branch_id="br_bad", pv_uci=["not_a_move"])
