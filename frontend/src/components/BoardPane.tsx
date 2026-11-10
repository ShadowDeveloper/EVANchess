import React, { useEffect, useRef } from 'react';
import { Chessground } from '@lichess-org/chessground';
import type { Api as ChessgroundApi } from '@lichess-org/chessground/api';
import type { Key } from '@lichess-org/chessground/types';
import type { DrawShape } from '@lichess-org/chessground/draw';
import {
  ChevronsLeft,
  ChevronLeft,
  ChevronRight,
  ChevronsRight,
  FlipVertical2,
  GitBranch,
  RotateCcw,
  Eye,
} from 'lucide-react';
import type {
  BoardArrow,
  BranchPreviewState,
  PlayerColor,
  PlyAnalysis,
} from '../types/evan';

interface BoardPaneProps {
  fen: string;
  orientation: PlayerColor;
  onToggleOrientation: () => void;
  currentPly: PlyAnalysis | null;
  plyPositionMode: 'before' | 'after';
  onChangePlyPositionMode: (mode: 'before' | 'after') => void;
  arrows: BoardArrow[];
  branchPreview: BranchPreviewState | null;
  onStepBranchPreview: (stepIndex: number) => void;
  onClearBranchPreview: () => void;
  canPrevPly: boolean;
  canNextPly: boolean;
  onFirstPly: () => void;
  onPrevPly: () => void;
  onNextPly: () => void;
  onLastPly: () => void;
  whiteName: string;
  blackName: string;
}

function normalizeBrush(brush?: string): 'green' | 'red' | 'blue' | 'yellow' {
  if (brush === 'red' || brush === 'blue' || brush === 'yellow' || brush === 'green') {
    return brush;
  }
  return 'green';
}

function toDrawShapes(arrows: BoardArrow[]): DrawShape[] {
  const validSquares = /^[a-h][1-8]$/;
  return arrows
    .filter((a) => validSquares.test(a.orig) && validSquares.test(a.dest))
    .map((a) => ({
      orig: a.orig as Key,
      dest: a.dest as Key,
      brush: normalizeBrush(a.brush),
    }));
}

function extractLastMoveKeys(uciMove?: string): Key[] | undefined {
  if (!uciMove || uciMove.length < 4) {
    return undefined;
  }
  const orig = uciMove.slice(0, 2);
  const dest = uciMove.slice(2, 4);
  if (/^[a-h][1-8]$/.test(orig) && /^[a-h][1-8]$/.test(dest)) {
    return [orig as Key, dest as Key];
  }
  return undefined;
}

export const BoardPane: React.FC<BoardPaneProps> = ({
  fen,
  orientation,
  onToggleOrientation,
  currentPly,
  plyPositionMode,
  onChangePlyPositionMode,
  arrows,
  branchPreview,
  onStepBranchPreview,
  onClearBranchPreview,
  canPrevPly,
  canNextPly,
  onFirstPly,
  onPrevPly,
  onNextPly,
  onLastPly,
  whiteName,
  blackName,
}) => {
  const boardContainerRef = useRef<HTMLDivElement>(null);
  const cgApiRef = useRef<ChessgroundApi | null>(null);

  const displayedFen = branchPreview ? branchPreview.fen : fen;
  const displayedArrows = branchPreview ? branchPreview.arrows : arrows;

  useEffect(() => {
    const el = boardContainerRef.current;
    if (!el) {
      return;
    }

    try {
      const shapes = toDrawShapes(displayedArrows);
      const lastMove =
        !branchPreview && plyPositionMode === 'after'
          ? extractLastMoveKeys(currentPly?.uci_move)
          : undefined;

      if (!cgApiRef.current) {
        cgApiRef.current = Chessground(el, {
          fen: displayedFen,
          orientation,
          viewOnly: false,
          movable: {
            free: false,
            color: undefined,
          },
          draggable: {
            enabled: false,
          },
          selectable: {
            enabled: true,
          },
          coordinates: true,
          highlight: {
            lastMove: true,
            check: true,
          },
          lastMove,
          drawable: {
            enabled: true,
            visible: true,
            autoShapes: shapes,
          },
        });
      } else {
        cgApiRef.current.set({
          fen: displayedFen,
          orientation,
          lastMove,
          drawable: {
            enabled: true,
            visible: true,
            autoShapes: shapes,
          },
        });
        cgApiRef.current.setAutoShapes(shapes);
      }
    } catch {
      return;
    }
  }, [
    displayedFen,
    orientation,
    displayedArrows,
    branchPreview,
    currentPly?.uci_move,
    plyPositionMode,
  ]);

  useEffect(() => {
    return () => {
      try {
        cgApiRef.current?.destroy();
      } catch {
        cgApiRef.current = null;
      }
      cgApiRef.current = null;
    };
  }, []);

  const topPlayer = orientation === 'white' ? blackName : whiteName;
  const topColor = orientation === 'white' ? 'Black' : 'White';
  const bottomPlayer = orientation === 'white' ? whiteName : blackName;
  const bottomColor = orientation === 'white' ? 'White' : 'Black';

  const isFenOnlyPly =
    currentPly &&
    currentPly.ply === 0 &&
    currentPly.san_move === 'Position' &&
    currentPly.uci_move === '';

  return (
    <div className="flex flex-col gap-2.5">
      {branchPreview && (
        <div
          role="region"
          aria-label="Previewing Evidence Branch"
          className="rounded-lg border border-[#D99B26]/60 bg-gradient-to-r from-[#D99B26]/20 via-[#191610] to-[#13151B] p-3 shadow-lg"
        >
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div className="flex items-center gap-2">
              <span className="inline-flex items-center gap-1.5 rounded bg-[#D99B26] px-2 py-0.5 font-mono-code text-[11px] font-bold uppercase tracking-wider text-[#0B0C0E]">
                <GitBranch className="h-3 w-3" />
                Previewing Evidence Branch
              </span>
              <span className="font-mono-code text-xs text-[#F4E0B8]">
                {branchPreview.branchId}
              </span>
            </div>

            <button
              type="button"
              onClick={onClearBranchPreview}
              className="inline-flex items-center gap-1.5 rounded border border-[#D99B26]/50 bg-[#0B0C0E]/80 px-2.5 py-1 text-xs font-semibold text-[#F4E0B8] transition hover:bg-[#D99B26] hover:text-[#0B0C0E]"
            >
              <RotateCcw className="h-3.5 w-3.5" />
              <span>Restore Game Position</span>
            </button>
          </div>

          {branchPreview.pvSan.length > 0 && (
            <div className="mt-2.5 flex flex-wrap items-center justify-between gap-2 border-t border-[#D99B26]/25 pt-2">
              <div className="flex flex-wrap items-center gap-1">
                <button
                  type="button"
                  onClick={() => onStepBranchPreview(0)}
                  className={`rounded px-2 py-0.5 font-mono-code text-[11px] transition ${
                    branchPreview.stepIndex === 0
                      ? 'bg-[#D99B26] font-bold text-[#0B0C0E]'
                      : 'bg-[#171A22] text-[#9499A6] hover:text-[#ECE9E2]'
                  }`}
                >
                  Root
                </button>
                {branchPreview.pvSan.map((san, idx) => {
                  const targetStep = idx + 1;
                  const canStep = targetStep < branchPreview.stateFens.length;
                  const isActiveStep = branchPreview.stepIndex === targetStep;
                  return (
                    <button
                      key={`${san}-${idx}`}
                      type="button"
                      disabled={!canStep}
                      onClick={() => onStepBranchPreview(targetStep)}
                      className={`rounded px-2 py-0.5 font-mono-code text-[11px] transition ${
                        isActiveStep
                          ? 'bg-[#D99B26] font-bold text-[#0B0C0E]'
                          : canStep
                            ? 'bg-[#171A22] text-[#ECE9E2] hover:bg-[#242936]'
                            : 'bg-[#12141A] text-[#5F6575] opacity-60'
                      }`}
                    >
                      {san}
                    </button>
                  );
                })}
              </div>

              {branchPreview.stateFens.length > 1 && (
                <div className="flex items-center gap-1">
                  <button
                    type="button"
                    aria-label="Previous branch ply"
                    disabled={branchPreview.stepIndex <= 0}
                    onClick={() =>
                      onStepBranchPreview(Math.max(0, branchPreview.stepIndex - 1))
                    }
                    className="rounded border border-[#2E3442] bg-[#13151B] p-1 text-xs text-[#ECE9E2] hover:border-[#D99B26]/50 disabled:opacity-40"
                  >
                    <ChevronLeft className="h-3.5 w-3.5" />
                  </button>
                  <span className="px-1.5 font-mono-code text-[11px] text-[#C5C8D2]">
                    Step {branchPreview.stepIndex}/
                    {Math.max(0, branchPreview.stateFens.length - 1)}
                  </span>
                  <button
                    type="button"
                    aria-label="Next branch ply"
                    disabled={
                      branchPreview.stepIndex >= branchPreview.stateFens.length - 1
                    }
                    onClick={() =>
                      onStepBranchPreview(
                        Math.min(
                          branchPreview.stateFens.length - 1,
                          branchPreview.stepIndex + 1,
                        ),
                      )
                    }
                    className="rounded border border-[#2E3442] bg-[#13151B] p-1 text-xs text-[#ECE9E2] hover:border-[#D99B26]/50 disabled:opacity-40"
                  >
                    <ChevronRight className="h-3.5 w-3.5" />
                  </button>
                </div>
              )}
            </div>
          )}
        </div>
      )}

      <div className="flex items-center justify-between rounded-md border border-[#22252D] bg-[#13151A] px-3 py-1.5 text-xs">
        <div className="flex items-center gap-2">
          <span
            className={`h-2.5 w-2.5 rounded-full border ${
              topColor === 'White'
                ? 'border-zinc-300 bg-[#F4F1EA]'
                : 'border-zinc-500 bg-[#1B1D24]'
            }`}
          />
          <span className="font-semibold text-[#ECE9E2]">{topPlayer}</span>
          <span className="font-mono-code text-[10px] uppercase text-[#858B99]">
            ({topColor})
          </span>
        </div>
        {currentPly && (
          <span className="font-mono-code text-[11px] text-[#9499A6]">
            {isFenOnlyPly
              ? 'Standalone FEN Root'
              : `Move ${currentPly.move_number}${
                  currentPly.turn === 'white' ? '.' : '...'
                } ${currentPly.san_move}`}
          </span>
        )}
      </div>

      <div className="relative mx-auto aspect-square w-full max-w-[540px] rounded-lg border border-[#2B2F3A] bg-[#16181F] p-2 shadow-2xl">
        <div
          ref={boardContainerRef}
          data-testid="chessground-board"
          data-fen={displayedFen}
          data-arrows-count={displayedArrows.length}
          className="h-full w-full"
        />
      </div>

      <div className="flex items-center justify-between rounded-md border border-[#22252D] bg-[#13151A] px-3 py-1.5 text-xs">
        <div className="flex items-center gap-2">
          <span
            className={`h-2.5 w-2.5 rounded-full border ${
              bottomColor === 'White'
                ? 'border-zinc-300 bg-[#F4F1EA]'
                : 'border-zinc-500 bg-[#1B1D24]'
            }`}
          />
          <span className="font-semibold text-[#ECE9E2]">{bottomPlayer}</span>
          <span className="font-mono-code text-[10px] uppercase text-[#858B99]">
            ({bottomColor})
          </span>
        </div>

        {displayedArrows.length > 0 && (
          <div className="flex items-center gap-1.5 font-mono-code text-[11px] text-[#E8B042]">
            <Eye className="h-3.5 w-3.5" />
            <span>
              {displayedArrows.length} evidence arrow
              {displayedArrows.length === 1 ? '' : 's'}
            </span>
          </div>
        )}
      </div>

      <div className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-[#22252D] bg-[#13151A] px-3 py-2">
        <div className="flex items-center gap-1">
          <button
            type="button"
            onClick={onFirstPly}
            disabled={!canPrevPly}
            aria-label="First ply"
            className="rounded border border-[#282C37] bg-[#181B22] p-1.5 text-[#ECE9E2] transition hover:border-[#D99B26]/50 disabled:opacity-40"
          >
            <ChevronsLeft className="h-4 w-4" />
          </button>
          <button
            type="button"
            onClick={onPrevPly}
            disabled={!canPrevPly}
            aria-label="Previous ply"
            className="rounded border border-[#282C37] bg-[#181B22] p-1.5 text-[#ECE9E2] transition hover:border-[#D99B26]/50 disabled:opacity-40"
          >
            <ChevronLeft className="h-4 w-4" />
          </button>
          <button
            type="button"
            onClick={onNextPly}
            disabled={!canNextPly}
            aria-label="Next ply"
            className="rounded border border-[#282C37] bg-[#181B22] p-1.5 text-[#ECE9E2] transition hover:border-[#D99B26]/50 disabled:opacity-40"
          >
            <ChevronRight className="h-4 w-4" />
          </button>
          <button
            type="button"
            onClick={onLastPly}
            disabled={!canNextPly}
            aria-label="Last ply"
            className="rounded border border-[#282C37] bg-[#181B22] p-1.5 text-[#ECE9E2] transition hover:border-[#D99B26]/50 disabled:opacity-40"
          >
            <ChevronsRight className="h-4 w-4" />
          </button>
        </div>

        {currentPly && !isFenOnlyPly && (
          <div className="flex items-center rounded-md border border-[#282C37] bg-[#0E1015] p-0.5 text-[11px]">
            <button
              type="button"
              onClick={() => onChangePlyPositionMode('before')}
              className={`rounded px-2 py-1 font-mono-code transition ${
                plyPositionMode === 'before' && !branchPreview
                  ? 'bg-[#D99B26]/25 font-semibold text-[#F4E0B8]'
                  : 'text-[#9499A6] hover:text-[#ECE9E2]'
              }`}
            >
              Pre-Move
            </button>
            <button
              type="button"
              onClick={() => onChangePlyPositionMode('after')}
              className={`rounded px-2 py-1 font-mono-code transition ${
                plyPositionMode === 'after' && !branchPreview
                  ? 'bg-[#D99B26]/25 font-semibold text-[#F4E0B8]'
                  : 'text-[#9499A6] hover:text-[#ECE9E2]'
              }`}
            >
              Post-Move
            </button>
          </div>
        )}

        <button
          type="button"
          onClick={onToggleOrientation}
          aria-label="Flip board orientation"
          className="inline-flex items-center gap-1.5 rounded border border-[#282C37] bg-[#181B22] px-2.5 py-1.5 text-xs font-medium text-[#ECE9E2] transition hover:border-[#D99B26]/50"
        >
          <FlipVertical2 className="h-3.5 w-3.5 text-[#D99B26]" />
          <span>Flip</span>
        </button>
      </div>
    </div>
  );
};
