import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { CommentaryPane } from '../components/CommentaryPane';
import type { PlyAnalysis, RealizedSentence } from '../types/evan';

const samplePlyWithCommentary: PlyAnalysis = {
  game_id: 'game_1',
  ply: 4,
  move_number: 3,
  turn: 'white',
  uci_move: 'd5c7',
  san_move: 'Nc7+',
  fen_before: 'r3kbnr/pp3ppp/8/3N4/8/8/PPPPPPPP/R1BQKBNR w KQkq - 0 1',
  fen_after: 'r3kbnr/ppN2ppp/8/8/8/8/PPPPPPPP/R1BQKBNR b KQkq - 1 1',
  state_before_hash: 'h1',
  state_after_hash: 'h2',
  coarse_eval_cp_white: 450,
  coarse_mate_white: null,
  coarse_eval_after_cp_white: 520,
  coarse_mate_after_white: null,
  eval_swing_cp: 70,
  critical_score: 48.5,
  critical_reason: {
    primary_reason: 'Critical sharp choice (280 cp gap between top moves)',
  },
  is_critical: true,
  deep_status: 'completed',
  ledger: {
    ply: 4,
    move_number: 3,
    turn: 'white',
    played_san: 'Nc7+',
    best_san: 'Nc7+',
    root_fen: 'r3kbnr/pp3ppp/8/3N4/8/8/PPPPPPPP/R1BQKBNR w KQkq - 0 1',
    stability_status: 'stable',
    claims: [
      {
        claim_id: 'clm_fork_1',
        type: 'motif',
        proposition:
          'In the analyzed continuation after Nc7+, Nc7+ creates a double attack from c7 against king on e8 and rook on a8.',
        root_state_id: 'st_0',
        branch_id: 'br_p4_played_d5c7',
        applicable_state_ids: ['st_1'],
        support_evidence_ids: ['ev_br_p4_played_d5c7_ply1_double_attack_d5c7'],
        evidence_source: 'replay_detector',
        assertion_scope: 'in_displayed_continuation',
        line_event_plies: [1],
        challenge_queries: [],
        discovered_contradictions: [],
        unresolved_questions: [],
        status: 'assert',
        preview_fen: 'r3kbnr/ppN2ppp/8/8/8/8/PPPPPPPP/R1BQKBNR b KQkq - 1 1',
        arrows: [
          { orig: 'c7', dest: 'e8', brush: 'red' },
          { orig: 'c7', dest: 'a8', brush: 'red' },
        ],
      },
    ],
    branch_pv_san_map: {
      br_p4_played_d5c7: ['Nc7+', 'Kd8', 'Nxa8'],
    },
    branch_fens_map: {
      br_p4_played_d5c7: [
        'r3kbnr/pp3ppp/8/3N4/8/8/PPPPPPPP/R1BQKBNR w KQkq - 0 1',
        'r3kbnr/ppN2ppp/8/8/8/8/PPPPPPPP/R1BQKBNR b KQkq - 1 1',
      ],
    },
    challenge_outcomes: [],
    engine_metadata: [],
    audit_log: [],
  },
  commentary: {
    sentences: [
      {
        sentence_id: 'sent_1',
        text: 'In the analyzed continuation after Nc7+, White forks the king on e8 and the rook on a8.',
        claim_ids: ['clm_fork_1'],
        branch_id: 'br_p4_played_d5c7',
        preview_fen: 'r3kbnr/ppN2ppp/8/8/8/8/PPPPPPPP/R1BQKBNR b KQkq - 1 1',
        arrows: [
          { orig: 'c7', dest: 'e8', brush: 'red' },
          { orig: 'c7', dest: 'a8', brush: 'red' },
        ],
      },
    ],
    abstention_notice: null,
    used_template: true,
  },
};

describe('CommentaryPane', () => {
  it('invokes onSelectSentence with claim_ids, branch_id, preview_fen, and arrows when clicking a sentence pill', () => {
    const onSelectSentence = vi.fn<(s: RealizedSentence) => void>();

    render(
      <CommentaryPane
        plyAnalysis={samplePlyWithCommentary}
        onSelectSentence={onSelectSentence}
      />,
    );

    expect(screen.getByText('In This Line')).toBeInTheDocument();
    expect(
      screen.getByText(/Deterministic Template Verified/i),
    ).toBeInTheDocument();

    const pillButton = screen.getByTestId('sentence-pill-sent_1');
    fireEvent.click(pillButton);

    expect(onSelectSentence).toHaveBeenCalledTimes(1);
    expect(onSelectSentence).toHaveBeenCalledWith({
      sentence_id: 'sent_1',
      text: 'In the analyzed continuation after Nc7+, White forks the king on e8 and the rook on a8.',
      claim_ids: ['clm_fork_1'],
      branch_id: 'br_p4_played_d5c7',
      preview_fen: 'r3kbnr/ppN2ppp/8/8/8/8/PPPPPPPP/R1BQKBNR b KQkq - 1 1',
      arrows: [
        { orig: 'c7', dest: 'e8', brush: 'red' },
        { orig: 'c7', dest: 'a8', brush: 'red' },
      ],
    });
  });

  it('renders an explicit abstention card when EVAN abstains from an unsupported explanation', () => {
    const abstainedPly: PlyAnalysis = {
      ...samplePlyWithCommentary,
      deep_status: 'abstained',
      commentary: {
        sentences: [],
        abstention_notice:
          'At this budget Stockfish evaluates both moves within 15 cp and deterministic replay detectors establish no concrete tactical witness; EVAN abstains from inventing a strategic story.',
      },
      ledger: {
        ...samplePlyWithCommentary.ledger!,
        claims: [
          {
            claim_id: 'clm_abstain_1',
            type: 'plan_interpretation',
            proposition: 'Abstained due to absence of deterministic tactical witness.',
            root_state_id: 'st_0',
            branch_id: 'br_p4_played_d5c7',
            applicable_state_ids: ['st_0'],
            support_evidence_ids: [],
            evidence_source: 'evan_abstention_policy',
            assertion_scope: 'heuristic_interpretation',
            line_event_plies: [],
            challenge_queries: [],
            discovered_contradictions: [],
            unresolved_questions: [
              'No immediate capture, check, pin, or double-attack witness separated the lines within the PV window.',
            ],
            status: 'abstain',
            preview_fen: samplePlyWithCommentary.fen_before,
            arrows: [],
          },
        ],
      },
    };

    render(
      <CommentaryPane
        plyAnalysis={abstainedPly}
        onSelectSentence={vi.fn()}
      />,
    );

    const card = screen.getByTestId('abstention-card');
    expect(card).toBeInTheDocument();
    expect(
      screen.getByText(/Calibrated Epistemic Abstention/i),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/EVAN abstains from inventing a strategic story/i),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/No immediate capture, check, pin, or double-attack witness/i),
    ).toBeInTheDocument();
  });
});
