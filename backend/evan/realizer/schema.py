from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from evan.evidence.detectors import BoardArrow


class RealizedSentence(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sentence_id: str
    text: str = Field(min_length=1)
    claim_ids: list[str] = Field(min_length=1)
    branch_id: str
    preview_fen: str = ""
    arrows: list[BoardArrow] = Field(default_factory=list)


class RealizedCommentary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sentences: list[RealizedSentence] = Field(default_factory=list)
    abstention_notice: str | None = None
    provider: str | None = None
    model: str | None = None
    usage: dict[str, Any] = Field(default_factory=dict)
    cost_usd: float | None = None
    used_fallback: bool = False
    audit_passed: bool = False
