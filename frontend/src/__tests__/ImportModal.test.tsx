import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { ImportModal } from '../components/ImportModal';
import * as apiClient from '../api/client';
import type { GameDetail } from '../types/evan';

vi.mock('../api/client', async () => {
  const actual = await vi.importActual<typeof import('../api/client')>('../api/client');
  return {
    ...actual,
    importGame: vi.fn(),
    fetchUserRecentGames: vi.fn(),
  };
});

const mockGameDetail: GameDetail = {
  game_id: 'game_test123',
  created_at: '2026-11-09T00:00:00Z',
  pgn_text: '1. e4 e5',
  fen_root: 'rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1',
  has_full_history: true,
  white: 'ClubPlayer',
  black: 'Opponent',
  result: '1-0',
  event: 'Rated Rapid',
  player_color: 'black',
  target_rating: 1600,
  platform: 'lichess',
  analysis_status: 'auto_analyzing',
  critical_plies: [0],
  warnings: [],
  untrusted_comments: {},
  plies: [],
};

describe('ImportModal', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('switches tabs between PGN/FEN, Lichess, and Chess.com and submits validated payload', async () => {
    const onClose = vi.fn();
    const onImported = vi.fn();
    vi.mocked(apiClient.importGame).mockResolvedValueOnce(mockGameDetail);

    render(
      <ImportModal isOpen={true} onClose={onClose} onImported={onImported} />,
    );

    expect(
      screen.getByRole('heading', { name: /Import Chess Game or FEN Position/i }),
    ).toBeInTheDocument();

    const lichessTab = screen.getByRole('tab', { name: /Lichess/i });
    fireEvent.click(lichessTab);

    const urlInput = screen.getByLabelText(/Lichess Game URL or PGN/i);
    fireEvent.change(urlInput, {
      target: { value: 'https://lichess.org/abcdefgh' },
    });

    const blackBtn = screen.getByRole('button', { name: /^black$/i });
    fireEvent.click(blackBtn);

    const ratingSelect = screen.getByLabelText(/Audience Rating Band/i);
    fireEvent.change(ratingSelect, { target: { value: '1600' } });

    const budgetSelect = screen.getByLabelText(/Engine Budget Profile/i);
    fireEvent.change(budgetSelect, { target: { value: 'deep' } });

    const submitBtn = screen.getByRole('button', {
      name: /Run Audited Analysis/i,
    });
    fireEvent.click(submitBtn);

    await waitFor(() => {
      expect(apiClient.importGame).toHaveBeenCalledWith({
        input: 'https://lichess.org/abcdefgh',
        player_color: 'black',
        target_rating: 1600,
        platform: 'lichess',
        budget_profile: 'deep',
      });
    });

    expect(onImported).toHaveBeenCalledWith(mockGameDetail);
    expect(onClose).toHaveBeenCalled();
  });

  it('fetches recent games by username on Chess.com tab and selects a game', async () => {
    vi.mocked(apiClient.fetchUserRecentGames).mockResolvedValueOnce([
      {
        id: '998877',
        url: 'https://www.chess.com/game/live/998877',
        white: 'OtherPlayer',
        black: 'Hikaru',
        time_class: 'blitz',
        pgn: '1. d4 Nf6 2. c4 e6',
        platform: 'chesscom',
      },
    ]);

    render(
      <ImportModal isOpen={true} onClose={vi.fn()} onImported={vi.fn()} />,
    );

    fireEvent.click(screen.getByRole('tab', { name: /Chess\.com/i }));

    const userField = screen.getByLabelText(
      /Or Fetch Recent Games by Chess\.com Username/i,
    );
    fireEvent.change(userField, { target: { value: 'Hikaru' } });

    fireEvent.click(screen.getByRole('button', { name: /Fetch Games/i }));

    await waitFor(() => {
      expect(apiClient.fetchUserRecentGames).toHaveBeenCalledWith(
        'chesscom',
        'Hikaru',
        10,
      );
    });

    expect(await screen.findByText(/OtherPlayer vs Hikaru/i)).toBeInTheDocument();
  });
});
