from typing import cast
import chess
import chess.engine
import pytest
from evan.engines.protocols import comparable_mover_cp, is_confident_record, mover_sort_key
from evan.engines.stockfish import (
    StockfishEngine,
    build_board_with_history,
    normalize_info_to_record,
    validate_root_moves,
)


def test_normalize_info_perspective_white_and_black():
    board = chess.Board("rnbqkbnr/pppp1ppp/8/4p3/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1")
    info: chess.engine.InfoDict = {
        "depth": 12,
        "seldepth": 18,
        "nodes": 25000,
        "score": chess.engine.PovScore(chess.engine.Cp(150), chess.BLACK),
        "wdl": chess.engine.PovWdl(chess.engine.Wdl(600, 300, 100), chess.BLACK),
        "pv": [chess.Move.from_uci("g8f6"), chess.Move.from_uci("b1c3")],
    }
    rec = normalize_info_to_record(
        info=info,
        board=board,
        uci_history=["e2e4", "e7e5"],
        engine_name="Stockfish 17",
        engine_path="stockfish",
        threads=1,
        hash_mb=64,
        node_limit=25000,
    )
    assert rec.score_cp_mover == 150
    assert rec.score_cp_white == -150
    assert rec.mate_mover is None
    assert rec.mate_white is None
    assert rec.score_bound == "exact"
    assert rec.is_complete is True
    assert rec.evidence_id.startswith("ev_eng_")
    assert len(rec.binary_sha256) == 64
    assert len(rec.options_fingerprint) == 64
    assert rec.wdl_white == (100, 300, 600)
    assert rec.pv_san == ["Nf6", "Nc3"]


def test_mate_kept_separate_from_cp_and_mate_zero_sign_preserved():
    board = chess.Board()
    mate_win_info: chess.engine.InfoDict = {
        "depth": 10,
        "seldepth": 10,
        "nodes": 5000,
        "score": chess.engine.PovScore(chess.engine.Mate(2), chess.WHITE),
        "pv": [chess.Move.from_uci("e2e4")],
    }
    rec_win = normalize_info_to_record(
        info=mate_win_info,
        board=board,
        uci_history=[],
        engine_name="Stockfish",
        engine_path="stockfish",
        threads=1,
        hash_mb=16,
        node_limit=5000,
    )
    assert rec_win.mate_white == 2
    assert rec_win.mate_mover == 2
    assert rec_win.score_cp_white is None
    assert rec_win.score_cp_mover is None
    comp_win = comparable_mover_cp(rec_win)
    assert comp_win is not None and comp_win > 9000

    mated_board = chess.Board("rnb1kbnr/pppp1ppp/8/4p3/6Pq/5P2/PPPPP2P/RNBQKBNR w KQkq - 1 3")
    mate_zero_info: chess.engine.InfoDict = {
        "depth": 1,
        "seldepth": 1,
        "nodes": 1,
        "score": chess.engine.PovScore(chess.engine.Mate(0), chess.WHITE),
        "pv": [],
    }
    rec_mated = normalize_info_to_record(
        info=mate_zero_info,
        board=mated_board,
        uci_history=[],
        engine_name="Stockfish",
        engine_path="stockfish",
        threads=1,
        hash_mb=16,
        node_limit=100,
    )
    assert rec_mated.mate_mover == 0
    assert rec_mated.score_cp_mover is None
    assert comparable_mover_cp(rec_mated) == -10000
    assert mover_sort_key(rec_win) > mover_sort_key(rec_mated)


def test_bounds_and_incomplete_records_marked_not_confident():
    board = chess.Board()
    bound_info = cast(
        chess.engine.InfoDict,
        {
            "depth": 8,
            "seldepth": 12,
            "nodes": 1000,
            "score": chess.engine.PovScore(chess.engine.Cp(80), chess.WHITE),
            "upperbound": True,
            "pv": [chess.Move.from_uci("e2e4")],
        },
    )
    rec_bound = normalize_info_to_record(
        info=bound_info,
        board=board,
        uci_history=[],
        engine_name="Stockfish",
        engine_path="stockfish",
        threads=1,
        hash_mb=16,
        node_limit=1000,
    )
    assert rec_bound.score_bound == "upperbound"
    assert is_confident_record(rec_bound) is False
    assert comparable_mover_cp(rec_bound) is None

    illegal_pv_info: chess.engine.InfoDict = {
        "depth": 8,
        "seldepth": 12,
        "nodes": 1000,
        "score": chess.engine.PovScore(chess.engine.Cp(80), chess.WHITE),
        "pv": [chess.Move.from_uci("e7e5")],
    }
    rec_incomplete = normalize_info_to_record(
        info=illegal_pv_info,
        board=board,
        uci_history=[],
        engine_name="Stockfish",
        engine_path="stockfish",
        threads=1,
        hash_mb=16,
        node_limit=1000,
    )
    assert rec_incomplete.is_complete is False
    assert is_confident_record(rec_incomplete) is False


def test_validate_root_moves_and_history_reconstruction():
    board = chess.Board()
    with pytest.raises(ValueError, match="Illegal root move"):
        validate_root_moves(board, ["e7e5"])
    with pytest.raises(ValueError, match="empty"):
        validate_root_moves(board, [])

    rep_moves = ["g1f3", "g8f6", "f3g1", "f6g8"]
    b_played = chess.Board()
    for m in rep_moves:
        b_played.push_uci(m)
    b_fen_only = chess.Board(b_played.fen())
    reconstructed, hist = build_board_with_history(b_fen_only, rep_moves)
    assert hist == rep_moves
    assert reconstructed.is_repetition(2) is True

    with pytest.raises(ValueError):
        build_board_with_history(b_fen_only, ["e2e4", "e7e5"])


def test_real_stockfish_uci_analysis(tmp_path):
    engine = StockfishEngine(threads=1, hash_mb=16)
    try:
        board = chess.Board()
        records = engine.analyze_root(board, uci_history=[], nodes=5000, multipv=2)
        assert len(records) == 2
        assert records[0].reported_nodes > 0
        assert len(records[0].pv_uci) >= 1
        assert len(records[0].pv_san) >= 1
        assert records[0].hash_policy == "clear_before_search"
        assert len(records[0].binary_sha256) == 64
        assert len(records[0].options_fingerprint) == 64
        assert records[0].wall_time_seconds >= 0.0
    finally:
        engine.close()
