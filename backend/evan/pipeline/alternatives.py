from __future__ import annotations

import chess
from pydantic import BaseModel
from evan.engines.protocols import EngineAnalysisRecord, HumanPolicyProtocol


class CandidateMoveSpec(BaseModel):
    uci: str
    san: str
    role: str  # "played" | "engine_best" | "alternative" | "human_policy"
    nomination_source: str


def select_candidate_moves(
    board: chess.Board,
    played_uci: str,
    multipv_records: list[EngineAnalysisRecord],
    human_policy: HumanPolicyProtocol | None = None,
    target_rating: int = 1500,
    max_alternatives: int = 3,
) -> list[CandidateMoveSpec]:
    """Step 4: Always include played move and engine-preferred move, plus 1-2 legal alternatives."""
    legal_ucis = {m.uci(): m for m in board.legal_moves}
    if played_uci not in legal_ucis:
        raise ValueError(f"Played move '{played_uci}' is not legal in root board.")

    candidates: list[CandidateMoveSpec] = []
    seen: set[str] = set()

    # 1. Played move is always included
    played_move = legal_ucis[played_uci]
    candidates.append(
        CandidateMoveSpec(
            uci=played_uci,
            san=board.san(played_move),
            role="played",
            nomination_source="game_record",
        )
    )
    seen.add(played_uci)

    # 2. Engine-preferred candidate from MultiPV
    for rec in multipv_records:
        if not rec.pv_uci:
            continue
        mv_uci = rec.pv_uci[0]
        if mv_uci in legal_ucis and mv_uci not in seen:
            role = "engine_best" if not any(c.role == "engine_best" for c in candidates) else "alternative"
            candidates.append(
                CandidateMoveSpec(
                    uci=mv_uci,
                    san=board.san(legal_ucis[mv_uci]),
                    role=role,
                    nomination_source=f"multipv_{rec.multipv_index}",
                )
            )
            seen.add(mv_uci)
            if len(candidates) >= max_alternatives:
                break

    # 3. Optional Maia-2 / HumanPolicyProtocol candidate
    if human_policy is not None and len(candidates) < max_alternatives:
        policy_preds = human_policy.predict_candidates(
            board, rating_white=target_rating, rating_black=target_rating, top_k=3
        )
        for pred in policy_preds:
            if pred.uci in legal_ucis and pred.uci not in seen:
                candidates.append(
                    CandidateMoveSpec(
                        uci=pred.uci,
                        san=board.san(legal_ucis[pred.uci]),
                        role="human_policy",
                        nomination_source=f"{pred.source}_p={pred.probability:.2f}",
                    )
                )
                seen.add(pred.uci)
                if len(candidates) >= max_alternatives:
                    break

    # 4. If played move was already the engine best, ensure at least one second legal option is analyzed when available
    if len(candidates) == 1 and len(legal_ucis) > 1:
        for uci_str, mv_obj in legal_ucis.items():
            if uci_str not in seen:
                candidates.append(
                    CandidateMoveSpec(
                        uci=uci_str,
                        san=board.san(mv_obj),
                        role="alternative",
                        nomination_source="legal_fallback",
                    )
                )
                seen.add(uci_str)
                break

    return candidates
