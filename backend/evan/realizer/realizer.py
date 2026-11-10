from __future__ import annotations

from pydantic import ValidationError

from evan.claims.schema import ClaimStatus, MomentClaimLedger
from evan.config import EvanSettings
from evan.realizer.llm_client import LLMClient, LLMGenerationError, parse_generation, record_usage
from evan.realizer.prompts import SYSTEM_PROMPT, realization_prompt
from evan.realizer.schema import RealizedCommentary, RealizedSentence
from evan.realizer.templates import ABSTENTION_NOTICE


def parse_commentary(payload: dict, ledger: MomentClaimLedger) -> RealizedCommentary:
    if set(payload) != {"sentences"}:
        raise ValueError("Generation must contain only sentences")
    commentary = RealizedCommentary.model_validate(payload)
    if not commentary.sentences:
        raise ValueError("Generation omitted all supported claims")
    claims = {claim.claim_id: claim for claim in ledger.claims}
    seen = set()
    for sentence in commentary.sentences:
        if sentence.sentence_id in seen:
            raise ValueError("Duplicate sentence ID")
        seen.add(sentence.sentence_id)
        for claim_id in sentence.claim_ids:
            claim = claims.get(claim_id)
            if claim is None or claim.status == ClaimStatus.ABSTAIN:
                raise ValueError("Unknown or abstaining claim reference")
            if sentence.branch_id != claim.branch_id:
                raise ValueError("Cross-branch claim reference")
    return commentary


class ConstrainedRealizer:
    def __init__(self, settings: EvanSettings):
        self.settings = settings
        self.client = LLMClient(settings)

    async def realize(
        self, ledger: MomentClaimLedger, rating_band: int = 1500
    ) -> RealizedCommentary:
        self.settings.require_llm_api_key()
        result = RealizedCommentary(provider=self.settings.llm_provider, model=self.settings.llm_model)
        if not any(claim.status != ClaimStatus.ABSTAIN and claim.proposition.strip() for claim in ledger.claims):
            result.abstention_notice = ABSTENTION_NOTICE
            result.audit_passed = True
            ledger.audit_log.append({"stage": "realizer", "event": "abstention", "reason": "no_supported_claims"})
            return result
        response = None
        try:
            response = await self.client.generate(SYSTEM_PROMPT, realization_prompt(ledger, rating_band))
            generated = parse_commentary(parse_generation(response), ledger)
            result.sentences = generated.sentences
        except (LLMGenerationError, ValidationError, ValueError) as exc:
            if isinstance(exc, LLMGenerationError) and exc.response is not None:
                response = exc.response
            record_usage(result, response)
            ledger.audit_log.append({
                "stage": "realizer", "event": "generation_failure", "error_type": type(exc).__name__,
                "original_output": response.text if response else None,
            })
            from evan.audit.prose_checker import audited_fallback

            return audited_fallback(ledger, result)
        record_usage(result, response)
        ledger.audit_log.append({"stage": "realizer", "event": "generated", "usage": result.usage, "cost_usd": result.cost_usd})
        return result


__all__ = ["ConstrainedRealizer", "RealizedCommentary", "RealizedSentence"]
