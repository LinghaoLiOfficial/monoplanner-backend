# Test-Set Run Results

## Experiment scope

This run uses the eight held-out chains (`chain-03` through `chain-10`), containing
24 sequential requirement changes. Per the revised runtime scope, it compares two
methods once per change:

- `rule`: deterministic shared-contract baseline with no model call.
- `joint`: Monoplanner synchronized frontend/backend prompt generation.

The run therefore contains 24 changes x 2 methods x 1 repeat = 48 planned units.
It does not estimate repeat-to-repeat variance and does not include the separate
frontend/backend generation method.

## Execution results

| Item | Result |
| --- | ---: |
| Planned units | 48 |
| Completed units | 48 |
| Generation failures | 0 |
| Structural-invalid units | 0 |
| Actual model calls | 24 |
| Provider-reported tokens | 114,707 |
| Provider-reported cost | 0.215806 |

Every request, raw response, parsed prompt pack and usage record is retained under
`units/`. The rule method generated 24 deterministic packages without model calls;
the joint method made one successful model call for each of the 24 changes.

## Final reviewed metrics

Automatic structure checks found no required-side mismatch or empty required
prompt. The submitted review covers all 48 packages and 688 facts.

| Metric | All packages | `rule` | `joint` |
| --- | ---: | ---: | ---: |
| Planned units | 48 | 24 | 24 |
| Completed units | 48 | 24 | 24 |
| Evaluable units | 13 (27.08%) | 7 (29.17%) | 6 (25.00%) |
| Strict zero units | 13 (27.08%) | 7 (29.17%) | 6 (25.00%) |
| Observed contradictions | 2 | 0 | 2 |
| Omission facts | 273 (39.68%) | 138 | 135 |
| Uncertain facts | 4 (0.58%) | 2 | 2 |
| Common-error facts | 1 (0.15%) | 0 | 1 |

The effective contradiction count `C_total` among evaluable packages is 0 and
`C_mean` is 0.0. Separately, two contradictions were observed in one package
that also contained omissions, so they are reported as `observed_C_total=2`
instead of being silently treated as a successful zero. The strict all-unit
success rate is 13/48 = 27.08%, below the 90% target.

The paired comparison contains 24 rule/joint pairs: joint has 0 strict wins,
rule has 1, and 23 are ties. Joint has three fewer omission labels overall but
two observed contradictions; this is not evidence of improvement because most
packages remain non-evaluable.

Review inputs are under `review/`:

- `packets.json`: 48 shuffled prompt packages and 688 fact assessments.
- `reviews.template.json`: output template to complete as `reviews.json`.
- `REVIEW_SUBMISSION_GUIDE_ZH.md`: submission and evidence rules.
- `blind-key.json`: sealed method mapping; do not inspect before review completion.

The machine-readable final report is `report-reviewed-final.json`. The command
used to reproduce it was:

```sh
.venv/bin/python -m evals.requirement_eval report \
  results/test-run-20261003-two-methods \
  results/test-run-20261003-two-methods/report-reviewed.json \
  --reviews results/test-run-20261003-two-methods/review/reviews.json
```

## Coverage boundary

This is a requirement-direct prompt-pack evaluation, not a complete database-backed
requirement-to-assets workflow. The supplied dataset contains no old/new asset
snapshots or change sets, so the complete orchestration layer remains
`not_run_missing_asset_snapshots`. Invented snapshots are not used to fill that gap.
