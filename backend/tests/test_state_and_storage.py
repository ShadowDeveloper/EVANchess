import chess
import pytest
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


def test_state_identity_preserves_raw_ep_even_when_uncapturable():
    board = chess.Board()
    board.push_uci("e2e4")
    state = GameStateIdentity.from_board(board)
    assert state.ep_square == "e3"
    assert state.fen == board.fen(en_passant="fen")
    no_ep = board.copy()
    no_ep.ep_square = None
    assert state.state_hash != GameStateIdentity.from_board(no_ep).state_hash


@pytest.mark.parametrize("field", ["halfmove_clock", "fullmove_number"])
def test_state_identity_includes_both_rule_counters(field):
    board = chess.Board()
    changed = board.copy()
    setattr(changed, field, getattr(changed, field) + 1)
    assert GameStateIdentity.from_board(board).state_hash != GameStateIdentity.from_board(changed).state_hash


def test_state_identity_distinguishes_starting_fen_and_available_history():
    board = chess.Board()
    board.push_uci("g1f3")
    board.push_uci("g8f6")
    from_fen = chess.Board(board.fen(en_passant="fen"))
    history = ["g1f3", "g8f6"]
    known = GameStateIdentity.from_board(board, uci_history=history)
    unknown = GameStateIdentity.from_board(from_fen, uci_history=history)
    assert known.fen == unknown.fen
    assert known.state_hash != unknown.state_hash
    assert known.uci_history_since_irreversible == history
    assert unknown.uci_history_since_irreversible == []


def test_state_identity_counts_fivefold_without_mutating_board_or_supplied_history():
    board = chess.Board()
    moves = ["g1f3", "g8f6", "f3g1", "f6g8"] * 4
    for move in moves:
        board.push_uci(move)
    fen = board.fen(en_passant="fen")
    state = GameStateIdentity.from_board(board, uci_history=moves)
    assert state.repetition_count == 5
    assert state.uci_history_since_irreversible == moves
    assert board.fen(en_passant="fen") == fen
    assert [move.uci() for move in board.move_stack] == moves
    assert len(moves) == 16
    assert len(state.state_hash) == 64
    assert state.state_id == f"state_{state.state_hash}"
    assert state.state_hash == GameStateIdentity.from_board(board).state_hash
    moves.clear()
    assert len(state.uci_history_since_irreversible) == 16


def test_state_history_boundary_resets_after_pawn_move():
    board = chess.Board()
    for move in ["g1f3", "g8f6", "e2e4", "f6g8"]:
        board.push_uci(move)
    state = GameStateIdentity.from_board(board)
    assert state.uci_history_since_irreversible == ["f6g8"]
    assert state.halfmove_clock == 1


def test_state_history_boundary_resets_when_castling_rights_are_lost():
    board = chess.Board("r3k2r/8/8/8/8/8/8/R3K2R w KQkq - 12 20")
    board.push_uci("h1h2")
    state = GameStateIdentity.from_board(board)
    assert state.halfmove_clock == 13
    assert state.castling_rights == "Qkq"
    assert state.uci_history_since_irreversible == []
    board.push_uci("h8h7")
    board.push_uci("h2h1")
    state = GameStateIdentity.from_board(board)
    assert state.uci_history_since_irreversible == ["h2h1"]
    assert state.repetition_count == 1


def test_state_history_boundary_resets_after_legal_ep_opportunity_expires():
    board = chess.Board("4k3/8/8/3pP3/8/8/8/4K3 w - d6 0 20")
    assert board.has_legal_en_passant()
    board.push_uci("e1f1")
    state = GameStateIdentity.from_board(board)
    assert state.halfmove_clock == 1
    assert state.uci_history_since_irreversible == []


def test_state_identity_does_not_treat_uncapturable_ep_as_distinct_repetition():
    board = chess.Board()
    for move in ["e2e4", "g8f6", "g1f3", "f6g8", "f3g1"]:
        board.push_uci(move)
    assert GameStateIdentity.from_board(board).repetition_count == 2


def test_state_identity_keeps_distinct_declared_history_contexts_separate():
    board = chess.Board()
    first = GameStateIdentity.from_board(board, uci_history=[])
    second = GameStateIdentity.from_board(board, uci_history=["g1f3", "f3g1"])
    assert first.fen == second.fen
    assert first.state_hash != second.state_hash


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
