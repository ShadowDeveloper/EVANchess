from __future__ import annotations

import re
from collections.abc import Mapping

import chess
from pydantic import BaseModel, Field, ValidationError

from evan.claims.schema import AssertionScope, ClaimRecord, ClaimStatus, MomentClaimLedger
from evan.config import EvanSettings
from evan.realizer.llm_client import LLMClient, LLMGenerationError, parse_generation, record_usage
from evan.realizer.prompts import SYSTEM_PROMPT, repair_prompt
from evan.realizer.realizer import parse_commentary
from evan.realizer.schema import RealizedCommentary, RealizedSentence
from evan.realizer.templates import ABSTENTION_NOTICE, render_deterministic_template, scoped_proposition

SAN_PATTERN = re.compile(
    r"(?<![A-Za-z0-9_])(?:O-O(?:-O)?[+#]?|[KQRBN](?:[a-h1-8]{0,2})x?[a-z][0-9](?:=[QRBN])?[+#]?|[a-h]x[a-z][0-9](?:=[QRBN])?[+#]?|[a-h][1-8](?:=[QRBN])?[+#]?)(?![A-Za-z0-9_])"
)
SCOPE_ESCALATION = re.compile(
    r"\b(?:only (?:legal )?move|forc(?:ed|es|ing)|necessarily|against (?:any|every|all) defen[cs]e|"
    r"regardless of (?:the )?(?:reply|defen[cs]e)|proves that|because the engine wants|"
    r"guarantee(?:d|s)?|unstoppable|unavoidable|must win|wins? by force|all (?:legal )?(?:replies|defen[cs]es))\b",
    re.IGNORECASE,
)


class AuditResult(BaseModel):
    passed: bool
    sentence_id: str | None = None
    violation_codes: list[str] = Field(default_factory=list)
    details: list[str] = Field(default_factory=list)


def san_tokens(text: str) -> set[str]:
    tokens = set()
    for match in SAN_PATTERN.finditer(text):
        token = match.group()
        if re.fullmatch(r"[a-h][1-8]", token):
            before = text[:match.start()]
            after = text[match.end():]
            if re.search(r"\b(?:on|at|from|to|square|king|queen|rook|bishop|knight|pawn)\s+$", before, re.IGNORECASE):
                continue
            if re.match(r"\s+(?:square|rook|knight|bishop|pawn|queen|king)\b", after, re.IGNORECASE):
                continue
        tokens.add(token)
    return tokens


def _normalize(text: str) -> str:
    return " ".join(text.split())


def audit_sentence_against_claims(
    sentence: RealizedSentence,
    claims_by_id: dict[str, ClaimRecord],
    branch_legal_sans: Mapping[str, set[str] | list[str]],
) -> AuditResult:
    codes: list[str] = []
    details: list[str] = []

    def violation(code: str, detail: str) -> None:
        if code not in codes:
            codes.append(code)
        details.append(detail)

    claims = []
    if not sentence.claim_ids:
        violation("unknown_claim", "Every sentence requires a claim citation.")
    for claim_id in sentence.claim_ids:
        claim = claims_by_id.get(claim_id)
        if claim is None:
            violation("unknown_claim", f"Unknown claim: {claim_id}")
            continue
        claims.append(claim)
        if claim.status == ClaimStatus.ABSTAIN:
            violation("abstain_claim", f"Abstaining claim: {claim_id}")
        if claim.branch_id != sentence.branch_id:
            violation("branch_transfer", f"Claim {claim_id} belongs to {claim.branch_id}, not {sentence.branch_id}.")
    if any(claim.assertion_scope != AssertionScope.EXACT_RULES_OR_TABLEBASE for claim in claims):
        if SCOPE_ESCALATION.search(sentence.text):
            violation("scope_escalation", "Universal or forcing language exceeds the cited non-exact evidence.")
    allowed_sans = set(branch_legal_sans.get(sentence.branch_id, []))
    for token in sorted(san_tokens(sentence.text)):
        if token not in allowed_sans:
            other_branch = any(token in sans for branch, sans in branch_legal_sans.items() if branch != sentence.branch_id)
            violation("branch_transfer" if other_branch else "illegal_san", f"SAN {token} is not legal in the cited branch states.")
    if claims:
        allowed_texts = {_normalize(scoped_proposition(claim)) for claim in claims}
        if len(claims) != 1 or _normalize(sentence.text) not in allowed_texts:
            violation("unsupported_proposition", "Prose is not a conservative projection of exactly one cited proposition.")
        claim = claims[0]
        if sentence.preview_fen and claim.preview_fen and sentence.preview_fen != claim.preview_fen:
            violation("preview_mismatch", "Preview FEN differs from the cited claim state.")
        if sentence.arrows != claim.arrows:
            violation("arrows_mismatch", "Arrows differ from the cited claim evidence.")
    return AuditResult(passed=not codes, sentence_id=sentence.sentence_id, violation_codes=codes, details=details)


def branch_legal_sans(ledger: MomentClaimLedger) -> dict[str, set[str]]:
    result: dict[str, set[str]] = {}
    branches = set(ledger.branch_legal_sans_map) | set(ledger.branch_fens_map) | {c.branch_id for c in ledger.claims}
    for branch in branches:
        fens = ledger.branch_fens_map.get(branch, [])
        if fens:
            sans: set[str] = set()
            for fen in [ledger.root_fen, *fens]:
                try:
                    board = chess.Board(fen)
                    if not board.is_valid():
                        continue
                    sans.update(board.san(move) for move in board.legal_moves)
                except ValueError:
                    continue
            result[branch] = sans
        else:
            result[branch] = set(ledger.branch_legal_sans_map.get(branch, []))
            try:
                board = chess.Board(ledger.root_fen)
                if board.is_valid():
                    result[branch].update(board.san(move) for move in board.legal_moves)
            except ValueError:
                pass
    return result


def audit_realized_commentary(
    commentary: RealizedCommentary, ledger: MomentClaimLedger
) -> AuditResult:
    claims = {claim.claim_id: claim for claim in ledger.claims}
    legal = branch_legal_sans(ledger)
    codes: list[str] = []
    details: list[str] = []
    seen = set()
    for sentence in commentary.sentences:
        result = audit_sentence_against_claims(sentence, claims, legal)
        codes.extend(result.violation_codes)
        details.extend(f"{sentence.sentence_id}: {detail}" for detail in result.details)
        if sentence.sentence_id in seen:
            codes.append("duplicate_sentence_id")
        seen.add(sentence.sentence_id)
        cited = [claims[cid] for cid in sentence.claim_ids if cid in claims]
        if cited:
            expected_fen = cited[0].preview_fen or ledger.root_fen
            if sentence.preview_fen != expected_fen:
                codes.append("preview_mismatch")
                details.append(f"{sentence.sentence_id}: Missing or incorrect preview FEN.")
            try:
                board = chess.Board(sentence.preview_fen)
                if not board.is_valid():
                    raise ValueError("Invalid board")
            except ValueError:
                codes.append("invalid_preview_fen")
                details.append(f"{sentence.sentence_id}: Preview FEN is not a legal board state.")
    if commentary.abstention_notice not in (None, ABSTENTION_NOTICE):
        codes.append("unsupported_notice")
        details.append("Abstention notices must use the fixed non-propositional notice.")
    if not commentary.sentences and commentary.abstention_notice != ABSTENTION_NOTICE:
        codes.append("missing_abstention")
    if len(claims) != len(ledger.claims):
        codes.append("duplicate_claim_id")
    return AuditResult(passed=not codes, violation_codes=list(dict.fromkeys(codes)), details=details)


def audited_fallback(
    ledger: MomentClaimLedger, previous: RealizedCommentary
) -> RealizedCommentary:
    fallback = render_deterministic_template(ledger)
    fallback.provider = previous.provider
    fallback.model = previous.model
    fallback.usage = previous.usage
    fallback.cost_usd = previous.cost_usd
    result = audit_realized_commentary(fallback, ledger)
    if not result.passed:
        ledger.audit_log.append({"stage": "audit", "event": "fallback_rejected", "report": result.model_dump()})
        retained = []
        for sentence in fallback.sentences:
            candidate = fallback.model_copy(update={"sentences": [sentence]})
            if audit_realized_commentary(candidate, ledger).passed:
                retained.append(sentence)
        fallback.sentences = retained
        fallback.abstention_notice = ABSTENTION_NOTICE
        result = audit_realized_commentary(fallback, ledger)
        if not result.passed:
            fallback.sentences = []
            result = audit_realized_commentary(fallback, ledger)
            if not result.passed:
                raise ValueError("Ledger cannot support an audited fallback")
    fallback.audit_passed = result.passed
    ledger.audit_log.append({
        "stage": "audit", "event": "deterministic_fallback", "report": result.model_dump(),
        "sentence_ids": [sentence.sentence_id for sentence in fallback.sentences],
        "usage": fallback.usage, "cost_usd": fallback.cost_usd,
    })
    return fallback


class ProseAuditPipeline:
    def __init__(self, settings: EvanSettings):
        self.settings = settings
        self.client = LLMClient(settings)

    async def verify_or_repair(
        self, commentary: RealizedCommentary, ledger: MomentClaimLedger, rating_band: int = 1500
    ) -> RealizedCommentary:
        self.settings.require_llm_api_key()
        result = audit_realized_commentary(commentary, ledger)
        ledger.audit_log.append({"stage": "audit", "event": "initial_audit", "report": result.model_dump()})
        if result.passed:
            commentary.audit_passed = True
            return commentary
        ledger.audit_log.append({
            "stage": "audit", "event": "repair_requested", "original": commentary.model_dump(mode="json"),
            "report": result.model_dump(),
        })
        response = None
        try:
            response = await self.client.generate(SYSTEM_PROMPT, repair_prompt(
                ledger, commentary.model_dump(mode="json"), [result.model_dump()], rating_band,
            ))
            repaired = parse_commentary(parse_generation(response), ledger)
        except (LLMGenerationError, ValidationError, ValueError) as exc:
            if isinstance(exc, LLMGenerationError) and exc.response is not None:
                response = exc.response
            record_usage(commentary, response)
            ledger.audit_log.append({"stage": "audit", "event": "repair_failure", "error_type": type(exc).__name__})
            return audited_fallback(ledger, commentary)
        record_usage(commentary, response)
        repaired.provider = commentary.provider or self.settings.llm_provider
        repaired.model = commentary.model or self.settings.llm_model
        repaired.usage = commentary.usage
        repaired.cost_usd = commentary.cost_usd
        result = audit_realized_commentary(repaired, ledger)
        ledger.audit_log.append({"stage": "audit", "event": "repair_audit", "report": result.model_dump()})
        if result.passed:
            repaired.audit_passed = True
            return repaired
        return audited_fallback(ledger, repaired)
