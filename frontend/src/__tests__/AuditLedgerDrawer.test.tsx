import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { AuditLedgerDrawer } from '../components/AuditLedgerDrawer';
import type { PlyAnalysis } from '../types/evan';

const plyWithFullLedger: PlyAnalysis = {
  game_id: 'game_ledger_99',
  ply: 6,
  move_number: 4,
  turn: 'white',
  uci_move: 'f3g5',
  san_move: 'Ng5',
  fen_before: 'r1bqkb1r/pppp1ppp/2n2n2/4p3/2B1P3/5N2/PPPP1PPP/RNBQK2R w KQkq - 4 4',
  fen_after: 'r1bqkb1r/pppp1ppp/2n2n2/4p1N1/2B1P3/8/PPPP1PPP/RNBQK2R b KQkq - 5 4',
  state_before_hash: 'hb',
  state_after_hash: 'ha',
  coarse_eval_cp_white: 40,
  coarse_mate_white: null,
  coarse_eval_after_cp_white: 45,
  coarse_mate_after_white: null,
  eval_swing_cp: 5,
  critical_score: 30,
  critical_reason: { primary_reason: 'Tactical transition' },
  is_critical: true,
  deep_status: 'completed',
  commentary: {
    sentences: [],
  },
  ledger: {
    ply: 6,
    move_number: 4,
    turn: 'white',
    played_san: 'Ng5',
    best_san: 'Ng5',
    root_fen: 'r1bqkb1r/pppp1ppp/2n2n2/4p3/2B1P3/5N2/PPPP1PPP/RNBQK2R w KQkq - 4 4',
    stability_status: 'stable',
    claims: [
      {
        claim_id: 'clm_target_1',
        type: 'conditional_line_event',
        proposition: 'Across top analyzed defenses, White captures on f7.',
        root_state_id: 'st_0',
        branch_id: 'br_p6_played_f3g5',
        applicable_state_ids: ['st_1'],
        support_evidence_ids: ['ev_br_p6_played_f3g5_ply1_capture_g5f7'],
        evidence_source: 'replay_detector',
        assertion_scope: 'across_analyzed_defenses_at_budget',
        line_event_plies: [1],
        challenge_queries: ['chal_br_p6_played_f3g5'],
        discovered_contradictions: [],
        unresolved_questions: [],
        status: 'assert',
        preview_fen: 'r1bqkb1r/pppp1ppp/2n2n2/4p1N1/2B1P3/8/PPPP1PPP/RNBQK2R b KQkq - 5 4',
        arrows: [{ orig: 'g5', dest: 'f7', brush: 'yellow' }],
      },
    ],
    branch_pv_san_map: {
      br_p6_played_f3g5: ['Ng5', 'd5', 'exd5'],
    },
    branch_fens_map: {
      br_p6_played_f3g5: [
        'r1bqkb1r/pppp1ppp/2n2n2/4p3/2B1P3/5N2/PPPP1PPP/RNBQK2R w KQkq - 4 4',
      ],
    },
    challenge_outcomes: [
      {
        query_id: 'chal_br_p6_played_f3g5',
        branch_id: 'br_p6_played_f3g5',
        challenged_at_ply_offset: 2,
        opponent_punishing_move_san: 'd5',
        defenses_tested: [
          {
            defense_uci: 'e4d5',
            defense_san: 'exd5',
            eval_cp_original_mover: 45,
            pv_san: ['exd5', 'Na5'],
          },
        ],
        refutation_holds_across_top_defenses: true,
        discovered_contradictions: [],
        recommended_scope: 'across_analyzed_defenses_at_budget',
      },
    ],
    engine_metadata: [
      {
        engine_name: 'Stockfish 17',
        engine_path: '/usr/bin/stockfish',
        threads: 1,
        hash_mb: 64,
        root_fen: 'r1bqkb1r/pppp1ppp/2n2n2/4p3/2B1P3/5N2/PPPP1PPP/RNBQK2R w KQkq - 4 4',
        root_state_hash: 'hb',
        uci_history: [],
        multipv_index: 1,
        node_limit: 150000,
        reported_nodes: 150120,
        depth: 18,
        seldepth: 26,
        score_cp_white: 45,
        score_cp_mover: 45,
        wdl_white: [380, 510, 110],
        pv_uci: ['f3g5', 'd7d5', 'e4d5'],
        pv_san: ['Ng5', 'd5', 'exd5'],
      },
    ],
    audit_log: [
      {
        stage: 'prose_audit',
        passed: true,
        details: 'All SAN tokens and scope connectives verified.',
      },
    ],
    evidence_graph: {
      ply: 6,
      root_fen: 'r1bqkb1r/pppp1ppp/2n2n2/4p3/2B1P3/5N2/PPPP1PPP/RNBQK2R w KQkq - 4 4',
      branch_traces: {
        br_p6_played_f3g5: {
          branch_id: 'br_p6_played_f3g5',
          root_fen: 'r1bqkb1r/pppp1ppp/2n2n2/4p3/2B1P3/5N2/PPPP1PPP/RNBQK2R w KQkq - 4 4',
          root_move_uci: 'f3g5',
          root_move_san: 'Ng5',
          pv_uci: ['f3g5', 'd7d5'],
          pv_san: ['Ng5', 'd5'],
          state_fens: [],
          state_ids: ['st_0', 'st_1'],
          legal_sans_in_branch: ['Ng5', 'd5'],
          net_material_delta_mover: 100,
          events: [
            {
              evidence_id: 'ev_br_p6_played_f3g5_ply1_capture_g5f7',
              branch_id: 'br_p6_played_f3g5',
              ply_offset: 1,
              state_id: 'st_1',
              fen: 'r1bqkb1r/pppp1ppp/2n2n2/4p1N1/2B1P3/8/PPPP1PPP/RNBQK2R b KQkq - 5 4',
              move_uci: 'g5f7',
              move_san: 'Nxf7',
              mover_color: 'white',
              event_type: 'capture',
              description: 'White captures the pawn on f7 with Nxf7.',
              squares: ['g5', 'f7'],
              arrows: [{ orig: 'g5', dest: 'f7', brush: 'yellow' }],
              material_delta_mover_cp: 100,
            },
          ],
        },
      },
    },
  },
};

describe('AuditLedgerDrawer', () => {
  it('highlights cited claims and backing evidence items and renders engine/challenge/audit sections and export links', () => {
    const onSelectClaim = vi.fn();

    render(
      <AuditLedgerDrawer
        isOpen={true}
        onClose={vi.fn()}
        gameId="game_ledger_99"
        plyAnalysis={plyWithFullLedger}
        highlightedClaimIds={['clm_target_1']}
        onSelectClaim={onSelectClaim}
      />,
    );

    const claimCard = screen.getByTestId('ledger-claim-clm_target_1');
    expect(claimCard).toHaveAttribute('data-highlighted', 'true');

    const evidenceCard = screen.getByTestId(
      'ledger-evidence-ev_br_p6_played_f3g5_ply1_capture_g5f7',
    );
    expect(evidenceCard).toHaveAttribute('data-highlighted', 'true');

    expect(screen.getByText(/Stockfish 17/i)).toBeInTheDocument();
    expect(screen.getByText(/chal_br_p6_played_f3g5/i)).toBeInTheDocument();
    expect(screen.getByText('prose_audit', { exact: true })).toBeInTheDocument();

    const pgnLink = screen.getByRole('link', { name: /Export PGN/i });
    expect(pgnLink).toHaveAttribute(
      'href',
      '/api/games/game_ledger_99/export/pgn',
    );

    const ledgerLink = screen.getByRole('link', {
      name: /Export Ledger JSON/i,
    });
    expect(ledgerLink).toHaveAttribute(
      'href',
      '/api/games/game_ledger_99/export/ledger',
    );

    fireEvent.click(claimCard);
    expect(onSelectClaim).toHaveBeenCalledTimes(1);
  });
});
