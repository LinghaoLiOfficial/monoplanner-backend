# Evaluation Results

## Canonical evidence

Use the following three releases for the final submission. They answer different questions and must not be combined into one score.

| Release | Status | What it establishes |
| --- | --- | --- |
| `test-run-20261003-two-methods/report-reviewed-final.json` | Completed v1 diagnostic test | 48/48 packs completed. Human review of 688 facts found 27.08% strict success, 39.68% omissions, two observed contradictions, four uncertain facts, and one common error. It revealed that the v1 inputs and scoring expectations were misaligned. |
| `v2.1-dev-pilot-20261004/report-reviewed-final.json` | Final human semantic evidence | 12/12 packs completed. Structural, marker, and exact-statement coverage were 100%. Human review of 82 facts found 81 consistent and one uncertain, for 98.78% semantic coverage and 91.67% overall strict success. The joint method reached 83.33% strict success. |
| `v2.2-dev-pilot-20261004/report.json` | Final automatic regression evidence | 12/12 packs completed with 100% structural, marker, and exact-statement coverage. The known unsafe optional suggestion disappeared. No new human review was performed, so semantic metrics remain undefined. |

`EVALUATION_FINAL_DECISION_ZH.md` records the decision not to repeat the same 82-item human review for v2.2. The v2.1 labels are not copied to the changed v2.2 outputs.

## Final interpretation

The v1 result is evidence about the original protocol as well as the two generation methods. Its high omission rate largely came from expecting inherited facts that were not explicitly supplied to either method. The result therefore motivated a data-model correction rather than a claim that model generation had failed in isolation.

The v2.1 result shows that the revised contract-fact protocol can measure explicit synchronization without hiding omissions behind a zero contradiction count. Its overall strict-success rate exceeds the 90% target, but the Monoplanner joint method alone reaches 83.33% while the deterministic rule baseline reaches 100%. The available evidence does not show that joint model generation outperforms contract copying.

The v2.2 run verifies structure and literal coverage after a prompt change that forbids optional implementation suggestions with different boundary semantics. Automatic checks cannot establish semantic correctness. Accordingly, v2.2 has no reported `C_evaluable`, `C_observed`, evaluability rate, or strict-success rate.

## Supporting contents

Each completed run retains:

- `manifest.json` with protocol and effective public model configuration;
- `dataset.json` with the exact run input;
- `units/<unit-id>/` with pack inputs, outputs, and recorded calls;
- `review/packets.json` and `review/reviews.json` with blind-review material and judgments;
- report JSON with per-unit and aggregate metrics.

Provider authorization values are not stored. Review ZIP files are convenience copies of the same materials and are not additional experiments.

## Historical and non-canonical runs

- `dev-pilot-20261003` is an early three-method development pilot.
- `v2-dev-pilot-20261003` is the first contract-fact pilot and exposed fact-ID-only output and omission problems.
- Directories containing `partial`, `cancelled`, `parallel`, `serial`, or `late` are retained execution history. They are not final results and must not be used to replace failed units or inflate the sample size.
- `software-tests.xml` records an earlier evaluation-software test run. It is not a model-effectiveness result.

No historical directory is deleted or overwritten when the protocol changes.

## Reproduction

From the backend repository root:

```bash
uv run python -m evals.requirement_eval_v2 report \
  results/v2.1-dev-pilot-20261004 \
  /tmp/monoplanner-v2.1-report.json \
  --reviews results/v2.1-dev-pilot-20261004/review/reviews.json

uv run python -m evals.requirement_eval report \
  results/test-run-20261003-two-methods \
  /tmp/monoplanner-v1-report.json \
  --reviews results/test-run-20261003-two-methods/review/reviews.json
```

These commands make no API call and require no database. Compare the recomputed aggregate fields with the canonical JSON reports. Use a fresh destination each time because the writer does not overwrite existing artifacts.

## Evidence boundary

The evidence is limited to one public source repository, ten authored requirement chains, one reviewer, and one model repetition per tested change. The refined v2 result covers two development chains. No database-backed full-orchestration experiment was completed, and no result supports a general claim about code quality, implementation speed, or all software projects.
