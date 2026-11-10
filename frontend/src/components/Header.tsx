import React, { useState, useRef, useEffect } from 'react';
import {
  ShieldCheck,
  AlertTriangle,
  WifiOff,
  FolderOpen,
  Plus,
  Download,
  Scale,
  ChevronDown,
  Activity,
  Sparkles,
  CheckCircle2,
  Clock,
  FileCode2,
} from 'lucide-react';
import type { GameDetail, GameSummary, HealthResponse } from '../types/evan';
import { getExportLedgerUrl, getExportPgnUrl } from '../api/client';

interface HeaderProps {
  health: HealthResponse | null;
  isOffline: boolean;
  games: GameSummary[];
  currentGame: GameDetail | null;
  onSelectGame: (gameId: string) => void;
  onOpenImport: () => void;
  onToggleLedgerDrawer: () => void;
  isLedgerOpen: boolean;
}

function formatStatusLabel(status: string): {
  label: string;
  tone: string;
  pulse: boolean;
} {
  switch (status) {
    case 'pending':
      return {
        label: 'Queued',
        tone: 'text-amber-300 border-amber-500/40 bg-amber-500/10',
        pulse: true,
      };
    case 'auto_analyzing':
      return {
        label: 'Stage A · Critical Moments',
        tone: 'text-amber-300 border-amber-500/40 bg-amber-500/10',
        pulse: true,
      };
    case 'auto_complete':
      return {
        label: 'Critical Moments Ready',
        tone: 'text-emerald-300 border-emerald-500/40 bg-emerald-500/10',
        pulse: false,
      };
    case 'full_analyzing':
      return {
        label: 'Stage B · Full-Game Queue',
        tone: 'text-sky-300 border-sky-500/40 bg-sky-500/10',
        pulse: true,
      };
    case 'full_complete':
      return {
        label: 'Full Game Audited',
        tone: 'text-emerald-300 border-emerald-500/40 bg-emerald-500/10',
        pulse: false,
      };
    case 'failed':
      return {
        label: 'Analysis Failed',
        tone: 'text-rose-300 border-rose-500/40 bg-rose-500/10',
        pulse: false,
      };
    default:
      return {
        label: status,
        tone: 'text-zinc-300 border-zinc-700 bg-zinc-800/70',
        pulse: false,
      };
  }
}

export const Header: React.FC<HeaderProps> = ({
  health,
  isOffline,
  games,
  currentGame,
  onSelectGame,
  onOpenImport,
  onToggleLedgerDrawer,
  isLedgerOpen,
}) => {
  const [libraryOpen, setLibraryOpen] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (
        dropdownRef.current &&
        !dropdownRef.current.contains(event.target as Node)
      ) {
        setLibraryOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const statusMeta = currentGame
    ? formatStatusLabel(currentGame.analysis_status)
    : null;

  const auditedCount = currentGame
    ? currentGame.plies.filter(
        (p) => p.deep_status === 'completed' || p.deep_status === 'abstained',
      ).length
    : 0;
  const totalPlies = currentGame ? currentGame.plies.length : 0;

  return (
    <header className="sticky top-0 z-30 border-b border-[#22252D] bg-[#0B0C0E]/95 backdrop-blur-md">
      <div className="mx-auto flex max-w-[1680px] flex-wrap items-center justify-between gap-3 px-4 py-2.5 lg:px-6">
        <div className="flex min-w-0 max-w-full flex-wrap items-center gap-4">
          <div className="flex items-center gap-2.5">
            <div className="flex h-9 w-9 items-center justify-center rounded-md border border-[#D99B26]/50 bg-gradient-to-br from-[#D99B26]/25 to-[#D99B26]/5 text-[#E8B042] shadow-inner">
              <ShieldCheck className="h-5 w-5" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <span className="font-editorial text-xl font-semibold tracking-tight text-[#F5F2EB]">
                  EVAN
                </span>
                <span className="rounded border border-[#D99B26]/30 bg-[#D99B26]/10 px-1.5 py-0.5 font-mono-code text-[10px] font-medium uppercase tracking-widest text-[#E8B042]">
                  Audited Workbench
                </span>
              </div>
              <p className="hidden text-[11px] text-[#9499A6] sm:block">
                Evidence-Verified Analysis &amp; Narration
              </p>
            </div>
          </div>

          <div className="h-6 w-px bg-[#22252D] hidden md:block" />

          <div className="relative" ref={dropdownRef}>
            <button
              type="button"
              onClick={() => setLibraryOpen((prev) => !prev)}
              aria-expanded={libraryOpen}
              aria-label="Open game library"
              className="flex items-center gap-2 rounded-md border border-[#262932] bg-[#13151A] px-3 py-1.5 text-xs font-medium text-[#ECE9E2] transition hover:border-[#D99B26]/50 hover:bg-[#191C23]"
            >
              <FolderOpen className="h-3.5 w-3.5 text-[#D99B26]" />
              <span className="max-w-[180px] truncate sm:max-w-[240px]">
                {currentGame
                  ? `${currentGame.white} vs ${currentGame.black}`
                  : 'Game Library'}
              </span>
              <span className="rounded bg-[#22252D] px-1.5 py-0.5 font-mono-code text-[10px] text-[#9499A6]">
                {games.length}
              </span>
              <ChevronDown className="h-3.5 w-3.5 text-[#9499A6]" />
            </button>

            {libraryOpen && (
              <div
                role="menu"
                aria-label="Imported Games Library"
                className="absolute left-0 mt-2 w-80 sm:w-96 rounded-lg border border-[#2A2E39] bg-[#13151A] p-2 shadow-2xl z-50"
              >
                <div className="mb-2 flex items-center justify-between border-b border-[#22252D] px-2 pb-1.5">
                  <span className="font-mono-code text-[11px] uppercase tracking-wider text-[#9499A6]">
                    Stored Game Ledgers ({games.length})
                  </span>
                  <button
                    type="button"
                    onClick={() => {
                      setLibraryOpen(false);
                      onOpenImport();
                    }}
                    className="text-[11px] font-medium text-[#D99B26] hover:underline"
                  >
                    + New Import
                  </button>
                </div>

                {games.length === 0 ? (
                  <div className="py-6 text-center text-xs text-[#9499A6]">
                    No games in library yet. Import a PGN, FEN, or Lichess/Chess.com game.
                  </div>
                ) : (
                  <div className="max-h-80 space-y-1 overflow-y-auto pr-1">
                    {games.map((g) => {
                      const isSelected = currentGame?.game_id === g.game_id;
                      const badge = formatStatusLabel(g.analysis_status);
                      return (
                        <button
                          key={g.game_id}
                          type="button"
                          onClick={() => {
                            onSelectGame(g.game_id);
                            setLibraryOpen(false);
                          }}
                          className={`w-full rounded-md border p-2.5 text-left transition ${
                            isSelected
                              ? 'border-[#D99B26]/60 bg-[#D99B26]/10'
                              : 'border-transparent bg-[#171A21]/60 hover:border-[#2C313C] hover:bg-[#1C2029]'
                          }`}
                        >
                          <div className="flex items-center justify-between gap-2">
                            <span className="truncate text-xs font-semibold text-[#F4F1EA]">
                              {g.white} vs {g.black}
                            </span>
                            <span className="font-mono-code text-[10px] text-[#9499A6]">
                              {g.result}
                            </span>
                          </div>
                          <div className="mt-1.5 flex items-center justify-between gap-2 text-[11px] text-[#9499A6]">
                            <span className="truncate">
                              {g.event || g.platform.toUpperCase()} · {g.target_rating} Elo
                            </span>
                            <span
                              className={`inline-flex items-center gap-1 rounded border px-1.5 py-0.5 text-[10px] font-medium ${badge.tone}`}
                            >
                              {g.analysis_status === 'full_complete' ? (
                                <CheckCircle2 className="h-2.5 w-2.5" />
                              ) : (
                                <Clock className="h-2.5 w-2.5" />
                              )}
                              {badge.label}
                            </span>
                          </div>
                        </button>
                      );
                    })}
                  </div>
                )}
              </div>
            )}
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-2.5">
          {isOffline && (
            <div
              role="status"
              className="flex items-center gap-1.5 rounded-md border border-rose-500/40 bg-rose-500/10 px-2.5 py-1 text-xs font-medium text-rose-300"
            >
              <WifiOff className="h-3.5 w-3.5" />
              <span>Backend Offline</span>
            </div>
          )}

          {!isOffline && health && !health.configured && (
            <div
              role="status"
              title={health.configuration_errors.join(' | ')}
              className="flex items-center gap-1.5 rounded-md border border-amber-500/40 bg-amber-500/10 px-2.5 py-1 text-xs font-medium text-amber-300"
            >
              <AlertTriangle className="h-3.5 w-3.5" />
              <span className="max-w-[220px] truncate">
                Config Warning ({health.configuration_errors.length})
              </span>
            </div>
          )}

          {currentGame && statusMeta && (
            <div className="hidden xl:flex items-center gap-2 rounded-md border border-[#262932] bg-[#13151A] px-3 py-1 text-xs">
              <span
                className={`inline-flex items-center gap-1.5 rounded border px-2 py-0.5 font-mono-code text-[11px] ${statusMeta.tone}`}
              >
                {statusMeta.pulse ? (
                  <Activity className="h-3 w-3 animate-pulse" />
                ) : (
                  <Sparkles className="h-3 w-3" />
                )}
                {statusMeta.label}
              </span>
              <span className="font-mono-code text-[11px] text-[#9499A6]">
                {auditedCount}/{totalPlies} plies audited
              </span>
            </div>
          )}

          {currentGame && (
            <div className="flex items-center gap-1.5">
              <a
                href={getExportPgnUrl(currentGame.game_id)}
                download={`${currentGame.game_id}_annotated.pgn`}
                className="inline-flex items-center gap-1.5 rounded-md border border-[#262932] bg-[#13151A] px-2.5 py-1.5 text-xs font-medium text-[#ECE9E2] transition hover:border-[#D99B26]/50 hover:text-[#F4E0B8]"
                title="Download Annotated PGN with [%evan_claim_ids]"
              >
                <Download className="h-3.5 w-3.5 text-[#D99B26]" />
                <span className="hidden sm:inline">PGN</span>
              </a>
              <a
                href={getExportLedgerUrl(currentGame.game_id)}
                download={`${currentGame.game_id}_ledger.json`}
                className="inline-flex items-center gap-1.5 rounded-md border border-[#262932] bg-[#13151A] px-2.5 py-1.5 text-xs font-medium text-[#ECE9E2] transition hover:border-[#D99B26]/50 hover:text-[#F4E0B8]"
                title="Download Full JSON Claim & Evidence Ledger"
              >
                <FileCode2 className="h-3.5 w-3.5 text-[#D99B26]" />
                <span className="hidden sm:inline">Ledger JSON</span>
              </a>
              <button
                type="button"
                onClick={onToggleLedgerDrawer}
                aria-expanded={isLedgerOpen}
                className={`inline-flex items-center gap-1.5 rounded-md border px-3 py-1.5 text-xs font-semibold transition ${
                  isLedgerOpen
                    ? 'border-[#D99B26] bg-[#D99B26]/20 text-[#F4E0B8]'
                    : 'border-[#262932] bg-[#13151A] text-[#ECE9E2] hover:border-[#D99B26]/50'
                }`}
              >
                <Scale className="h-3.5 w-3.5 text-[#D99B26]" />
                <span>Audit Ledger</span>
              </button>
            </div>
          )}

          <button
            type="button"
            onClick={onOpenImport}
            className="inline-flex items-center gap-1.5 rounded-md bg-[#D99B26] px-3.5 py-1.5 text-xs font-semibold text-[#0B0C0E] shadow-sm transition hover:bg-[#E5AA3A]"
          >
            <Plus className="h-4 w-4 stroke-[2.5]" />
            <span>Import Game</span>
          </button>
        </div>
      </div>

      {!isOffline && health && !health.configured && health.configuration_errors.length > 0 && (
        <div className="border-t border-amber-500/30 bg-amber-500/10 px-4 py-1.5 text-xs text-amber-200">
          <div className="mx-auto flex max-w-[1680px] flex-wrap items-center justify-between gap-2">
            <div className="flex items-center gap-2">
              <AlertTriangle className="h-3.5 w-3.5 shrink-0 text-amber-400" />
              <span>
                <strong>Configuration Notice:</strong>{' '}
                {health.configuration_errors.join(' • ')}
              </span>
            </div>
            <span className="font-mono-code text-[11px] text-amber-300/80">
              Copy .env.example to .env, set the selected provider’s live API key, then restart the server. Missing keys block analysis.
            </span>
          </div>
        </div>
      )}
    </header>
  );
};
