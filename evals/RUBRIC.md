# Synchronised prompt-pack rubric v1

The unit is one requirement change, one versioned pack, one repetition, one arm.
The primary outcome is C: the number of unique atomic facts that cannot both be
true in frontend and backend instructions for the SAME operation and state.
Build success, code quality and agent speed are not project outcome measures.

## Human labels

| Label | Meaning | Evidence |
| --- | --- | --- |
| consistent | Required fact agrees with target and retained rules | Every required side |
| contradiction | Both sides assert incompatible rules | Exact quotes from BOTH sides |
| omission | Required rule/instruction absent | Explain what is missing; quote present side if any |
| uncertain | Meaning or applicability cannot be resolved | Quote ambiguity when present; explain uncertainty |
| common_error | Both sides agree but jointly violate the target | Exact quotes from BOTH sides |

Examples: string vs integer, PATCH vs PUT for the same endpoint, owner-only vs
all-users permission, zero- vs one-based pagination, rejected vs accepted null,
different error status for the same condition, obsolete vs restored field limit.
"string" and "text" need not conflict. Different endpoints or operations do not
conflict simply because their methods differ. A historical old-state quote is
not a target instruction unless the prompt actually asks the agent to implement it.

## Evidence and counting

Review only prompt text in `frontend_prompt.prompt` and `backend_prompt.prompt`.
Evidence uses zero-based Python character offsets, `[start,end)`; quote MUST
equal the exact substring. Offsets count Unicode characters, not bytes or lines.
Each assessment records fact ID, label, explanation, and evidence spans.
Count repeated statements about the same atomic fact once. Duplicate same-ID,
same-label assessments count once; inconsistent labels for one ID are rejected.
Use `extra:<semantic-id>` for new observed conflicts not covered by gold facts;
these still need both-side evidence and human semantic deduplication. Do not use
different IDs to count repeated wording of the same conflict multiple times.

Code verifies structure, scope flags, completeness of annotations, exact evidence
spans and fact-ID counting. It does NOT decide unrestricted natural-language
entailment. Human review must check path/method, request/response types, required
fields/nullability, enum values, permissions, paging, errors, history and retained
constraints, not just the wording of facts that happen to be easy to find.
No model judge or automatic semantic repair is enabled. If adding a model
extractor later, first freeze separate human normal/conflict calibration pairs
and report TP/FP/FN, precision=TP/(TP+FP), recall=TP/(TP+FN); it cannot replace
human truth or share generation outputs as calibration labels.

## Failures and denominator

Empty/malformed pack, missing required side, incorrect needed flag, generation
failure, missing outcome, omitted necessary fact or unresolved review: C is null,
NOT zero. `observed_contradictions` retains conflicts found in otherwise
unevaluable packs. A complete common-error pack may have C=0 but is NOT success.

Success = evaluated, complete, zero contradictions, zero common errors.
Valid-zero rate = successes / ALL planned units, including failures and pending
reviews. Target >= 0.90. C total/mean/distribution use evaluable packs ONLY, with
their count shown. Never imply that a low C mean makes failures successful.
Each method's rate matters; overall combines different arms, not a system score.

## Blind review and interpretation

Export random review IDs and shuffled packets, without method/repeat/chain IDs.
Read `packets.json` and fill `reviews.json`; do not inspect `blind-key.json` or raw
run directories until review is complete. Set status=reviewed, your actual name,
human_attestation=true only after checking every fact. Blinding is practical,
not cryptographic; style may reveal the method. One reviewer is a limitation.

After unblinding inspect paired baseline-minus-joint C differences and per-chain,
per-repeat rates. Missing pairs stay null. A zero-C baseline means a tie, not an
improvement. Do not treat successive chain steps or repeated stochastic runs as
independent samples or claim statistical significance from 288 independent cases.
Conclusions cover one repo, ten manual chains and one human reviewer only, not
general code quality, developer productivity or universal synchronisation.
