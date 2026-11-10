from __future__ import annotations

from enum import Enum
from typing import Any
from pydantic import BaseModel, Field
from evan.evidence.detectors import BoardArrow


class ClaimType(str, Enum):
    STATE_FACT = "state_fact"
    CONDITIONAL_LINE_EVENT = "conditional_line_event"
    ENGINE_PREFERENCE = "engine_preference"
    MOTIF = "motif"
    PLAN_INTERPRETATION = "plan_interpretation"
    EXACT_OUTCOME = "exact_outcome"


class AssertionScope(str, Enum):
    CURRENT_BOARD_ONLY = "current_board_only"
    IN_DISPLAYED_CONTINUATION = "in_displayed_continuation"
    ACROSS_ANALYZED_DEFENSES_AT_BUDGET = "across_analyzed_defenses_at_budget"
    ENGINE_PREFERENCE_AT_BUDGET = "engine_preference_at_budget"
    HEURISTIC_INTERPRETATION = "heuristic_interpretation"
    EXACT_RULES_OR_TABLEBASE = "exact_rules_or_tablebase"


class ClaimStatus(str, Enum):
    ASSERT = "assert"
    QUALIFY = "qualify"
    ABSTAIN = "abstain"


class ClaimRecord(BaseModel):
    claim_id: str
    type: ClaimType
    proposition: str
    root_state_id: str
    branch_id: str
    applicable_state_ids: list[str] = Field(default_factory=list)
    support_evidence_ids: list[str] = Field(default_factory=list)
    evidence_source: str
    assertion_scope: AssertionScope
    line_event_plies: list[int] = Field(default_factory=list)
    validation_results: dict[str, Any] = Field(default_factory=dict)
    challenge_queries: list[str] = Field(default_factory=list)
    discovered_contradictions: list[str] = Field(default_factory=list)
    unresolved_questions: list[str] = Field(default_factory=list)
    status: ClaimStatus = ClaimStatus.ASSERT
    preview_fen: str = ""
    arrows: list[BoardArrow] = Field(default_factory=list)


class MomentClaimLedger(BaseModel):
    ply: int
    move_number: int
    turn: str
    played_san: str
    best_san: str
    root_fen: str
    root_state_id: str = ""
    root_state_hash: str = ""
    uci_history: list[str] = Field(default_factory=list)
    stability_status: str
    claims: list[ClaimRecord] = Field(default_factory=list)
    branch_pv_san_map: dict[str, list[str]] = Field(default_factory=dict)
    branch_legal_sans_map: dict[str, list[str]] = Field(default_factory=dict)
    branch_fens_map: dict[str, list[str]] = Field(default_factory=dict)
    evidence_branch_map: dict[str, str] = Field(default_factory=dict)
    evidence_witness_map: dict[str, dict[str, Any]] = Field(default_factory=dict)
    challenge_outcomes: list[dict[str, Any]] = Field(default_factory=list)
    engine_metadata: list[dict[str, Any]] = Field(default_factory=list)
    audit_log: list[dict[str, Any]] = Field(default_factory=list)
