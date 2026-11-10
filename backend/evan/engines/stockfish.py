from __future__ import annotations

import hashlib
import json
import chess
import chess.engine
from evan.chess_core.state import GameStateIdentity
from evan.config import resolve_stockfish_path
from evan.engines.protocols import EngineAnalysisRecord
from evan.storage.repository import EvanRepository


def normalize_info_to_record(
    info: chess.engine.InfoDict,
    board: chess.Board,
    uci_history: list[str],
    engine_name: str,
    engine_path: str,
    threads: int,
    hash_mb: int,
    node_limit: int,
    allowed_root_moves: list[str] | None = None,
    multipv_index: int = 1,
) -> EngineAnalysisRecord:
    state_id = GameStateIdentity.from_board(board, uci_history=uci_history)

    score_cp_white: int | None = None
    score_cp_mover: int | None = None
    mate_white: int | None = None
    mate_mover: int | None = None

    pov_score = info.get("score")
    if pov_score is not None:
        white_sc = pov_score.white()
        mover_sc = pov_score.relative
        if white_sc.is_mate():
            mate_white = white_sc.mate()
            mate_mover = mover_sc.mate()
            # Provide synthetic centipawn equivalent for sorting/delta math while retaining mate field
            score_cp_white = (10000 - abs(mate_white) * 50) * (1 if (mate_white or 0) > 0 else -1)
            score_cp_mover = (10000 - abs(mate_mover) * 50) * (1 if (mate_mover or 0) > 0 else -1)
        else:
            score_cp_white = white_sc.score()
            score_cp_mover = mover_sc.score()

    wdl_tuple: tuple[int, int, int] | None = None
    pov_wdl = info.get("wdl")
    if pov_wdl is not None:
        w = pov_wdl.white()
        wdl_tuple = (int(w.wins), int(w.draws), int(w.losses))

    raw_pv = info.get("pv", [])
    pv_uci: list[str] = []
    pv_san: list[str] = []
    sim_board = board.copy()
    for move in raw_pv:
        if move not in sim_board.legal_moves:
            break
        pv_uci.append(move.uci())
        pv_san.append(sim_board.san(move))
        sim_board.push(move)

    return EngineAnalysisRecord(
        engine_name=engine_name,
        engine_path=engine_path,
        threads=threads,
        hash_mb=hash_mb,
        root_fen=board.fen(),
        root_state_hash=state_id.state_hash,
        uci_history=list(uci_history),
        allowed_root_moves=allowed_root_moves,
        multipv_index=int(info.get("multipv", multipv_index)),
        node_limit=node_limit,
        reported_nodes=int(info.get("nodes", 0)),
        depth=int(info.get("depth", 0)),
        seldepth=int(info.get("seldepth", 0)),
        score_cp_white=score_cp_white,
        score_cp_mover=score_cp_mover,
        mate_white=mate_white,
        mate_mover=mate_mover,
        wdl_white=wdl_tuple,
        pv_uci=pv_uci,
        pv_san=pv_san,
    )


class StockfishEngine:
    """UCI Stockfish engine wrapper with rule-aware caching and exact EngineAnalysisRecord output."""

    def __init__(
        self,
        stockfish_path: str | None = None,
        threads: int = 1,
        hash_mb: int = 64,
        repository: EvanRepository | None = None,
    ) -> None:
        self.engine_path = resolve_stockfish_path(stockfish_path)
        self.threads = threads
        self.hash_mb = hash_mb
        self.repository = repository
        self._engine: chess.engine.SimpleEngine | None = None
        self._engine_name: str = "Stockfish"

    def _ensure_open(self) -> chess.engine.SimpleEngine:
        if self._engine is None:
            self._engine = chess.engine.SimpleEngine.popen_uci(self.engine_path)
            self._engine_name = self._engine.id.get("name", "Stockfish")
            opts: dict[str, object] = {}
            if "Threads" in self._engine.options:
                opts["Threads"] = self.threads
            if "Hash" in self._engine.options:
                opts["Hash"] = self.hash_mb
            if "UCI_ShowWDL" in self._engine.options:
                opts["UCI_ShowWDL"] = True
            if opts:
                self._engine.configure(opts)
        return self._engine

    def _make_cache_key(
        self,
        state_hash: str,
        nodes: int,
        multipv: int,
        root_moves: list[str] | None,
    ) -> str:
        payload = json.dumps(
            {
                "state_hash": state_hash,
                "engine_path": self.engine_path,
                "threads": self.threads,
                "nodes": nodes,
                "multipv": multipv,
                "root_moves": sorted(root_moves) if root_moves else None,
            },
            sort_keys=True,
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:32]

    def analyze_root(
        self,
        board: chess.Board,
        uci_history: list[str] | None = None,
        nodes: int = 25_000,
        multipv: int = 1,
        root_moves: list[str] | None = None,
    ) -> list[EngineAnalysisRecord]:
        if board.is_game_over():
            return []

        hist = list(uci_history) if uci_history is not None else [m.uci() for m in board.move_stack]
        state_id = GameStateIdentity.from_board(board, uci_history=hist)
        cache_key = self._make_cache_key(state_id.state_hash, nodes, multipv, root_moves)

        if self.repository is not None:
            cached = self.repository.get_engine_cache(cache_key)
            if cached and "records" in cached:
                return [EngineAnalysisRecord.model_validate(r) for r in cached["records"]]

        eng = self._ensure_open()
        limit = chess.engine.Limit(nodes=nodes)
        move_objs = [chess.Move.from_uci(u) for u in root_moves] if root_moves else None

        raw_result = eng.analyse(
            board,
            limit=limit,
            multipv=multipv,
            root_moves=move_objs,
        )
        infos: list[chess.engine.InfoDict] = (
            raw_result if isinstance(raw_result, list) else [raw_result]
        )

        records: list[EngineAnalysisRecord] = []
        for idx, info in enumerate(infos, start=1):
            rec = normalize_info_to_record(
                info=info,
                board=board,
                uci_history=hist,
                engine_name=self._engine_name,
                engine_path=self.engine_path,
                threads=self.threads,
                hash_mb=self.hash_mb,
                node_limit=nodes,
                allowed_root_moves=root_moves,
                multipv_index=idx,
            )
            records.append(rec)

        if self.repository is not None and records:
            self.repository.set_engine_cache(
                cache_key,
                {"records": [r.model_dump() for r in records]},
            )
        return records

    def close(self) -> None:
        if self._engine is not None:
            try:
                self._engine.quit()
            except Exception:
                pass
            self._engine = None
