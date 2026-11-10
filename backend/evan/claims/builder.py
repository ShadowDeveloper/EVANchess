from __future__ import annotations

import chess
from evan.claims.schema import (
    AssertionScope,
    ClaimRecord,
    ClaimStatus,
    ClaimType,
    MomentClaimLedger,
)
from evan.engines.protocols import (
    comparable_mover_cp,
    format_mover_eval,
    is_confident_record,
)
from evan.evidence.challenger import ChallengeOutcome
from evan.evidence.detectors import BoardArrow
from evan.evidence.graph import MomentEvidenceGraph
from evan.pipeline.branch_search import MomentBranchBundle


def validate_claim_branch_isolation(
    claim: ClaimRecord,
    evidence_branch_map: dict[str, str],
    allowed_comparison_branches: set[str] | None = None,
) -> bool:
    if claim.status != ClaimStatus.ABSTAIN and not claim.support_evidence_ids:
        return False

    for ev_id in claim.support_evidence_ids:
        if ev_id not in evidence_branch_map:
            return False
        ev_branch = evidence_branch_map[ev_id]
        if ev_branch == claim.branch_id:
            continue
        if ev_branch == "root" and claim.type == ClaimType.STATE_FACT:
            continue
        if (
            claim.type == ClaimType.ENGINE_PREFERENCE
            and allowed_comparison_branches is not None
            and ev_branch in allowed_comparison_branches
        ):
            continue
        return False
    return True


def _validate_and_append_claim(
    claims: list[ClaimRecord],
    claim: ClaimRecord,
    evidence_branch_map: dict[str, str],
    allowed_comparison_branches: set[str] | None = None,
) -> None:
    passed = validate_claim_branch_isolation(
        claim,
        evidence_branch_map,
        allowed_comparison_branches=allowed_comparison_branches,
    )
    claim.validation_results = {
        "branch_isolation_passed": passed,
        "evidence_ids_verified": all(ev_id in evidence_branch_map for ev_id in claim.support_evidence_ids),
        "scope_verified": claim.assertion_scope.value,
    }
    if passed:
        claims.append(claim)


def build_moment_claims(
    move_number: int,
    bundle: MomentBranchBundle,
    graph: MomentEvidenceGraph,
    challenges: dict[str, ChallengeOutcome] | None = None,
) -> MomentClaimLedger:
    challenges = challenges or {}
    claims: list[ClaimRecord] = []

    if not bundle.branches:
        return MomentClaimLedger(
            ply=bundle.ply,
            move_number=move_number,
            turn=bundle.turn,
            played_san="",
            best_san="",
            root_fen=bundle.root_fen,
            root_state_id=graph.root_state_id or "s_root",
            root_state_hash=graph.root_state_hash,
            uci_history=list(graph.uci_history or bundle.uci_history),
            stability_status=bundle.stability_status,
            claims=[],
            branch_pv_san_map={},
            branch_legal_sans_map={},
            branch_fens_map={},
            evidence_branch_map=dict(graph.evidence_branch_map),
            evidence_witness_map=dict(graph.evidence_witness_map),
            challenge_outcomes=[c.model_dump() for c in challenges.values()],
            engine_metadata=[],
        )

    played_br = next(
        (b for b in bundle.branches if b.branch_id == bundle.played_branch_id),
        bundle.branches[0],
    )
    best_br = next(
        (b for b in bundle.branches if b.branch_id == bundle.best_branch_id),
        bundle.branches[0],
    )

    played_trace = graph.branch_traces[played_br.branch_id]
    best_trace = graph.branch_traces[best_br.branch_id]
    root_state_id = (
        graph.root_state_id
        or (played_trace.state_ids[0] if played_trace.state_ids else "s_root")
    )

    mover_label = "White" if bundle.turn == "white" else "Black"
    root_board = chess.Board(bundle.root_fen)

    undef_all = graph.root_undefended_white + graph.root_undefended_black
    for idx, u in enumerate(undef_all[:2], start=1):
        if u.attackers:
            ev_id = u.evidence_id or f"ev_root_undef_{u.color}_{u.square}"
            graph.evidence_branch_map.setdefault(ev_id, "root")
            graph.evidence_witness_map.setdefault(ev_id, u.model_dump())
            prot_note = (
                "because its only geometric defender is pinned to the king"
                if u.protection_status == "pinned_defender_only"
                else "with no legal defenders"
            )
            state_claim = ClaimRecord(
                claim_id=f"clm_p{bundle.ply}_state_{idx}",
                type=ClaimType.STATE_FACT,
                proposition=(
                    f"On the current board before the move, the {u.color} {u.piece_type} on {u.square} "
                    f"is attacked ({', '.join(u.attackers)}) and lacks effective protection ({prot_note})."
                ),
                root_state_id=root_state_id,
                branch_id=played_br.branch_id,
                applicable_state_ids=[root_state_id],
                support_evidence_ids=[ev_id],
                evidence_source="legal_board_computation",
                assertion_scope=AssertionScope.CURRENT_BOARD_ONLY,
                status=ClaimStatus.ASSERT,
                preview_fen=bundle.root_fen,
                arrows=[
                    BoardArrow(orig=att, dest=u.square, brush="yellow")
                    for att in u.attackers[:2]
                ],
            )
            _validate_and_append_claim(claims, state_claim, graph.evidence_branch_map)

    played_eval_str = format_mover_eval(played_br.primary_record)
    best_eval_str = format_mover_eval(best_br.primary_record)
    played_comp = comparable_mover_cp(played_br.primary_record)
    best_comp = comparable_mover_cp(best_br.primary_record)
    nodes_used = best_br.primary_record.node_limit

    p_orig = played_br.root_move_uci[:2]
    p_dest = played_br.root_move_uci[2:4]
    b_orig = best_br.root_move_uci[:2]
    b_dest = best_br.root_move_uci[2:4]

    played_pri_ev = played_br.primary_record.evidence_id or f"ev_eng_primary_{played_br.branch_id}"
    played_t1_ev = played_br.tier1_record.evidence_id or f"ev_eng_tier1_{played_br.branch_id}"
    best_pri_ev = best_br.primary_record.evidence_id or f"ev_eng_primary_{best_br.branch_id}"
    best_t1_ev = best_br.tier1_record.evidence_id or f"ev_eng_tier1_{best_br.branch_id}"

    for ev_k, br_k, rec_k in (
        (played_pri_ev, played_br.branch_id, played_br.primary_record),
        (played_t1_ev, played_br.branch_id, played_br.tier1_record),
        (best_pri_ev, best_br.branch_id, best_br.primary_record),
        (best_t1_ev, best_br.branch_id, best_br.tier1_record),
    ):
        graph.evidence_branch_map.setdefault(ev_k, br_k)
        graph.evidence_witness_map.setdefault(ev_k, rec_k.model_dump())

    comp_branches = {played_br.branch_id, best_br.branch_id}
    both_confident = is_confident_record(played_br.primary_record) and is_confident_record(
        best_br.primary_record
    )

    if not both_confident or bundle.stability_status == "incomplete":
        pref_ev_ids = list(dict.fromkeys([best_pri_ev, played_pri_ev]))
        pref_claim = ClaimRecord(
            claim_id=f"clm_p{bundle.ply}_pref_incomplete",
            type=ClaimType.ENGINE_PREFERENCE,
            proposition=(
                f"Engine search records for {played_br.root_move_san} or {best_br.root_move_san} are incomplete "
                f"or carry non-exact score bounds at the {nodes_used}-node budget, so EVAN abstains from "
                f"asserting a confident evaluation preference."
            ),
            root_state_id=root_state_id,
            branch_id=best_br.branch_id,
            applicable_state_ids=[root_state_id],
            support_evidence_ids=pref_ev_ids,
            evidence_source="stockfish_uci",
            assertion_scope=AssertionScope.ENGINE_PREFERENCE_AT_BUDGET,
            unresolved_questions=[
                "At least one branch search returned an incomplete record or non-exact bound."
            ],
            status=ClaimStatus.ABSTAIN,
            preview_fen=bundle.root_fen,
            arrows=[BoardArrow(orig=b_orig, dest=b_dest, brush="blue")],
        )
        _validate_and_append_claim(
            claims, pref_claim, graph.evidence_branch_map, allowed_comparison_branches=comp_branches
        )
    elif bundle.stability_status == "unstable_reversal":
        pref_ev_ids = list(
            dict.fromkeys([best_t1_ev, best_pri_ev, played_t1_ev, played_pri_ev])
        )
        pref_claim = ClaimRecord(
            claim_id=f"clm_p{bundle.ply}_pref_unstable",
            type=ClaimType.ENGINE_PREFERENCE,
            proposition=(
                f"Search rankings between {played_br.root_move_san} and {best_br.root_move_san} shifted across "
                f"node budgets ({best_br.tier1_record.node_limit} vs {nodes_used} nodes), so engine preference "
                f"is qualified as close and budget-sensitive."
            ),
            root_state_id=root_state_id,
            branch_id=best_br.branch_id,
            applicable_state_ids=[root_state_id],
            support_evidence_ids=pref_ev_ids,
            evidence_source="stockfish_multi_budget_comparison",
            assertion_scope=AssertionScope.ENGINE_PREFERENCE_AT_BUDGET,
            unresolved_questions=["Ranking reverses between tier-1 and primary search budgets."],
            status=ClaimStatus.QUALIFY,
            preview_fen=bundle.root_fen,
            arrows=[
                BoardArrow(orig=p_orig, dest=p_dest, brush="yellow"),
                BoardArrow(orig=b_orig, dest=b_dest, brush="green"),
            ],
        )
        _validate_and_append_claim(
            claims, pref_claim, graph.evidence_branch_map, allowed_comparison_branches=comp_branches
        )
    elif bundle.played_is_best:
        pref_ev_ids = list(dict.fromkeys([played_pri_ev, best_pri_ev]))
        pref_claim = ClaimRecord(
            claim_id=f"clm_p{bundle.ply}_pref_best",
            type=ClaimType.ENGINE_PREFERENCE,
            proposition=(
                f"At the {nodes_used}-node budget, the played move {played_br.root_move_san} matches or is "
                f"within 10 centipawns of Stockfish's top choice ({played_eval_str} for {mover_label})."
            ),
            root_state_id=root_state_id,
            branch_id=played_br.branch_id,
            applicable_state_ids=[root_state_id],
            support_evidence_ids=pref_ev_ids,
            evidence_source="stockfish_uci",
            assertion_scope=AssertionScope.ENGINE_PREFERENCE_AT_BUDGET,
            status=ClaimStatus.ASSERT,
            preview_fen=bundle.root_fen,
            arrows=[BoardArrow(orig=p_orig, dest=p_dest, brush="green")],
        )
        _validate_and_append_claim(
            claims, pref_claim, graph.evidence_branch_map, allowed_comparison_branches=comp_branches
        )
    else:
        pref_ev_ids = list(dict.fromkeys([best_pri_ev, played_pri_ev]))
        pref_claim = ClaimRecord(
            claim_id=f"clm_p{bundle.ply}_pref_contrast",
            type=ClaimType.ENGINE_PREFERENCE,
            proposition=(
                f"At the {nodes_used}-node budget, Stockfish prefers {best_br.root_move_san} "
                f"({best_eval_str} for {mover_label}) over the played move {played_br.root_move_san} "
                f"({played_eval_str}, a {bundle.eval_gap_played_vs_best_cp} cp difference)."
            ),
            root_state_id=root_state_id,
            branch_id=best_br.branch_id,
            applicable_state_ids=[root_state_id],
            support_evidence_ids=pref_ev_ids,
            evidence_source="stockfish_uci",
            assertion_scope=AssertionScope.ENGINE_PREFERENCE_AT_BUDGET,
            status=ClaimStatus.ASSERT,
            preview_fen=bundle.root_fen,
            arrows=[
                BoardArrow(orig=b_orig, dest=b_dest, brush="green"),
                BoardArrow(orig=p_orig, dest=p_dest, brush="red"),
            ],
        )
        _validate_and_append_claim(
            claims, pref_claim, graph.evidence_branch_map, allowed_comparison_branches=comp_branches
        )

    chal_played = challenges.get(played_br.branch_id)
    for ev in played_trace.events[:3]:
        scope = AssertionScope.IN_DISPLAYED_CONTINUATION
        status = ClaimStatus.ASSERT
        chal_ids: list[str] = []
        contradictions: list[str] = []
        scope_prefix = (
            f"In the analyzed continuation after {played_br.root_move_san} "
            f"({' '.join(played_trace.pv_san[:4])})"
        )

        if chal_played is not None and ev.ply_offset >= 2:
            chal_ids.append(chal_played.query_id)
            contradictions = list(chal_played.discovered_contradictions)
            if contradictions:
                status = ClaimStatus.QUALIFY

        claim_type = (
            ClaimType.EXACT_OUTCOME
            if ev.event_type == "mate" and ev.ply_offset == 1
            else (
                ClaimType.MOTIF
                if ev.event_type in ("double_attack", "pin")
                else ClaimType.CONDITIONAL_LINE_EVENT
            )
        )
        if claim_type == ClaimType.EXACT_OUTCOME:
            scope = AssertionScope.EXACT_RULES_OR_TABLEBASE

        candidate_claim = ClaimRecord(
            claim_id=f"clm_{ev.evidence_id}",
            type=claim_type,
            proposition=f"{scope_prefix}, {ev.description}",
            root_state_id=root_state_id,
            branch_id=played_br.branch_id,
            applicable_state_ids=[ev.state_id],
            support_evidence_ids=[ev.evidence_id],
            evidence_source="replay_detector",
            assertion_scope=scope,
            line_event_plies=[ev.ply_offset],
            challenge_queries=chal_ids,
            discovered_contradictions=contradictions,
            status=status,
            preview_fen=ev.fen,
            arrows=ev.arrows,
        )
        _validate_and_append_claim(claims, candidate_claim, graph.evidence_branch_map)

    if best_br.branch_id != played_br.branch_id:
        for ev in best_trace.events[:2]:
            scope_prefix = (
                f"In the alternative continuation after {best_br.root_move_san} "
                f"({' '.join(best_trace.pv_san[:4])})"
            )
            claim_type = (
                ClaimType.EXACT_OUTCOME
                if ev.event_type == "mate" and ev.ply_offset == 1
                else (
                    ClaimType.MOTIF
                    if ev.event_type in ("double_attack", "pin")
                    else ClaimType.CONDITIONAL_LINE_EVENT
                )
            )
            scope = (
                AssertionScope.EXACT_RULES_OR_TABLEBASE
                if claim_type == ClaimType.EXACT_OUTCOME
                else AssertionScope.IN_DISPLAYED_CONTINUATION
            )
            candidate_claim = ClaimRecord(
                claim_id=f"clm_{ev.evidence_id}",
                type=claim_type,
                proposition=f"{scope_prefix}, {ev.description}",
                root_state_id=root_state_id,
                branch_id=best_br.branch_id,
                applicable_state_ids=[ev.state_id],
                support_evidence_ids=[ev.evidence_id],
                evidence_source="replay_detector",
                assertion_scope=scope,
                line_event_plies=[ev.ply_offset],
                status=ClaimStatus.ASSERT,
                preview_fen=ev.fen,
                arrows=ev.arrows,
            )
            _validate_and_append_claim(claims, candidate_claim, graph.evidence_branch_map)

    has_concrete_event = any(
        c.type in (ClaimType.CONDITIONAL_LINE_EVENT, ClaimType.MOTIF, ClaimType.EXACT_OUTCOME, ClaimType.STATE_FACT)
        for c in claims
    )
    if not has_concrete_event:
        abstain_status = (
            ClaimStatus.ABSTAIN
            if (not both_confident or best_comp is None or played_comp is None or abs(best_comp - played_comp) < 40)
            else ClaimStatus.QUALIFY
        )
        abstain_ev_ids = list(dict.fromkeys([best_pri_ev, played_pri_ev]))
        abstain_claim = ClaimRecord(
            claim_id=f"clm_p{bundle.ply}_abstain_reason",
            type=ClaimType.PLAN_INTERPRETATION,
            proposition=(
                f"At this budget Stockfish evaluates {best_br.root_move_san} at {best_eval_str} "
                f"and {played_br.root_move_san} at {played_eval_str}, but current deterministic "
                f"replay detectors do not establish a concrete tactical refutation; EVAN abstains "
                f"from fabricating an unverified strategic causal story."
            ),
            root_state_id=root_state_id,
            branch_id=best_br.branch_id,
            applicable_state_ids=[root_state_id],
            support_evidence_ids=abstain_ev_ids if abstain_status == ClaimStatus.ABSTAIN else [best_pri_ev],
            evidence_source="evan_abstention_policy",
            assertion_scope=AssertionScope.HEURISTIC_INTERPRETATION,
            unresolved_questions=[
                "No immediate capture, check, pin, or double-attack witness separated the lines within the PV window."
            ],
            status=abstain_status,
            preview_fen=bundle.root_fen,
            arrows=[BoardArrow(orig=b_orig, dest=b_dest, brush="blue")],
        )
        _validate_and_append_claim(claims, abstain_claim, graph.evidence_branch_map)

    pv_map = {
        b_id: tr.pv_san for b_id, tr in graph.branch_traces.items()
    }
    legal_map = {
        b_id: tr.legal_sans_in_branch for b_id, tr in graph.branch_traces.items()
    }
    root_sans = {root_board.san(m) for m in root_board.legal_moves}
    for b_id in legal_map:
        legal_map[b_id] = sorted(set(legal_map[b_id]) | root_sans)

    fens_map = {
        b_id: tr.state_fens for b_id, tr in graph.branch_traces.items()
    }

    return MomentClaimLedger(
        ply=bundle.ply,
        move_number=move_number,
        turn=bundle.turn,
        played_san=played_br.root_move_san,
        best_san=best_br.root_move_san,
        root_fen=bundle.root_fen,
        root_state_id=root_state_id,
        root_state_hash=graph.root_state_hash,
        uci_history=list(graph.uci_history or bundle.uci_history),
        stability_status=bundle.stability_status,
        claims=claims,
        branch_pv_san_map=pv_map,
        branch_legal_sans_map=legal_map,
        branch_fens_map=fens_map,
        evidence_branch_map=dict(graph.evidence_branch_map),
        evidence_witness_map=dict(graph.evidence_witness_map),
        challenge_outcomes=[c.model_dump() for c in challenges.values()],
        engine_metadata=[b.primary_record.model_dump() for b in bundle.branches],
    )
