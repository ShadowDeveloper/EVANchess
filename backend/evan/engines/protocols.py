from __future__ import annotations

from typing import Any, Literal, Protocol, runtime_checkable
import chess
from pydantic import BaseModel, Field


ScoreBound = Literal["exact", "upperbound", "lowerbound"]


class EngineAnalysisRecord(BaseModel):
    evidence_id: str = ""
    engine_name: str
    engine_path: str
    binary_sha256: str = ""
    options_fingerprint: str = ""
    uci_options: dict[str, Any] = Field(default_factory=dict)
    network_hash: str | None = None
    threads: int
    hash_mb: int
    hash_policy: str = "clear_before_search"
    root_fen: str
    root_state_hash: str
    uci_history: list[str] = Field(default_factory=list)
    allowed_root_moves: list[str] | None = None
    multipv_index: int = 1
    node_limit: int
    reported_nodes: int = 0
    depth: int = 0
    seldepth: int = 0
    wall_time_seconds: float = 0.0
    score_cp_white: int | None = None
    score_cp_mover: int | None = None
    mate_white: int | None = None
    mate_mover: int | None = None
    score_bound: ScoreBound = "exact"
    is_complete: bool = True
    wdl_white: tuple[int, int, int] | None = None
    pv_uci: list[str] = Field(default_factory=list)
    pv_san: list[str] = Field(default_factory=list)


def is_confident_record(record: EngineAnalysisRecord | None) -> bool:
    if record is None:
        return False
    if not record.is_complete or record.score_bound != "exact":
        return False
    return record.score_cp_mover is not None or record.mate_mover is not None


def _side_sort_value(cp: int | None, mate: int | None) -> int | None:
    if mate is not None:
        if mate > 0:
            return 1_000_000 - mate
        if mate < 0:
            return -1_000_000 - mate
        return -2_000_000
    return cp


def mover_sort_key(record: EngineAnalysisRecord) -> tuple[int, int]:
    val = _side_sort_value(record.score_cp_mover, record.mate_mover)
    if val is None or not is_confident_record(record):
        return (0, -99_999_999 if val is None else val)
    return (1, val)


def white_sort_key(record: EngineAnalysisRecord) -> tuple[int, int]:
    val = _side_sort_value(record.score_cp_white, record.mate_white)
    if val is None or not is_confident_record(record):
        return (0, -99_999_999 if val is None else val)
    return (1, val)


def comparable_mover_cp(record: EngineAnalysisRecord | None) -> int | None:
    if not is_confident_record(record) or record is None:
        return None
    if record.mate_mover is not None:
        if record.mate_mover > 0:
            return max(3000, 10000 - abs(record.mate_mover) * 50)
        if record.mate_mover < 0:
            return min(-3000, -(10000 - abs(record.mate_mover) * 50))
        return -10000
    return record.score_cp_mover


def comparable_white_cp(record: EngineAnalysisRecord | None) -> int | None:
    if not is_confident_record(record) or record is None:
        return None
    if record.mate_white is not None:
        if record.mate_white > 0:
            return max(3000, 10000 - abs(record.mate_white) * 50)
        if record.mate_white < 0:
            return min(-3000, -(10000 - abs(record.mate_white) * 50))
        return -10000 if record.mate_mover == 0 and record.root_fen.split(" ")[1] == "w" else 10000
    return record.score_cp_white


def format_mover_eval(record: EngineAnalysisRecord) -> str:
    if record.mate_mover is not None:
        return f"mate in {record.mate_mover}"
    if record.score_cp_mover is not None:
        return f"{record.score_cp_mover:+} cp"
    return "unscored"


class PolicyCandidate(BaseModel):
    uci: str
    san: str
    probability: float
    source: str = "maia2"


class TablebaseResult(BaseModel):
    wdl: int
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
