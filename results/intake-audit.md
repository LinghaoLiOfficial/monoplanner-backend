# Dataset intake and experiment readiness, 2026-10-03

Source: `data/intake/Monoplanner_Data_Specification_ZH_v2.md`, SHA-256
`a92983e73c9a9fc627dccf47124609343c284a02fb9b282efd323fd90947f55b`.
This audit records available evidence, not a model benchmark report.

| Check | Observed result | Consequence |
| --- | --- | --- |
| Scenario rows | 10 chains, 30 ordered steps (6 dev, 24 test) extracted | Requirement draft exists |
| Independently reviewed ground truth | No complete per-step `gold_label` file or review sign-off; section 22.2 explicitly states this | Cannot establish frozen truth |
| Pack inputs | Existing `data/inputs/benchmark.json` remains empty draft snapshots and change sets | Generation must not start |
| Answer schema | Existing evaluator accepts `Fact` without `gold_label`; received 2.0 specification requires it | Adapter, validator, scoring and tests need a versioned update |
| Provenance | Document states AI-assisted scenario design, human review pending; existing schema requires `human_handwritten` and true attestation | Cannot assert compliant human-authored dataset |
| Offline sources | Document cites API mount/config/registration and package dependency files absent from checked-in source subset | Offline replay/source validation incomplete |
| Dataset validation | Rejected with 181 schema errors on current draft | No pilot/formal freeze |
| Software tests | 28 passed, 0 failed; Ruff passed | Only verifies evaluator software, not model quality |
| Model experiment | 0 units generated, 0 reviewed | `C_total`, `C_mean`, valid-zero rate and paired differences are **undefined**, not zero |

Required sequence for a valid experiment:

1. Complete the cited offline source set and verify bytes/line references against
   the pinned commit; correct disputed static claims before formalizing facts.
2. Transform all thirty scenarios into complete, continuous layer snapshots,
   change sets and nonempty step sources. Validate the actual target asset shapes.
3. Create separate atomic truth labels for all thirty steps and obtain independent
   semantic review of requirements, snapshots, statements, sources and labels.
   Record actual creator/reviewer identities and provenance, without converting
   the AI-assisted draft into an untrue human-authorship assertion.
4. Version the evaluator and adapter for the received `2.0.0` schema; test
   per-side observed values against gold, including omission, single-side errors,
   common errors, conflicts, evidence spans, and answer-hash verification.
5. Freeze data/code/configuration before outputs; run and review a six-step dev
   pilot. Freeze the formal version after development-only changes.
6. Execute the planned 24-step, four-arm, three-repeat formal experiment (288
   planned units), preserving failures and raw outputs. Review blind, then report
   C, evaluability, common errors, success denominator and chain-level variation.

No paid model calls or database operations were executed in this intake audit.
The source document must not be used as the full-chain generation input because
it contains target states and evaluation guidance. Formal scores cannot be
calculated from the 30 scenario descriptions alone.
