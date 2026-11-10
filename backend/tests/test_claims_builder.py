import chess
from evan.claims.builder import build_moment_claims, validate_claim_branch_isolation
from evan.claims.schema import AssertionScope, ClaimRecord, ClaimStatus, ClaimType
from evan.engines.protocols import EngineAnalysisRecord
from evan.evidence.challenger import ChallengeDefenseLine, ChallengeOutcome
from evan.evidence.graph import build_moment_evidence_graph
from evan.pipeline.branch_search import BranchAnalysis, MomentBranchBundle


def test_cross_branch_evidence_is_rejected():
    claim = ClaimRecord(
        claim_id="clm_1",
        type=ClaimType.CONDITIONAL_LINE_EVENT,
        proposition="In the played line, White wins a rook on a8.",
        root_state_id="state_0",
        branch_id="br_played",
        applicable_state_ids=["state_0"],
        support_evidence_ids=["ev_br_alt_ply3_capture_a8"],
        evidence_source="replay_detector",
        assertion_scope=AssertionScope.IN_DISPLAYED_CONTINUATION,
        line_event_plies=[1, 2, 3],
        status=ClaimStatus.ASSERT,
    )
    evidence_branch_map = {"ev_br_alt_ply3_capture_a8": "br_alt"}
    assert validate_claim_branch_isolation(claim, evidence_branch_map) is False

    unknown_ev_claim = claim.model_copy(update={"support_evidence_ids": ["ev_unknown_id"]})
    assert validate_claim_branch_isolation(unknown_ev_claim, evidence_branch_map) is False

    root_bypass_claim = claim.model_copy(
        update={"branch_id": "root", "support_evidence_ids": ["ev_br_alt_ply3_capture_a8"]}
    )
    assert validate_claim_branch_isolation(root_bypass_claim, evidence_branch_map) is False


def test_build_moment_claims_creates_scoped_contrastive_ledger():
    board = chess.Board("r3kbnr/ppp2ppp/8/3N4/8/8/PPPPPPPP/R1BQKBNR w KQkq - 0 1")
    rec_played = EngineAnalysisRecord(
        engine_name="Stockfish",
        engine_path="sf",
        threads=1,
        hash_mb=16,
        root_fen=board.fen(),
        root_state_hash="h0",
        node_limit=150000,
        score_cp_white=0,
        score_cp_mover=0,
        pv_uci=["d5e3", "e8d8", "g1f3"],
        pv_san=["Ne3", "Kd8", "Nf3"],
    )
    rec_best = EngineAnalysisRecord(
        engine_name="Stockfish",
        engine_path="sf",
        threads=1,
        hash_mb=16,
        root_fen=board.fen(),
        root_state_hash="h0",
        node_limit=150000,
        score_cp_white=520,
        score_cp_mover=520,
        pv_uci=["d5c7", "e8d8", "c7a8"],
        pv_san=["Nxc7+", "Kd8", "Nxa8"],
    )
    bundle = MomentBranchBundle(
        ply=8,
        root_fen=board.fen(),
        turn="white",
        branches=[
            BranchAnalysis(
                branch_id="br_p8_played_d5e3",
                root_move_uci="d5e3",
                root_move_san="Ne3",
                role="played",
                nomination_source="game",
                tier1_record=rec_played,
                primary_record=rec_played,
            ),
            BranchAnalysis(
                branch_id="br_p8_best_d5c7",
                root_move_uci="d5c7",
                root_move_san="Nxc7+",
                role="engine_best",
                nomination_source="multipv_1",
                tier1_record=rec_best,
                primary_record=rec_best,
            ),
        ],
        played_branch_id="br_p8_played_d5e3",
        best_branch_id="br_p8_best_d5c7",
        played_is_best=False,
        eval_gap_played_vs_best_cp=520,
    )
    graph = build_moment_evidence_graph(bundle)
    chal = {
        "br_p8_played_d5e3": ChallengeOutcome(
            query_id="chal_br_p8_played_d5e3",
            branch_id="br_p8_played_d5e3",
            challenged_at_ply_offset=2,
            opponent_punishing_move_san="Kd8",
            defenses_tested=[
                ChallengeDefenseLine(
                    defense_uci="g1f3",
                    defense_san="Nf3",
                    eval_cp_original_mover=-250,
                    pv_san=["Nf3"],
                )
            ],
            refutation_holds_across_top_defenses=True,
            evaluation_only_check=True,
            discovered_contradictions=[],
        )
    }
    ledger = build_moment_claims(move_number=5, bundle=bundle, graph=graph, challenges=chal)
    assert len(ledger.claims) >= 2
    pref_claims = [c for c in ledger.claims if c.type == ClaimType.ENGINE_PREFERENCE]
    assert len(pref_claims) == 1
    assert len(pref_claims[0].support_evidence_ids) >= 2
    for ev_id in pref_claims[0].support_evidence_ids:
        assert ev_id in ledger.evidence_branch_map
        assert ev_id in ledger.evidence_witness_map

    for c in ledger.claims:
        if c.type in (ClaimType.CONDITIONAL_LINE_EVENT, ClaimType.MOTIF):
            assert c.assertion_scope == AssertionScope.IN_DISPLAYED_CONTINUATION
            assert c.assertion_scope != AssertionScope.ACROSS_ANALYZED_DEFENSES_AT_BUDGET

    assert any(
        c.branch_id == "br_p8_best_d5c7" and "Nxc7+" in c.proposition
        for c in ledger.claims
    )
