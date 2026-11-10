from __future__ import annotations

from pydantic import BaseModel
from evan.pipeline.coarse import CoarsePlySummary


class CriticalMomentScore(BaseModel):
    ply: int
    total_score: float
    eval_swing_score: float
    sharpness_score: float
    tactical_motif_bonus: float
    phase_diversity_adjustment: float
    primary_reason: str


def select_critical_moments(
    summaries: list[CoarsePlySummary],
    count: int = 5,
    player_color: str | None = None,
) -> list[CriticalMomentScore]:
    if not summaries or count <= 0:
        return []

    raw_candidates: list[tuple[CoarsePlySummary, float, float, float, str]] = []
    for s in summaries:
        if not s.is_confident:
            swing_score = 0.0
            sharpness_score = 0.0
        else:
            wp_abs = abs(s.win_prob_delta_mover)
            cp_abs = min(abs(s.eval_swing_cp_mover), 600) / 600.0
            swing_score = wp_abs * 60.0 + cp_abs * 25.0

            if player_color and s.turn == player_color and s.eval_swing_cp_mover < -60:
                swing_score += 8.0

            sharpness_score = min(s.top1_top2_gap_cp, 350) / 350.0 * 28.0

        tactical_bonus = 0.0
        if s.gives_check:
            tactical_bonus += 5.0
        if s.is_capture:
            tactical_bonus += 3.0
        if s.mate_before_white is not None or s.mate_after_white is not None:
            tactical_bonus += 15.0

        if swing_score >= sharpness_score and abs(s.eval_swing_cp_mover) >= 80:
            if s.eval_swing_cp_mover < 0:
                reason = f"Evaluation drop ({s.eval_swing_cp_mover} cp)"
            else:
                reason = f"Evaluation swing (+{s.eval_swing_cp_mover} cp)"
        elif sharpness_score >= 12.0:
            reason = f"Critical sharp choice ({s.top1_top2_gap_cp} cp gap between top moves)"
        else:
            reason = "Key positional/tactical transition"

        raw_candidates.append((s, swing_score, sharpness_score, tactical_bonus, reason))

    selected: list[CriticalMomentScore] = []
    selected_plies: set[int] = set()
    phase_counts: dict[str, int] = {"opening": 0, "middlegame": 0, "endgame": 0}

    target_k = min(count, len(summaries))
    for _ in range(target_k):
        best_item: CriticalMomentScore | None = None
        best_phase: str = "middlegame"

        for s, swing_sc, sharp_sc, tac_bon, reason in raw_candidates:
            if s.ply in selected_plies:
                continue

            div_adj = 0.0
            if phase_counts.get(s.phase, 0) == 0:
                div_adj += 6.0
            elif phase_counts.get(s.phase, 0) >= 2:
                div_adj -= 5.0 * phase_counts[s.phase]

            if any(abs(s.ply - p) <= 1 for p in selected_plies):
                div_adj -= 28.0
            elif any(abs(s.ply - p) == 2 for p in selected_plies):
                div_adj -= 10.0

            total = round(swing_sc + sharp_sc + tac_bon + div_adj, 3)
            if best_item is None or total > best_item.total_score:
                best_item = CriticalMomentScore(
                    ply=s.ply,
                    total_score=total,
                    eval_swing_score=round(swing_sc, 3),
                    sharpness_score=round(sharp_sc, 3),
                    tactical_motif_bonus=round(tac_bon, 3),
                    phase_diversity_adjustment=round(div_adj, 3),
                    primary_reason=reason,
                )
                best_phase = s.phase

        if best_item is not None:
            selected.append(best_item)
            selected_plies.add(best_item.ply)
            phase_counts[best_phase] = phase_counts.get(best_phase, 0) + 1

    return sorted(selected, key=lambda m: m.ply)
