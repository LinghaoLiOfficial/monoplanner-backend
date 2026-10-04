# Development Pilot Results

## Scope

Protocol: `requirement-direct-v1`.

Dataset: `monoplanner-new-data-v1`; source SHA-256:
`10733be498330e8d023cb25542fd3f925310fb76206bc85fe8833fee17d8f6ba`.

Split: development only (`chain-01` and `chain-02`), six sequential change
steps. Methods: `rule`, `independent`, and `joint`. Each method ran once,
giving 18 planned prompt-pack units. The model configuration is recorded in
`manifest.json`; model outputs, requests, parsed data, retries, and usage reside
under `units/`.

## Actual execution

All 18 units completed without transport or structured-output failure. Eighteen
model responses were recorded. Provider-reported aggregate usage was 60,542
tokens and cost was 0.11305675. The deterministic rule arm made no model call.

The structure check detected one invalid package:

| Unit | Finding | Treatment |
| --- | --- | --- |
| `chain-01-c01-s1-independent-r1` | required-side scope mismatch | invalid; cannot receive `C=0` |

No other automatic structural issue was detected. This is not a semantic
correctness result: structure checking cannot establish that front-end and
back-end directions agree on an atomic contract fact.

## Semantic metric status

Before review, `C_total`, `C_mean`, and `valid_zero_rate` were correctly retained
as `null`. The invalid package remains in the planned denominator and cannot be
discarded to improve a rate. The completed reviewed report is
`report-reviewed-final.json`:

| Metric | Result |
| --- | ---: |
| `C_total` | 0 |
| `C_mean` among 7 evaluable units | 0.0 |
| Evaluable rate | 7/18 = 38.89% |
| Strict zero rate over all planned units | 7/18 = 38.89% |
| Invalid structural units | 1/18 |
| Not evaluable units | 10/18 |
| Reviewed fact labels | 158 consistent, 35 omission, 25 uncertain, 1 common error |

The zero contradiction result is therefore conditional: it applies to the 7
evaluable units only. The strict all-unit result is 38.89%, far below the
pre-registered 90% target, because omission and uncertainty are retained as
failures rather than hidden. The detailed metric definitions and dataset changes
are in `data/DATASET_AND_METRIC_OPTIMIZATION_ZH.md`.

Review material is in `review/packets.json`. It intentionally omits the method
and unit identity. A reviewer completes a copy of `review/reviews.template.json`
as `review/reviews.json`, including named attestation, per-fact label,
explanation, and quoted character-offset evidence. The reviewer must not inspect
`review/blind-key.json` before completion. Generate a post-review report with:

```sh
.venv/bin/python -m evals.requirement_eval report \
  results/dev-pilot-20261003 results/dev-pilot-20261003/report-reviewed.json \
  --reviews results/dev-pilot-20261003/review/reviews.json
```

## Boundary

The supplied release does not contain old/new assets, layer change sets, or
intermediate generated states. Full orchestration cannot be evaluated without
fabricating those inputs, so this run records
`fullchain: not_run_missing_asset_snapshots`. It is a development pilot only,
not the planned formal 24-step, three-repeat test set evaluation.
