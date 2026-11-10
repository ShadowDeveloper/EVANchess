# Audited Chess Commentary
## A research proposal for branch-conditioned, evidence-scoped explanations

**Research cutoff:** November 9, 2026.  
**Primary use case:** Post-game coaching for club players.  
**Status:** Literature-grounded proposal, not an implemented or experimentally validated system.

## Executive summary

A useful chess commentator must do more than recommend the engine's first move. It must explain a concrete consequence, distinguish that consequence from a strategic interpretation, and show why a plausible alternative is less attractive. Existing research includes data-driven commentary, neural-engine conditioning, concept-guided generation, and tool-assisted verification. Open projects also separate deterministic chess analysis from LLM narration. Consequently, neither “Stockfish plus an LLM” nor “attach an explanation to a variation” is a defensible novelty claim. [citation:Jhamtani et al., 2018](https://aclanthology.org/P18-1154/) [citation:Zang et al., 2019](https://aclanthology.org/P19-1597/) [citation:Kim et al., 2025](https://aclanthology.org/2025.naacl-long.481/) [citation:kibitz implementation](https://github.com/ekkx/kibitz)

I propose **Audited Chess Commentary**, provisionally named **EVAN**: an engine-analysis service, a branch-conditioned evidence ledger, and a constrained LLM realizer. Its narrow research question is:

> At matched inference budgets and comparable substantive coverage, does explicitly binding each contrastive explanation to its supporting branch, evidence provenance, and permissible assertion scope reduce unsupported or over-scoped commentary relative to a strong engine-and-tool-using LLM?

This is an **untested contribution hypothesis**, not an established novelty claim. The proposed distinction is the enforcement and evaluation of a *claim–witness contract*, especially when explanations contrast a played move with a plausible alternative. A supporting principal variation is a conditional example, not proof of unrestricted necessity, and an engine evaluation does not identify the engine's internal causal reasoning. The design therefore records supporting evidence, attempted checks, discovered contradictions, and unresolved uncertainty separately.

The MVP should analyze a small number of important moments in completed games, initially using Stockfish, a legal move library, deterministic tactical detectors, and prompted structured generation. Maia-2 is an optional selector of population-level plausible alternatives—not a model of what a particular player actually considered. [citation:Maia-2](https://arxiv.org/abs/2409.20553)

The decisive experiment compares EVAN with LLM-only, straightforward engine-plus-LLM, concept-guided, and strong tool-using baselines. Independent auditors assess factual correctness, evidence support, assertion scope, substantive coverage, and instructional usefulness. Results must include abstentions, discarded explanations, latency, and cost. If a flat evidence packet or a strong verifier matches EVAN at the same cost and coverage, the outcome is an engineering improvement or negative result, not a new explanation method.

---

## 1. Review scope, method, and evidence boundaries

This is a **targeted, multi-angle landscape review**, not a systematic review. The research covered commentary generation, engine/tool integration, position/concept representations, verification, human-choice modeling, and documented interfaces. It does not establish exhaustive coverage of every paper, patent, non-English publication, or closed product through the cutoff.

Evidence labels used below:

- **Published report:** A peer-reviewed paper's reported method or result; not independently reproduced here.
- **Preprint/excerpt:** A preprint, sometimes accessible only through indexed excerpts. Its claims require additional checking before use as benchmark targets.
- **Project/vendor claim:** Public documentation or a README; not an independent assessment of correctness, architecture, performance, or learning benefit.
- **Proposal/inference:** The architecture, hypotheses, limitations inferred from methods, and experimental design developed in this report.

**Important gaps.** Direct full-text HTML access failed for ACT-Eval and BinProp; the review relied on indexed excerpts for parts of those works. Accordingly, their detailed scores, model rankings, and metric definitions are **not used as quantitative premises** here. Repository descriptions were not substantive code audits. Commercial internals, training data, and comparative explanation quality could not be established from the available public evidence. No experiments, engine analyses, expert annotations, or learning-outcome study were performed for this proposal. A final novelty submission needs a renewed full-text comparison with recent symbolic, counterfactual, and sentence-to-board explanation work; this report does not claim those mechanisms are absent from prior work.

### 1.1 What the strongest accessible quantitative evidence supports

In the CCC/GCC-Eval study, five **Chess.com rapid players** rated 50 moves under five conditions. They should not be relabeled as verified expert raters. Normalized correctness/relevance/completeness ratings were **.36/.49/.40** for GPT-4o, **.43/.56/.49** with expert information, and **.60/.67/.59** for CCC. These are normalized human ratings, **not factual-accuracy percentages**. The reference comments received **.62/.52/.30**. [citation:Kim et al., 2025](https://aclanthology.org/2025.naacl-long.481/) [citation:CCC full-text version](https://arxiv.org/html/2410.20811v2)

The same study's reported error analysis distinguishes illegal-move/nonexistent-piece errors (**.46 → .28 → .20**) from wrong-position/move-evaluation errors (**.32 → .30 → .34**) across those three generated conditions. The latter figures do not show an improvement in that category; they also do not, by themselves, establish a general failure to explain strategy. Fleiss' κ was **.5393** for correctness and approximately **.1782–.2449** for the other dimensions. This motivates separate factual and subjective measures, not abandoning human evaluation or inferring statistical power from κ alone. [citation:CCC full-text version](https://arxiv.org/html/2410.20811v2)

**Interpretation:** Concept guidance is promising, but these small-study ratings neither establish that commentary is solved nor identify the cause of every residual error. There is sufficient motivation to test tighter evidential scope; there is not sufficient evidence to assert that it will work.

---

## 2. Related-work comparison

### 2.1 Commentary, verification, and adjacent research

“Not established” means the reviewed evidence did not establish the item; it does not mean the original system lacks it. Limitations marked as methodological inferences are not reported benchmark failures.

| Work / system | Approach and representation | Engine integration | Training / source data | Evaluation evidence | Strengths | Limitations and relevance | Code / data availability |
|---|---|---|---|---|---|---|---|
| **Jhamtani et al., ACL 2018** | Neural move-by-move commentary conditioned on game-state aspects | Not an engine-evidence ledger | About 298K move–commentary pairs from about 11K forum games | Automated measures and human assessment, including direct move descriptions | Foundational task and large paired corpus | Inference: imitating commentary does not certify chess truth or branch support; reference text is not a complete gold explanation | [Paper](https://aclanthology.org/P18-1154/); access and redistribution of derived data require checking |
| **Zang, Yu & Wan, ACL 2019 / SCC** | Neural commentator powered by a learned chess-engine representation | Learned policy/value knowledge rather than an explicit claim audit | Commentary corpus plus learned chess knowledge; verify precise training recipe before reproduction | Paper reports automatic and human evaluation | Early integration of chess knowledge with generation | Inference: latent knowledge does not itself provide an inspectable witness for each sentence | [Paper](https://aclanthology.org/P19-1597/), [code](https://github.com/zhyack/SCC); repository release is not complete reproducibility or license clearance |
| **CCC / GCC-Eval, NAACL 2025** | Concept probes and before/after concept changes guide GPT-4o | LeelaChessZero representations; Stockfish-derived concept targets | 200K Lichess positions for concept learning; Gameknot commentary used in task preparation | Five-player, 50-move human study; ratings and error taxonomy in §1.1 | Concrete concept grounding and multi-dimensional evaluation | Concepts and deltas are useful inputs, not proofs of a verbal reason; modest evaluation sample and low agreement on some dimensions | [Paper](https://aclanthology.org/2025.naacl-long.481/), [repository](https://github.com/ml-postech/concept-guided-chess-commentary); crawling instructions do not resolve source-text rights |
| **ACT-Eval, 2026 preprint** | Atomic-claim assessment of generated commentary with chess tools | Tool-assisted verification of chess assertions | Benchmark and atom annotations described in indexed material; release/rights need confirmation | Reports tool/no-tool comparisons; numerical definitions not independently confirmed here | Close precedent for claim-level checking | Full-text access gap; do not assume it is only post-hoc, that all atoms are independently verified, or that it omits scope without a full comparison | [Preprint](https://arxiv.org/abs/2608.04240); verify exact benchmark and code release before reproduction |
| **BinProp, 2026 preprint** | Executable binary predicates/motifs and engine-grounded explanation assessment | Engine-derived selection/evaluation signals | Position-based predicate discovery; exact recipe needs full-text confirmation | Reported explanation/engine-agreement experiments; no numerical comparisons used here | Relevant to explicit concepts, alternatives, and executable evidence | Predicate association is not a proof of causal explanation; full-text access gap prevents strong exclusion claims | [Preprint](https://arxiv.org/abs/2610.23166), [repository](https://github.com/oripress/BinProp); release terms require checking |
| **ekkx/kibitz, public project** | Documented separation of deterministic chess facts and LLM narration | Stockfish lines plus feature/motif extraction | No task-specific training established from documentation | No controlled comparison established in this review | Very close engineering precedent: engine/code facts, language-model wording | README claims are not tested guarantees; precise claim-scope and validation behavior require code audit | [Repository](https://github.com/ekkx/kibitz); license not confirmed here |
| **riskydissonance/Kibitz, public project** | Tool-connected analysis interface with variations | Stockfish/MultiPV in project description | No commentary training corpus established | No independent evaluation located | Practical alternative/variation exploration | Do not infer pedagogical benefit or claim-level verification from interface features | [Repository](https://github.com/riskydissonance/Kibitz); confirm current release and license |
| **Maia-2, NeurIPS 2024** | Skill-conditioned human move prediction | Human policy, not a truth oracle | Human Lichess games | Human move-prediction/alignment evaluations | Useful source of rating-conditioned candidate alternatives | Does not explain engine decisions or reveal an individual's thoughts; rating systems require calibration | [Paper](https://arxiv.org/abs/2409.20553), [code](https://github.com/CSSLab/maia2); check code, weights, and data terms separately |
| **Grandmaster-Level Chess Without Search, 2024** | Transformer prediction of engine action-values without search at inference | Distillation from Stockfish analysis | Engine-labeled positions/actions | Playing-strength and chess-task evaluations | Adjacent candidate-ranking/evaluation component | Not a commentary system; action-values do not provide verbal reasons or support provenance | [Paper](https://arxiv.org/abs/2402.04494v1); verify accompanying assets before adopting |

Each row links its primary paper or project; project claims must not be read as independently measured results.

### 2.2 Documented interfaces and commercial evidence

The public Kibitz guide documents explanation-oriented interaction, making it relevant to rendering evidence and variations. A sentence-to-board interaction is therefore not an adequate novelty claim. Documentation does not demonstrate that every explanatory sentence is correct. [citation:Kibitz guide](https://kibitzchess.org/guide.html) [citation:Kibitz site](https://kibitzchess.org/)

| System / class | Approach and engine integration | Training data | Evaluation / strengths | Limits and availability |
|---|---|---|---|---|
| **Kibitz documented interface** | Board-based explanations and analysis presentation described in its guide; internals should be checked rather than inferred from the UI | Not established | Useful precedent for inspectable explanations; no independent comparison established here | Public [guide](https://kibitzchess.org/guide.html); do not conflate this site with every similarly named repository |
| **Lichess analysis / move-quality classification** | Public explanation of mapping evaluations to move-quality judgments | Not an LLM training-data claim | Transparent example of distinguishing score changes from practical move labels | [Documented classification discussion](https://lichess.org/@/tolius/blog/blunder-mistake-or-inaccuracy-how-does-lichess-decide/lGMJZrYw); not evidence of an LLM commentary architecture |
| **Commercial products, including Chess.com Game Review and ChessBase explanation features** | Closed systems are relevant comparators, but the collected evidence is insufficient to specify their current LLM/engine internals | Not established | No controlled, public, apples-to-apples explanation evaluation established in this review | Proprietary code/data; product-specific architecture, latency, and reliability claims are deliberately left unverified rather than filled with assumptions |

**Commercial coverage is an evidence gap, not evidence of inferiority.** In particular, this report does not claim that commercial explanations are merely templated, that they lack provenance internally, or that EVAN would outperform them. A product-quality study would require dated official documentation, recorded outputs, permission-compatible access, and a common position set. The research experiment below can proceed without making those claims.

### 2.3 Synthesis and closest approaches

The reviewed directions contribute different pieces: paired commentary supports language learning; learned chess representations and probes provide concepts; search provides candidate lines and evaluations; symbolic tools check some assertions; public interfaces make variations inspectable. These are complementary, not cleanly successive generations. [citation:Jhamtani et al., 2018](https://aclanthology.org/P18-1154/) [citation:SCC](https://aclanthology.org/P19-1597/) [citation:CCC](https://aclanthology.org/2025.naacl-long.481/) [citation:ACT-Eval](https://arxiv.org/abs/2608.04240) [citation:Kibitz guide](https://kibitzchess.org/guide.html)

**Closest research comparisons:** CCC for concept-guided generation; ACT-Eval for atomic checking; BinProp for executable concepts and engine-grounded explanation assessment. **Closest engineering comparison:** kibitz's documented separation of analysis and narration. Additional symbolic/counterfactual explanation methods must be included before claiming publishable novelty. The proposed experiment cannot substitute for that literature check. [citation:CCC](https://aclanthology.org/2025.naacl-long.481/) [citation:ACT-Eval](https://arxiv.org/abs/2608.04240) [citation:BinProp](https://arxiv.org/abs/2610.23166) [citation:kibitz](https://github.com/ekkx/kibitz)

---

## 3. Research gap and contribution selection

### 3.1 Demonstrated limitations versus opportunities

**Supported observations:** CCC reports improved overall human ratings with concept guidance but residual errors and uneven agreement (§1.1). Recent verification research treats claim-level reliability as an explicit problem. These observations support studying commentary grounding; they do not establish that any specific architecture solves it. [citation:CCC](https://arxiv.org/html/2410.20811v2) [citation:ACT-Eval](https://arxiv.org/abs/2608.04240)

**Logical limitations, not empirical findings:** A scalar evaluation alone cannot distinguish several possible verbal reasons for the same preference. A single PV supplies a line, not an exhaustive defense tree. A legal branch comparison can demonstrate an analyzed consequence without revealing the engine's internal decision mechanism. These follow from the information contained in the proposed inputs; no benchmark result is asserted.

**Speculative opportunities:** Branch provenance may prevent mixing facts from incompatible continuations. Explicit assertion scope may prevent changing “in this line” into “necessarily.” Well-calibrated abstention may reduce unsupported claims, but may also remove exactly the explanations a learner needs. All three require experiments.

### 3.2 Candidate contributions

| Candidate | Increment over closest work | Feasibility | Novelty risk / decisive test |
|---|---|---|---|
| **C1. Audited contrastive explanations** | Bind each claim to branch/state provenance and scope; enforce those permissions through realization and independently audit final prose | High for bounded tactical claims; harder for open-ended plans | High overlap with verification and counterfactual work. Test against the same evidence flattened to text and a strong tool-using baseline |
| **C2. Strength-conditioned alternative coaching** | Select alternatives from a human policy, then tailor line length and vocabulary | Feasible with optional Maia-2 and user studies | Weak standalone novelty: human modeling and refutation explanations already exist. Must show improved relevance/learning, not just stylistic preference |
| **C3. Reliability stress test** | Independently annotated branch/scope failures, misleading explanations, and coverage-aware scoring | Feasible, annotation-heavy | A benchmark contribution only if its taxonomy and examples add beyond existing evaluation; useful even if C1 fails |

**Selection:** C1 as the primary hypothesis, C2 as an optional usefulness component, and C3 as the evaluation resource. The core study can omit Maia-2 entirely to isolate the evidential contract.

### 3.3 Explicit novelty boundary

The candidate contribution is **not** the graph data structure, tactical detectors, a counterfactual query, LLM self-critique, sentence links, or engine integration in isolation. It is a narrowly operationalized combination:

1. A representation distinguishing current-state facts, conditional line events, engine comparisons, and interpretive statements.
2. Generation and final-prose auditing that preserve those distinctions for contrastive move explanations.
3. A matched-budget, coverage-aware experiment that tests whether the distinctions reduce unsupported and over-scoped language.

**Novelty is not established.** If prior work already implements and evaluates the same contract, the contribution becomes a reproduction, comparative study, or engineering improvement. If equal-information baselines match it, the representation has no demonstrated methodological benefit. Even a successful study establishes improved *operational reliability*, not causal faithfulness to engine internals.

---

## 4. Proposed system and inference pipeline

Everything in this section is a design proposal unless explicitly cited.

### 4.1 Use case, audience, inputs, and outputs

**Primary use case:** Post-game review for club players, provisionally a 1200–2000 rating band on a stated platform. Ratings from different platforms or time controls must not be treated as interchangeable. Post-game analysis permits re-search and explicit uncertainty without the deadlines of live broadcasting. These are design reasons, not measured latency claims.

**Inputs:** PGN or a legal game prefix; optional selected move; player color; optional rating/platform and requested explanation level; analysis budget; pinned engine/configuration; tablebase availability. A FEN-only input is accepted with a warning that repetition history is unavailable.

**Outputs:** An annotated PGN or board report with a configurable small number of critical moments; for each moment, a short explanation, the played branch and selected alternative, and clickable evidence. A JSON ledger records claims, evidence, checks, revisions, abstentions, and engine metadata. If no substantive explanation is supported, the moment remains visible as an abstention rather than being replaced silently.

### 4.2 Representation: game state, branches, and claims

Use a legal board library such as python-chess, an engine accessed through UCI, and separate storage for game history and analysis. The initial implementation can use Stockfish rather than training a chess model. [citation:Stockfish](https://github.com/official-stockfish/stockfish)

**Game-state identity:** Piece placement, side to move, castling rights, en-passant state, halfmove clock, and relevant repetition/history context. Preserve the raw FEN and game prefix. A position hash convenient for caching must not accidentally erase draw-rule distinctions. UCI is the canonical move encoding; SAN is generated from the correct board for display.

**Evidence graph:** State nodes linked by legal moves; separate analysis records linked to their root states. Transpositions may share board computations where rule/history context permits, but retain distinct branch provenance. A PV is stored as an ordered conditional line, not as a proof tree.

**Engine-analysis record:** Engine version/build hash; network hash if applicable; UCI options; Threads/Hash; hash reset/reuse policy; root/history; allowed root moves; node/time limit; reported nodes, depth, selective depth, score/bound, score perspective, mate score, WDL when available, and PV. Store exact outputs. Search depth and selective depth are diagnostics, **not a simple semantic horizon or reliability probability**.

**Claim record, schematic:**

```text
claim_id, type, proposition
root_state_id, branch_id, applicable_state_ids
support_evidence_ids, evidence_source
assertion_scope, line_event_plies (if relevant)
validation_results
challenge_queries, discovered_contradictions
unresolved_questions
status: assert | qualify | abstain
```

Do not require a contradiction witness for a supported claim: a contradiction is evidence *against* it. Record challenges attempted and their outcomes. Failure to find a contradiction is not proof that none exists.

| Claim type | Acceptable support | Permitted wording / boundary |
|---|---|---|
| **State fact** | Direct legal-board computation | “The rook is undefended.” Define whether “defended” means geometric or legally effective protection |
| **Conditional line event** | Replay plus piece/material checks | “In the displayed line, the reply wins the queen.” Not “wins the queen against every defense” |
| **Engine preference / comparison** | Analyzed root moves with consistent perspective and recorded budgets | “At this analysis budget, the engine prefers A to B.” Not an unexplained universal ranking |
| **Motif** | Explicit detector definition plus supporting state/line | A geometric pin need not be decisive; an attack count is not king-safety proof |
| **Plan / interpretation** | Candidate continuation, supporting features, stability checks, and optional expert review | “One idea is…” or “The continuation suggests…”; engine agreement is not intent |
| **Exact outcome** | Applicable exact adjudication or tablebase semantics, with all prerequisites checked | State the result under the applicable rules; do not infer a unique forced move or optimal line without checking it |

### 4.3 Architecture

```text
PGN / FEN + history + user profile
               |
       Legal parse and validation
               |
       Budgeted engine orchestrator
               |
   Critical-moment and alternative selection
               |
    Legal branch expansion + evidence ledger
               |
       Typed candidate claim builder
               |
      Support / scope / challenge checks
               |
   LLM realization using permitted claims only
               |
 Independent final-prose checks and alignment
               |
 Report + variations + provenance + abstentions
```

The LLM is a language planner/realizer and, optionally, a proposer of questions to tools. It is not trusted to determine legality, invent a variation, or infer the truth of a motif from a FEN. Prompting does not guarantee compliance; the last stage is essential and itself fallible.

### 4.4 Step-by-step inference

**1. Validate the game.** Parse PGN and replay every move. Reject unsupported variants and malformed positions with a clear error; never silently repair a game and analyze the altered position. Preserve side-to-move and rule history. Validate promotions, castling, and en passant.

**2. Run a coarse analysis pass.** Analyze positions before and after played moves under a modest fixed budget. Normalize score perspective, distinguish mate from centipawn scores, and retain bounds. Exclude incomplete or failed searches from confident comparisons.

**3. Select critical moments.** Rank candidates using a transparent combination of evaluation change, close choices, detected tactical/positional features, and phase diversity. Avoid a multiplicative rule that automatically suppresses rare but important resources. Select a provisional three to six moments as a UI choice, then measure its effect. Run a fixed, independently selected position benchmark as well, so selection cannot hide difficult examples.

**4. Select alternatives.** Always include the played move and engine-preferred candidate. Add one or two legal alternatives based on engine proximity or a human policy such as Maia-2. Re-evaluate all retained candidates; a move absent from the top MultiPV list still needs explicit analysis. A policy probability means “plausible under this population model,” not “the player considered this.” [citation:Maia-2](https://arxiv.org/abs/2409.20553)

**5. Allocate deeper search.** Re-search the chosen branches under a documented resource policy. MultiPV can nominate candidates, followed by root-restricted searches with comparable resource allocations. Equal depth does not imply equal reliability; equal nodes does not either. Record both and check stability across increased budgets. The claim is a reproducible observation about these analyses, not a guarantee of objective optimality.

**6. Build replayable evidence.** Replay every line from its own root. Compute material changes, checking sequences, legal captures, and a conservative initial motif set. Start with simple facts such as an unprotected target, a double attack, or a promotion sequence; distinguish geometric relations from tactically effective threats. Complex positional labels remain heuristics with exposed definitions.

**7. Challenge promising explanations.** If the candidate explanation says B permits a tactical loss, analyze plausible defensive replies after B and compare the relevant continuation after A. Store the best discovered defense, refutations, and search failures. The MVP uses **legal continuations and move alternatives only**. Removing a bishop or blocking a pawn by editing the board changes many properties and is not a clean causal intervention; such synthetic positions are excluded from core causal claims.

**8. Propose and validate typed claims.** Rules construct a small set of facts, line events, comparisons, and qualified interpretations. Check that their evidence refers to the correct branch and state. An evidence item on B cannot justify a statement about A. Exact line events can be verified mechanically; explanatory completeness and the relevance of a strategic feature often cannot.

**9. Realize the permitted content.** Prompt a fixed LLM with claim IDs, safe scope, selected board/variation context, and an audience style guide. Request structured output mapping each sentence or clause to claim IDs. The model may combine compatible claims or decline to realize one. It must not upgrade “in this continuation” to “forced,” or “the engine prefers” to an unsupported causal account.

**10. Check the final text.** Validate all move notation in its intended context. Extract final-prose propositions independently of the generator's tags; compare with the ledger. Explicitly inspect connectives such as “therefore,” “only,” “must,” and “because,” which can add claims without adding chess nouns. A second LLM may assist extraction, but is not an authoritative judge. Revise once or use a safe template; record the original failure and any fallback. A ledger check passing does not certify every natural-language implication.

### 4.5 How engine numbers become explanations

The engine supplies candidate preferences and continuations; deterministic replay supplies concrete consequences. The proposed commentary combines them without treating them as equivalent.

A schematic, **not analyzed chess**, example illustrates the distinction:

- Engine observation: A is preferred over B under the recorded searches.
- Replay observation: In a selected continuation after B, a double attack wins material.
- Permitted explanation: “B allows this double-attack sequence in the analyzed line. A avoids that immediate pattern and is the engine's preferred choice at this budget.”
- Not established: “A is best because it is the only move that prevents a forced material loss.”

The last assertion needs substantially stronger coverage of legal alternatives and defenses. Even if established tactically, it would not identify the internal cause of the engine's choice.

Report centipawns when useful, with perspective and engine context; do not pretend they are universal probabilities. Native engine WDL and empirical human win-probability mappings have different meanings. Neither is a calibrated probability that a verbal explanation is correct. Lichess's documented move-label mapping is a useful example of an operational classification, not a universal law of chess quality. [citation:Lichess classification discussion](https://lichess.org/@/tolius/blog/blunder-mistake-or-inaccuracy-how-does-lichess-decide/lGMJZrYw)

### 4.6 Uncertainty and disagreements

- **Search instability:** Record reversals and close rankings across budgets. Qualify or omit the preference; retain true board facts.
- **Near-equal moves:** Say the engine finds several comparable options. Do not equate close scores with identical instructional value.
- **Different engines:** Show disagreement rather than voting it away. Optional Stockfish/Lc0 checks are robustness probes, not independent proofs or calibrated confidence.
- **Tablebases:** Use only when installed tables, position validity, castling restrictions, rule-50 interpretation, and WDL/DTZ semantics apply. A tablebase outcome alone does not prove a unique move or a specified forced sequence.
- **Human policy versus engine:** They answer different questions. A likely human move can be objectively inferior; an engine-best move can be hard to discover.
- **Incomplete explanations:** Say “the engine prefers this, but the current evidence does not support a concise reason” rather than fabricate a strategic story.

### 4.7 Components, resources, latency, and cost

| Component | Initial choice | Alternative / trade-off |
|---|---|---|
| Legal representation | Mature legal-board library, UCI/SAN and PGN | Custom implementation raises correctness burden; pin dependency versions |
| Engine | Pinned Stockfish build | Lc0 as optional cross-check; distinct hardware needs and still no causal explanation oracle |
| Branch store | JSON/SQLite with explicit state and analysis IDs | Graph database unnecessary for the MVP |
| Concepts | Small auditable deterministic set | CCC-style probes or BinProp predicates later; require independent validation before use |
| Realizer | One fixed API or local instruction model, prompting plus schema | Fine-tune only if development evidence shows a persistent realization failure or cost advantage |
| Human alternatives | Engine-close moves initially | Maia-2 optional; weights, data terms, and rating calibration are dependencies |
| Audit | Legal replay and rule checks plus assisted proposition extraction | No single LLM-as-judge score as final truth |

**Resource assumption:** One CPU workstation for serialized engine work; an API model avoids an initial GPU dependency. A local language model or Lc0 may require GPU resources. These are deployment choices, not benchmark measurements.

Define the budget before testing. An illustrative pilot profile could allocate a small coarse node budget to each half-move, larger budgets to selected branches, and a capped number of challenges and LLM revisions. The values must be tuned on development data. Do not claim that a given node count implies a fixed depth, runtime, or dollar cost.

If a game has `P` analyzed half-moves, `M` selected moments, and `B` retained branches per moment, engine work is approximately:

```text
P * N_coarse
+ sum_over_selected_branches(N_deep)
+ sum_over_challenges(N_challenge)
```

Count MultiPV nodes as actually reported; do not multiply the same shared search count by the number of displayed PVs. For LLM cost, record every call's input/output tokens, retries, model/pricing date, and actual billed amount. Report engine wall time and API latency separately, with p50/p95, hardware, concurrency, and cache hit rate. A local deployment still has hardware and electricity costs.

Exact reproducibility is not guaranteed simply by setting nodes. Pin versions, options, thread count, hash policy, and analysis order; prefer single-thread runs for experimental control, store raw outputs, and run repeatability checks. Production parallelism is a separate benchmark. Cache only with rule-aware state and configuration keys.

---

## 5. Data plan, licensing, and leakage

### 5.1 Candidate datasets and allowed uses

A public download is not sufficient permission for every training or redistribution use. Dataset licenses, originating commentary rights, code licenses, and model-weight terms must be reviewed separately.

| Resource | Proposed use | License / access status | Quality and leakage risks |
|---|---|---|---|
| **Lichess public games** | Sample positions and games by phase/rating/time control | Lichess database distributes relevant open game data under CC0; confirm the exact file and current terms at acquisition | Ratings are platform/time-control specific; repeated openings and usernames; remove unnecessary identifiers. [Source](https://database.lichess.org/#evals) |
| **Lichess evaluation database** | Sampling and preliminary difficulty screening; reanalyze final test positions | Public database; archive applicable dataset terms separately | Heterogeneous analysis budgets/configurations; not a gold explanation and not a substitute for controlled re-search. [Source](https://database.lichess.org/#evals) |
| **Lichess puzzles** | Candidate tactical stress tests after independent checking | Confirm puzzle-specific terms rather than inherit unrelated game-file terms | Famous/public puzzles can be memorized; solution strings do not prove a complete explanation. [Database documentation](https://database.lichess.org/#evals) |
| **2018 commentary corpus / SCC / CCC preparations** | Historical comparison or reference style, subject to permission | Rights to processed splits and original forum text require checking; do not assume a repository license clears scraped text | Informal/noisy comments, partial game context, public-web memorization; never use raw commentary as unquestioned correctness gold. [2018 paper](https://aclanthology.org/P18-1154/) [SCC repository](https://github.com/zhyack/SCC) [CCC repository](https://github.com/ml-postech/concept-guided-chess-commentary) |
| **YouTube-derived commentary dataset** | Optional style/alignment exploration only | Listed as CC BY-NC 4.0 in the reviewed dataset description; confirm terms and underlying creator rights before use | ASR/board alignment errors; noncommercial restrictions; a dataset label does not establish permission for originating audiovisual material. [Dataset](https://www.kaggle.com/datasets/huberthamelin/chess-reviews-from-youtube) |
| **ACT-Eval / GCC-Eval resources** | Secondary comparability/reporting sets if accessible | Confirm actual released files, annotation terms, and overlap before use | Public benchmark contamination and metric-definition differences. [ACT-Eval](https://arxiv.org/abs/2608.04240) [CCC](https://github.com/ml-postech/concept-guided-chess-commentary) |
| **New independently annotated set** | Primary support/scope and contrastive evaluation | Create with contributor agreements, compensation, and an explicit release license; obtain game-use permissions where needed | Expensive; annotator omissions, engine anchoring, and shared engine blind spots |

The dataset-documentation links above are acquisition starting points. Terms not explicitly confirmed must be treated as an access gate, not filled in from memory. No restricted corpus is essential to the MVP.

### 5.2 Constructing the new set

**Proposed scale, contingent on a pilot:** Approximately 30–50 development positions for schema/rubric refinement, followed by a few hundred held-out positions if annotation resources permit. These are planning quantities, not powered sample sizes.

1. Sample finished games with a frozen protocol spanning tactical, quiet strategic, opening, and endgame positions. Do not select exclusively on whether EVAN can explain them.
2. Ask independent annotators to identify the instructional question, legal alternatives worth discussing, supported core observations, and known traps. Retain disagreements and multiple acceptable explanations.
3. Use separate, larger-budget engine checks and applicable tablebases to challenge concrete claims. Annotations must record source, perspective, and conditional scope.
4. Double-annotate a pilot, adjudicate with a third reviewer, and publish the rubric. Estimate time and reliability before expanding.
5. Freeze the held-out set, sampling process, evidence-audit rules, and analysis plan before model tuning ends.

Humans can consult analysis to assess correctness, but auditors should not simply accept the system's own ledger. For support auditing, they inspect the cited evidence; for truth/robustness auditing, they additionally use independently obtained analysis. These are different judgments.

### 5.3 Leakage controls

Split by game, then group near-duplicate positions, transpositions, and opening families where feasible. Preserve full rule/history context for correctness while using coarser board hashes for duplicate detection. Track few-shot examples, prompt development positions, human annotations, synthetic training data, and every benchmark source.

Hold out a prospectively acquired or newly played set when possible. New dates reduce some overlap but cannot guarantee absence from proprietary pretraining, and public famous positions remain contamination risks. Report benchmark-known and less-public strata separately. Do not assert that excluding a date range eliminates overlap with a probe model or pretrained LLM.

### 5.4 Training strategy and licensing dependencies

Start **without task-specific fine-tuning**. Engine retrieval is on-demand analysis, not textual retrieval-augmented generation. A small curated glossary can support audience wording but cannot establish position-specific truth.

If prompting is insufficient, fine-tune the realizer on permitted claim-to-text pairs, including correct qualifications and abstentions. Keep synthetic data out of the test set and out of evaluator training. Validation-generated labels inherit validator blind spots; they are useful supervision, not independent gold.

Stockfish's repository documents GPL licensing; redistribution obligations need a deployment-specific review. Calling a separate UCI process is an architectural choice, not a universal licensing exemption. Check board-library, Lc0, Maia-2 code/weights, and dataset terms independently; do not attribute all engine/network assets a single blanket license. [citation:Stockfish repository and license](https://github.com/official-stockfish/stockfish) [citation:Lc0 license](https://github.com/LeelaChessZero/lc0/blob/master/COPYING) [citation:Maia-2 repository](https://github.com/CSSLab/maia2)

---

## 6. Evaluation: correctness without vacuous precision

### 6.1 Testable hypotheses

**H1 — Primary:** At matched total budgets and comparable substantive coverage, EVAN reduces independently assessed unsupported-or-over-scoped contrastive claims relative to both a straightforward engine-plus-LLM pipeline and a strong tool-using verifier baseline.

**H2 — Mechanism:** Giving the same underlying evidence explicit branch/scope structure and enforcing that structure reduces branch-confusion and scope-escalation errors compared with a flattened evidence packet. If not, the graph contract lacks demonstrated incremental value.

**H3 — Usefulness:** Improved support does not produce an unacceptable loss of audience-rated instructional usefulness or substantive reference coverage. Define the practical non-inferiority margin from a pilot and stakeholder judgment before the held-out test, not after seeing results.

**H4 — Calibration and robustness:** As analysis becomes unstable or relevant evidence is removed, the system qualifies/abstains appropriately rather than maintaining the same assertive prose. Test this by controlled evidence perturbations as well as observational difficulty strata.

**Optional H5:** Human-policy-selected alternatives improve perceived relevance or transfer performance compared with engine-only alternatives under the same explanation budget. This is independent of the core grounding claim.

No minimum effect size, runtime, sample-size power, or performance result is asserted in advance. Pre-register target effects and power only after estimating variability and annotation reliability in the pilot.

### 6.2 Baselines

Use the same realizer model/version, audience instructions, and output-length target unless a difference is the factor under study.

| Baseline | Inputs / behavior | What it tests |
|---|---|---|
| **B0: LLM only** | Legal position plus game/move context, no engine tools | Value of external chess evidence; not a presumed numerical “floor” |
| **B1: Straightforward engine + LLM** | FEN/history, selected move, evals, and PVs; ordinary explanation prompt | Required basic integration baseline |
| **B2: Concept-enriched prompting** | B1 plus matched feature/concept descriptions | Whether organized chess concepts suffice. Label a simplified implementation as a proxy, not a CCC reproduction |
| **B3: Strong tool-using agent** | Same tool capabilities, capped search/node/time/token budgets; allowed to request comparisons, challenge claims, and revise prose | Increment over competent tool use and verification, not over an intentionally weak prompt |
| **B4: Equal-information flat packet** | Exact evidence content available to EVAN, rendered as a flat list with provenance stated in prose; comparable final audit | Whether explicit structure/enforcement adds beyond more evidence |
| **B5: Templates from the ledger** | Validated claims with deterministic wording | Value of the LLM for readability/usefulness; separates evidence construction from realization |

B3 should have the tools relevant to recent tool-assisted verification, but must not be called an exact ACT-Eval reproduction without reproducing its protocol. Cross-paper published ratings are context only, not directly comparable test results. [citation:ACT-Eval](https://arxiv.org/abs/2608.04240) [citation:CCC](https://aclanthology.org/2025.naacl-long.481/)

### 6.3 Two complementary budget comparisons

**Equal-information experiment:** Freeze branch selection and engine evidence. Give B1/B2/B4/EVAN equivalent information to isolate representation, realization constraints, and auditing. Include a control that uses ordinary prose provenance so the claimed effect is not merely from hiding identifiers from a baseline.

**End-to-end budget experiment:** Start from the same positions and cap total engine nodes or compute, LLM tokens/calls, and wall time. Count exploration, failed calls, repairs, and fallbacks. B3 may allocate the budget adaptively. Evaluate quality–coverage–cost curves rather than selecting one favorable operating point.

An “unlimited tools” agent is not a matched-cost baseline. An optional high-budget reference can estimate attainable quality, but must be labeled separately.

### 6.4 Ablations

Use identical underlying positions and, where possible, the same evidence and realizer:

- Remove **branch bindings**, preserving the factual content.
- Remove **scope enforcement**, preserving scope metadata, to test whether merely stating scope is sufficient.
- Remove **challenge searches** while reallocating or explicitly accounting for their saved budget.
- Remove **final-prose auditing** to measure realization-induced errors.
- Remove **abstention**, forcing an explanation or template; include all failures in results.
- Replace the LLM with **templates**.
- Remove **human-policy selection**, holding the number of alternatives fixed.

Keep assertion classes comparable. If an ablation simply forbids all difficult claims, report that change as a coverage shift, not an improvement in their correctness. A small factorial subset can investigate interactions if resources allow; avoid claiming additive mechanisms from isolated ablations alone.

### 6.5 Measures and denominators

| Dimension | Primary operational measure | Independent check / limitation |
|---|---|---|
| **Chess truth** | Supported true, false, ambiguous/unknown atoms among all extracted asserted atoms | Board replay, applicable tablebases, independent deeper analysis, expert judgment; finite searches leave unknowns |
| **Evidence support** | Fraction of asserted substantive atoms justified by the evidence actually cited, under the permitted scope | Independent auditors assess the link, not only whether the cited line exists; true statements may still be unsupported |
| **Scope validity** | Unsupported universality, branch transfer, or causal/necessity escalation per assertion and per position | Written rubric; quote the offending clause and the narrower supported version |
| **Line / notation accuracy** | Legal replay rate, SAN-context validity, state/material consistency | Deterministic checks; legality alone does not establish quality |
| **Substantive coverage** | Fraction of independently defined instructional units covered, plus explanations delivered per requested position | Multiple valid explanations and incomplete reference units require expert adjudication |
| **Usefulness / completeness** | Target-user and expert ratings with anchored rubrics; relevance of alternatives | Separate from fluency and truth; preference is not evidence of learning |
| **Readability** | Audience comprehension and fluency ratings | Length/jargon scores are diagnostic proxies, not primary quality metrics |
| **Robustness / abstention** | Error–coverage curves, abstention by difficulty, outcomes under evidence perturbation | Report all requested cases, including dropped moments and fallback templates |
| **Runtime / cost** | Engine nodes/time, total tokens/calls, p50/p95 wall time, measured cost per requested and delivered explanation | Include retries, discarded outputs, caches, hardware, and model/date |

**Critical terminology:** The fraction of asserted claims that passes an audit is **audited precision/support**, not coverage. “Coverage” must refer to independent instructional targets or requested cases. A system that says only “White has a king” can achieve high precision and fail the task.

Report unweighted atomic results and position-level macro averages. Define segmentation rules before scoring, since splitting a harmless sentence into many atoms can inflate denominators. Any weighted score needs weights fixed independently of system output. Publish raw counts and unknown/abstained cases rather than collapse everything into one score.

Automated move legality and line replay are strong for their narrow predicates. Motif detectors and LLM judges have failure modes; calibrate them against held-out human labels and report false positives/negatives. Text-overlap metrics cannot distinguish a correct explanation from a similar but false one. Engine preference agreement measures agreement with an evaluator, not pedagogical usefulness, complete strategic explanation, or internal decision faithfulness.

### 6.6 Human evaluation and statistical plan

Use two complementary panels: strong players for chess truth/support/scope, and learners across the intended skill bands for clarity, relevance, and usefulness. Recruit based on documented platform/rating or coaching credentials; do not infer expertise from playing chess online. Final rater counts and workload depend on the pilot, budget, and power analysis.

Blind system identity, randomize presentation order, and counterbalance repeated positions to reduce memory effects. Use both absolute anchored judgments and paired comparisons. Conduct a separate “evidence visible” condition if the audit UI itself is being tested; otherwise keep presentation equivalent across systems.

Annotators first judge the text independently, then inspect cited evidence and additional analysis as required. Mark **correctness**, **support**, **scope**, and **missing instructional content** separately. A true tactical fact can be irrelevant; a persuasive explanation can be false. Two annotators and adjudication are a reasonable starting design, not a promise of sufficient reliability.

Use paired, position/game-clustered confidence intervals or an appropriate hierarchical model accounting for rater and game effects. Pre-register the primary comparison and handle multiple secondary comparisons transparently. Sample-size planning must use pilot effect variance, clustering, and expected missingness; κ alone does not determine power. If scope agreement is poor, revise the rubric and re-pilot before freezing the final test rather than substituting preference for correctness.

**Learning is a separate outcome.** If claiming instructiveness as improved learning, run a later randomized study with unseen transfer positions and delayed retention, not only “helpful” ratings. Stratify by skill and distinguish performance on near-identical motifs from general improvement.

### 6.7 Held-out and adversarial testing

Include naturally sampled positions plus labeled stress strata:

- Sound sacrifices and tempting recaptures that fail to intermediate moves.
- Quiet defensive resources, long-term compensation, and shallow-search reversals.
- Close engine rankings where “only move” would be unjustified.
- Geometric pins that do not make a move illegal; apparent threats that fail tactically.
- Transposed positions with different draw-rule histories; castling, en passant, underpromotions, stalemate, and rule-50 edge cases.
- Legal alternatives plausible to the audience, not just deliberately bad moves.
- False user premises such as an allegedly decisive bishop pair; the system should challenge the premise when unsupported.
- Correct claims attached to the wrong branch, wrong color/perspective, or wrong ply.
- False or over-scoped natural-language evidence injected into an otherwise valid packet.
- Position-specific plan labels that remain fluent after their supporting evidence is removed.

For **misleading-language tests**, hold chess evidence fixed and vary the false description. For **evidence-sensitivity tests**, remove or swap support while keeping irrelevant surface details constant. For **truth robustness**, independently analyze alternatives with a larger budget. These answer different questions and should not be combined into a single “faithfulness” score.

Reject untrusted game comments as instructions or authoritative facts. A malicious PGN annotation should not change tool permissions or override the evidence policy.

---

## 7. Implementation roadmap and feasibility

The schedule is staged by acceptance evidence rather than a promised completion date. A restricted prototype may take several researcher-weeks; independent annotation and comparative evaluation are a substantially larger effort whose duration depends on recruitment and rubric stability.

| Stage | Deliverable | Acceptance / decision gate |
|---|---|---|
| **0. Reproduction and evidence check** | Confirm closest full texts and available artifacts; license inventory; small test corpus; basic B1/B3 baselines | If an existing method already implements the same contract, revise the novelty claim before building |
| **1. Minimal engine prototype** | Legal PGN replay, pinned engine runner, root comparisons, cached raw outputs, templated conditional explanations | Unit tests cover legality, perspective, mate scores, branch identity, and rule-history edge cases; no causal claims |
| **2. Restricted LLM MVP** | Typed claims, prompted realization, sentence/claim alignment, final-prose checking, recorded fallbacks | On development positions, independent audit finds manageable error classes and nontrivial useful coverage; measure cost before scaling |
| **3. Research mechanisms** | Scope permissions, legal challenge searches, equal-information controls, controlled evidence perturbations | Pilot shows annotation reliability and no obvious evidence-budget confound; freeze hypotheses and protocol |
| **4. Held-out comparative study** | Matched-budget baselines, ablations, adversarial strata, independent human evaluation | Primary effect and usefulness/coverage trade-offs evaluated with uncertainty; publish null/negative outcomes |
| **5. Optional extensions** | Maia-2 alternatives, interactive “why not?”, probes/predicate discovery, model compression, UI experiment | Add only after the core effect is separated from extra evidence/compute |

Live commentary is a later, different operating point. Coarse preanalysis, speculative analysis of likely replies, caching, and a small realizer may help, but time pressure must not silently lower the evidential standard. Measure live quality under an explicit deadline rather than extrapolate post-game results.

### 7.1 Principal risks and mitigations

| Risk | Why it matters | Mitigation / rejection signal |
|---|---|---|
| **Novelty overlap** | Prior symbolic, counterfactual, or provenance work may already cover C1 | Full-text comparison and code audit before submission; reframe as comparative engineering if necessary |
| **True facts, wrong lesson** | A valid line may be incidental rather than the important reason | Independent instructional units and expert completeness judgments; avoid claiming engine causal faithfulness |
| **Self-certifying evaluator** | System-generated witnesses can pass its own checks by construction | Independent support audit and separate higher-budget truth checks; report validator error rates |
| **Vacuous precision** | Easy claims and silent dropping hide failures | Fixed benchmark cases, substantive coverage, all-case reporting, error–coverage curves |
| **Confounded counterfactuals** | Board edits alter material, legality, and strategic context | Legal branch comparisons in core system; edited positions only as explicitly exploratory probes |
| **Search instability / engine monoculture** | Engine preferences can change with resources and share biases | Budget sensitivity and optional alternate-engine checks; qualify disagreements |
| **Prose escapes permissions** | Connectives introduce necessity or causation | Independent clause extraction, targeted checks, safe templates; no claim of perfect prevention |
| **Low annotation reliability** | Support and scope may be hard to operationalize | Pilot and adjudicated examples; narrow claims or tasks if disagreement remains high |
| **Cost escalation** | Branches, challenges, and repairs multiply work | Hard budget caps and measured marginal utility; compare Pareto frontiers |
| **Audience mismatch** | Accurate comments can be too complex or trivial | Skill-stratified user testing; distinguish vocabulary tailoring from genuine learning |
| **Rights / access failure** | Scraped text and model assets may be unusable | Position-based MVP with permitted data; restrict or replace questionable resources |

### 7.2 Conditions for rejection or revision

Reject the methodological claim if the best equal-information or tool-using baseline matches EVAN within the pre-registered practical margin at comparable cost and coverage. More metadata alone is not an explanation advance.

Revise the task if gains arise solely from suppressing difficult claims, if useful coverage falls unacceptably, if lower cost rather than better grounding explains the outcome, or if human audits do not agree reliably enough to test scope. Drop causal/necessity wording entirely if it cannot be checked under the chosen task. Do not “fix” a failed study by redefining its primary metric afterward.

If the full method fails but templates, audit tooling, or the adversarial taxonomy are useful, release those with the negative result. Claims about broad pedagogical value require separate learning evidence.

---

## 8. Bottom line

The defensible proposal is a **bounded reliability experiment for contrastive commentary**, not a claim to recover why an engine thinks. Engine search supplies preferences and example continuations; legal replay supplies concrete conditional facts; an LLM turns permitted content into audience-appropriate language. The research question is whether explicit provenance and assertion-scope enforcement improve what is actually said, beyond strong tool use and the same evidence supplied plainly.

The feasible starting point is deliberately narrow: post-game analysis, a small auditable motif vocabulary, legal alternative branches, prompting rather than new model training, and independent evaluation that penalizes both unsupported prose and unhelpful silence. Success would be a measured quality–coverage–cost improvement. Failure would still clarify whether evidence structure, extra search, or language realization is the real bottleneck.

---

## Source bibliography

### Primary research

1. [Jhamtani et al. (2018), *Learning to Generate Move-by-Move Commentary for Chess Games from Large-Scale Social Forum Data*](https://aclanthology.org/P18-1154/) — Foundational paired commentary corpus and neural generation study.
2. [Zang, Yu & Wan (2019), *Automated Chess Commentator Powered by Neural Chess Engine*](https://aclanthology.org/P19-1597/) — Learned chess knowledge for commentary generation.
3. [Kim et al. (2025), *Bridging the Gap between Expert and Language Models: Concept-guided Chess Commentary Generation and Evaluation*](https://aclanthology.org/2025.naacl-long.481/) — CCC/GCC-Eval, concept guidance, human ratings, and error analysis.
4. [CCC full-text preprint version, arXiv:2410.20811v2](https://arxiv.org/html/2410.20811v2) — Detailed tables consulted; use the published version for authoritative bibliographic metadata.
5. [*Hallucinations on the Board: Tool-Augmented Evaluation of LLM Chess Commentary*, arXiv:2608.04240](https://arxiv.org/abs/2608.04240) — ACT-Eval; full-text access incomplete in this review, so detailed numerical comparisons are not relied upon.
6. [*Explaining Chess and Go in Natural Language*, arXiv:2610.23166](https://arxiv.org/abs/2610.23166) — BinProp; full-text access incomplete, requiring follow-up before exact method/metric reproduction.
7. [Tang et al. (2024), *Maia-2: A Unified Model for Human-AI Alignment in Chess*](https://arxiv.org/abs/2409.20553) — Strength-conditioned human move prediction, not explanation verification.
8. [*Grandmaster-Level Chess Without Search*, arXiv:2402.04494v1](https://arxiv.org/abs/2402.04494v1) — Adjacent engine-distillation work; not a commentary system.

### Implementations and documented interfaces

9. [SCC implementation](https://github.com/zhyack/SCC) — Commentary project and data preparation notes.
10. [CCC implementation](https://github.com/ml-postech/concept-guided-chess-commentary) — Concept-guided commentary code and preparation instructions.
11. [BinProp implementation](https://github.com/oripress/BinProp) — Executable-predicate project; verify current artifact/version and license.
12. [Maia-2 implementation](https://github.com/CSSLab/maia2) — Human-policy model; inspect code/weight terms separately.
13. [ekkx/kibitz](https://github.com/ekkx/kibitz) — Documented deterministic-analysis/LLM-narration separation; not an independently evaluated result.
14. [riskydissonance/Kibitz](https://github.com/riskydissonance/Kibitz) — Tool-connected chess-analysis project; do not conflate similarly named projects.
15. [Kibitz user guide](https://kibitzchess.org/guide.html) — Explanation-interface documentation, not a correctness benchmark.
16. [Kibitz project site](https://kibitzchess.org/) — Public interface description; association with any repository needs verification.
17. [Official Stockfish repository](https://github.com/official-stockfish/stockfish) — Engine implementation, releases, and licensing.
18. [Lc0 license](https://github.com/LeelaChessZero/lc0/blob/master/COPYING) — Component-specific licensing reference, not blanket clearance of all related assets.

### Data and operational documentation

19. [Lichess database and evaluation downloads](https://database.lichess.org/#evals) — Acquisition entry point; confirm exact file-specific terms and configuration metadata.
20. [YouTube-derived chess commentary dataset](https://www.kaggle.com/datasets/huberthamelin/chess-reviews-from-youtube) — Optional dataset with alignment and rights caveats; not a gold explanation set.
21. [Lichess: blunder, mistake, or inaccuracy classification](https://lichess.org/@/tolius/blog/blunder-mistake-or-inaccuracy-how-does-lichess-decide/lGMJZrYw) — Operational score-to-label mapping; not a universal calibration of explanation correctness.

**Evidence reminder:** Links identify the reviewed sources; they do not imply independent reproduction, code audit, confirmed redistribution permission, or a complete search through the cutoff. The proposal's architecture, hypotheses, sample scales, and roadmap are untested design choices.
