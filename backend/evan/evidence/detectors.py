from __future__ import annotations

import chess
from pydantic import BaseModel, Field
from evan.chess_core.state import GameStateIdentity
from evan.engines.stockfish import build_board_with_history


PIECE_VALUES_CP = {
    chess.PAWN: 100,
    chess.KNIGHT: 300,
    chess.BISHOP: 300,
    chess.ROOK: 500,
    chess.QUEEN: 900,
    chess.KING: 0,
}

PIECE_NAMES = {
    chess.PAWN: "pawn",
    chess.KNIGHT: "knight",
    chess.BISHOP: "bishop",
    chess.ROOK: "rook",
    chess.QUEEN: "queen",
    chess.KING: "king",
}


class BoardArrow(BaseModel):
    orig: str
    dest: str
    brush: str = "green"


class UndefendedPieceObservation(BaseModel):
    evidence_id: str = ""
    state_id: str = ""
    square: str
    piece_type: str
    color: str
    protection_status: str
    attackers: list[str] = Field(default_factory=list)
    geometric_defenders: list[str] = Field(default_factory=list)
    effective_defenders: list[str] = Field(default_factory=list)


class PinObservation(BaseModel):
    evidence_id: str = ""
    state_id: str = ""
    pinned_square: str
    pinned_piece: str
    pinned_color: str
    pinner_square: str
    pinner_piece: str
    pin_type: str
    shielded_square: str


class DoubleAttackObservation(BaseModel):
    attacker_square: str
    attacker_piece: str
    attacker_color: str
    targets: list[str] = Field(default_factory=list)
    target_pieces: list[str] = Field(default_factory=list)


class LineEvent(BaseModel):
    evidence_id: str
    branch_id: str
    ply_offset: int
    state_id: str
    fen: str
    move_uci: str
    move_san: str
    mover_color: str
    event_type: str
    description: str
    squares: list[str] = Field(default_factory=list)
    arrows: list[BoardArrow] = Field(default_factory=list)
    material_delta_mover_cp: int = 0


class BranchEvidenceTrace(BaseModel):
    branch_id: str
    root_fen: str
    root_state_id: str = ""
    root_state_hash: str = ""
    uci_history: list[str] = Field(default_factory=list)
    root_move_uci: str
    root_move_san: str
    pv_uci: list[str] = Field(default_factory=list)
    pv_san: list[str] = Field(default_factory=list)
    state_fens: list[str] = Field(default_factory=list)
    state_ids: list[str] = Field(default_factory=list)
    state_hashes: list[str] = Field(default_factory=list)
    legal_sans_in_branch: list[str] = Field(default_factory=list)
    net_material_delta_mover: int = 0
    events: list[LineEvent] = Field(default_factory=list)


def compute_material_cp(board: chess.Board, color: chess.Color) -> int:
    total = 0
    for pt, val in PIECE_VALUES_CP.items():
        if pt == chess.KING:
            continue
        total += len(board.pieces(pt, color)) * val
    return total


def detect_undefended_pieces(
    board: chess.Board,
    color: chess.Color,
    state_id: str = "",
) -> list[UndefendedPieceObservation]:
    results: list[UndefendedPieceObservation] = []
    enemy_color = not color
    color_name = "white" if color == chess.WHITE else "black"

    for sq in chess.SQUARES:
        piece = board.piece_at(sq)
        if piece is None or piece.color != color or piece.piece_type == chess.KING:
            continue

        geom_defenders_sq = list(board.attackers(color, sq))
        effective_defenders: list[str] = []
        for def_sq in geom_defenders_sq:
            if board.is_pinned(color, def_sq):
                pin_mask = board.pin(color, def_sq)
                if not (pin_mask & chess.BB_SQUARES[sq]):
                    continue
            effective_defenders.append(chess.square_name(def_sq))

        if len(effective_defenders) == 0:
            status = (
                "pinned_defender_only"
                if len(geom_defenders_sq) > 0
                else "completely_undefended"
            )
            enemy_attackers = [
                chess.square_name(a) for a in board.attackers(enemy_color, sq)
            ]
            sq_name = chess.square_name(sq)
            results.append(
                UndefendedPieceObservation(
                    evidence_id=f"ev_root_undef_{color_name}_{sq_name}",
                    state_id=state_id,
                    square=sq_name,
                    piece_type=PIECE_NAMES[piece.piece_type],
                    color=color_name,
                    protection_status=status,
                    attackers=enemy_attackers,
                    geometric_defenders=[chess.square_name(d) for d in geom_defenders_sq],
                    effective_defenders=[],
                )
            )
    return results


def detect_pins(
    board: chess.Board,
    pinned_color: chess.Color,
    state_id: str = "",
) -> list[PinObservation]:
    pins: list[PinObservation] = []
    king_sq = board.king(pinned_color)
    if king_sq is None:
        return pins

    enemy_color = not pinned_color
    color_name = "white" if pinned_color == chess.WHITE else "black"

    for sq in chess.SQUARES:
        piece = board.piece_at(sq)
        if piece is None or piece.color != pinned_color or piece.piece_type == chess.KING:
            continue
        if board.is_pinned(pinned_color, sq):
            pin_mask = board.pin(pinned_color, sq)
            pinner_sq_name = ""
            pinner_piece_name = "slider"
            for cand_sq in chess.SquareSet(pin_mask):
                cand_piece = board.piece_at(cand_sq)
                if cand_piece and cand_piece.color == enemy_color and cand_piece.piece_type in (
                    chess.BISHOP,
                    chess.ROOK,
                    chess.QUEEN,
                ):
                    if sq in chess.SquareSet(chess.between(king_sq, cand_sq)):
                        pinner_sq_name = chess.square_name(cand_sq)
                        pinner_piece_name = PIECE_NAMES[cand_piece.piece_type]
                        break
            sq_name = chess.square_name(sq)
            pins.append(
                PinObservation(
                    evidence_id=f"ev_root_pin_{color_name}_{sq_name}",
                    state_id=state_id,
                    pinned_square=sq_name,
                    pinned_piece=PIECE_NAMES[piece.piece_type],
                    pinned_color=color_name,
                    pinner_square=pinner_sq_name,
                    pinner_piece=pinner_piece_name,
                    pin_type="absolute_to_king",
                    shielded_square=chess.square_name(king_sq),
                )
            )
    return pins


def detect_double_attacks(
    board: chess.Board,
    attacker_sq: chess.Square,
) -> DoubleAttackObservation | None:
    attacker = board.piece_at(attacker_sq)
    if attacker is None:
        return None
    attacker_color = attacker.color
    enemy_color = not attacker_color
    attacker_val = PIECE_VALUES_CP[attacker.piece_type]

    attacked_squares = board.attacks(attacker_sq)
    if board.is_pinned(attacker_color, attacker_sq):
        attacked_squares &= board.pin(attacker_color, attacker_sq)
    undefended_enemy = {
        u.square for u in detect_undefended_pieces(board, enemy_color)
    }

    valuable_targets: list[tuple[str, str]] = []
    for t_sq in attacked_squares:
        target_piece = board.piece_at(t_sq)
        if target_piece is None or target_piece.color != enemy_color:
            continue
        sq_name = chess.square_name(t_sq)
        t_val = PIECE_VALUES_CP[target_piece.piece_type]
        is_king = target_piece.piece_type == chess.KING
        is_higher_value = t_val > attacker_val
        is_undefended_non_pawn = (
            sq_name in undefended_enemy and target_piece.piece_type != chess.PAWN
        )
        if is_king or is_higher_value or is_undefended_non_pawn:
            valuable_targets.append((sq_name, PIECE_NAMES[target_piece.piece_type]))

    if len(valuable_targets) >= 2:
        return DoubleAttackObservation(
            attacker_square=chess.square_name(attacker_sq),
            attacker_piece=PIECE_NAMES[attacker.piece_type],
            attacker_color="white" if attacker_color == chess.WHITE else "black",
            targets=[t[0] for t in valuable_targets],
            target_pieces=[f"{t[1]} on {t[0]}" for t in valuable_targets],
        )
    return None


def trace_line_events(
    root_board: chess.Board,
    branch_id: str,
    pv_uci: list[str],
    uci_history: list[str] | None = None,
) -> BranchEvidenceTrace:
    board, hist = build_board_with_history(root_board, uci_history)
    root_mover = board.turn
    enemy_root = not root_mover
    initial_diff = compute_material_cp(board, root_mover) - compute_material_cp(board, enemy_root)

    root_state = GameStateIdentity.from_board(
        board, uci_history=hist, state_id_prefix=f"st_{branch_id}_0"
    )

    state_fens: list[str] = [board.fen()]
    state_ids: list[str] = [root_state.state_id]
    state_hashes: list[str] = [root_state.state_hash]
    replayed_uci: list[str] = []
    pv_san: list[str] = []
    legal_sans_set: set[str] = {board.san(m) for m in board.legal_moves}
    events: list[LineEvent] = []

    for offset, uci_str in enumerate(pv_uci[:8], start=1):
        try:
            move = chess.Move.from_uci(uci_str)
        except ValueError as exc:
            raise ValueError(
                f"Malformed UCI move '{uci_str}' in PV for branch '{branch_id}' at ply_offset {offset}."
            ) from exc
        if move not in board.legal_moves:
            raise ValueError(
                f"Illegal PV move '{uci_str}' for branch '{branch_id}' at ply_offset {offset} on board '{board.fen()}'."
            )

        mover_color = board.turn
        mover_name = "White" if mover_color == chess.WHITE else "Black"
        san_str = board.san(move)
        replayed_uci.append(uci_str)
        pv_san.append(san_str)
        legal_sans_set.add(san_str)

        is_cap = board.is_capture(move)
        captured_piece = (
            board.piece_at(move.to_square)
            if not board.is_en_passant(move)
            else chess.Piece(chess.PAWN, not mover_color)
        )
        orig_sq = chess.square_name(move.from_square)
        dest_sq = chess.square_name(move.to_square)

        board.push(move)
        hist.append(uci_str)
        legal_sans_set.update(board.san(m) for m in board.legal_moves)

        st_after = GameStateIdentity.from_board(
            board, uci_history=hist, state_id_prefix=f"st_{branch_id}_{offset}"
        )
        state_fens.append(board.fen())
        state_ids.append(st_after.state_id)
        state_hashes.append(st_after.state_hash)

        cur_diff = compute_material_cp(board, root_mover) - compute_material_cp(board, enemy_root)
        mat_delta = cur_diff - initial_diff

        if board.is_checkmate():
            events.append(
                LineEvent(
                    evidence_id=f"ev_{branch_id}_ply{offset}_mate_{uci_str}",
                    branch_id=branch_id,
                    ply_offset=offset,
                    state_id=st_after.state_id,
                    fen=board.fen(),
                    move_uci=uci_str,
                    move_san=san_str,
                    mover_color=mover_name.lower(),
                    event_type="mate",
                    description=f"{mover_name} delivers checkmate with {san_str} on {dest_sq}.",
                    squares=[orig_sq, dest_sq],
                    arrows=[BoardArrow(orig=orig_sq, dest=dest_sq, brush="red")],
                    material_delta_mover_cp=mat_delta,
                )
            )
            if offset < len(pv_uci[:8]):
                raise ValueError(
                    f"PV for branch '{branch_id}' contains extra moves after checkmate at ply_offset {offset}."
                )
            break

        if is_cap and captured_piece is not None:
            cap_name = PIECE_NAMES[captured_piece.piece_type]
            events.append(
                LineEvent(
                    evidence_id=f"ev_{branch_id}_ply{offset}_capture_{uci_str}",
                    branch_id=branch_id,
                    ply_offset=offset,
                    state_id=st_after.state_id,
                    fen=board.fen(),
                    move_uci=uci_str,
                    move_san=san_str,
                    mover_color=mover_name.lower(),
                    event_type="capture",
                    description=f"{mover_name} captures the {cap_name} on {dest_sq} with {san_str}.",
                    squares=[orig_sq, dest_sq],
                    arrows=[BoardArrow(orig=orig_sq, dest=dest_sq, brush="yellow")],
                    material_delta_mover_cp=mat_delta,
                )
            )

        if move.promotion is not None:
            promo_name = PIECE_NAMES[move.promotion]
            events.append(
                LineEvent(
                    evidence_id=f"ev_{branch_id}_ply{offset}_promo_{uci_str}",
                    branch_id=branch_id,
                    ply_offset=offset,
                    state_id=st_after.state_id,
                    fen=board.fen(),
                    move_uci=uci_str,
                    move_san=san_str,
                    mover_color=mover_name.lower(),
                    event_type="promotion",
                    description=f"{mover_name} promotes to a {promo_name} on {dest_sq} ({san_str}).",
                    squares=[orig_sq, dest_sq],
                    arrows=[BoardArrow(orig=orig_sq, dest=dest_sq, brush="green")],
                    material_delta_mover_cp=mat_delta,
                )
            )

        dbl = detect_double_attacks(board, move.to_square)
        if dbl is not None:
            arrows = [BoardArrow(orig=orig_sq, dest=dest_sq, brush="green")] + [
                BoardArrow(orig=dest_sq, dest=t, brush="red") for t in dbl.targets
            ]
            targets_str = " and ".join(dbl.target_pieces)
            events.append(
                LineEvent(
                    evidence_id=f"ev_{branch_id}_ply{offset}_double_attack_{uci_str}",
                    branch_id=branch_id,
                    ply_offset=offset,
                    state_id=st_after.state_id,
                    fen=board.fen(),
                    move_uci=uci_str,
                    move_san=san_str,
                    mover_color=mover_name.lower(),
                    event_type="double_attack",
                    description=f"{san_str} creates a double attack from {dest_sq} against {targets_str}.",
                    squares=[dest_sq] + dbl.targets,
                    arrows=arrows,
                    material_delta_mover_cp=mat_delta,
                )
            )

        if board.is_check():
            king_sq = board.king(board.turn)
            k_name = chess.square_name(king_sq) if king_sq is not None else dest_sq
            events.append(
                LineEvent(
                    evidence_id=f"ev_{branch_id}_ply{offset}_check_{uci_str}",
                    branch_id=branch_id,
                    ply_offset=offset,
                    state_id=st_after.state_id,
                    fen=board.fen(),
                    move_uci=uci_str,
                    move_san=san_str,
                    mover_color=mover_name.lower(),
                    event_type="check",
                    description=f"{mover_name} plays {san_str}, checking the king on {k_name}.",
                    squares=[dest_sq, k_name],
                    arrows=[BoardArrow(orig=dest_sq, dest=k_name, brush="blue")],
                    material_delta_mover_cp=mat_delta,
                )
            )

        pins = detect_pins(board, board.turn, state_id=st_after.state_id)
        if pins and offset <= 2:
            p0 = pins[0]
            events.append(
                LineEvent(
                    evidence_id=f"ev_{branch_id}_ply{offset}_pin_{p0.pinned_square}",
                    branch_id=branch_id,
                    ply_offset=offset,
                    state_id=st_after.state_id,
                    fen=board.fen(),
                    move_uci=uci_str,
                    move_san=san_str,
                    mover_color=mover_name.lower(),
                    event_type="pin",
                    description=f"The {p0.pinned_color} {p0.pinned_piece} on {p0.pinned_square} is pinned to the king on {p0.shielded_square}.",
                    squares=[p0.pinned_square, p0.shielded_square],
                    arrows=(
                        [BoardArrow(orig=p0.pinner_square, dest=p0.shielded_square, brush="blue")]
                        if p0.pinner_square
                        else []
                    ),
                    material_delta_mover_cp=mat_delta,
                )
            )

    final_diff = compute_material_cp(board, root_mover) - compute_material_cp(board, enemy_root)
    net_delta = final_diff - initial_diff

    return BranchEvidenceTrace(
        branch_id=branch_id,
        root_fen=root_state.fen,
        root_state_id=root_state.state_id,
        root_state_hash=root_state.state_hash,
        uci_history=list(uci_history) if uci_history is not None else [m.uci() for m in root_board.move_stack],
        root_move_uci=replayed_uci[0] if replayed_uci else "",
        root_move_san=pv_san[0] if pv_san else "",
        pv_uci=replayed_uci,
        pv_san=pv_san,
        state_fens=state_fens,
        state_ids=state_ids,
        state_hashes=state_hashes,
        legal_sans_in_branch=sorted(legal_sans_set),
        net_material_delta_mover=net_delta,
        events=events,
    )
