from __future__ import annotations

import re

import chess
import chess.pgn
from pydantic import BaseModel, Field

from evan.chess_core.state import GameStateIdentity


class GameParseError(ValueError):
    pass


class ParsedPly(BaseModel):
    ply: int
    move_number: int
    turn: str
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
_HEADER_PATTERN = re.compile(r'\[([A-Za-z0-9_]+)\s+"((?:[^"\\\r\n]|\\["\\])*)"\s*\]')
_TOKEN_PATTERN = re.compile(
    r"(?P<space>\s+)"
    r"|(?P<brace>\{[^}]*\})"
    r"|(?P<line>;[^\r\n]*)"
    r"|(?P<result>1/2-1/2|1-0|0-1|\*)"
    r"|(?P<number>[0-9]+\.(?:\.\.)?)"
    r"|(?P<nag>\$[0-9]+|!!|\?\?|!\?|\?!|!|\?)"
    r"|(?P<variation>[()])"
    r"|(?P<san>(?:O-O(?:-O)?|0-0(?:-0)?|[KQRBN]?[a-h]?[1-8]?x?[a-h][1-8](?:=[QRBN])?)[+#]?)"
)
_RESULTS = {"1-0", "0-1", "1/2-1/2", "*"}


def _looks_like_fen(text: str) -> bool:
    return "\n" not in text and bool(_FEN_PATTERN.fullmatch(text))


def _validated_board(fen: str) -> chess.Board:
    try:
        board = chess.Board(fen)
    except ValueError as exc:
        raise GameParseError(f"Invalid FEN string: {exc}") from exc
    if not board.is_valid():
        raise GameParseError(f"Illegal board position in FEN (status={board.status()}).")
    return board


def _parse_pgn(text: str) -> tuple[chess.pgn.Game, chess.Board]:
    headers: dict[str, str] = {}
    offset = 0
    while offset < len(text):
        if text[offset].isspace():
            offset += 1
            continue
        if text[offset] != "[":
            break
        header = _HEADER_PATTERN.match(text, offset)
        if header is None:
            raise GameParseError("Malformed PGN header.")
        name, value = header.groups()
        if name in headers:
            raise GameParseError(f"Duplicate PGN header: {name}.")
        headers[name] = re.sub(r'\\(["\\])', r"\1", value)
        offset = header.end()

    variant = headers.get("Variant", "Standard")
    if variant.casefold() not in ("standard", "from position", "chess"):
        raise GameParseError(
            f"Unsupported chess variant '{variant}'. EVAN only supports standard chess."
        )
    setup = headers.get("SetUp", "0")
    if setup not in ("0", "1"):
        raise GameParseError("PGN SetUp must be '0' or '1'.")
    if (setup == "1") != ("FEN" in headers):
        raise GameParseError("PGN FEN and SetUp '1' headers must be provided together.")
    if headers.get("Result", "*") not in _RESULTS:
        raise GameParseError("Invalid PGN Result header.")

    root = _validated_board(headers.get("FEN", chess.STARTING_FEN))
    board = root.copy()
    game = chess.pgn.Game()
    game.headers.update(headers)
    node: chess.pgn.GameNode = game
    variations: list[tuple[chess.pgn.GameNode, chess.Board, chess.pgn.GameNode]] = []
    variation_root: chess.pgn.GameNode = game
    finished = False
    pending_number = False
    while offset < len(text):
        token = _TOKEN_PATTERN.match(text, offset)
        if token is None:
            raise GameParseError(f"Unknown or malformed PGN movetext at offset {offset}.")
        offset = token.end()
        kind = token.lastgroup
        value = token.group()
        if kind == "space":
            continue
        if kind in ("brace", "line"):
            comment = value[1:-1] if kind == "brace" else value[1:]
            node.comment = " ".join(filter(None, (node.comment, comment.strip())))
            continue
        if finished:
            raise GameParseError("Trailing movetext or multiple games after the PGN result.")
        if kind == "number":
            expected_dots = "." if board.turn == chess.WHITE else "..."
            if pending_number or value != f"{board.fullmove_number}{expected_dots}":
                raise GameParseError("Invalid or misplaced PGN move number.")
            pending_number = True
        elif kind == "variation":
            if pending_number:
                raise GameParseError("PGN move number is not followed by a move.")
            if value == "(":
                if node.parent is None:
                    raise GameParseError("PGN variation has no preceding move.")
                variations.append((node, board, variation_root))
                node = node.parent
                variation_root = node
                board = board.copy()
                board.pop()
            else:
                if not variations or node is variation_root:
                    raise GameParseError("Unbalanced or empty PGN variation.")
                node, board, variation_root = variations.pop()
        elif kind == "result":
            if variations or pending_number:
                raise GameParseError("Misplaced PGN result.")
            if "Result" in headers and headers["Result"] != value:
                raise GameParseError("PGN result does not match the Result header.")
            game.headers["Result"] = value
            finished = True
        elif kind == "nag":
            if node is variation_root or pending_number:
                raise GameParseError("PGN annotation has no preceding move.")
            if value.startswith("$") and int(value[1:]) > 255:
                raise GameParseError("PGN numeric annotation must be between 0 and 255.")
        elif kind == "san":
            if offset < len(text) and not text[offset].isspace() and text[offset] not in "{;()$!?":
                raise GameParseError(f"Malformed PGN move near '{value}'.")
            try:
                move = board.parse_san(value)
            except ValueError as exc:
                raise GameParseError(f"Illegal or unparseable move '{value}': {exc}") from exc
            san = board.san(move)
            normalized = value.replace("0", "O")
            if normalized.rstrip("+#") != san.rstrip("+#"):
                raise GameParseError(f"Illegal or unparseable move '{value}'; expected SAN '{san}'.")
            if normalized.endswith(("+", "#")) and normalized != san:
                raise GameParseError(f"Incorrect check or mate suffix in '{value}'; expected '{san}'.")
            node = node.add_variation(move)
            board.push(move)
            pending_number = False
    if variations:
        raise GameParseError("Unclosed PGN variation.")
    if pending_number:
        raise GameParseError("PGN move number is not followed by a move.")
    return game, root


def parse_game_input(raw_input: str) -> ParsedGame:
    if not raw_input or not raw_input.strip():
        raise GameParseError("Empty game input provided.")

    text = raw_input.strip()
    if _looks_like_fen(text):
        board = _validated_board(text)
        fen_root = board.fen(en_passant="fen")
        exporter = chess.pgn.Game.from_board(board)
        exporter.headers["FEN"] = fen_root
        exporter.headers["SetUp"] = "1"
        return ParsedGame(
            fen_root=fen_root,
            has_full_history=False,
            event="FEN Position",
            warnings=[
                "Input is a standalone FEN position; prior move and threefold-repetition history is unavailable."
            ],
            clean_pgn=str(exporter),
        )

    game, board = _parse_pgn(text)
    fen_root = board.fen(en_passant="fen")
    has_full_history = game.headers.get("SetUp", "0") != "1" and fen_root == chess.STARTING_FEN
    warnings: list[str] = []
    if not has_full_history:
        warnings.append("Game starts from a custom FEN setup; earlier repetition history is unavailable.")

    plies: list[ParsedPly] = []
    untrusted_comments: dict[int, str] = {}
    uci_history: list[str] = []
    if game.comment.strip():
        untrusted_comments[-1] = game.comment.strip()

    for ply_idx, next_node in enumerate(game.mainline()):
        move = next_node.move
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
        if next_node.comment.strip():
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

    if not plies and has_full_history:
        raise GameParseError("No legal moves found in PGN input.")

    clean_game = chess.pgn.Game()
    for key in ("Event", "Site", "Date", "Round", "White", "Black", "Result", "FEN", "SetUp"):
        if key in game.headers:
            clean_game.headers[key] = game.headers[key]
    current: chess.pgn.GameNode = clean_game
    for ply in plies:
        current = current.add_variation(chess.Move.from_uci(ply.uci))

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
