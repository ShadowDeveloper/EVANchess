from __future__ import annotations

from typing import Protocol, runtime_checkable
import chess
from pydantic import BaseModel, Field


class EngineAnalysisRecord(BaseModel):
    """Exact UCI engine analysis record per EVAN proposal §4.2."""

    engine_name: str
    engine_path: str
    threads: int
    hash_mb: int
    hash_policy: str = "reuse_within_game"
    root_fen: str
    root_state_hash: str
    uci_history: list[str] = Field(default_factory=list)
    allowed_root_moves: list[str] | None = None
    multipv_index: int = 1
    node_limit: int
    reported_nodes: int = 0
    depth: int = 0
    seldepth: int = 0
    score_cp_white: int | None = None
    score_cp_mover: int | None = None
    mate_white: int | None = None
    mate_mover: int | None = None
    wdl_white: tuple[int, int, int] | None = None
    pv_uci: list[str] = Field(default_factory=list)
    pv_san: list[str] = Field(default_factory=list)


class PolicyCandidate(BaseModel):
    uci: str
    san: str
    probability: float
    source: str = "maia2"


class TablebaseResult(BaseModel):
    wdl: int  # 2=win, 1=cursed win, 0=draw, -1=blessed loss, -2=loss
    dtz: int | None = None
    is_exact: bool = True


@runtime_checkable
class EngineProtocol(Protocol):
    def analyze_root(
        self,
        board: chess.Board,
        uci_history: list[str] | None = None,
        nodes: int = 25_000,
        multipv: int = 1,
        root_moves: list[str] | None = None,
    ) -> list[EngineAnalysisRecord]: ...

    def close(self) -> None: ...


@runtime_checkable
class HumanPolicyProtocol(Protocol):
    def predict_candidates(
        self,
        board: chess.Board,
        rating_white: int = 1500,
        rating_black: int = 1500,
        top_k: int = 3,
    ) -> list[PolicyCandidate]: ...


@runtime_checkable
class TablebaseProtocol(Protocol):
    def probe_position(self, board: chess.Board) -> TablebaseResult | None: ...
