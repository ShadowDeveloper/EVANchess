from __future__ import annotations

from evan.claims.schema import AssertionScope, ClaimRecord, ClaimStatus, MomentClaimLedger
from evan.realizer.schema import RealizedCommentary, RealizedSentence

ABSTENTION_NOTICE = "EVAN abstains: no independently supported coaching explanation is available at this analysis budget."
SCOPE_PREFIXES = {
    AssertionScope.CURRENT_BOARD_ONLY: "On the current board only: ",
    AssertionScope.IN_DISPLAYED_CONTINUATION: "In the displayed continuation only: ",
    AssertionScope.ACROSS_ANALYZED_DEFENSES_AT_BUDGET: "Across the analyzed defenses at this budget only: ",
    AssertionScope.ENGINE_PREFERENCE_AT_BUDGET: "As an engine preference at this analysis budget only: ",
    AssertionScope.HEURISTIC_INTERPRETATION: "As a tentative heuristic interpretation only: ",
    AssertionScope.EXACT_RULES_OR_TABLEBASE: "According to the cited exact rules or tablebase evidence: ",
}


def scoped_proposition(claim: ClaimRecord) -> str:
    qualification = "Qualified evidence: " if claim.status == ClaimStatus.QUALIFY else ""
    return qualification + SCOPE_PREFIXES[claim.assertion_scope] + claim.proposition.strip()


def render_deterministic_template(ledger: MomentClaimLedger) -> RealizedCommentary:
    sentences = [
        RealizedSentence(
            sentence_id=f"sent_{index}",
            text=scoped_proposition(claim),
            claim_ids=[claim.claim_id],
            branch_id=claim.branch_id,
            preview_fen=claim.preview_fen or ledger.root_fen,
            arrows=claim.arrows,
        )
        for index, claim in enumerate(ledger.claims, 1)
        if claim.status != ClaimStatus.ABSTAIN and claim.proposition.strip()
    ]
    return RealizedCommentary(
        sentences=sentences,
        abstention_notice=ABSTENTION_NOTICE if not sentences else None,
        used_fallback=True,
    )
