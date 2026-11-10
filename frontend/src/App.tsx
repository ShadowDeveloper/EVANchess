import React, { useState, useEffect, useCallback, useMemo } from 'react';
import {
  ShieldCheck,
  Plus,
  AlertTriangle,
  Loader2,
  GitBranch,
  Scale,
  Cpu,
} from 'lucide-react';
import type {
  BoardArrow,
  BranchPreviewState,
  ClaimRecord,
  GameDetail,
  GameSummary,
  HealthResponse,
  PlayerColor,
  RealizedSentence,
} from './types/evan';
import {
  fetchGameDetail,
  fetchGames,
  fetchHealth,
  prioritizePlyAnalysis,
  subscribeToGameEvents,
} from './api/client';
import { Header } from './components/Header';
import { ImportModal } from './components/ImportModal';
import { BoardPane } from './components/BoardPane';
import { EvalTimeline } from './components/EvalTimeline';
import { MoveListSidebar } from './components/MoveListSidebar';
import { CommentaryPane } from './components/CommentaryPane';
import { AuditLedgerDrawer } from './components/AuditLedgerDrawer';

const STARTING_FEN =
  'rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1';

export const App: React.FC = () => {
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [isOffline, setIsOffline] = useState<boolean>(false);
  const [games, setGames] = useState<GameSummary[]>([]);
  const [currentGame, setCurrentGame] = useState<GameDetail | null>(null);
  const [selectedPly, setSelectedPly] = useState<number>(0);
  const [plyPositionMode, setPlyPositionMode] = useState<'before' | 'after'>(
    'after',
  );
  const [orientation, setOrientation] = useState<PlayerColor>('white');

  const [isImportOpen, setIsImportOpen] = useState<boolean>(false);
  const [isLedgerOpen, setIsLedgerOpen] = useState<boolean>(false);
  const [isLoadingInitial, setIsLoadingInitial] = useState<boolean>(true);
  const [errorBanner, setErrorBanner] = useState<string | null>(null);

  const [selectedSentenceId, setSelectedSentenceId] = useState<string | null>(
    null,
  );
  const [highlightedClaimIds, setHighlightedClaimIds] = useState<string[]>([]);
  const [branchPreview, setBranchPreview] =
    useState<BranchPreviewState | null>(null);
  const [hoverPreview, setHoverPreview] = useState<BranchPreviewState | null>(
    null,
  );

  const syncGameIntoList = useCallback((detail: GameDetail) => {
    setGames((prev) => {
      const exists = prev.some((g) => g.game_id === detail.game_id);
      if (!exists) {
        return [detail, ...prev];
      }
      return prev.map((g) => (g.game_id === detail.game_id ? detail : g));
    });
  }, []);

  const loadSelectGame = useCallback(
    async (gameId: string) => {
      setErrorBanner(null);
      try {
        const detail = await fetchGameDetail(gameId);
        setCurrentGame(detail);
        if (detail.error) setErrorBanner(detail.error);
        setOrientation(detail.player_color || 'white');
        setBranchPreview(null);
        setHoverPreview(null);
        setSelectedSentenceId(null);
        setHighlightedClaimIds([]);

        const firstCritical =
          detail.critical_plies?.[0] ??
          detail.plies.find((p) => p.is_critical)?.ply ??
          detail.plies[0]?.ply ??
          0;
        setSelectedPly(firstCritical);
        syncGameIntoList(detail);
      } catch (err) {
        setErrorBanner(
          err instanceof Error ? err.message : 'Failed to load game details.',
        );
      }
    },
    [syncGameIntoList],
  );

  useEffect(() => {
    let cancelled = false;

    const bootstrap = async () => {
      setIsLoadingInitial(true);
      try {
        const [healthRes, gamesRes] = await Promise.all([
          fetchHealth(),
          fetchGames(),
        ]);
        if (cancelled) {
          return;
        }
        setHealth(healthRes);
        setIsOffline(false);
        setGames(gamesRes);

        if (gamesRes.length > 0) {
          await loadSelectGame(gamesRes[0].game_id);
        }
      } catch {
        if (!cancelled) {
          setIsOffline(true);
        }
      } finally {
        if (!cancelled) {
          setIsLoadingInitial(false);
        }
      }
    };

    bootstrap();
    return () => {
      cancelled = true;
    };
  }, [loadSelectGame]);

  const streamingGameId = currentGame?.game_id;
  const streamingStatus = currentGame?.analysis_status;
  useEffect(() => {
    if (!streamingGameId) {
      return;
    }
    if (streamingStatus === 'full_complete' || streamingStatus === 'failed') {
      return;
    }

    const unsubscribe = subscribeToGameEvents(streamingGameId, {
      onSnapshot: (updatedGame) => {
        setCurrentGame(updatedGame);
        if (updatedGame.error) setErrorBanner(updatedGame.error);
        syncGameIntoList(updatedGame);
      },
      onComplete: (finalGame) => {
        if (finalGame) {
          setCurrentGame(finalGame);
          syncGameIntoList(finalGame);
        }
      },
      onError: (msg) => {
        setErrorBanner(msg);
      },
    });

    return () => {
      unsubscribe();
    };
  }, [
    streamingGameId,
    streamingStatus,
    syncGameIntoList,
  ]);

  const plies = useMemo(() => currentGame?.plies ?? [], [currentGame?.plies]);
  const currentPlyObj =
    plies.find((p) => p.ply === selectedPly) ?? plies[0] ?? null;

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      const target = e.target as HTMLElement | null;
      if (
        target &&
        (target.tagName === 'INPUT' ||
          target.tagName === 'TEXTAREA' ||
          target.tagName === 'SELECT')
      ) {
        return;
      }
      if (!plies.length) {
        return;
      }
      const idx = plies.findIndex((p) => p.ply === selectedPly);
      if (e.key === 'ArrowLeft' && idx > 0) {
        e.preventDefault();
        setBranchPreview(null);
        setSelectedPly(plies[idx - 1].ply);
      } else if (e.key === 'ArrowRight' && idx < plies.length - 1) {
        e.preventDefault();
        setBranchPreview(null);
        setSelectedPly(plies[idx + 1].ply);
      } else if (e.key === 'Escape' && branchPreview) {
        setBranchPreview(null);
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [plies, selectedPly, branchPreview]);

  const buildPreviewFromSentence = (
    sentence: RealizedSentence,
  ): BranchPreviewState => {
    const ledger = currentPlyObj?.ledger;
    const branchId = sentence.branch_id || 'root';
    const pvSan = ledger?.branch_pv_san_map?.[branchId] ?? [];
    const stateFens = ledger?.branch_fens_map?.[branchId] ?? [];
    const fallbackFen =
      currentPlyObj?.fen_before ||
      currentPlyObj?.fen_after ||
      currentGame?.fen_root ||
      STARTING_FEN;
    const previewFen = sentence.preview_fen || stateFens[0] || fallbackFen;

    const matchedStep = stateFens.findIndex((f) => f === previewFen);
    const stepIndex = matchedStep >= 0 ? matchedStep : 0;

    return {
      sourceSentenceId: sentence.sentence_id,
      sourceClaimIds: sentence.claim_ids,
      branchId,
      fen: previewFen,
      arrows: sentence.arrows ?? [],
      pvSan,
      stateFens: stateFens.length > 0 ? stateFens : [previewFen],
      stepIndex,
    };
  };

  const handleSelectSentence = (sentence: RealizedSentence) => {
    const preview = buildPreviewFromSentence(sentence);
    setBranchPreview(preview);
    setSelectedSentenceId(sentence.sentence_id);
    setHighlightedClaimIds(sentence.claim_ids);
    setIsLedgerOpen(true);
  };

  const handleHoverSentence = (sentence: RealizedSentence | null) => {
    if (!sentence) {
      setHoverPreview(null);
      return;
    }
    setHoverPreview(buildPreviewFromSentence(sentence));
  };

  const handleSelectClaimFromLedger = (claim: ClaimRecord) => {
    const ledger = currentPlyObj?.ledger;
    const pvSan = ledger?.branch_pv_san_map?.[claim.branch_id] ?? [];
    const stateFens = ledger?.branch_fens_map?.[claim.branch_id] ?? [];
    const previewFen =
      claim.preview_fen ||
      stateFens[0] ||
      currentPlyObj?.fen_before ||
      STARTING_FEN;
    const matchedStep = stateFens.findIndex((f) => f === previewFen);

    setHighlightedClaimIds([claim.claim_id]);
    setBranchPreview({
      sourceClaimIds: [claim.claim_id],
      branchId: claim.branch_id,
      fen: previewFen,
      arrows: claim.arrows ?? [],
      pvSan,
      stateFens: stateFens.length > 0 ? stateFens : [previewFen],
      stepIndex: matchedStep >= 0 ? matchedStep : 0,
    });
  };

  const handleStepBranchPreview = (stepIndex: number) => {
    setBranchPreview((prev) => {
      if (!prev) {
        return null;
      }
      const nextFen = prev.stateFens[stepIndex] || prev.fen;
      return {
        ...prev,
        stepIndex,
        fen: nextFen,
        arrows: [],
      };
    });
  };

  const handleSelectPly = (ply: number) => {
    setSelectedPly(ply);
    setBranchPreview(null);
    setHoverPreview(null);
    setSelectedSentenceId(null);
    setHighlightedClaimIds([]);
  };

  const handlePrioritizePly = async (ply: number) => {
    if (!currentGame) {
      return;
    }
    try {
      const res = await prioritizePlyAnalysis(currentGame.game_id, ply);
      if (res.game) {
        setCurrentGame(res.game);
        syncGameIntoList(res.game);
      } else {
        const refreshed = await fetchGameDetail(currentGame.game_id);
        setCurrentGame(refreshed);
        syncGameIntoList(refreshed);
      }
    } catch (err) {
      setErrorBanner(
        err instanceof Error ? err.message : 'Failed to prioritize ply.',
      );
    }
  };

  const handleImported = (newGame: GameDetail) => {
    setCurrentGame(newGame);
    setOrientation(newGame.player_color || 'white');
    setBranchPreview(null);
    setHoverPreview(null);
    setSelectedSentenceId(null);
    setHighlightedClaimIds([]);
    const firstCritical =
      newGame.critical_plies?.[0] ??
      newGame.plies.find((p) => p.is_critical)?.ply ??
      newGame.plies[0]?.ply ??
      0;
    setSelectedPly(firstCritical);
    syncGameIntoList(newGame);
  };

  const activePreview = branchPreview ?? hoverPreview;
  const baseFen = currentPlyObj
    ? plyPositionMode === 'before'
      ? currentPlyObj.fen_before
      : currentPlyObj.fen_after
    : currentGame?.fen_root || STARTING_FEN;

  const defaultArrows: BoardArrow[] = [];
  if (
    !activePreview &&
    currentPlyObj &&
    currentPlyObj.uci_move &&
    currentPlyObj.uci_move.length >= 4
  ) {
    defaultArrows.push({
      orig: currentPlyObj.uci_move.slice(0, 2),
      dest: currentPlyObj.uci_move.slice(2, 4),
      brush: 'yellow',
    });
  }

  const currentIdx = plies.findIndex((p) => p.ply === selectedPly);
  const canPrevPly = currentIdx > 0;
  const canNextPly = currentIdx >= 0 && currentIdx < plies.length - 1;

  return (
    <div className="min-h-screen bg-[#0B0C0E] text-[#ECE9E2] flex flex-col">
      <Header
        health={health}
        isOffline={isOffline}
        games={games}
        currentGame={currentGame}
        onSelectGame={loadSelectGame}
        onOpenImport={() => setIsImportOpen(true)}
        onToggleLedgerDrawer={() => setIsLedgerOpen((prev) => !prev)}
        isLedgerOpen={isLedgerOpen}
      />

      {errorBanner && (
        <div
          role="alert"
          className="border-b border-rose-500/35 bg-rose-500/10 px-4 py-2 text-xs text-rose-200"
        >
          <div className="mx-auto flex max-w-[1680px] items-center justify-between gap-2">
            <div className="flex items-center gap-2">
              <AlertTriangle className="h-4 w-4 text-rose-400" />
              <span>{errorBanner}</span>
            </div>
            <button
              type="button"
              onClick={() => setErrorBanner(null)}
              className="font-mono-code text-[11px] underline"
            >
              Dismiss
            </button>
          </div>
        </div>
      )}

      {currentGame && currentGame.warnings && currentGame.warnings.length > 0 && (
        <div className="border-b border-amber-500/30 bg-amber-500/10 px-4 py-1.5 text-xs text-amber-200">
          <div className="mx-auto flex max-w-[1680px] items-center gap-2">
            <AlertTriangle className="h-3.5 w-3.5 shrink-0 text-amber-400" />
            <span>{currentGame.warnings.join(' • ')}</span>
          </div>
        </div>
      )}

      <main className="mx-auto w-full max-w-[1680px] flex-1 px-4 py-5 lg:px-6">
        {isLoadingInitial ? (
          <div className="flex min-h-[65vh] flex-col items-center justify-center gap-3">
            <Loader2 className="h-8 w-8 animate-spin text-[#D99B26]" />
            <p className="font-mono-code text-xs text-[#9499A6]">
              Initializing EVAN Workbench &amp; Checking Stockfish / Ledger Storage...
            </p>
          </div>
        ) : !currentGame ? (
          <div className="mx-auto my-8 max-w-3xl rounded-2xl border border-[#242834] bg-gradient-to-b from-[#13161E] to-[#0E1015] p-8 shadow-2xl">
            <span className="inline-flex items-center gap-1.5 rounded border border-[#D99B26]/40 bg-[#D99B26]/10 px-2.5 py-1 font-mono-code text-[11px] font-semibold uppercase tracking-widest text-[#E8B042]">
              <ShieldCheck className="h-3.5 w-3.5" />
              Branch-Conditioned Provenance Workbench
            </span>
            <h1 className="mt-4 font-editorial text-4xl font-semibold leading-tight text-[#F5F2EB]">
              Chess explanations linked to inspectable evidence, with uncertainty kept in view.
            </h1>
            <p className="mt-3 text-sm leading-relaxed text-[#A7ACB8]">
              EVAN separates engine analysis from prose selection. Each displayed sentence is bound to a typed{' '}
              <code className="font-mono-code text-[#F4E0B8]">ClaimRecord</code>, a legal branch trajectory, and an explicit assertion scope—or openly abstains when deterministic detectors cannot verify a reason.
            </p>

            <div className="mt-6 grid grid-cols-1 gap-3 sm:grid-cols-3">
              <div className="rounded-lg border border-[#232733] bg-[#141720] p-3.5">
                <GitBranch className="h-4 w-4 text-[#D99B26]" />
                <h2 className="mt-2 font-editorial text-base font-semibold text-[#F5F2EB]">
                  Multi-Budget Branch Lock
                </h2>
                <p className="mt-1 text-xs text-[#9499A6]">
                  Root-restricted Stockfish searches across two node budgets expose ranking changes and keep branch provenance explicit.
                </p>
              </div>
              <div className="rounded-lg border border-[#232733] bg-[#141720] p-3.5">
                <Scale className="h-4 w-4 text-[#D99B26]" />
                <h2 className="mt-2 font-editorial text-base font-semibold text-[#F5F2EB]">
                  Legal Challenge Verification
                </h2>
                <p className="mt-1 text-xs text-[#9499A6]">
                  Evaluates top legal defensive replies at ply+2; individual PV events remain conditional examples, not exhaustive refutations.
                </p>
              </div>
              <div className="rounded-lg border border-[#232733] bg-[#141720] p-3.5">
                <Cpu className="h-4 w-4 text-[#D99B26]" />
                <h2 className="mt-2 font-editorial text-base font-semibold text-[#F5F2EB]">
                  Independent Prose Auditor
                </h2>
                <p className="mt-1 text-xs text-[#9499A6]">
                  Scans every SAN token and scope connective, falling back to deterministic templates if an LLM overclaims.
                </p>
              </div>
            </div>

            <div className="mt-7 flex flex-wrap items-center gap-3">
              <button
                type="button"
                onClick={() => setIsImportOpen(true)}
                className="inline-flex items-center gap-2 rounded-lg bg-[#D99B26] px-5 py-2.5 text-sm font-semibold text-[#0B0C0E] shadow-lg transition hover:bg-[#E5AA3A]"
              >
                <Plus className="h-4 w-4 stroke-[2.5]" />
                <span>Import PGN, FEN, or Lichess / Chess.com Game</span>
              </button>
            </div>
          </div>
        ) : (
          <div className="space-y-4">
            <EvalTimeline
              plies={plies}
              selectedPlyIndex={selectedPly}
              onSelectPly={handleSelectPly}
            />

            <div className="grid grid-cols-1 gap-5 lg:grid-cols-12">
              <div className="lg:col-span-5 xl:col-span-5">
                <BoardPane
                  fen={baseFen}
                  orientation={orientation}
                  onToggleOrientation={() =>
                    setOrientation((prev) =>
                      prev === 'white' ? 'black' : 'white',
                    )
                  }
                  currentPly={currentPlyObj}
                  plyPositionMode={plyPositionMode}
                  onChangePlyPositionMode={setPlyPositionMode}
                  arrows={defaultArrows}
                  branchPreview={activePreview}
                  onStepBranchPreview={handleStepBranchPreview}
                  onClearBranchPreview={() => {
                    setBranchPreview(null);
                    setHoverPreview(null);
                  }}
                  canPrevPly={canPrevPly}
                  canNextPly={canNextPly}
                  onFirstPly={() => {
                    if (plies.length > 0) {
                      handleSelectPly(plies[0].ply);
                    }
                  }}
                  onPrevPly={() => {
                    if (canPrevPly) {
                      handleSelectPly(plies[currentIdx - 1].ply);
                    }
                  }}
                  onNextPly={() => {
                    if (canNextPly) {
                      handleSelectPly(plies[currentIdx + 1].ply);
                    }
                  }}
                  onLastPly={() => {
                    if (plies.length > 0) {
                      handleSelectPly(plies[plies.length - 1].ply);
                    }
                  }}
                  whiteName={currentGame.white}
                  blackName={currentGame.black}
                />
              </div>

              <div className="lg:col-span-4 xl:col-span-4">
                <CommentaryPane
                  plyAnalysis={currentPlyObj}
                  selectedSentenceId={selectedSentenceId}
                  activeClaimIds={highlightedClaimIds}
                  onSelectSentence={handleSelectSentence}
                  onHoverSentence={handleHoverSentence}
                  onPrioritizePly={handlePrioritizePly}
                  onOpenLedgerForClaims={(cids) => {
                    setHighlightedClaimIds(cids);
                    setIsLedgerOpen(true);
                  }}
                />
              </div>

              <div className="lg:col-span-3 xl:col-span-3">
                <MoveListSidebar
                  plies={plies}
                  selectedPly={selectedPly}
                  onSelectPly={handleSelectPly}
                  onPrioritizePly={handlePrioritizePly}
                />
              </div>
            </div>
          </div>
        )}
      </main>

      <ImportModal
        isOpen={isImportOpen}
        onClose={() => setIsImportOpen(false)}
        onImported={handleImported}
      />

      <AuditLedgerDrawer
        isOpen={isLedgerOpen}
        onClose={() => setIsLedgerOpen(false)}
        gameId={currentGame?.game_id || ''}
        plyAnalysis={currentPlyObj}
        highlightedClaimIds={highlightedClaimIds}
        onSelectClaim={handleSelectClaimFromLedger}
      />
    </div>
  );
};

export default App;
