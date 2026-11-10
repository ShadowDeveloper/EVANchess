from __future__ import annotations

from typing import Any
import chess
from pydantic import BaseModel, Field
from evan.chess_core.state import GameStateIdentity
from evan.engines.stockfish import build_board_with_history
from evan.evidence.detectors import (
    BranchEvidenceTrace,
    PinObservation,
    UndefendedPieceObservation,
    detect_pins,
    detect_undefended_pieces,
    trace_line_events,
)
from evan.pipeline.branch_search import MomentBranchBundle


class MomentEvidenceGraph(BaseModel):
    ply: int
    root_fen: str
    root_state_id: str = ""
    root_state_hash: str = ""
    uci_history: list[str] = Field(default_factory=list)
    root_undefended_white: list[UndefendedPieceObservation] = Field(default_factory=list)
    root_undefended_black: list[UndefendedPieceObservation] = Field(default_factory=list)
    root_pins_white: list[PinObservation] = Field(default_factory=list)
    root_pins_black: list[PinObservation] = Field(default_factory=list)
    branch_traces: dict[str, BranchEvidenceTrace] = Field(default_factory=dict)
    evidence_branch_map: dict[str, str] = Field(default_factory=dict)
    evidence_witness_map: dict[str, dict[str, Any]] = Field(default_factory=dict)


def build_moment_evidence_graph(
    bundle: MomentBranchBundle,
    uci_history: list[str] | None = None,
) -> MomentEvidenceGraph:
    raw_board = chess.Board(bundle.root_fen)
    hist_input = uci_history if uci_history is not None else (bundle.uci_history or None)
    root_board, hist = build_board_with_history(raw_board, hist_input)

    root_state = GameStateIdentity.from_board(
        root_board, uci_history=hist, state_id_prefix=f"st_root_p{bundle.ply}"
    )

    undef_w = detect_undefended_pieces(root_board, chess.WHITE, state_id=root_state.state_id)
    undef_b = detect_undefended_pieces(root_board, chess.BLACK, state_id=root_state.state_id)
    pins_w = detect_pins(root_board, chess.WHITE, state_id=root_state.state_id)
    pins_b = detect_pins(root_board, chess.BLACK, state_id=root_state.state_id)

    traces: dict[str, BranchEvidenceTrace] = {}
    ev_map: dict[str, str] = {}
    witness_map: dict[str, dict[str, Any]] = {}

    for u in undef_w + undef_b:
        ev_map[u.evidence_id] = "root"
        witness_map[u.evidence_id] = u.model_dump()

    for p in pins_w + pins_b:
        ev_map[p.evidence_id] = "root"
        witness_map[p.evidence_id] = p.model_dump()

    for br in bundle.branches:
        pv_uci = br.primary_record.pv_uci or ([br.root_move_uci] if br.root_move_uci else [])
        tr = trace_line_events(
            root_board=root_board,
            branch_id=br.branch_id,
            pv_uci=pv_uci,
            uci_history=hist,
        )
        traces[br.branch_id] = tr
        for ev in tr.events:
            ev_map[ev.evidence_id] = br.branch_id
            witness_map[ev.evidence_id] = ev.model_dump()

        t1_ev_id = br.tier1_record.evidence_id or f"ev_eng_tier1_{br.branch_id}"
        pri_ev_id = br.primary_record.evidence_id or f"ev_eng_primary_{br.branch_id}"
        br.tier1_record.evidence_id = t1_ev_id
        br.primary_record.evidence_id = pri_ev_id

        ev_map[t1_ev_id] = br.branch_id
        witness_map[t1_ev_id] = br.tier1_record.model_dump()
        ev_map[pri_ev_id] = br.branch_id
        witness_map[pri_ev_id] = br.primary_record.model_dump()

    return MomentEvidenceGraph(
        ply=bundle.ply,
        root_fen=root_state.fen,
        root_state_id=root_state.state_id,
        root_state_hash=root_state.state_hash,
        uci_history=hist,
        root_undefended_white=undef_w,
        root_undefended_black=undef_b,
        root_pins_white=pins_w,
        root_pins_black=pins_b,
        branch_traces=traces,
        evidence_branch_map=ev_map,
        evidence_witness_map=witness_map,
    )
