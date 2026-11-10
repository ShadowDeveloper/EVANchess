from __future__ import annotations

import chess
from pydantic import BaseModel
from evan.engines.protocols import (
    EngineAnalysisRecord,
    HumanPolicyProtocol,
    is_confident_record,
    mover_sort_key,
)


class CandidateMoveSpec(BaseModel):
    uci: str
    san: str
    role: str
    nomination_source: str


def select_candidate_moves(
    board: chess.Board,
    played_uci: str,
    multipv_records: list[EngineAnalysisRecord],
    human_policy: HumanPolicyProtocol | None = None,
    target_rating: int = 1500,
    max_alternatives: int = 3,
) -> list[CandidateMoveSpec]:
    legal_ucis = {m.uci(): m for m in board.legal_moves}
    if played_uci not in legal_ucis:
        raise ValueError(f"Played move '{played_uci}' is not legal in root board.")

    candidates: list[CandidateMoveSpec] = []
    seen: set[str] = set()

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

    confident_records = [
        r for r in multipv_records if r.pv_uci and r.pv_uci[0] in legal_ucis and is_confident_record(r)
    ]
    ordered_records = sorted(
        confident_records if confident_records else [r for r in multipv_records if r.pv_uci and r.pv_uci[0] in legal_ucis],
        key=lambda r: (
            0 if r.multipv_index == 1 else 1,
            -mover_sort_key(r)[0],
            -mover_sort_key(r)[1],
            r.multipv_index,
        ),
    )

    top_engine_uci: str | None = ordered_records[0].pv_uci[0] if ordered_records else None
    engine_best_assigned = top_engine_uci == played_uci

    for rec in ordered_records:
        mv_uci = rec.pv_uci[0]
        if mv_uci in legal_ucis and mv_uci not in seen:
            if not engine_best_assigned and mv_uci == top_engine_uci:
                role = "engine_best"
                engine_best_assigned = True
            else:
                role = "alternative"
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

    if len(candidates) == 1 and len(legal_ucis) > 1 and max_alternatives > 1:
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
