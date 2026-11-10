import React from 'react';
import {
  X,
  Scale,
  ShieldCheck,
  GitBranch,
  Cpu,
  AlertTriangle,
  CheckCircle2,
  Download,
  FileCode2,
  Swords,
  FileCheck2,
  Sparkles,
} from 'lucide-react';
import type {
  ClaimRecord,
  LineEvent,
  MomentClaimLedger,
  PlyAnalysis,
} from '../types/evan';
import { getExportLedgerUrl, getExportPgnUrl } from '../api/client';
import { getScopeBadgeMeta } from './CommentaryPane';

interface AuditLedgerDrawerProps {
  isOpen: boolean;
  onClose: () => void;
  gameId: string;
  plyAnalysis: PlyAnalysis | null;
  highlightedClaimIds: string[];
  onSelectClaim?: (claim: ClaimRecord) => void;
}

function collectEvidenceItems(ledger: MomentClaimLedger | null): LineEvent[] {
  if (!ledger?.evidence_graph?.branch_traces) {
    return [];
  }
  const allEvents: LineEvent[] = [];
  for (const trace of Object.values(ledger.evidence_graph.branch_traces)) {
    if (Array.isArray(trace.events)) {
      allEvents.push(...trace.events);
    }
  }
  return allEvents;
}

export const AuditLedgerDrawer: React.FC<AuditLedgerDrawerProps> = ({
  isOpen,
  onClose,
  gameId,
  plyAnalysis,
  highlightedClaimIds,
  onSelectClaim,
}) => {
  if (!isOpen) {
    return null;
  }

  const ledger = plyAnalysis?.ledger ?? null;
  const claims = ledger?.claims ?? [];
  const evidenceEvents = collectEvidenceItems(ledger);
  const highlightedEvidenceIds = new Set<string>(
    claims
      .filter((c) => highlightedClaimIds.includes(c.claim_id))
      .flatMap((c) => c.support_evidence_ids),
  );

  const rootUndefended = [
    ...(ledger?.evidence_graph?.root_undefended_white ?? []),
    ...(ledger?.evidence_graph?.root_undefended_black ?? []),
  ];
  const rootPins = [
    ...(ledger?.evidence_graph?.root_pins_white ?? []),
    ...(ledger?.evidence_graph?.root_pins_black ?? []),
  ];

  const challenges = ledger?.challenge_outcomes ?? [];
  const engineRecords = ledger?.engine_metadata ?? [];
  const auditLogs = ledger?.audit_log ?? [];
  const branchBundle = ledger?.branch_bundle ?? null;

  return (
    <aside
      aria-label="Inspectable Audit Ledger Drawer"
      className="fixed inset-y-0 right-0 z-40 flex w-full max-w-xl flex-col border-l border-[#2B303D] bg-[#0F1117] shadow-2xl"
    >
      <div className="flex items-center justify-between border-b border-[#22252D] bg-[#141720] px-5 py-4">
        <div className="flex items-center gap-2.5">
          <div className="rounded-md border border-[#D99B26]/50 bg-[#D99B26]/15 p-2 text-[#E8B042]">
            <Scale className="h-4 w-4" />
          </div>
          <div>
            <span className="font-mono-code text-[10px] font-semibold uppercase tracking-widest text-[#D99B26]">
              Claim–Witness Contract Inspector
            </span>
            <h2 className="font-editorial text-xl font-semibold text-[#F5F2EB]">
              Audit Ledger{' '}
              {plyAnalysis
                ? `· Ply ${plyAnalysis.ply} (${plyAnalysis.san_move})`
                : ''}
            </h2>
          </div>
        </div>

        <div className="flex items-center gap-2">
          {gameId && (
            <>
              <a
                href={getExportPgnUrl(gameId)}
                download={`${gameId}_annotated.pgn`}
                className="inline-flex items-center gap-1 rounded border border-[#2B303C] bg-[#181B24] px-2.5 py-1.5 text-xs font-medium text-[#ECE9E2] transition hover:border-[#D99B26]/60"
              >
                <Download className="h-3.5 w-3.5 text-[#D99B26]" />
                <span>Export PGN</span>
              </a>
              <a
                href={getExportLedgerUrl(gameId)}
                download={`${gameId}_ledger.json`}
                className="inline-flex items-center gap-1 rounded border border-[#2B303C] bg-[#181B24] px-2.5 py-1.5 text-xs font-medium text-[#ECE9E2] transition hover:border-[#D99B26]/60"
              >
                <FileCode2 className="h-3.5 w-3.5 text-[#D99B26]" />
                <span>Export Ledger JSON</span>
              </a>
            </>
          )}
          <button
            type="button"
            onClick={onClose}
            aria-label="Close Audit Ledger Drawer"
            className="rounded-md p-1.5 text-[#9499A6] transition hover:bg-[#22252D] hover:text-[#F5F2EB]"
          >
            <X className="h-5 w-5" />
          </button>
        </div>
      </div>

      {!ledger ? (
        <div className="flex flex-1 flex-col items-center justify-center p-8 text-center">
          <Scale className="mb-3 h-8 w-8 text-[#5F6575]" />
          <p className="font-editorial text-lg text-[#ECE9E2]">
            No deep audit ledger recorded for this ply yet.
          </p>
          <p className="mt-1 max-w-sm text-xs text-[#9499A6]">
            Select an audited critical moment or click a queued move to prioritize its 10-step verification.
          </p>
        </div>
      ) : (
        <div className="flex-1 space-y-6 overflow-y-auto p-5">
          <section aria-label="Typed Claim Records">
            <div className="mb-2.5 flex items-center justify-between">
              <h3 className="flex items-center gap-1.5 font-mono-code text-xs font-semibold uppercase tracking-wider text-[#E8B042]">
                <ShieldCheck className="h-3.5 w-3.5" />
                <span>Typed Claim Records ({claims.length})</span>
              </h3>
              <span className="font-mono-code text-[11px] text-[#9499A6]">
                Stability: {ledger.stability_status}
              </span>
            </div>

            <div className="space-y-2.5">
              {claims.map((claim) => {
                const isHighlighted = highlightedClaimIds.includes(
                  claim.claim_id,
                );
                const scopeMeta = getScopeBadgeMeta(claim.assertion_scope);

                return (
                  <div
                    key={claim.claim_id}
                    data-testid={`ledger-claim-${claim.claim_id}`}
                    data-highlighted={isHighlighted ? 'true' : 'false'}
                    onClick={() => onSelectClaim?.(claim)}
                    className={`cursor-pointer rounded-lg border p-3.5 transition ${
                      isHighlighted
                        ? 'border-[#D99B26] bg-[#D99B26]/15 ring-1 ring-[#D99B26]'
                        : 'border-[#252934] bg-[#141720] hover:border-[#394052]'
                    }`}
                  >
                    <div className="mb-2 flex flex-wrap items-center justify-between gap-1.5">
                      <div className="flex flex-wrap items-center gap-1.5">
                        <span className="rounded bg-[#0B0C0E] px-2 py-0.5 font-mono-code text-[11px] font-bold text-[#E8B042]">
                          {claim.claim_id}
                        </span>
                        <span className="rounded border border-[#2D3342] bg-[#181C26] px-1.5 py-0.5 font-mono-code text-[10px] text-[#C5C8D2]">
                          {claim.type}
                        </span>
                        <span
                          className={`rounded border px-1.5 py-0.5 font-mono-code text-[10px] font-semibold ${scopeMeta.tone}`}
                        >
                          {scopeMeta.label}
                        </span>
                      </div>

                      <span
                        className={`rounded px-1.5 py-0.5 font-mono-code text-[10px] font-bold uppercase ${
                          claim.status === 'assert'
                            ? 'bg-emerald-500/20 text-emerald-300'
                            : claim.status === 'qualify'
                              ? 'bg-amber-500/20 text-amber-300'
                              : 'bg-zinc-500/20 text-zinc-300'
                        }`}
                      >
                        {claim.status}
                      </span>
                    </div>

                    <p className="text-xs leading-relaxed text-[#F3F0E8]">
                      {claim.proposition}
                    </p>

                    <div className="mt-2.5 flex flex-wrap items-center gap-2 border-t border-[#222632] pt-2 font-mono-code text-[10px] text-[#9499A6]">
                      <span className="inline-flex items-center gap-1">
                        <GitBranch className="h-3 w-3 text-[#D99B26]" />
                        Branch: {claim.branch_id}
                      </span>
                      <span>•</span>
                      <span>Source: {claim.evidence_source}</span>
                      {claim.support_evidence_ids.length > 0 && (
                        <>
                          <span>•</span>
                          <span className="text-[#F4E0B8]">
                            Witnesses: {claim.support_evidence_ids.join(', ')}
                          </span>
                        </>
                      )}
                    </div>

                    {claim.discovered_contradictions.length > 0 && (
                      <div className="mt-2 rounded border border-amber-500/35 bg-amber-500/10 p-2 text-[11px] text-amber-200">
                        <strong>Defensive Resource Noted:</strong>{' '}
                        {claim.discovered_contradictions.join(' ')}
                      </div>
                    )}

                    {claim.unresolved_questions.length > 0 && (
                      <div className="mt-2 rounded border border-zinc-600/40 bg-zinc-800/40 p-2 text-[11px] text-zinc-300">
                        <strong>Unresolved Question:</strong>{' '}
                        {claim.unresolved_questions.join(' ')}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          </section>

          {Object.keys(ledger.evidence_witness_map ?? {}).length > 0 && (
            <section aria-label="Exact Evidence Witness Records" className="space-y-2">
              <h3 className="font-mono-code text-xs text-[#E8B042]">Exact Board &amp; Engine Witnesses</h3>
              {Object.entries(ledger.evidence_witness_map ?? {}).map(([id, witness]) => (
                <details key={id} data-testid={`ledger-witness-${id}`} data-highlighted={highlightedEvidenceIds.has(id)} open={highlightedEvidenceIds.has(id)} className={`rounded border p-2 text-xs ${highlightedEvidenceIds.has(id) ? 'border-[#D99B26] bg-[#D99B26]/10' : 'border-[#2B303C]'}`}>
                  <summary className="cursor-pointer break-all font-mono-code">{id}</summary>
                  <pre className="mt-2 max-h-80 overflow-auto text-[10px]">{JSON.stringify(witness, null, 2)}</pre>
                </details>
              ))}
            </section>
          )}

          {(evidenceEvents.length > 0 ||
            rootUndefended.length > 0 ||
            rootPins.length > 0) && (
            <section aria-label="Deterministic Replay Witnesses">
              <h3 className="mb-2.5 flex items-center gap-1.5 font-mono-code text-xs font-semibold uppercase tracking-wider text-[#E8B042]">
                <Sparkles className="h-3.5 w-3.5" />
                <span>
                  Step 6 · Deterministic Replay &amp; Board Witnesses
                </span>
              </h3>

              <div className="space-y-2">
                {rootUndefended.map((u, idx) => {
                  const evId = `ev_root_undef_${u.square}`;
                  const isHi = highlightedEvidenceIds.has(evId);
                  return (
                    <div
                      key={`${evId}-${idx}`}
                      data-testid={`ledger-evidence-${evId}`}
                      className={`rounded-md border p-2.5 text-xs ${
                        isHi
                          ? 'border-[#D99B26] bg-[#D99B26]/15'
                          : 'border-[#242834] bg-[#141720]'
                      }`}
                    >
                      <div className="flex items-center justify-between font-mono-code text-[10px] text-[#E8B042]">
                        <span>{evId}</span>
                        <span>{u.protection_status}</span>
                      </div>
                      <p className="mt-1 text-[#ECE9E2]">
                        Root {u.color} {u.piece_type} on{' '}
                        <strong>{u.square}</strong> (attackers:{' '}
                        {u.attackers.join(', ') || 'none'})
                      </p>
                    </div>
                  );
                })}

                {rootPins.map((p, idx) => (
                  <div
                    key={`pin-${p.pinned_square}-${idx}`}
                    className="rounded-md border border-[#242834] bg-[#141720] p-2.5 text-xs"
                  >
                    <span className="font-mono-code text-[10px] text-sky-300">
                      {p.pin_type}
                    </span>
                    <p className="mt-1 text-[#ECE9E2]">
                      {p.pinned_color} {p.pinned_piece} on {p.pinned_square}{' '}
                      pinned to {p.shielded_square} by {p.pinner_piece} on{' '}
                      {p.pinner_square}.
                    </p>
                  </div>
                ))}

                {evidenceEvents.map((ev) => {
                  const isHi = highlightedEvidenceIds.has(ev.evidence_id);
                  return (
                    <div
                      key={ev.evidence_id}
                      data-testid={`ledger-evidence-${ev.evidence_id}`}
                      data-highlighted={isHi ? 'true' : 'false'}
                      className={`rounded-md border p-2.5 text-xs ${
                        isHi
                          ? 'border-[#D99B26] bg-[#D99B26]/15 ring-1 ring-[#D99B26]/60'
                          : 'border-[#242834] bg-[#141720]'
                      }`}
                    >
                      <div className="flex items-center justify-between font-mono-code text-[10px]">
                        <span className="font-semibold text-[#E8B042]">
                          {ev.evidence_id}
                        </span>
                        <span className="text-[#9499A6]">
                          {ev.branch_id} · +{ev.ply_offset} ply · {ev.event_type}
                        </span>
                      </div>
                      <p className="mt-1 text-[#ECE9E2]">{ev.description}</p>
                    </div>
                  );
                })}
              </div>
            </section>
          )}

          {challenges.length > 0 && (
            <section aria-label="Legal Challenge Searches">
              <h3 className="mb-2.5 flex items-center gap-1.5 font-mono-code text-xs font-semibold uppercase tracking-wider text-[#E8B042]">
                <Swords className="h-3.5 w-3.5" />
                <span>
                  Step 7 · Legal Continuation Challenge Searches ({challenges.length})
                </span>
              </h3>

              <div className="space-y-2.5">
                {challenges.map((ch) => (
                  <div
                    key={ch.query_id}
                    className="rounded-lg border border-[#252934] bg-[#141720] p-3 text-xs"
                  >
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <span className="font-mono-code font-semibold text-[#F4E0B8]">
                        {ch.query_id} (after {ch.opponent_punishing_move_san})
                      </span>
                      <span
                        className={`rounded px-2 py-0.5 font-mono-code text-[10px] font-semibold ${
                          ch.refutation_holds_across_top_defenses
                            ? 'bg-sky-500/20 text-sky-300'
                            : 'bg-amber-500/20 text-amber-300'
                        }`}
                      >
                        {ch.refutation_holds_across_top_defenses
                          ? 'Negative Evaluation Persists'
                          : 'Evaluation Check · Conditional Line'}
                      </span>
                    </div>

                    {ch.defenses_tested && ch.defenses_tested.length > 0 && (
                      <div className="mt-2 space-y-1 font-mono-code text-[11px] text-[#C5C8D2]">
                        {ch.defenses_tested.map((d, idx) => (
                          <div
                            key={`${d.defense_uci}-${idx}`}
                            className="flex items-center justify-between rounded bg-[#0D0F14] px-2 py-1"
                          >
                            <span>
                              Defense {d.defense_san}:{' '}
                              {d.pv_san?.join(' ') || d.defense_uci}
                            </span>
                            <span className="text-[#E8B042]">
                              {d.eval_cp_original_mover >= 0
                                ? `+${d.eval_cp_original_mover}`
                                : d.eval_cp_original_mover}{' '}
                              cp
                            </span>
                          </div>
                        ))}
                      </div>
                    )}

                    {ch.discovered_contradictions &&
                      ch.discovered_contradictions.length > 0 && (
                        <ul className="mt-2 list-disc space-y-1 pl-4 text-[11px] text-amber-200">
                          {ch.discovered_contradictions.map((c, idx) => (
                            <li key={idx}>{c}</li>
                          ))}
                        </ul>
                      )}
                  </div>
                ))}
              </div>
            </section>
          )}

          <section aria-label="Final-Prose Audit Log">
            <h3 className="mb-2.5 flex items-center gap-1.5 font-mono-code text-xs font-semibold uppercase tracking-wider text-[#E8B042]">
              <FileCheck2 className="h-3.5 w-3.5" />
              <span>
                Step 10 · Independent Final-Prose Auditor ({auditLogs.length})
              </span>
            </h3>

            {auditLogs.length === 0 ? (
              <div className="rounded-md border border-[#242834] bg-[#141720] p-3 text-xs text-[#9499A6]">
                All realized sentences satisfied SAN legality and assertion-scope constraints.
              </div>
            ) : (
              <div className="space-y-2">
                {auditLogs.map((entry, idx) => {
                  const passed = entry.passed !== false;
                  return (
                    <div
                      key={idx}
                      className="rounded-md border border-[#252934] bg-[#141720] p-3 text-xs"
                    >
                      <div className="flex items-center justify-between gap-2">
                        <span className="font-mono-code text-[11px] font-semibold text-[#F4E0B8]">
                          {String(entry.stage || entry.event || `Audit Step #${idx + 1}`)}
                        </span>
                        <span
                          className={`inline-flex items-center gap-1 rounded px-1.5 py-0.5 font-mono-code text-[10px] ${
                            passed
                              ? 'bg-emerald-500/20 text-emerald-300'
                              : 'bg-amber-500/20 text-amber-300'
                          }`}
                        >
                          {passed ? (
                            <CheckCircle2 className="h-3 w-3" />
                          ) : (
                            <AlertTriangle className="h-3 w-3" />
                          )}
                          <span>{passed ? 'Verified' : 'Revised / Fallback'}</span>
                        </span>
                      </div>

                      {Array.isArray(entry.violation_codes) &&
                        entry.violation_codes.length > 0 && (
                          <p className="mt-1 font-mono-code text-[11px] text-rose-300">
                            Violations: {entry.violation_codes.join(', ')}
                          </p>
                        )}

                      <pre className="mt-1.5 overflow-x-auto rounded bg-[#0B0C0E] p-2 font-mono-code text-[10px] text-[#C5C8D2]">
                        {JSON.stringify(entry, null, 2)}
                      </pre>
                    </div>
                  );
                })}
              </div>
            )}
          </section>

          <section aria-label="Engine Reproducibility Metadata">
            <h3 className="mb-2.5 flex items-center gap-1.5 font-mono-code text-xs font-semibold uppercase tracking-wider text-[#E8B042]">
              <Cpu className="h-3.5 w-3.5" />
              <span>
                Step 5 · UCI Engine Reproducibility Records ({engineRecords.length})
              </span>
            </h3>

            {branchBundle && (
              <div className="mb-2 rounded-md border border-[#242834] bg-[#141720] p-2.5 font-mono-code text-[11px] text-[#C5C8D2]">
                <div>
                  Eval Gap (Played vs Best):{' '}
                  <strong className="text-[#F4E0B8]">
                    {branchBundle.eval_gap_played_vs_best_cp} cp
                  </strong>{' '}
                  • Reversed Across Budgets:{' '}
                  <strong>
                    {branchBundle.ranking_reversed_across_budgets ? 'Yes' : 'No'}
                  </strong>
                </div>
              </div>
            )}

            <div className="space-y-2">
              {engineRecords.map((rec, idx) => (
                <div
                  key={`${rec.root_state_hash}-${idx}`}
                  className="rounded-md border border-[#242834] bg-[#141720] p-3 font-mono-code text-[11px]"
                >
                  <div className="flex flex-wrap items-center justify-between gap-2 text-[#F4E0B8]">
                    <span className="font-semibold">{rec.engine_name}</span>
                    <span>
                      {rec.reported_nodes || rec.node_limit} nodes · d{rec.depth}/
                      {rec.seldepth}
                    </span>
                  </div>
                  <div className="mt-1 flex flex-wrap gap-3 text-[10px] text-[#9499A6]">
                    <span>Threads: {rec.threads}</span>
                    <span>Hash: {rec.hash_mb}MB</span>
                    <span>
                      Score (Mover):{' '}
                      {rec.score_cp_mover !== null && rec.score_cp_mover !== undefined
                        ? `${rec.score_cp_mover >= 0 ? '+' : ''}${rec.score_cp_mover} cp`
                        : 'N/A'}
                    </span>
                    {rec.wdl_white && (
                      <span>WDL (W): [{rec.wdl_white.join(', ')}]</span>
                    )}
                  </div>
                  <div className="mt-1.5 truncate text-[#ECE9E2]">
                    PV: {rec.pv_san?.join(' ') || rec.pv_uci?.join(' ')}
                  </div>
                </div>
              ))}
            </div>
          </section>
        </div>
      )}
    </aside>
  );
};
