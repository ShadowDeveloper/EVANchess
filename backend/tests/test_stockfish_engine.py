import chess
import chess.engine
from evan.engines.stockfish import StockfishEngine, normalize_info_to_record


def test_normalize_info_perspective_white_and_black():
    # Black to move, Black is +150 cp ahead (so White perspective is -150 cp)
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
    assert rec.wdl_white == (100, 300, 600)
    assert rec.pv_san == ["Nf6", "Nc3"]


def test_real_stockfish_uci_analysis(tmp_path):
    engine = StockfishEngine(threads=1, hash_mb=16)
    try:
        board = chess.Board()
        records = engine.analyze_root(board, uci_history=[], nodes=5000, multipv=2)
        assert len(records) == 2
        assert records[0].reported_nodes > 0
        assert len(records[0].pv_uci) >= 1
        assert len(records[0].pv_san) >= 1
    finally:
        engine.close()
