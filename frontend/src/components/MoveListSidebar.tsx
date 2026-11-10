import React, { useState } from 'react';
import {
  Star,
  CheckCircle2,
  Clock,
  Ban,
  Loader2,
  Zap,
  AlertCircle,
} from 'lucide-react';
import type { PlyAnalysis } from '../types/evan';

interface MoveListSidebarProps {
  plies: PlyAnalysis[];
  selectedPly: number;
  onSelectPly: (ply: number) => void;
  onPrioritizePly: (ply: number) => Promise<void>;
}

type MoveFilter = 'all' | 'critical' | 'audited';

function renderStatusBadge(plyItem: PlyAnalysis) {
  switch (plyItem.deep_status) {
    case 'completed':
      return (
        <span
          title="Audited 10-step commentary ready"
          className="inline-flex items-center gap-1 rounded border border-emerald-500/40 bg-emerald-500/10 px-1.5 py-0.5 font-mono-code text-[10px] font-medium text-emerald-300"
        >
          <CheckCircle2 className="h-2.5 w-2.5" />
          <span>✓ Audited</span>
        </span>
      );
    case 'abstained':
      return (
        <span
          title="Abstained: deterministic detectors found no concrete witness to assert"
          className="inline-flex items-center gap-1 rounded border border-zinc-500/40 bg-zinc-500/15 px-1.5 py-0.5 font-mono-code text-[10px] font-medium text-zinc-300"
        >
          <Ban className="h-2.5 w-2.5" />
          <span>⊘ Abstained</span>
        </span>
      );
    case 'running':
      return (
        <span
          title="Running deep multi-budget search & prose audit"
          className="inline-flex items-center gap-1 rounded border border-sky-500/40 bg-sky-500/15 px-1.5 py-0.5 font-mono-code text-[10px] font-medium text-sky-300"
        >
          <Loader2 className="h-2.5 w-2.5 animate-spin" />
          <span>Analyzing</span>
        </span>
      );
    case 'failed':
      return (
        <span
          title="Deep analysis failed on this ply"
          className="inline-flex items-center gap-1 rounded border border-rose-500/40 bg-rose-500/15 px-1.5 py-0.5 font-mono-code text-[10px] font-medium text-rose-300"
        >
          <AlertCircle className="h-2.5 w-2.5" />
          <span>Failed</span>
        </span>
      );
    case 'queued':
    default:
      return (
        <span
          title="Queued in Stage B deferred worker (click move to prioritize)"
          className="inline-flex items-center gap-1 rounded border border-amber-500/35 bg-amber-500/10 px-1.5 py-0.5 font-mono-code text-[10px] font-medium text-amber-300"
        >
          <Clock className="h-2.5 w-2.5" />
          <span>⏳ Queued</span>
        </span>
      );
  }
}

export const MoveListSidebar: React.FC<MoveListSidebarProps> = ({
  plies,
  selectedPly,
  onSelectPly,
  onPrioritizePly,
}) => {
  const [filter, setFilter] = useState<MoveFilter>('all');
  const [prioritizingPly, setPrioritizingPly] = useState<number | null>(null);

  const filteredPlies = plies.filter((p) => {
    if (filter === 'critical') {
      return p.is_critical;
    }
    if (filter === 'audited') {
      return p.deep_status === 'completed' || p.deep_status === 'abstained';
    }
    return true;
  });

  const handleRowClick = async (plyItem: PlyAnalysis) => {
    onSelectPly(plyItem.ply);
    if (plyItem.deep_status === 'queued') {
      setPrioritizingPly(plyItem.ply);
      try {
        await onPrioritizePly(plyItem.ply);
      } finally {
        setPrioritizingPly(null);
      }
    }
  };

  return (
    <aside
      aria-label="Move List and Queue Status"
      className="flex h-full flex-col rounded-lg border border-[#22252D] bg-[#12141A]"
    >
      <div className="border-b border-[#22252D] px-3.5 py-3">
        <div className="flex items-center justify-between">
          <h2 className="font-editorial text-base font-semibold text-[#F5F2EB]">
            Move Ledger &amp; Queue
          </h2>
          <span className="font-mono-code text-[11px] text-[#9499A6]">
            {plies.length} {plies.length === 1 ? 'ply' : 'plies'}
          </span>
        </div>

        <div className="mt-2.5 grid grid-cols-3 gap-1 rounded-md border border-[#262A34] bg-[#0D0F13] p-0.5 text-[11px]">
          {(
            [
              { id: 'all', label: 'All Plies' },
              { id: 'critical', label: '★ Critical' },
              { id: 'audited', label: '✓ Audited' },
            ] as { id: MoveFilter; label: string }[]
          ).map((tab) => (
            <button
              key={tab.id}
              type="button"
              onClick={() => setFilter(tab.id)}
              className={`rounded py-1 font-medium transition ${
                filter === tab.id
                  ? 'bg-[#D99B26] font-semibold text-[#0B0C0E]'
                  : 'text-[#9499A6] hover:text-[#ECE9E2]'
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>
      </div>

      <div className="flex-1 space-y-1 overflow-y-auto p-2 max-h-[540px]">
        {filteredPlies.length === 0 ? (
          <div className="py-10 text-center text-xs text-[#858B99]">
            No moves match the current filter.
          </div>
        ) : (
          filteredPlies.map((p) => {
            const isSelected = p.ply === selectedPly;
            const isFenRoot =
              p.ply === 0 && p.san_move === 'Position' && p.uci_move === '';
            const evalCp =
              p.coarse_eval_after_cp_white ?? p.coarse_eval_cp_white ?? 0;
            const evalPawns = (evalCp / 100).toFixed(1);

            return (
              <div
                key={p.ply}
                className={`group rounded-md border transition ${
                  isSelected
                    ? 'border-[#D99B26] bg-[#D99B26]/15'
                    : 'border-[#1E222B] bg-[#161921]/70 hover:border-[#2E3442] hover:bg-[#1B1F29]'
                }`}
              >
                <button
                  type="button"
                  onClick={() => handleRowClick(p)}
                  className="flex w-full items-center justify-between gap-2 px-2.5 py-2 text-left"
                >
                  <div className="flex min-w-0 items-center gap-2">
                    <span className="w-8 shrink-0 font-mono-code text-[11px] text-[#858B99]">
                      {isFenRoot
                        ? 'FEN'
                        : `${p.move_number}${p.turn === 'white' ? '.' : '...'}`}
                    </span>
                    <span className="truncate font-mono-code text-xs font-semibold text-[#F4F1EA]">
                      {p.san_move}
                    </span>
                    {p.is_critical && (
                      <span
                        title={
                          p.critical_reason?.primary_reason || 'Critical Moment'
                        }
                        className="inline-flex items-center gap-0.5 rounded bg-[#D99B26]/25 px-1.5 py-0.5 font-mono-code text-[10px] font-semibold text-[#F4E0B8]"
                      >
                        <Star className="h-2.5 w-2.5 fill-[#D99B26] text-[#D99B26]" />
                        <span>Critical</span>
                      </span>
                    )}
                  </div>

                  <div className="flex shrink-0 items-center gap-1.5">
                    <span className="font-mono-code text-[10px] text-[#9499A6]">
                      {evalCp >= 0 ? `+${evalPawns}` : evalPawns}
                    </span>
                    {renderStatusBadge(p)}
                  </div>
                </button>

                {p.deep_status === 'queued' && (
                  <div className="flex items-center justify-between border-t border-[#222630] px-2.5 py-1 text-[10px] text-[#9499A6]">
                    <span>Deferred full-game queue</span>
                    <button
                      type="button"
                      disabled={prioritizingPly === p.ply}
                      onClick={async (e) => {
                        e.stopPropagation();
                        onSelectPly(p.ply);
                        setPrioritizingPly(p.ply);
                        try {
                          await onPrioritizePly(p.ply);
                        } finally {
                          setPrioritizingPly(null);
                        }
                      }}
                      className="inline-flex items-center gap-1 font-mono-code font-semibold text-[#E8B042] hover:underline disabled:opacity-50"
                    >
                      <Zap className="h-2.5 w-2.5" />
                      <span>
                        {prioritizingPly === p.ply
                          ? 'Boosting...'
                          : 'Click to prioritize'}
                      </span>
                    </button>
                  </div>
                )}
              </div>
            );
          })
        )}
      </div>
    </aside>
  );
};
