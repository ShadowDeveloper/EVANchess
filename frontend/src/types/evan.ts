export type PlayerColor = 'white' | 'black';
export type BudgetProfile = 'quick' | 'standard' | 'deep';
export type ImportPlatform = 'pgn' | 'fen' | 'lichess' | 'chesscom' | string;

export type GameAnalysisStatus =
  | 'pending'
  | 'auto_analyzing'
  | 'auto_complete'
  | 'full_analyzing'
  | 'full_complete'
  | 'failed';

export type PlyDeepStatus =
  | 'queued'
  | 'running'
  | 'completed'
  | 'abstained'
  | 'failed';

export type ClaimType =
  | 'state_fact'
  | 'conditional_line_event'
  | 'engine_preference'
  | 'motif'
  | 'plan_interpretation'
  | 'exact_outcome';

export type AssertionScope =
  | 'current_board_only'
  | 'in_displayed_continuation'
  | 'across_analyzed_defenses_at_budget'
  | 'engine_preference_at_budget'
  | 'heuristic_interpretation'
  | 'exact_rules_or_tablebase';

export type ClaimStatus = 'assert' | 'qualify' | 'abstain';

export interface HealthResponse {
  configured: boolean;
  configuration_errors: string[];
}

export interface BoardArrow {
  orig: string;
  dest: string;
  brush: string;
}

export interface UndefendedPieceObservation {
  square: string;
  piece_type: string;
  color: string;
  protection_status: string;
  attackers: string[];
  geometric_defenders: string[];
  effective_defenders: string[];
}

export interface PinObservation {
  pinned_square: string;
  pinned_piece: string;
  pinned_color: string;
  pinner_square: string;
  pinner_piece: string;
  pin_type: string;
  shielded_square: string;
}

export interface LineEvent {
  evidence_id: string;
  branch_id: string;
  ply_offset: number;
  state_id: string;
  fen: string;
  move_uci: string;
  move_san: string;
  mover_color: string;
  event_type: string;
  description: string;
  squares: string[];
  arrows: BoardArrow[];
  material_delta_mover_cp: number;
}

export interface BranchEvidenceTrace {
  branch_id: string;
  root_fen: string;
  root_move_uci: string;
  root_move_san: string;
  pv_uci: string[];
  pv_san: string[];
  state_fens: string[];
  state_ids: string[];
  legal_sans_in_branch: string[];
  net_material_delta_mover: number;
  events: LineEvent[];
}

export interface MomentEvidenceGraph {
  ply: number;
  root_fen: string;
  root_undefended_white?: UndefendedPieceObservation[];
  root_undefended_black?: UndefendedPieceObservation[];
  root_pins_white?: PinObservation[];
  root_pins_black?: PinObservation[];
  branch_traces?: Record<string, BranchEvidenceTrace>;
  evidence_branch_map?: Record<string, string>;
}

export interface EngineAnalysisRecord {
  engine_name: string;
  engine_path: string;
  threads: number;
  hash_mb: number;
  hash_policy?: string;
  root_fen: string;
  root_state_hash: string;
  uci_history: string[];
  allowed_root_moves?: string[] | null;
  multipv_index: number;
  node_limit: number;
  reported_nodes: number;
  depth: number;
  seldepth: number;
  score_cp_white?: number | null;
  score_cp_mover?: number | null;
  mate_white?: number | null;
  mate_mover?: number | null;
  wdl_white?: [number, number, number] | number[] | null;
  pv_uci: string[];
  pv_san: string[];
}

export interface BranchAnalysis {
  branch_id: string;
  root_move_uci: string;
  root_move_san: string;
  role: string;
  nomination_source: string;
  tier1_record: EngineAnalysisRecord;
  primary_record: EngineAnalysisRecord;
  score_drift_cp: number;
  is_stable: boolean;
}

export interface MomentBranchBundle {
  ply: number;
  root_fen: string;
  turn: string;
  branches: BranchAnalysis[];
  played_branch_id: string;
  best_branch_id: string;
  played_is_best: boolean;
  ranking_reversed_across_budgets: boolean;
  is_near_equal_top_choice: boolean;
  stability_status: string;
  eval_gap_played_vs_best_cp: number;
}

export interface ChallengeDefenseLine {
  defense_uci: string;
  defense_san: string;
  eval_cp_original_mover: number;
  pv_san: string[];
}

export interface ChallengeOutcome {
  query_id: string;
  branch_id: string;
  challenged_at_ply_offset: number;
  opponent_punishing_move_san: string;
  defenses_tested: ChallengeDefenseLine[];
  refutation_holds_across_top_defenses: boolean;
  discovered_contradictions: string[];
  recommended_scope: string;
}

export interface ClaimRecord {
  claim_id: string;
  type: ClaimType;
  proposition: string;
  root_state_id: string;
  branch_id: string;
  applicable_state_ids: string[];
  support_evidence_ids: string[];
  evidence_source: string;
  assertion_scope: AssertionScope;
  line_event_plies: number[];
  validation_results?: Record<string, unknown>;
  challenge_queries: string[];
  discovered_contradictions: string[];
  unresolved_questions: string[];
  status: ClaimStatus;
  preview_fen: string;
  arrows: BoardArrow[];
}

export interface AuditLogEntry {
  stage?: string;
  event?: string;
  sentence_id?: string;
  passed?: boolean;
  violation_codes?: string[];
  details?: string | Record<string, unknown>;
  provider?: string;
  model?: string;
  used_fallback?: boolean;
  used_template?: boolean;
  [key: string]: unknown;
}

export interface MomentClaimLedger {
  ply: number;
  move_number: number;
  turn: string;
  played_san: string;
  best_san: string;
  root_fen: string;
  stability_status: string;
  claims: ClaimRecord[];
  branch_pv_san_map: Record<string, string[]>;
  branch_legal_sans_map?: Record<string, string[]>;
  branch_fens_map: Record<string, string[]>;
  challenge_outcomes: ChallengeOutcome[];
  engine_metadata: EngineAnalysisRecord[];
  audit_log: AuditLogEntry[];
  evidence_witness_map?: Record<string, unknown>;
  metrics?: Record<string, unknown>;
  evidence_graph?: MomentEvidenceGraph | null;
  branch_bundle?: MomentBranchBundle | null;
}

export interface RealizedSentence {
  sentence_id: string;
  text: string;
  claim_ids: string[];
  branch_id: string;
  preview_fen: string;
  arrows: BoardArrow[];
}

export interface RealizedCommentary {
  sentences: RealizedSentence[];
  abstention_notice?: string | null;
  used_template?: boolean;
  used_fallback?: boolean;
  audit_passed?: boolean;
  provider?: string | null;
  model?: string | null;
  usage?: Record<string, number>;
  cost_usd?: number | null;
}

export interface CriticalMomentReason {
  ply?: number;
  total_score?: number;
  eval_swing_score?: number;
  sharpness_score?: number;
  tactical_motif_bonus?: number;
  phase_diversity_adjustment?: number;
  primary_reason?: string;
}

export interface PlyAnalysis {
  game_id: string;
  ply: number;
  move_number: number;
  turn: PlayerColor;
  uci_move: string;
  san_move: string;
  fen_before: string;
  fen_after: string;
  state_before_hash: string;
  state_after_hash: string;
  coarse_eval_cp_white: number | null;
  coarse_mate_white: number | null;
  coarse_eval_after_cp_white: number | null;
  coarse_mate_after_white: number | null;
  eval_swing_cp: number;
  critical_score: number;
  critical_reason: CriticalMomentReason;
  is_critical: boolean;
  deep_status: PlyDeepStatus;
  priority_boost?: number;
  ledger: MomentClaimLedger | null;
  commentary: RealizedCommentary | null;
}

export interface GameSummary {
  game_id: string;
  created_at: string;
  pgn_text: string;
  fen_root: string;
  has_full_history: boolean;
  white: string;
  black: string;
  result: string;
  event: string;
  player_color: PlayerColor;
  target_rating: number;
  platform: string;
  error?: string | null;
  analysis_status: GameAnalysisStatus;
  critical_plies: number[];
  warnings: string[];
  untrusted_comments: Record<string, string>;
}

export interface GameDetail extends GameSummary {
  plies: PlyAnalysis[];
}

export interface ImportGamePayload {
  input: string;
  player_color: PlayerColor;
  target_rating: number;
  platform: string;
  budget_profile: BudgetProfile;
  username?: string;
}

export interface RemotePlatformGame {
  id: string;
  url?: string;
  white: string;
  black: string;
  speed?: string;
  time_class?: string;
  winner?: string | null;
  pgn: string;
  platform: 'lichess' | 'chesscom' | string;
}

export interface BranchPreviewState {
  sourceSentenceId?: string;
  sourceClaimIds: string[];
  branchId: string;
  fen: string;
  arrows: BoardArrow[];
  pvSan: string[];
  stateFens: string[];
  stepIndex: number;
}
