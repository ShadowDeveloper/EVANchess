import React from 'react';
import {
  ShieldCheck,
  GitBranch,
  Ban,
  Zap,
  Loader2,
  Scale,
  ArrowUpRight,
  AlertTriangle,
  Star,
  Cpu,
} from 'lucide-react';
import type {
  AssertionScope,
  ClaimRecord,
  PlyAnalysis,
  RealizedSentence,
} from '../types/evan';

interface CommentaryPaneProps {
  plyAnalysis: PlyAnalysis | null;
  selectedSentenceId?: string | null;
  activeClaimIds?: string[];
  onSelectSentence: (sentence: RealizedSentence) => void;
  onHoverSentence?: (sentence: RealizedSentence | null) => void;
  onPrioritizePly?: (ply: number) => Promise<void>;
  onOpenLedgerForClaims?: (claimIds: string[]) => void;
}

export function getScopeBadgeMeta(scope?: AssertionScope | string): {
  label: string;
  tone: string;
} {
  switch (scope) {
    case 'current_board_only':
      return {
        label: 'Board Fact',
        tone: 'border-emerald-500/40 bg-emerald-500/10 text-emerald-300',
      };
    case 'in_displayed_continuation':
      return {
        label: 'In This Line',
        tone: 'border-[#D99B26]/50 bg-[#D99B26]/15 text-[#F4E0B8]',
      };
    case 'across_analyzed_defenses_at_budget':
      return {
        label: 'Verified vs Top Defenses',
        tone: 'border-sky-500/40 bg-sky-500/15 text-sky-300',
      };
    case 'engine_preference_at_budget':
      return {
        label: 'Engine Preference @ Budget',
        tone: 'border-indigo-400/40 bg-indigo-500/15 text-indigo-200',
      };
    case 'heuristic_interpretation':
      return {
        label: 'Heuristic Idea',
        tone: 'border-purple-400/40 bg-purple-500/15 text-purple-200',
      };
    case 'exact_rules_or_tablebase':
      return {
        label: 'Exact Outcome',
        tone: 'border-teal-400/50 bg-teal-500/15 text-teal-200',
      };
    default:
      return {
        label: 'In This Line',
        tone: 'border-[#D99B26]/40 bg-[#D99B26]/10 text-[#F4E0B8]',
      };
  }
}

function resolveSentenceScope(
  sentence: RealizedSentence,
  claimsById: Map<string, ClaimRecord>,
): AssertionScope | undefined {
  for (const cid of sentence.claim_ids) {
    const claim = claimsById.get(cid);
    if (claim) {
      return claim.assertion_scope;
    }
  }
  return undefined;
}

export const CommentaryPane: React.FC<CommentaryPaneProps> = ({
  plyAnalysis,
  selectedSentenceId,
  activeClaimIds = [],
  onSelectSentence,
  onHoverSentence,
  onPrioritizePly,
  onOpenLedgerForClaims,
}) => {
  if (!plyAnalysis) {
    return (
      <section
        aria-label="Audited Commentary Reader"
        className="flex h-full flex-col justify-center rounded-lg border border-[#22252D] bg-[#12141A] p-6 text-center"
      >
        <p className="font-editorial text-lg text-[#ECE9E2]">
          Select a move to inspect its evidence-scoped commentary.
        </p>
      </section>
    );
  }

  const ledger = plyAnalysis.ledger;
  const commentary = plyAnalysis.commentary;
  const claims = ledger?.claims ?? [];
  const claimsById = new Map<string, ClaimRecord>(
    claims.map((c) => [c.claim_id, c]),
  );

  const sentences = commentary?.sentences ?? [];
  const abstentionNotice = commentary?.abstention_notice;
  const usedTemplate =
    Boolean(commentary?.used_template) || Boolean(commentary?.used_fallback);

  const isFenOnlyRoot =
    plyAnalysis.ply === 0 &&
    plyAnalysis.san_move === 'Position' &&
    plyAnalysis.uci_move === '';

  const abstainedClaims = claims.filter((c) => c.status === 'abstain');
  const isAbstainedMoment =
    plyAnalysis.deep_status === 'abstained' ||
    Boolean(abstentionNotice) ||
    (sentences.length === 0 && abstainedClaims.length > 0);

  return (
    <section
      aria-label="Audited Commentary Reader"
      className="flex flex-col rounded-lg border border-[#22252D] bg-[#12141A] shadow-xl"
    >
      <div className="border-b border-[#22252D] bg-[#151821] px-5 py-4">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div className="flex items-center gap-2">
            <span className="font-mono-code text-[10px] font-semibold uppercase tracking-widest text-[#D99B26]">
              Steps 8–10 · Audited Narration
            </span>
            {plyAnalysis.is_critical && (
              <span className="inline-flex items-center gap-1 rounded border border-[#D99B26]/50 bg-[#D99B26]/15 px-2 py-0.5 font-mono-code text-[10px] font-semibold text-[#F4E0B8]">
                <Star className="h-2.5 w-2.5 fill-[#D99B26] text-[#D99B26]" />
                {plyAnalysis.critical_reason?.primary_reason || 'Critical Moment'}
              </span>
            )}
          </div>

          {usedTemplate && (
            <span
              title="Rendered via deterministic ClaimRecord template (zero-hallucination fallback)"
              className="inline-flex items-center gap-1 rounded border border-sky-500/40 bg-sky-500/10 px-2 py-0.5 font-mono-code text-[10px] font-medium text-sky-300"
            >
              <Cpu className="h-3 w-3" />
              <span>Deterministic Template Verified</span>
            </span>
          )}
        </div>

        <div className="mt-2 flex flex-wrap items-baseline justify-between gap-2">
          <h2 className="font-editorial text-2xl font-semibold text-[#F5F2EB]">
            {isFenOnlyRoot
              ? 'Standalone FEN Position Analysis'
              : `Move ${plyAnalysis.move_number}${
                  plyAnalysis.turn === 'white' ? '.' : '...'
                } ${plyAnalysis.san_move}`}
          </h2>

          {ledger && (
            <div className="flex items-center gap-2 font-mono-code text-xs text-[#9499A6]">
              <span>
                Played:{' '}
                <strong className="text-[#ECE9E2]">{ledger.played_san}</strong>
              </span>
              <span>•</span>
              <span>
                Best:{' '}
                <strong className="text-[#E8B042]">{ledger.best_san}</strong>
              </span>
              <span className="rounded border border-[#2A2F3D] bg-[#0E1015] px-1.5 py-0.5 text-[10px] uppercase">
                {ledger.stability_status}
              </span>
            </div>
          )}
        </div>
      </div>

      <div className="space-y-4 p-5">
        {plyAnalysis.deep_status === 'queued' && (
          <div className="rounded-lg border border-amber-500/35 bg-amber-500/10 p-4">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div className="space-y-1">
                <h3 className="font-editorial text-base font-semibold text-amber-200">
                  Queued for Deferred Full-Game Analysis
                </h3>
                <p className="text-xs text-amber-200/80">
                  Coarse pass complete. Click below to bump this move to the front of the deep 10-step verification queue.
                </p>
              </div>
              {onPrioritizePly && (
                <button
                  type="button"
                  onClick={() => onPrioritizePly(plyAnalysis.ply)}
                  className="inline-flex items-center gap-1.5 rounded-md bg-[#D99B26] px-3.5 py-2 text-xs font-semibold text-[#0B0C0E] shadow transition hover:bg-[#E5AA3A]"
                >
                  <Zap className="h-3.5 w-3.5" />
                  <span>Prioritize Deep Audit Now</span>
                </button>
              )}
            </div>
          </div>
        )}

        {plyAnalysis.deep_status === 'running' && (
          <div className="flex items-center gap-3 rounded-lg border border-sky-500/35 bg-sky-500/10 p-4 text-xs text-sky-200">
            <Loader2 className="h-5 w-5 shrink-0 animate-spin text-sky-400" />
            <div>
              <p className="font-semibold">
                Running Multi-Budget Search, Legal Challenge Queries &amp; Prose Audit...
              </p>
              <p className="mt-0.5 text-sky-300/80">
                Verifying candidate move branches and checking SAN legality and assertion scopes.
              </p>
            </div>
          </div>
        )}

        {sentences.length > 0 && (
          <div className="space-y-2.5">
            <div className="flex items-center justify-between">
              <span className="font-mono-code text-[11px] text-[#9499A6]">
                Click or hover any sentence pill to preview its branch state, draw tactical arrows, and inspect its witness:
              </span>
            </div>

            <div className="space-y-2.5" role="list" aria-label="Audited Sentence Pills">
              {sentences.map((sentence, idx) => {
                const scope = resolveSentenceScope(sentence, claimsById);
                const scopeMeta = getScopeBadgeMeta(scope);
                const isSelected =
                  selectedSentenceId === sentence.sentence_id ||
                  sentence.claim_ids.some((id) => activeClaimIds.includes(id));

                return (
                  <div
                    key={sentence.sentence_id || `sent-${idx}`}
                    role="listitem"
                  >
                    <button
                      type="button"
                      data-testid={`sentence-pill-${sentence.sentence_id}`}
                      onClick={() => onSelectSentence(sentence)}
                      onMouseEnter={() => onHoverSentence?.(sentence)}
                      onMouseLeave={() => onHoverSentence?.(null)}
                      className={`group w-full rounded-lg border p-3.5 text-left transition ${
                        isSelected
                          ? 'border-[#D99B26] bg-[#D99B26]/15 shadow-md ring-1 ring-[#D99B26]/50'
                          : 'border-[#262B36] bg-[#161922] hover:border-[#D99B26]/60 hover:bg-[#1B1F2B]'
                      }`}
                    >
                      <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
                        <div className="flex flex-wrap items-center gap-1.5">
                          <span
                            className={`inline-flex items-center gap-1 rounded border px-2 py-0.5 font-mono-code text-[10px] font-semibold ${scopeMeta.tone}`}
                          >
                            <ShieldCheck className="h-3 w-3" />
                            <span>{scopeMeta.label}</span>
                          </span>

                          {sentence.branch_id && (
                            <span className="inline-flex items-center gap-1 rounded border border-[#2D3342] bg-[#101218] px-2 py-0.5 font-mono-code text-[10px] text-[#9499A6]">
                              <GitBranch className="h-2.5 w-2.5 text-[#D99B26]" />
                              <span>{sentence.branch_id}</span>
                            </span>
                          )}
                        </div>

                        <div className="flex items-center gap-1.5">
                          {sentence.claim_ids.map((cid) => (
                            <span
                              key={cid}
                              className="rounded bg-[#0D0F14] px-1.5 py-0.5 font-mono-code text-[10px] text-[#D99B26]"
                            >
                              {cid}
                            </span>
                          ))}
                          <ArrowUpRight className="h-3.5 w-3.5 text-[#858B99] transition group-hover:text-[#D99B26]" />
                        </div>
                      </div>

                      <p className="text-sm leading-relaxed text-[#F3F0E8]">
                        {sentence.text}
                      </p>
                    </button>
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {isAbstainedMoment && (
          <div
            data-testid="abstention-card"
            role="region"
            aria-label="Epistemic Abstention Notice"
            className="rounded-lg border border-amber-500/40 bg-gradient-to-br from-amber-500/15 via-[#181612] to-[#13151B] p-4"
          >
            <div className="flex items-start gap-3">
              <div className="mt-0.5 rounded-md border border-amber-500/40 bg-amber-500/20 p-1.5 text-amber-300">
                <Ban className="h-4 w-4" />
              </div>
              <div className="flex-1 space-y-2">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <h3 className="font-editorial text-base font-semibold text-amber-200">
                    Calibrated Epistemic Abstention
                  </h3>
                  <span className="rounded border border-amber-500/40 bg-amber-500/10 px-2 py-0.5 font-mono-code text-[10px] font-semibold uppercase text-amber-300">
                    No Unverified Storytelling
                  </span>
                </div>

                <p className="text-xs leading-relaxed text-[#ECE9E2]">
                  {abstentionNotice ||
                    abstainedClaims[0]?.proposition ||
                    'At the current search budget, deterministic replay detectors did not establish a concrete tactical witness separating these moves; EVAN abstains from inventing an unsupported causal explanation.'}
                </p>

                {abstainedClaims.some(
                  (c) => c.unresolved_questions && c.unresolved_questions.length > 0,
                ) && (
                  <div className="rounded border border-[#2C303C] bg-[#0E1015]/80 p-2.5">
                    <span className="block font-mono-code text-[10px] uppercase tracking-wider text-[#9499A6]">
                      Attempted Detector Checks &amp; Unresolved Questions:
                    </span>
                    <ul className="mt-1 list-disc space-y-1 pl-4 text-xs text-[#C5C8D2]">
                      {abstainedClaims
                        .flatMap((c) => c.unresolved_questions)
                        .map((q, i) => (
                          <li key={i}>{q}</li>
                        ))}
                    </ul>
                  </div>
                )}

                {onOpenLedgerForClaims && abstainedClaims.length > 0 && (
                  <button
                    type="button"
                    onClick={() =>
                      onOpenLedgerForClaims(abstainedClaims.map((c) => c.claim_id))
                    }
                    className="inline-flex items-center gap-1.5 rounded border border-amber-500/40 bg-amber-500/15 px-2.5 py-1 text-xs font-semibold text-amber-200 transition hover:bg-amber-500/25"
                  >
                    <Scale className="h-3.5 w-3.5" />
                    <span>Inspect Abstention Record in Audit Ledger</span>
                  </button>
                )}
              </div>
            </div>
          </div>
        )}

        {ledger && ledger.branch_pv_san_map && Object.keys(ledger.branch_pv_san_map).length > 0 && (
          <div className="border-t border-[#22252D] pt-3.5">
            <div className="mb-2 flex items-center justify-between">
              <span className="font-mono-code text-[10px] font-semibold uppercase tracking-widest text-[#9499A6]">
                Analyzed Principal Variations (Step 5 Root-Restricted Branches)
              </span>
              {onOpenLedgerForClaims && (
                <button
                  type="button"
                  onClick={() =>
                    onOpenLedgerForClaims(claims.map((c) => c.claim_id))
                  }
                  className="inline-flex items-center gap-1 font-mono-code text-[11px] font-medium text-[#D99B26] hover:underline"
                >
                  <Scale className="h-3 w-3" />
                  <span>Open Full Claim–Witness Ledger ({claims.length})</span>
                </button>
              )}
            </div>

            <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
              {Object.entries(ledger.branch_pv_san_map).map(([branchId, pvSans]) => {
                const branchFens = ledger.branch_fens_map?.[branchId] ?? [];
                return (
                  <div
                    key={branchId}
                    className="rounded-md border border-[#242834] bg-[#0E1015] p-2.5"
                  >
                    <div className="flex items-center justify-between gap-2">
                      <span className="font-mono-code text-[11px] font-semibold text-[#E8B042]">
                        {branchId}
                      </span>
                      {branchFens.length > 0 && (
                        <button
                          type="button"
                          onClick={() =>
                            onSelectSentence({
                              sentence_id: `branch_preview_${branchId}`,
                              text: `Preview branch ${branchId}`,
                              claim_ids: claims
                                .filter((c) => c.branch_id === branchId)
                                .map((c) => c.claim_id),
                              branch_id: branchId,
                              preview_fen: branchFens[Math.min(1, branchFens.length - 1)] || ledger.root_fen,
                              arrows: [],
                            })
                          }
                          className="rounded border border-[#2D3342] bg-[#161922] px-2 py-0.5 font-mono-code text-[10px] text-[#ECE9E2] hover:border-[#D99B26]/60"
                        >
                          Preview Line
                        </button>
                      )}
                    </div>
                    <p className="mt-1 font-mono-code text-xs text-[#C5C8D2]">
                      {pvSans.length > 0 ? pvSans.join(' ') : 'No continuation moves'}
                    </p>
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {plyAnalysis.deep_status === 'failed' && (
          <div className="flex items-center gap-2 rounded-lg border border-rose-500/40 bg-rose-500/10 p-3.5 text-xs text-rose-200">
            <AlertTriangle className="h-4 w-4 shrink-0 text-rose-400" />
            <span>
              Deep analysis encountered an error on this ply. Try prioritizing or re-importing.
            </span>
          </div>
        )}
      </div>
    </section>
  );
};
