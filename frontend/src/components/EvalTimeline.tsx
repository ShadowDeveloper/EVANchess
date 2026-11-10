import React from 'react';
import { Star } from 'lucide-react';
import type { PlyAnalysis } from '../types/evan';

interface EvalTimelineProps {
  plies: PlyAnalysis[];
  selectedPlyIndex: number;
  onSelectPly: (ply: number) => void;
}

function formatEvalLabel(
  cpWhite: number | null,
  mateWhite: number | null,
): string {
  if (mateWhite !== null && mateWhite !== undefined) {
    if (mateWhite === 0) {
      return 'Mate';
    }
    return `M${mateWhite > 0 ? `+${mateWhite}` : mateWhite}`;
  }
  if (cpWhite === null || cpWhite === undefined) return 'Not analyzed';
  const cp = cpWhite;
  const pawns = cp / 100;
  return `${pawns >= 0 ? '+' : ''}${pawns.toFixed(1)}`;
}

function cpToWhiteHeightPercent(
  cpWhite: number | null,
  mateWhite: number | null,
): number {
  if (mateWhite !== null && mateWhite !== undefined) {
    return mateWhite >= 0 ? 96 : 4;
  }
  const cp = Math.max(-900, Math.min(900, cpWhite ?? 0));
  const winProb = 1 / (1 + Math.exp(-0.00368208 * cp));
  return Math.round(Math.max(6, Math.min(94, winProb * 100)));
}

export const EvalTimeline: React.FC<EvalTimelineProps> = ({
  plies,
  selectedPlyIndex,
  onSelectPly,
}) => {
  if (plies.length === 0) {
    return null;
  }

  const currentPly =
    plies.find((p) => p.ply === selectedPlyIndex) ?? plies[0];
  const criticalPlies = plies.filter((p) => p.is_critical);

  const evalAfterCp =
    currentPly.coarse_eval_after_cp_white ?? currentPly.coarse_eval_cp_white;
  const mateAfter =
    currentPly.coarse_mate_after_white ?? currentPly.coarse_mate_white;

  return (
    <section
      aria-label="Evaluation Timeline"
      className="rounded-lg border border-[#22252D] bg-[#12141A] p-3.5"
    >
      <div className="mb-2.5 flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2.5">
          <span className="font-mono-code text-[10px] font-semibold uppercase tracking-widest text-[#9499A6]">
            Coarse Trajectory &amp; Turning Points
          </span>
          {criticalPlies.length > 0 && (
            <span className="inline-flex items-center gap-1 rounded border border-[#D99B26]/40 bg-[#D99B26]/15 px-2 py-0.5 font-mono-code text-[10px] font-medium text-[#F4E0B8]">
              <Star className="h-2.5 w-2.5 fill-[#D99B26] text-[#D99B26]" />
              {criticalPlies.length} Critical Moment
              {criticalPlies.length === 1 ? '' : 's'}
            </span>
          )}
        </div>

        <div className="flex items-center gap-3 font-mono-code text-xs">
          <span className="text-[#9499A6]">
            Selected:{' '}
            <strong className="text-[#ECE9E2]">
              {currentPly.ply === 0 &&
              currentPly.san_move === 'Position' &&
              currentPly.uci_move === ''
                ? 'Position'
                : `${currentPly.move_number}${
                    currentPly.turn === 'white' ? '.' : '...'
                  }${currentPly.san_move}`}
            </strong>
          </span>
          <span className="rounded border border-[#2B303D] bg-[#181B24] px-2 py-0.5 font-semibold text-[#F4E0B8]">
            {formatEvalLabel(evalAfterCp, mateAfter)}
          </span>
        </div>
      </div>

      <div className="relative flex h-16 w-full items-stretch gap-[2px] overflow-hidden rounded border border-[#252934] bg-[#0B0C0E] p-1">
        <div className="pointer-events-none absolute inset-x-0 top-1/2 z-10 border-t border-dashed border-[#383F52]/70" />
        {plies.map((p) => {
          const cp =
            p.coarse_eval_after_cp_white ?? p.coarse_eval_cp_white ?? 0;
          const mate = p.coarse_mate_after_white ?? p.coarse_mate_white;
          const whitePct = cpToWhiteHeightPercent(cp, mate);
          const isSelected = p.ply === selectedPlyIndex;
          const isFenRoot =
            p.ply === 0 && p.san_move === 'Position' && p.uci_move === '';
          const moveLabel = isFenRoot
            ? 'Position'
            : `${p.move_number}${p.turn === 'white' ? '.' : '...'}${p.san_move}`;

          return (
            <button
              key={p.ply}
              type="button"
              onClick={() => onSelectPly(p.ply)}
              aria-label={`Ply ${p.ply} ${moveLabel} (${formatEvalLabel(cp, mate)})`}
              title={`${moveLabel} (${formatEvalLabel(cp, mate)})${
                p.is_critical
                  ? ` ★ ${p.critical_reason?.primary_reason || 'Critical Moment'}`
                  : ''
              }`}
              className={`group relative flex flex-1 flex-col justify-end overflow-hidden rounded-[2px] transition ${
                isSelected
                  ? 'ring-2 ring-[#D99B26] z-20'
                  : p.is_critical
                    ? 'ring-1 ring-[#D99B26]/60'
                    : 'hover:opacity-90'
              }`}
            >
              <div className="w-full flex-1 bg-[#1B1E28]" />
              <div
                style={{ height: `${whitePct}%` }}
                className={`w-full transition-all ${
                  p.is_critical
                    ? 'bg-[#D99B26]'
                    : isSelected
                      ? 'bg-[#F4E0B8]'
                      : 'bg-[#C4C7D0]/85 group-hover:bg-[#E5E2DC]'
                }`}
              />
              {p.is_critical && (
                <span className="pointer-events-none absolute top-0.5 left-1/2 -translate-x-1/2 text-[9px] font-bold text-[#F4E0B8] drop-shadow">
                  ★
                </span>
              )}
            </button>
          );
        })}
      </div>

      {criticalPlies.length > 0 && (
        <div className="mt-2.5 flex flex-wrap items-center gap-1.5">
          <span className="font-mono-code text-[10px] uppercase tracking-wider text-[#858B99]">
            Jump to Critical:
          </span>
          {criticalPlies.map((cp) => {
            const active = cp.ply === selectedPlyIndex;
            return (
              <button
                key={cp.ply}
                type="button"
                onClick={() => onSelectPly(cp.ply)}
                className={`inline-flex items-center gap-1 rounded border px-2 py-0.5 font-mono-code text-[11px] transition ${
                  active
                    ? 'border-[#D99B26] bg-[#D99B26] font-bold text-[#0B0C0E]'
                    : 'border-[#D99B26]/40 bg-[#D99B26]/10 text-[#F4E0B8] hover:bg-[#D99B26]/20'
                }`}
              >
                <span>★</span>
                <span>
                  {cp.move_number}
                  {cp.turn === 'white' ? '.' : '...'}
                  {cp.san_move}
                </span>
              </button>
            );
          })}
        </div>
      )}
    </section>
  );
};
