import json

import chess
import httpx
import pytest

from evan.audit.prose_checker import (
    ProseAuditPipeline,
    audit_realized_commentary,
    audit_sentence_against_claims,
    san_tokens,
)
from evan.claims.schema import AssertionScope, ClaimRecord, ClaimStatus, ClaimType, MomentClaimLedger
from evan.config import ConfigurationError, EvanSettings
from evan.evidence.detectors import BoardArrow
from evan.realizer.llm_client import LLMClient, LLMGenerationError, LLMResponse
from evan.realizer.realizer import ConstrainedRealizer, RealizedCommentary
from evan.realizer.templates import ABSTENTION_NOTICE, render_deterministic_template


@pytest.mark.parametrize("status", [401, 403])
async def test_provider_rejected_key_never_becomes_template_success(settings, status):
    transport = httpx.MockTransport(lambda request: httpx.Response(status, json={"error": "access denied"}))
    async with httpx.AsyncClient(transport=transport) as client:
        with pytest.raises(ConfigurationError, match="rejected authentication"):
            await LLMClient(settings, client).generate("system", "prompt")


@pytest.fixture
def settings():
    return EvanSettings(llm_provider="openrouter", openrouter_api_key="test-key")


@pytest.fixture
def ledger():
    board = chess.Board()
    root = board.fen()
    board.push_san("e4")
    return MomentClaimLedger(
        ply=1, move_number=1, turn="white", played_san="e4", best_san="e4",
        root_fen=root, stability_status="stable",
        claims=[ClaimRecord(
            claim_id="c1", type=ClaimType.CONDITIONAL_LINE_EVENT,
            proposition="After e4 e5 in the analyzed continuation, White advances a pawn.",
            root_state_id="s0", branch_id="played", applicable_state_ids=["s0", "s1"],
            support_evidence_ids=["ev1"], evidence_source="replay_detector",
            assertion_scope=AssertionScope.IN_DISPLAYED_CONTINUATION,
            preview_fen=root, arrows=[BoardArrow(orig="e2", dest="e4", brush="green")],
        )],
        branch_fens_map={"played": [root, board.fen()]},
        branch_legal_sans_map={"played": ["e4", "e5"]},
        branch_pv_san_map={"played": ["e4", "e5"]},
    )


def payload_for(ledger):
    return {"sentences": [s.model_dump(mode="json") for s in render_deterministic_template(ledger).sentences]}


def install_generator(target, monkeypatch, outputs):
    calls = []

    async def generate(system, prompt):
        calls.append((system, json.loads(prompt)))
        output = outputs[min(len(calls) - 1, len(outputs) - 1)]
        if isinstance(output, Exception):
            raise output
        return output

    monkeypatch.setattr(target.client, "generate", generate)
    return calls


@pytest.mark.asyncio
async def test_realizer_generates_cited_json_and_records_actual_usage(settings, ledger, monkeypatch):
    realizer = ConstrainedRealizer(settings)
    calls = install_generator(realizer, monkeypatch, [LLMResponse(
        json.dumps(payload_for(ledger)), {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15, "cost": .001}, .001,
    )])
    result = await realizer.realize(ledger, rating_band=1200)
    assert len(calls) == 1
    assert calls[0][1]["rating_band"] == 1200
    assert result.sentences[0].claim_ids == ["c1"]
    assert result.usage["total_tokens"] == 15
    assert result.cost_usd == .001
    assert not result.used_fallback
    assert audit_realized_commentary(result, ledger).passed


@pytest.mark.parametrize("claim_id,status", [("unknown", ClaimStatus.ASSERT), ("c1", ClaimStatus.ABSTAIN)])
@pytest.mark.asyncio
async def test_realizer_never_returns_unknown_or_abstain_references(settings, ledger, monkeypatch, claim_id, status):
    candidate = payload_for(ledger)
    candidate["sentences"][0]["claim_ids"] = [claim_id]
    ledger.claims[0].status = status
    if status == ClaimStatus.ABSTAIN:
        ledger.claims.append(ledger.claims[0].model_copy(update={"claim_id": "c2", "status": ClaimStatus.ASSERT}))
    realizer = ConstrainedRealizer(settings)
    install_generator(realizer, monkeypatch, [LLMResponse(json.dumps(candidate))])
    result = await realizer.realize(ledger)
    assert result.used_fallback and result.audit_passed
    assert all(cid in {c.claim_id for c in ledger.claims if c.status != ClaimStatus.ABSTAIN} for s in result.sentences for cid in s.claim_ids)
    assert any(entry["event"] == "generation_failure" for entry in ledger.audit_log)


@pytest.mark.asyncio
async def test_all_abstain_no_provider_generation(settings, ledger, monkeypatch):
    ledger.claims[0].status = ClaimStatus.ABSTAIN
    realizer = ConstrainedRealizer(settings)
    calls = install_generator(realizer, monkeypatch, [AssertionError("Must not call")])
    result = await realizer.realize(ledger)
    assert not calls
    assert result.sentences == []
    assert result.abstention_notice == ABSTENTION_NOTICE
    assert result.audit_passed


@pytest.mark.parametrize("provider,key_field", [
    ("openrouter", "openrouter_api_key"), ("openai", "openai_api_key"),
    ("anthropic", "anthropic_api_key"), ("local", "openai_api_key"),
])
@pytest.mark.parametrize("empty_key", [None, "", "   "])
@pytest.mark.asyncio
async def test_missing_credentials_never_fallback_even_on_abstention(ledger, provider, key_field, empty_key):
    settings = EvanSettings(**{"llm_provider": provider, key_field: empty_key, "llm_base_url": "http://localhost:1234/v1"})
    ledger.claims.clear()
    with pytest.raises(ConfigurationError):
        await ConstrainedRealizer(settings).realize(ledger)
    with pytest.raises(ConfigurationError):
        await ProseAuditPipeline(settings).verify_or_repair(RealizedCommentary(), ledger)
    assert not ledger.audit_log


@pytest.mark.parametrize("failure", [LLMGenerationError("HTTP failure"), LLMResponse("not JSON"), LLMResponse("[]"), LLMResponse('{"sentences":[]}')])
@pytest.mark.asyncio
async def test_provider_or_generation_failure_returns_audited_fallback(settings, ledger, monkeypatch, failure):
    realizer = ConstrainedRealizer(settings)
    install_generator(realizer, monkeypatch, [failure])
    result = await realizer.realize(ledger)
    assert result.used_fallback and result.audit_passed
    assert result.cost_usd is None
    assert ledger.audit_log[-1]["event"] == "deterministic_fallback"


def test_templates_project_only_supported_claims_with_scope(ledger):
    ledger.claims[0].status = ClaimStatus.QUALIFY
    result = render_deterministic_template(ledger)
    assert "Qualified evidence" in result.sentences[0].text
    assert "displayed continuation only" in result.sentences[0].text
    assert audit_realized_commentary(result, ledger).passed


@pytest.mark.parametrize("text,code", [
    ("e4 is the only move and forces a win against every defense.", "scope_escalation"),
    ("e4 wins Black's queen.", "unsupported_proposition"),
    ("Qh9 wins.", "illegal_san"),
    ("Nxc7+ wins.", "branch_transfer"),
    ("e4 wins because the engine wants a kingside attack.", "scope_escalation"),
])
def test_auditor_flags_unsupported_prose(ledger, text, code):
    sentence = render_deterministic_template(ledger).sentences[0]
    sentence.text = text
    result = audit_sentence_against_claims(sentence, {"c1": ledger.claims[0]}, {"played": {"e4", "e5"}, "best": {"Nxc7+"}})
    assert not result.passed
    assert code in result.violation_codes


@pytest.mark.parametrize("field,value,code", [
    ("claim_ids", ["unknown"], "unknown_claim"),
    ("branch_id", "best", "branch_transfer"),
    ("preview_fen", chess.Board().mirror().fen(), "preview_mismatch"),
    ("arrows", [], "arrows_mismatch"),
])
def test_auditor_checks_provenance(ledger, field, value, code):
    commentary = render_deterministic_template(ledger)
    setattr(commentary.sentences[0], field, value)
    result = audit_realized_commentary(commentary, ledger)
    assert code in result.violation_codes


def test_auditor_checks_abstaining_citations_and_freeform_notices(ledger):
    commentary = render_deterministic_template(ledger)
    ledger.claims[0].status = ClaimStatus.ABSTAIN
    commentary.abstention_notice = "White wins by force."
    result = audit_realized_commentary(commentary, ledger)
    assert "abstain_claim" in result.violation_codes
    assert "unsupported_notice" in result.violation_codes


def test_san_detection_does_not_treat_piece_square_as_pawn_move():
    assert san_tokens("The rook on a8 and the knight on f3.") == set()
    assert san_tokens("1. e4 e5 2. Nf3 Nc6 3. Bb5 and exd8=Q+ O-O.") == {"e4", "e5", "Nf3", "Nc6", "Bb5", "exd8=Q+", "O-O"}


def test_legal_san_is_replayed_not_trusted_from_map(ledger):
    ledger.branch_legal_sans_map["played"].append("Nxc7+")
    ledger.claims[0].proposition = "After Nxc7+, White captures a pawn."
    commentary = render_deterministic_template(ledger)
    assert "illegal_san" in audit_realized_commentary(commentary, ledger).violation_codes


@pytest.mark.asyncio
async def test_one_repair_succeeds_and_usage_is_accumulated(settings, ledger, monkeypatch):
    commentary = render_deterministic_template(ledger)
    commentary.used_fallback = False
    commentary.sentences[0].text = "e4 forces a win."
    pipeline = ProseAuditPipeline(settings)
    calls = install_generator(pipeline, monkeypatch, [LLMResponse(json.dumps(payload_for(ledger)), {"prompt_tokens": 30, "completion_tokens": 10})])
    result = await pipeline.verify_or_repair(commentary, ledger)
    assert len(calls) == 1
    assert "scope_escalation" in calls[0][1]["violations"][0]["violation_codes"]
    assert result.audit_passed and not result.used_fallback
    assert result.usage["input_tokens"] == 30
    assert result.cost_usd is None
    assert ledger.audit_log[-1]["event"] == "repair_audit"


@pytest.mark.parametrize("failure", ["bad_prose", "bad_json", "http_failure"])
@pytest.mark.asyncio
async def test_failed_single_repair_then_audited_template(settings, ledger, monkeypatch, failure):
    commentary = render_deterministic_template(ledger)
    commentary.sentences[0].text = "e4 is necessarily winning."
    output = {
        "bad_prose": LLMResponse(json.dumps({"sentences": [s.model_dump(mode="json") for s in commentary.sentences]})),
        "bad_json": LLMResponse("invalid", {"prompt_tokens": 22}),
        "http_failure": LLMGenerationError("Provider HTTP status 500"),
    }[failure]
    pipeline = ProseAuditPipeline(settings)
    calls = install_generator(pipeline, monkeypatch, [output])
    result = await pipeline.verify_or_repair(commentary, ledger)
    assert len(calls) == 1
    assert result.audit_passed and result.used_fallback
    assert "necessarily" not in result.sentences[0].text
    assert ledger.audit_log[1]["event"] == "repair_requested"
    assert ledger.audit_log[-1]["event"] == "deterministic_fallback"
    if failure == "bad_json":
        assert result.usage["input_tokens"] == 22


@pytest.mark.asyncio
async def test_safe_initial_prose_no_repair(settings, ledger, monkeypatch):
    pipeline = ProseAuditPipeline(settings)
    calls = install_generator(pipeline, monkeypatch, [AssertionError("Must not call")])
    result = await pipeline.verify_or_repair(render_deterministic_template(ledger), ledger)
    assert result.audit_passed and not calls


@pytest.mark.asyncio
async def test_invalid_source_proposition_is_not_trusted_by_fallback(settings, ledger, monkeypatch):
    ledger.claims[0].proposition = "Nxc7+ is the only move and guarantees victory."
    realizer = ConstrainedRealizer(settings)
    install_generator(realizer, monkeypatch, [LLMGenerationError("Provider failure")])
    result = await realizer.realize(ledger)
    assert not result.sentences
    assert result.abstention_notice == ABSTENTION_NOTICE
    assert result.audit_passed
    assert any(entry["event"] == "fallback_rejected" for entry in ledger.audit_log)


@pytest.mark.parametrize("provider,expected_path", [
    ("openrouter", "/api/v1/chat/completions"), ("openai", "/v1/chat/completions"),
    ("anthropic", "/v1/messages"), ("local", "/v1/chat/completions"),
])
@pytest.mark.asyncio
async def test_provider_http_protocols(provider, expected_path):
    settings = EvanSettings(
        llm_provider=provider, llm_model="chosen-model", openrouter_api_key="or-key",
        openai_api_key="oa-key", anthropic_api_key="an-key",
        llm_base_url="http://localhost:1234/v1" if provider == "local" else None,
    )
    requests = []

    def handler(request):
        requests.append(request)
        body = json.loads(request.content)
        assert body["model"] == "chosen-model"
        if provider == "anthropic":
            assert request.headers["x-api-key"] == "an-key"
            assert body["system"] == "system"
            return httpx.Response(200, json={"content": [{"type": "text", "text": '{"sentences":[]}'}], "usage": {"input_tokens": 3, "output_tokens": 2}})
        assert request.headers["authorization"] == f"Bearer {'or-key' if provider == 'openrouter' else 'oa-key'}"
        return httpx.Response(200, json={"choices": [{"message": {"content": '{"sentences":[]}'}, "finish_reason": "stop"}], "usage": {"prompt_tokens": 3, "completion_tokens": 2, "cost": .002}})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await LLMClient(settings, client).generate("system", "prompt")
    assert requests[0].url.path == expected_path
    assert result.cost_usd == (None if provider == "anthropic" else .002)
    assert result.text == '{"sentences":[]}'


@pytest.mark.asyncio
async def test_http_auth_failure_is_explicit_without_leaking_credentials(settings):
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda _: httpx.Response(401, json={"error": "secret body"}))) as client:
        with pytest.raises(ConfigurationError, match="rejected authentication") as exc:
            await LLMClient(settings, client).generate("system", "prompt")
    assert "secret" not in str(exc.value)
    assert "test-key" not in str(exc.value)


@pytest.mark.asyncio
async def test_truncated_provider_response_preserves_reported_usage(settings):
    def handler(request):
        return httpx.Response(200, json={"choices": [{"message": {"content": "{}"}, "finish_reason": "length"}], "usage": {"prompt_tokens": 12, "completion_tokens": 20}})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(LLMGenerationError) as exc:
            await LLMClient(settings, client).generate("system", "prompt")
    assert exc.value.response.usage["completion_tokens"] == 20


@pytest.mark.asyncio
async def test_cost_not_invented_for_provider_without_price(settings, ledger, monkeypatch):
    realizer = ConstrainedRealizer(settings)
    install_generator(realizer, monkeypatch, [LLMResponse(json.dumps(payload_for(ledger)), {"prompt_tokens": 100, "completion_tokens": 200})])
    result = await realizer.realize(ledger)
    assert result.cost_usd is None
    assert result.usage["input_tokens"] == 100
