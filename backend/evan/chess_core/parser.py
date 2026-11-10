from __future__ import annotations

import io
import re
import chess
import chess.pgn
from pydantic import BaseModel, Field
from evan.chess_core.state import GameStateIdentity


class GameParseError(ValueError):
    """Raised when PGN or FEN input is malformed, contains illegal moves, or uses an unsupported variant."""


class ParsedPly(BaseModel):
    ply: int
    move_number: int
    turn: str  # "white" | "black"
    uci: str
    san: str
    state_before: GameStateIdentity
    state_after: GameStateIdentity


class ParsedGame(BaseModel):
    fen_root: str
    has_full_history: bool
    white: str = "White"
    black: str = "Black"
    result: str = "*"
    event: str = ""
    plies: list[ParsedPly] = Field(default_factory=list)
    untrusted_comments: dict[int, str] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)
    clean_pgn: str = ""


_FEN_PATTERN = re.compile(
    r"^\s*([rnbqkpRNBQKP1-8]+/){7}[rnbqkpRNBQKP1-8]+\s+[wb]\s+(-|[KQkq]+)\s+(-|[a-h][36])(\s+\d+\s+\d+)?\s*$"
)


def _looks_like_fen(text: str) -> bool:
    stripped = text.strip()
    if "\n" in stripped:
        return False
    return bool(_FEN_PATTERN.match(stripped))


def parse_game_input(raw_input: str) -> ParsedGame:
    """Strictly parse and replay a PGN or FEN string per EVAN §4.4 Step 1 & §6.7."""
    if not raw_input or not raw_input.strip():
        raise GameParseError("Empty game input provided.")

    text = raw_input.strip()

    if _looks_like_fen(text):
        try:
            board = chess.Board(text)
        except ValueError as exc:
            raise GameParseError(f"Invalid FEN string: {exc}") from exc
        if not board.is_valid():
            status = board.status()
            raise GameParseError(f"Illegal board position in FEN (status={status}).")

        exporter = chess.pgn.Game.from_board(board)
        return ParsedGame(
            fen_root=board.fen(),
            has_full_history=False,
            white="White",
            black="Black",
            result="*",
            event="FEN Position",
            plies=[],
            untrusted_comments={},
            warnings=[
                "Input is a standalone FEN position; prior move and threefold-repetition history is unavailable."
            ],
            clean_pgn=str(exporter),
        )

    pgn_io = io.StringIO(text)
    game = chess.pgn.read_game(pgn_io)
    if game is None:
        raise GameParseError("Could not parse PGN input.")

    if game.errors:
        err_msgs = "; ".join(str(e) for e in game.errors)
        raise GameParseError(f"Illegal or unparseable move in PGN: {err_msgs}")

    variant = game.headers.get("Variant", "Standard")
    if variant.lower() not in ("standard", "from position", "chess"):
        raise GameParseError(
            f"Unsupported chess variant '{variant}'. EVAN only supports standard chess."
        )

    try:
        board = game.board()
    except ValueError as exc:
        raise GameParseError(f"Invalid starting board in PGN headers: {exc}") from exc

    if not board.is_valid():
        raise GameParseError("Starting position in PGN is not a legal chess position.")

    fen_root = board.fen()
    has_full_history = game.headers.get("SetUp", "0") != "1" and fen_root == chess.STARTING_FEN
    warnings: list[str] = []
    if not has_full_history:
        warnings.append(
            "Game starts from a custom FEN setup; earlier repetition history is unavailable."
        )

    plies: list[ParsedPly] = []
    untrusted_comments: dict[int, str] = {}
    uci_history: list[str] = []

    if game.comment and game.comment.strip():
        untrusted_comments[-1] = game.comment.strip()

    node = game
    ply_idx = 0
    while node.variations:
        next_node = node.variation(0)
        move = next_node.move
        if move not in board.legal_moves:
            raise GameParseError(
                f"Illegal or unparseable move '{move.uci()}' at ply {ply_idx + 1}."
            )

        turn_str = "white" if board.turn == chess.WHITE else "black"
        move_number = board.fullmove_number
        san_str = board.san(move)
        uci_str = move.uci()

        state_before = GameStateIdentity.from_board(
            board, uci_history=uci_history, state_id_prefix=f"s_p{ply_idx}_pre"
        )
        board.push(move)
        uci_history.append(uci_str)
        state_after = GameStateIdentity.from_board(
            board, uci_history=uci_history, state_id_prefix=f"s_p{ply_idx}_post"
        )

        if next_node.comment and next_node.comment.strip():
            untrusted_comments[ply_idx] = next_node.comment.strip()

        plies.append(
            ParsedPly(
                ply=ply_idx,
                move_number=move_number,
                turn=turn_str,
                uci=uci_str,
                san=san_str,
                state_before=state_before,
                state_after=state_after,
            )
        )
        node = next_node
        ply_idx += 1

    if len(plies) == 0 and not has_full_history:
        pass
    elif len(plies) == 0:
        raise GameParseError("No legal moves found in PGN input.")

    clean_game = chess.pgn.Game()
    for k in ("Event", "Site", "Date", "Round", "White", "Black", "Result", "FEN", "SetUp"):
        if k in game.headers:
            clean_game.headers[k] = game.headers[k]
    curr = clean_game
    for p in plies:
        curr = curr.add_variation(chess.Move.from_uci(p.uci))

    return ParsedGame(
        fen_root=fen_root,
        has_full_history=has_full_history,
        white=game.headers.get("White", "White"),
        black=game.headers.get("Black", "Black"),
        result=game.headers.get("Result", "*"),
        event=game.headers.get("Event", ""),
        plies=plies,
        untrusted_comments=untrusted_comments,
        warnings=warnings,
        clean_pgn=str(clean_game),
    )
