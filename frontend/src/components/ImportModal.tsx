import React, { useState, useRef } from 'react';
import {
  X,
  Upload,
  Globe,
  FileText,
  Search,
  Sparkles,
  AlertCircle,
  Loader2,
  Check,
} from 'lucide-react';
import type {
  BudgetProfile,
  GameDetail,
  ImportGamePayload,
  PlayerColor,
  RemotePlatformGame,
} from '../types/evan';
import { fetchUserRecentGames, importGame } from '../api/client';

interface ImportModalProps {
  isOpen: boolean;
  onClose: () => void;
  onImported: (game: GameDetail) => void;
}

type ImportTab = 'pgn' | 'lichess' | 'chesscom';

const SAMPLE_TACTICAL_PGN = `[Event "Audited Workbench Study"]
[Site "Vienna"]
[Date "2026.11.09"]
[White "Tactician"]
[Black "Defender"]
[Result "1-0"]

1. e4 e5 2. Nf3 Nc6 3. Bc4 Nf6 4. Ng5 d5 5. exd5 Nxd5 6. Nxf7 Kxf7 7. Qf3+ Ke6 8. Nc3 Ne7 1-0`;

const SAMPLE_FEN =
  'r3kbnr/pp3ppp/8/3N4/8/8/PPPPPPPP/R1BQKBNR w KQkq - 0 1';

const RATING_BANDS = [1200, 1400, 1500, 1600, 1800, 2000];

export const ImportModal: React.FC<ImportModalProps> = ({
  isOpen,
  onClose,
  onImported,
}) => {
  const [activeTab, setActiveTab] = useState<ImportTab>('pgn');
  const [rawInput, setRawInput] = useState<string>('');
  const [username, setUsername] = useState<string>('');
  const [recentGames, setRecentGames] = useState<RemotePlatformGame[]>([]);
  const [selectedRemoteId, setSelectedRemoteId] = useState<string | null>(null);
  const [playerColor, setPlayerColor] = useState<PlayerColor>('white');
  const [targetRating, setTargetRating] = useState<number>(1500);
  const [budgetProfile, setBudgetProfile] = useState<BudgetProfile>('standard');
  const [isDragging, setIsDragging] = useState<boolean>(false);
  const [isFetchingRecent, setIsFetchingRecent] = useState<boolean>(false);
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [uploadedFilename, setUploadedFilename] = useState<string | null>(null);

  const fileInputRef = useRef<HTMLInputElement>(null);

  if (!isOpen) {
    return null;
  }

  const handleFileContent = (file: File) => {
    setError(null);
    const reader = new FileReader();
    reader.onload = (ev) => {
      const content = typeof ev.target?.result === 'string' ? ev.target.result : '';
      setRawInput(content);
      setUploadedFilename(file.name);
      setActiveTab('pgn');
    };
    reader.onerror = () => {
      setError(`Failed to read file "${file.name}".`);
    };
    reader.readAsText(file);
  };

  const handleDrop = (event: React.DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    setIsDragging(false);
    const file = event.dataTransfer.files?.[0];
    if (file) {
      handleFileContent(file);
    }
  };

  const handleFetchRecent = async () => {
    const cleanUser = username.trim();
    if (!cleanUser) {
      setError('Enter a username to browse recent games.');
      return;
    }
    const platform = activeTab === 'chesscom' ? 'chesscom' : 'lichess';
    setError(null);
    setIsFetchingRecent(true);
    try {
      const games = await fetchUserRecentGames(platform, cleanUser, 10);
      setRecentGames(games);
      if (games.length === 0) {
        setError(`No recent standard games found for "${cleanUser}".`);
      } else {
        const first = games[0];
        setSelectedRemoteId(first.id);
        setRawInput(first.pgn || first.url || first.id);
        if (first.black.toLowerCase() === cleanUser.toLowerCase()) {
          setPlayerColor('black');
        } else if (first.white.toLowerCase() === cleanUser.toLowerCase()) {
          setPlayerColor('white');
        }
      }
    } catch (err) {
      setError(
        err instanceof Error ? err.message : 'Failed to fetch recent games.',
      );
    } finally {
      setIsFetchingRecent(false);
    }
  };

  const handleSelectRemoteGame = (game: RemotePlatformGame) => {
    setSelectedRemoteId(game.id);
    setRawInput(game.pgn || game.url || game.id);
    const cleanUser = username.trim().toLowerCase();
    if (cleanUser && game.black.toLowerCase() === cleanUser) {
      setPlayerColor('black');
    } else if (cleanUser && game.white.toLowerCase() === cleanUser) {
      setPlayerColor('white');
    }
  };

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    const trimmed = rawInput.trim();
    if (!trimmed) {
      setError(
        activeTab === 'pgn'
          ? 'Paste a PGN or FEN string, or upload a .pgn file.'
          : `Enter a ${activeTab === 'lichess' ? 'Lichess' : 'Chess.com'} game URL or pick a recent game.`,
      );
      return;
    }

    setError(null);
    setIsSubmitting(true);

    const payload: ImportGamePayload = {
      input: trimmed,
      player_color: playerColor,
      target_rating: targetRating,
      platform: activeTab,
      budget_profile: budgetProfile,
      ...(username.trim() ? { username: username.trim() } : {}),
    };

    try {
      const created = await importGame(payload);
      onImported(created);
      onClose();
    } catch (err) {
      setError(
        err instanceof Error ? err.message : 'Game import failed. Verify the PGN/FEN or URL.',
      );
    } finally {
      setIsSubmitting(false);
    }
  };

  const switchTab = (tab: ImportTab) => {
    setActiveTab(tab);
    setError(null);
    setRecentGames([]);
    setSelectedRemoteId(null);
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/75 p-4 backdrop-blur-sm"
      role="dialog"
      aria-modal="true"
      aria-labelledby="import-modal-title"
    >
      <div className="relative flex max-h-[92vh] w-full max-w-2xl flex-col overflow-hidden rounded-xl border border-[#2B303C] bg-[#111318] shadow-2xl">
        <div className="flex items-center justify-between border-b border-[#22252D] bg-[#151820] px-6 py-4">
          <div>
            <span className="font-mono-code text-[10px] uppercase tracking-widest text-[#D99B26]">
              Step 1 · Legal Parse &amp; Provenance Quarantine
            </span>
            <h2
              id="import-modal-title"
              className="font-editorial text-2xl font-semibold text-[#F5F2EB]"
            >
              Import Chess Game or FEN Position
            </h2>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close import modal"
            className="rounded-md p-1.5 text-[#9499A6] transition hover:bg-[#22252D] hover:text-[#F5F2EB]"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        <div className="flex border-b border-[#22252D] bg-[#13161D] px-6">
          <button
            type="button"
            role="tab"
            aria-selected={activeTab === 'pgn'}
            onClick={() => switchTab('pgn')}
            className={`flex items-center gap-2 border-b-2 px-4 py-3 text-xs font-semibold transition ${
              activeTab === 'pgn'
                ? 'border-[#D99B26] text-[#F4E0B8]'
                : 'border-transparent text-[#9499A6] hover:text-[#ECE9E2]'
            }`}
          >
            <FileText className="h-3.5 w-3.5" />
            <span>PGN / FEN / File</span>
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={activeTab === 'lichess'}
            onClick={() => switchTab('lichess')}
            className={`flex items-center gap-2 border-b-2 px-4 py-3 text-xs font-semibold transition ${
              activeTab === 'lichess'
                ? 'border-[#D99B26] text-[#F4E0B8]'
                : 'border-transparent text-[#9499A6] hover:text-[#ECE9E2]'
            }`}
          >
            <Globe className="h-3.5 w-3.5" />
            <span>Lichess</span>
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={activeTab === 'chesscom'}
            onClick={() => switchTab('chesscom')}
            className={`flex items-center gap-2 border-b-2 px-4 py-3 text-xs font-semibold transition ${
              activeTab === 'chesscom'
                ? 'border-[#D99B26] text-[#F4E0B8]'
                : 'border-transparent text-[#9499A6] hover:text-[#ECE9E2]'
            }`}
          >
            <Globe className="h-3.5 w-3.5" />
            <span>Chess.com</span>
          </button>
        </div>

        <form
          onSubmit={handleSubmit}
          className="flex-1 space-y-5 overflow-y-auto px-6 py-5"
        >
          {activeTab === 'pgn' && (
            <div className="space-y-3">
              <div
                onDragOver={(e) => {
                  e.preventDefault();
                  setIsDragging(true);
                }}
                onDragLeave={() => setIsDragging(false)}
                onDrop={handleDrop}
                className={`flex flex-wrap items-center justify-between gap-3 rounded-lg border border-dashed px-4 py-3 transition ${
                  isDragging
                    ? 'border-[#D99B26] bg-[#D99B26]/10'
                    : 'border-[#2E3442] bg-[#161921]'
                }`}
              >
                <div className="flex items-center gap-2.5 text-xs text-[#9499A6]">
                  <Upload className="h-4 w-4 text-[#D99B26]" />
                  <span>
                    {uploadedFilename
                      ? `Loaded: ${uploadedFilename}`
                      : 'Drag and drop a .pgn file here, or load a preset'}
                  </span>
                </div>
                <div className="flex items-center gap-2">
                  <input
                    ref={fileInputRef}
                    type="file"
                    accept=".pgn,.txt"
                    aria-label="Upload PGN file"
                    className="hidden"
                    onChange={(e) => {
                      const file = e.target.files?.[0];
                      if (file) {
                        handleFileContent(file);
                      }
                    }}
                  />
                  <button
                    type="button"
                    onClick={() => fileInputRef.current?.click()}
                    className="rounded border border-[#2E3442] bg-[#1E222D] px-2.5 py-1 text-[11px] font-medium text-[#ECE9E2] hover:border-[#D99B26]/50"
                  >
                    Browse .pgn
                  </button>
                  <button
                    type="button"
                    onClick={() => setRawInput(SAMPLE_TACTICAL_PGN)}
                    className="rounded border border-[#D99B26]/40 bg-[#D99B26]/10 px-2.5 py-1 text-[11px] font-medium text-[#F4E0B8] hover:bg-[#D99B26]/20"
                  >
                    Load Sample PGN
                  </button>
                  <button
                    type="button"
                    onClick={() => setRawInput(SAMPLE_FEN)}
                    className="rounded border border-[#2E3442] bg-[#1E222D] px-2.5 py-1 text-[11px] font-medium text-[#ECE9E2] hover:border-[#D99B26]/50"
                  >
                    Load Sample FEN
                  </button>
                </div>
              </div>

              <div>
                <label
                  htmlFor="pgn-fen-textarea"
                  className="mb-1.5 block text-xs font-medium text-[#C5C8D2]"
                >
                  PGN Movetext or Standalone FEN String
                </label>
                <textarea
                  id="pgn-fen-textarea"
                  rows={5}
                  value={rawInput}
                  onChange={(e) => setRawInput(e.target.value)}
                  placeholder="Paste standard PGN (e.g. 1. e4 e5 2. Nf3 Nc6...) or a single-line FEN string..."
                  className="w-full rounded-lg border border-[#2B303C] bg-[#0D0F13] p-3 font-mono-code text-xs text-[#ECE9E2] placeholder-[#5F6575] focus:border-[#D99B26] focus:outline-none"
                />
                <p className="mt-1 text-[11px] text-[#858B99]">
                  Embedded PGN comments are automatically quarantined so they never pollute the evidence ledger.
                </p>
              </div>
            </div>
          )}

          {(activeTab === 'lichess' || activeTab === 'chesscom') && (
            <div className="space-y-4">
              <div>
                <label
                  htmlFor="platform-url-input"
                  className="mb-1.5 block text-xs font-medium text-[#C5C8D2]"
                >
                  {activeTab === 'lichess' ? 'Lichess' : 'Chess.com'} Game URL or PGN
                </label>
                <input
                  id="platform-url-input"
                  type="text"
                  value={rawInput}
                  onChange={(e) => setRawInput(e.target.value)}
                  placeholder={
                    activeTab === 'lichess'
                      ? 'https://lichess.org/abcdefgh or game PGN'
                      : 'https://www.chess.com/game/live/123456789'
                  }
                  className="w-full rounded-lg border border-[#2B303C] bg-[#0D0F13] px-3.5 py-2.5 font-mono-code text-xs text-[#ECE9E2] placeholder-[#5F6575] focus:border-[#D99B26] focus:outline-none"
                />
              </div>

              <div className="rounded-lg border border-[#262A34] bg-[#151821] p-3.5">
                <label
                  htmlFor="platform-username-input"
                  className="mb-1.5 block text-xs font-medium text-[#C5C8D2]"
                >
                  Or Fetch Recent Games by {activeTab === 'lichess' ? 'Lichess' : 'Chess.com'} Username
                </label>
                <div className="flex gap-2">
                  <input
                    id="platform-username-input"
                    type="text"
                    value={username}
                    onChange={(e) => setUsername(e.target.value)}
                    placeholder={
                      activeTab === 'lichess' ? 'e.g. DrNykterstein' : 'e.g. Hikaru'
                    }
                    className="flex-1 rounded-md border border-[#2B303C] bg-[#0D0F13] px-3 py-2 text-xs text-[#ECE9E2] placeholder-[#5F6575] focus:border-[#D99B26] focus:outline-none"
                  />
                  <button
                    type="button"
                    onClick={handleFetchRecent}
                    disabled={isFetchingRecent}
                    className="inline-flex items-center gap-1.5 rounded-md border border-[#D99B26]/50 bg-[#D99B26]/15 px-3.5 py-2 text-xs font-semibold text-[#F4E0B8] transition hover:bg-[#D99B26]/25 disabled:opacity-50"
                  >
                    {isFetchingRecent ? (
                      <Loader2 className="h-3.5 w-3.5 animate-spin" />
                    ) : (
                      <Search className="h-3.5 w-3.5" />
                    )}
                    <span>Fetch Games</span>
                  </button>
                </div>

                {recentGames.length > 0 && (
                  <div className="mt-3 max-h-40 space-y-1.5 overflow-y-auto pr-1">
                    {recentGames.map((g) => {
                      const isSel = selectedRemoteId === g.id;
                      return (
                        <button
                          key={g.id}
                          type="button"
                          onClick={() => handleSelectRemoteGame(g)}
                          className={`flex w-full items-center justify-between rounded border px-3 py-2 text-left text-xs transition ${
                            isSel
                              ? 'border-[#D99B26] bg-[#D99B26]/15 text-[#F4E0B8]'
                              : 'border-[#252933] bg-[#101218] text-[#ECE9E2] hover:border-[#394050]'
                          }`}
                        >
                          <div className="truncate">
                            <span className="font-semibold">
                              {g.white} vs {g.black}
                            </span>
                            <span className="ml-2 font-mono-code text-[10px] text-[#9499A6]">
                              {g.speed || g.time_class || g.platform}
                            </span>
                          </div>
                          {isSel && <Check className="h-3.5 w-3.5 shrink-0 text-[#D99B26]" />}
                        </button>
                      );
                    })}
                  </div>
                )}
              </div>
            </div>
          )}

          <div className="grid grid-cols-1 gap-4 border-t border-[#22252D] pt-4 sm:grid-cols-3">
            <div>
              <span className="mb-1.5 block text-xs font-medium text-[#C5C8D2]">
                Perspective / Player Color
              </span>
              <div className="grid grid-cols-2 gap-1.5 rounded-lg border border-[#2B303C] bg-[#0D0F13] p-1">
                {(['white', 'black'] as PlayerColor[]).map((col) => (
                  <button
                    key={col}
                    type="button"
                    onClick={() => setPlayerColor(col)}
                    aria-pressed={playerColor === col}
                    className={`rounded-md py-1.5 text-xs font-semibold capitalize transition ${
                      playerColor === col
                        ? 'bg-[#D99B26] text-[#0B0C0E]'
                        : 'text-[#9499A6] hover:text-[#ECE9E2]'
                    }`}
                  >
                    {col}
                  </button>
                ))}
              </div>
            </div>

            <div>
              <label
                htmlFor="target-rating-select"
                className="mb-1.5 block text-xs font-medium text-[#C5C8D2]"
              >
                Audience Rating Band
              </label>
              <select
                id="target-rating-select"
                value={targetRating}
                onChange={(e) => setTargetRating(Number(e.target.value))}
                className="w-full rounded-lg border border-[#2B303C] bg-[#0D0F13] px-3 py-2 text-xs font-medium text-[#ECE9E2] focus:border-[#D99B26] focus:outline-none"
              >
                {RATING_BANDS.map((rating) => (
                  <option key={rating} value={rating}>
                    {rating} Elo {rating === 1500 ? '(Club Default)' : ''}
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label
                htmlFor="budget-profile-select"
                className="mb-1.5 block text-xs font-medium text-[#C5C8D2]"
              >
                Engine Budget Profile
              </label>
              <select
                id="budget-profile-select"
                value={budgetProfile}
                onChange={(e) => setBudgetProfile(e.target.value as BudgetProfile)}
                className="w-full rounded-lg border border-[#2B303C] bg-[#0D0F13] px-3 py-2 text-xs font-medium text-[#ECE9E2] focus:border-[#D99B26] focus:outline-none"
              >
                <option value="quick">Quick (Fast Triage)</option>
                <option value="standard">Standard (75k / 150k Nodes)</option>
                <option value="deep">Deep (Extended Verification)</option>
              </select>
            </div>
          </div>

          {error && (
            <div
              role="alert"
              className="flex items-start gap-2 rounded-lg border border-rose-500/40 bg-rose-500/10 p-3 text-xs text-rose-200"
            >
              <AlertCircle className="mt-0.5 h-4 w-4 shrink-0 text-rose-400" />
              <span>{error}</span>
            </div>
          )}

          <div className="flex items-center justify-end gap-3 border-t border-[#22252D] pt-4">
            <button
              type="button"
              onClick={onClose}
              className="rounded-lg border border-[#2B303C] bg-[#161922] px-4 py-2 text-xs font-semibold text-[#C5C8D2] hover:bg-[#1E222E]"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={isSubmitting}
              className="inline-flex items-center gap-2 rounded-lg bg-[#D99B26] px-5 py-2 text-xs font-semibold text-[#0B0C0E] shadow-md transition hover:bg-[#E5AA3A] disabled:opacity-50"
            >
              {isSubmitting ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin" />
                  <span>Validating &amp; Starting Pipeline...</span>
                </>
              ) : (
                <>
                  <Sparkles className="h-4 w-4" />
                  <span>Run Audited Analysis</span>
                </>
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
