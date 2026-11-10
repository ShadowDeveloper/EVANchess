import chess
from evan.chess_core.state import GameStateIdentity
from evan.storage.repository import EvanRepository


def test_state_identity_distinguishes_repetition_and_rule50():
    board1 = chess.Board()
    id1 = GameStateIdentity.from_board(board1, uci_history=[])

    board2 = chess.Board()
    moves = ["g1f3", "g8f6", "f3g1", "f6g8"]
    for m in moves:
        board2.push_uci(m)
    id2 = GameStateIdentity.from_board(board2, uci_history=moves)

    assert id1.board_fen == id2.board_fen
    assert id1.state_hash != id2.state_hash
    assert id2.is_repetition_relevant is True


def test_repository_persists_game_and_engine_cache(tmp_path):
    db_file = tmp_path / "test_evan.db"
    repo = EvanRepository(str(db_file))
    repo.init_db()

    game_id = repo.create_game(
        pgn_text="1. e4 e5 2. Nf3 Nc6",
        white="PlayerA",
        black="PlayerB",
        player_color="white",
        target_rating=1500,
        platform="lichess",
    )
    game = repo.get_game(game_id)
    assert game is not None
    assert game["white"] == "PlayerA"
    assert game["analysis_status"] == "pending"

    repo.set_engine_cache("k1", {"score": 45})
    assert repo.get_engine_cache("k1") == {"score": 45}
