from __future__ import annotations

import asyncio
from collections.abc import Callable
from time import perf_counter
from typing import Any

import chess

from evan.audit.prose_checker import ProseAuditPipeline
from evan.chess_core.parser import ParsedGame, parse_game_input
from evan.claims.builder import build_moment_claims
from evan.config import ConfigurationError, EvanSettings
from evan.engines.protocols import EngineProtocol
from evan.engines.stockfish import StockfishEngine
from evan.evidence.challenger import run_challenge_search_for_branch
from evan.evidence.graph import build_moment_evidence_graph
from evan.pipeline.alternatives import select_candidate_moves
from evan.pipeline.branch_search import run_deep_branch_search
from evan.pipeline.coarse import CoarsePlySummary, run_coarse_game_pass
from evan.pipeline.moment_selector import select_critical_moments
from evan.realizer.realizer import ConstrainedRealizer
from evan.storage.repository import EvanRepository


class AnalysisOrchestrator:
    def __init__(
        self,
        settings: EvanSettings,
        repository: EvanRepository,
        engine_factory: Callable[..., EngineProtocol] = StockfishEngine,
        realizer: Any = None,
        auditor: Any = None,
    ) -> None:
        self.settings = settings
        self.repository = repository
        self.engine_factory = engine_factory
        self.realizer = realizer or ConstrainedRealizer(settings)
        self.auditor = auditor or ProseAuditPipeline(settings)
        self.queue: asyncio.Queue[str] = asyncio.Queue(maxsize=20)
        self.worker: asyncio.Task[None] | None = None
        self.changed: dict[str, asyncio.Event] = {}
        self.accepting = True

    def start(self) -> None:
        self.worker = asyncio.create_task(self._worker())

    async def close(self) -> None:
        self.accepting = False
        if self.worker:
            self.worker.cancel()
            try:
                await self.worker
            except asyncio.CancelledError:
                pass

    def notify(self, game_id: str) -> None:
        self.repository.bump_revision(game_id)
        self.changed.setdefault(game_id, asyncio.Event()).set()

    def submit(self, game_id: str) -> None:
        if not self.accepting:
            raise RuntimeError("Analysis worker is shutting down.")
        self.queue.put_nowait(game_id)
        self.notify(game_id)

    def prioritize(self, game_id: str, ply: int) -> bool:
        row = self.repository.get_ply_analysis(game_id, ply)
        if row is None:
            return False
        if row["deep_status"] == "queued":
            self.repository.prioritize_ply(game_id, ply)
            self.notify(game_id)
        return True

    async def _worker(self) -> None:
        while True:
            game_id = await self.queue.get()
            try:
                await self.analyze_game(game_id)
            except asyncio.CancelledError:
                self.repository.record_error(game_id, "Analysis interrupted by server shutdown.")
                self.notify(game_id)
                raise
            except ConfigurationError as exc:
                self.repository.record_error(game_id, str(exc))
                self.notify(game_id)
            except Exception:
                self.repository.record_error(game_id, "Analysis failed. Check engine and LLM configuration, then import again.")
                self.notify(game_id)
            finally:
                self.queue.task_done()

    async def _engine_call(self, function: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
        job = asyncio.create_task(asyncio.to_thread(function, *args, **kwargs))
        try:
            return await asyncio.shield(job)
        except asyncio.CancelledError:
            await job
            raise

    def _budgets(self, profile: str) -> tuple[int, int, int, int]:
        factor = {"quick": 0.25, "standard": 1.0, "deep": 2.0}[profile]
        budgets = [max(1000, int(n * factor)) for n in (
            self.settings.coarse_nodes,
            self.settings.deep_nodes_tier1,
            self.settings.deep_nodes_primary,
            self.settings.challenge_nodes,
        )]
        return budgets[0], budgets[1], budgets[2], budgets[3]

    async def analyze_game(self, game_id: str) -> None:
        game = self.repository.get_game(game_id)
        if game is None:
            return
        self.settings.require_llm_api_key()
        parsed = parse_game_input(game["pgn_text"])
        coarse_nodes, tier1, primary, challenge = self._budgets(game["budget_profile"])
        engine = self.engine_factory(
            stockfish_path=self.settings.stockfish_path,
            threads=self.settings.engine_threads,
            hash_mb=self.settings.engine_hash_mb,
            repository=self.repository,
        )
        try:
            self.repository.update_game_status(game_id, "auto_analyzing")
            self.notify(game_id)
            summaries = await self._engine_call(run_coarse_game_pass, parsed, engine, coarse_nodes)
            moments = select_critical_moments(summaries, self.settings.critical_moments_count, game["player_color"])
            selected = {moment.ply: moment for moment in moments}
            for summary in summaries:
                moment = selected.get(summary.ply)
                self.repository.update_ply_coarse(
                    game_id, summary.ply, summary.eval_before_cp_white, summary.mate_before_white,
                    summary.eval_after_cp_white, summary.mate_after_white, summary.eval_swing_cp_mover,
                    moment.total_score if moment else 0.0, moment.model_dump() if moment else {}, moment is not None,
                )
            critical = list(selected) if parsed.plies else [0]
            self.repository.update_game_status(game_id, "auto_analyzing", critical)
            self.notify(game_id)
            summary_by_ply = {summary.ply: summary for summary in summaries}
            for ply in critical:
                await self._deep(game_id, ply, parsed, engine, summary_by_ply.get(ply), tier1, primary, challenge, game["target_rating"])
            self.repository.update_game_status(game_id, "auto_complete")
            self.notify(game_id)
            await asyncio.sleep(0)
            self.repository.update_game_status(game_id, "full_analyzing")
            self.notify(game_id)
            while True:
                remaining = [row for row in self.repository.list_ply_analyses(game_id) if row["deep_status"] == "queued"]
                if not remaining:
                    break
                row = max(remaining, key=lambda item: (item["priority_boost"], abs(item["eval_swing_cp"]), -item["ply"]))
                ply = row["ply"]
                await self._deep(game_id, ply, parsed, engine, summary_by_ply.get(ply), tier1, primary, challenge, game["target_rating"])
            self.repository.update_game_status(game_id, "full_complete")
            self.notify(game_id)
        finally:
            await self._engine_call(engine.close)

    async def _deep(
        self, game_id: str, ply: int, parsed: ParsedGame, engine: EngineProtocol,
        summary: CoarsePlySummary | None, tier1: int, primary: int, challenge_nodes: int, rating: int,
    ) -> None:
        started = perf_counter()
        self.repository.update_ply_deep_result(game_id, ply, "running")
        self.notify(game_id)
        board = chess.Board(parsed.fen_root)
        history = [item.uci for item in parsed.plies[:ply]]
        for uci in history:
            board.push_uci(uci)
        if board.is_game_over():
            outcome = board.outcome()
            ledger: dict[str, Any] = {"claims": [], "audit_log": [], "root_fen": board.fen(), "exact_outcome": outcome.result() if outcome else None}
            commentary = {"sentences": [], "abstention_notice": "This position is already terminal under the applicable chess rules; no move comparison is available.", "audit_passed": True}
            self.repository.update_ply_deep_result(game_id, ply, "abstained", ledger, commentary)
            self.notify(game_id)
            return
        nominations = summary.multipv_before if summary else await self._engine_call(engine.analyze_root, board, history, tier1, 3)
        played = parsed.plies[ply].uci if parsed.plies else nominations[0].pv_uci[0]
        candidates = select_candidate_moves(board, played, nominations, target_rating=rating)
        bundle = await self._engine_call(run_deep_branch_search, ply, board, history, candidates, engine, tier1, primary)
        graph = build_moment_evidence_graph(bundle, history)
        challenges = {}
        for branch in bundle.branches:
            trace = graph.branch_traces[branch.branch_id]
            if any(event.event_type in {"capture", "double_attack", "mate", "promotion"} for event in trace.events):
                result = await self._engine_call(run_challenge_search_for_branch, board, branch, engine, history, challenge_nodes)
                if result:
                    challenges[branch.branch_id] = result
        ledger_model = build_moment_claims(board.fullmove_number, bundle, graph, challenges)
        commentary_model = await self.realizer.realize(ledger_model, rating_band=rating)
        commentary_model = await self.auditor.verify_or_repair(commentary_model, ledger_model, rating_band=rating)
        ledger = ledger_model.model_dump(mode="json")
        ledger["evidence_graph"] = graph.model_dump(mode="json")
        ledger["branch_bundle"] = bundle.model_dump(mode="json")
        ledger["has_full_history"] = parsed.has_full_history
        ledger["metrics"] = {
            "elapsed_seconds": perf_counter() - started,
            "llm_usage": commentary_model.usage,
            "llm_cost_usd": commentary_model.cost_usd,
            "node_budget_note": "MultiPV records share search node totals; do not sum identical reported_nodes within a search.",
        }
        commentary = commentary_model.model_dump(mode="json")
        status = "abstained" if commentary.get("abstention_notice") else "completed"
        self.repository.update_ply_deep_result(game_id, ply, status, ledger, commentary)
        self.notify(game_id)
