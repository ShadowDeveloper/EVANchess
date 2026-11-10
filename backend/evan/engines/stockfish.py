from __future__ import annotations

import hashlib
import json
from pathlib import Path
import time
from typing import Any, cast
import chess
import chess.engine
from evan.chess_core.state import GameStateIdentity
from evan.config import resolve_stockfish_path
from evan.engines.protocols import EngineAnalysisRecord, ScoreBound
from evan.storage.repository import EvanRepository


def _compute_file_sha256(path_str: str) -> str:
    try:
        path = Path(path_str)
        if not path.is_file():
            return hashlib.sha256(path_str.encode("utf-8")).hexdigest()
        hasher = hashlib.sha256()
        with path.open("rb") as fh:
            for chunk in iter(lambda: fh.read(65536), b""):
                hasher.update(chunk)
        return hasher.hexdigest()
    except OSError:
        return hashlib.sha256(path_str.encode("utf-8")).hexdigest()


def _compute_options_fingerprint(
    binary_sha256: str,
    engine_name: str,
    uci_options: dict[str, Any],
    network_hash: str | None,
    hash_policy: str,
) -> str:
    payload = json.dumps(
        {
            "binary_sha256": binary_sha256,
            "engine_name": engine_name,
            "uci_options": uci_options,
            "network_hash": network_hash,
            "hash_policy": hash_policy,
        },
        sort_keys=True,
        default=str,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def build_board_with_history(
    board: chess.Board,
    uci_history: list[str] | None,
) -> tuple[chess.Board, list[str]]:
    if not board.is_valid():
        raise ValueError(f"Illegal board position: {board.fen()}")

    stack_ucis = [m.uci() for m in board.move_stack]
    if uci_history is None:
        return board.copy(), stack_ucis

    hist = list(uci_history)
    if stack_ucis:
        if stack_ucis == hist:
            return board.copy(), hist
        raise ValueError("Board move_stack conflicts with provided uci_history.")

    if not hist:
        return board.copy(stack=False), []

    replay = chess.Board()
    for idx, uci_str in enumerate(hist):
        try:
            mv = chess.Move.from_uci(uci_str)
        except ValueError as exc:
            raise ValueError(f"Malformed UCI move '{uci_str}' in uci_history at index {idx}.") from exc
        if mv not in replay.legal_moves:
            raise ValueError(f"Illegal move '{uci_str}' in uci_history at index {idx}.")
        replay.push(mv)

    if replay.fen() == board.fen():
        return replay, hist

    if board.halfmove_clock == 0:
        return board.copy(stack=False), hist

    raise ValueError(
        f"Replayed uci_history reaches '{replay.fen()}', which does not match board '{board.fen()}'."
    )


def validate_root_moves(
    board: chess.Board,
    root_moves: list[str] | None,
) -> list[chess.Move] | None:
    if root_moves is None:
        return None
    if len(root_moves) == 0:
        raise ValueError("root_moves cannot be an empty list.")
    legal_set = set(board.legal_moves)
    move_objs: list[chess.Move] = []
    seen: set[str] = set()
    for uci_str in root_moves:
        try:
            mv = chess.Move.from_uci(uci_str)
        except ValueError as exc:
            raise ValueError(f"Malformed root move UCI '{uci_str}'.") from exc
        if mv not in legal_set:
            raise ValueError(f"Illegal root move '{uci_str}' for board '{board.fen()}'.")
        if mv.uci() not in seen:
            seen.add(mv.uci())
            move_objs.append(mv)
    return move_objs


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
    binary_sha256: str = "",
    options_fingerprint: str = "",
    uci_options: dict[str, Any] | None = None,
    network_hash: str | None = None,
    hash_policy: str = "clear_before_search",
    wall_time_seconds: float | None = None,
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
            score_cp_white = None
            score_cp_mover = None
        else:
            score_cp_white = white_sc.score()
            score_cp_mover = mover_sc.score()
            mate_white = None
            mate_mover = None

    score_bound: ScoreBound = "exact"
    if info.get("upperbound") or (pov_score is not None and getattr(pov_score.relative, "upperbound", False)):
        score_bound = "upperbound"
    elif info.get("lowerbound") or (pov_score is not None and getattr(pov_score.relative, "lowerbound", False)):
        score_bound = "lowerbound"

    wdl_tuple: tuple[int, int, int] | None = None
    pov_wdl = info.get("wdl")
    if pov_wdl is not None:
        w = pov_wdl.white()
        wdl_tuple = (int(w.wins), int(w.draws), int(w.losses))

    raw_pv = info.get("pv", [])
    pv_uci: list[str] = []
    pv_san: list[str] = []
    sim_board = board.copy()
    pv_truncated_illegal = False
    for move in raw_pv:
        if move not in sim_board.legal_moves:
            pv_truncated_illegal = True
            break
        pv_uci.append(move.uci())
        pv_san.append(sim_board.san(move))
        sim_board.push(move)

    has_score = score_cp_mover is not None or mate_mover is not None
    has_pv = len(pv_uci) > 0 or board.is_game_over()
    is_complete = bool(has_score and has_pv and not pv_truncated_illegal)

    mpv_idx = int(info.get("multipv", multipv_index))
    reported_nodes = int(info.get("nodes", 0))
    depth = int(info.get("depth", 0))
    seldepth = int(info.get("seldepth", 0))
    elapsed = (
        float(wall_time_seconds)
        if wall_time_seconds is not None
        else float(info.get("time", 0.0) or 0.0)
    )

    resolved_opts = dict(uci_options) if uci_options is not None else {"Threads": threads, "Hash": hash_mb}
    bin_hash = binary_sha256 or _compute_file_sha256(engine_path)
    opt_fp = options_fingerprint or _compute_options_fingerprint(
        binary_sha256=bin_hash,
        engine_name=engine_name,
        uci_options=resolved_opts,
        network_hash=network_hash,
        hash_policy=hash_policy,
    )
    root_mv_tag = "_".join(sorted(allowed_root_moves)) if allowed_root_moves else "all"
    evidence_id = f"ev_eng_{state_id.state_hash[:10]}_n{node_limit}_mpv{mpv_idx}_{root_mv_tag}"

    return EngineAnalysisRecord(
        evidence_id=evidence_id,
        engine_name=engine_name,
        engine_path=engine_path,
        binary_sha256=bin_hash,
        options_fingerprint=opt_fp,
        uci_options=resolved_opts,
        network_hash=network_hash,
        threads=threads,
        hash_mb=hash_mb,
        hash_policy=hash_policy,
        root_fen=board.fen(),
        root_state_hash=state_id.state_hash,
        uci_history=list(uci_history),
        allowed_root_moves=list(allowed_root_moves) if allowed_root_moves is not None else None,
        multipv_index=mpv_idx,
        node_limit=node_limit,
        reported_nodes=reported_nodes,
        depth=depth,
        seldepth=seldepth,
        wall_time_seconds=round(elapsed, 6),
        score_cp_white=score_cp_white,
        score_cp_mover=score_cp_mover,
        mate_white=mate_white,
        mate_mover=mate_mover,
        score_bound=score_bound,
        is_complete=is_complete,
        wdl_white=wdl_tuple,
        pv_uci=pv_uci,
        pv_san=pv_san,
    )


class StockfishEngine:
    def __init__(
        self,
        stockfish_path: str | None = None,
        threads: int = 1,
        hash_mb: int = 64,
        repository: EvanRepository | None = None,
        clear_hash_before_search: bool = True,
    ) -> None:
        self.engine_path = resolve_stockfish_path(stockfish_path)
        self.threads = threads
        self.hash_mb = hash_mb
        self.repository = repository
        self.clear_hash_before_search = clear_hash_before_search
        self.hash_policy = "clear_before_search" if clear_hash_before_search else "reuse_within_session"
        self.binary_sha256 = _compute_file_sha256(self.engine_path)
        self._engine: chess.engine.SimpleEngine | None = None
        self._engine_name: str = "Stockfish"
        self._uci_options: dict[str, Any] = {
            "Threads": self.threads,
            "Hash": self.hash_mb,
            "UCI_ShowWDL": True,
        }
        self._network_hash: str | None = None
        self._options_fingerprint: str = _compute_options_fingerprint(
            binary_sha256=self.binary_sha256,
            engine_name=self._engine_name,
            uci_options=self._uci_options,
            network_hash=self._network_hash,
            hash_policy=self.hash_policy,
        )

    def _ensure_open(self) -> chess.engine.SimpleEngine:
        if self._engine is None:
            self._engine = chess.engine.SimpleEngine.popen_uci(self.engine_path)
            self._engine_name = self._engine.id.get("name", "Stockfish")
            opts: dict[str, str | int | bool | None] = {}
            if "Threads" in self._engine.options:
                opts["Threads"] = self.threads
            if "Hash" in self._engine.options:
                opts["Hash"] = self.hash_mb
            if "UCI_ShowWDL" in self._engine.options:
                opts["UCI_ShowWDL"] = True
            if opts:
                self._engine.configure(opts)

            recorded_opts: dict[str, Any] = dict(opts)
            net_parts: list[str] = []
            for opt_name in ("EvalFile", "EvalFileSmall"):
                if opt_name in self._engine.options:
                    default_val = getattr(self._engine.options[opt_name], "default", None)
                    recorded_opts[opt_name] = default_val
                    if default_val:
                        net_parts.append(f"{opt_name}={default_val}")
            self._uci_options = recorded_opts
            self._network_hash = ";".join(net_parts) if net_parts else None
            self._options_fingerprint = _compute_options_fingerprint(
                binary_sha256=self.binary_sha256,
                engine_name=self._engine_name,
                uci_options=self._uci_options,
                network_hash=self._network_hash,
                hash_policy=self.hash_policy,
            )
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
                "binary_sha256": self.binary_sha256,
                "options_fingerprint": self._options_fingerprint,
                "threads": self.threads,
                "hash_mb": self.hash_mb,
                "hash_policy": self.hash_policy,
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
        if nodes <= 0:
            raise ValueError("nodes must be positive.")
        if multipv <= 0:
            raise ValueError("multipv must be positive.")

        analysis_board, hist = build_board_with_history(board, uci_history)
        move_objs = validate_root_moves(analysis_board, root_moves)
        normalized_root_moves = [m.uci() for m in move_objs] if move_objs is not None else None

        if analysis_board.is_game_over():
            return []

        eng = self._ensure_open()
        state_id = GameStateIdentity.from_board(analysis_board, uci_history=hist)
        cache_key = self._make_cache_key(
            state_id.state_hash, nodes, multipv, normalized_root_moves
        )

        if self.repository is not None and self.clear_hash_before_search:
            cached = self.repository.get_engine_cache(cache_key)
            if cached and "records" in cached:
                return [EngineAnalysisRecord.model_validate(r) for r in cached["records"]]

        if self.clear_hash_before_search and "Clear Hash" in eng.options:
            eng.configure({"Clear Hash": None})

        limit = chess.engine.Limit(nodes=nodes)
        t0 = time.perf_counter()
        snapshots: dict[int, dict[str, Any]] = {}
        with eng.analysis(analysis_board, limit=limit, multipv=multipv, root_moves=move_objs) as analysis:
            for update in analysis:
                index = int(update.get("multipv", 1))
                snapshot = snapshots.setdefault(index, {})
                if "score" in update:
                    snapshot.pop("lowerbound", None)
                    snapshot.pop("upperbound", None)
                    snapshot.pop("pv", None)
                snapshot.update(update)
        wall_elapsed = time.perf_counter() - t0
        infos = [snapshots[index] for index in sorted(snapshots) if "score" in snapshots[index]]

        records: list[EngineAnalysisRecord] = []
        for idx, info in enumerate(infos, start=1):
            rec = normalize_info_to_record(
                info=cast(chess.engine.InfoDict, info),
                board=analysis_board,
                uci_history=hist,
                engine_name=self._engine_name,
                engine_path=self.engine_path,
                threads=self.threads,
                hash_mb=self.hash_mb,
                node_limit=nodes,
                allowed_root_moves=normalized_root_moves,
                multipv_index=idx,
                binary_sha256=self.binary_sha256,
                options_fingerprint=self._options_fingerprint,
                uci_options=self._uci_options,
                network_hash=self._network_hash,
                hash_policy=self.hash_policy,
                wall_time_seconds=wall_elapsed,
            )
            records.append(rec)

        if (
            self.repository is not None
            and self.clear_hash_before_search
            and records
            and all(r.is_complete and r.score_bound == "exact" for r in records)
        ):
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
