# Monoplanner Evaluation Data

## Purpose

This directory contains the requirement-chain data, separate evaluation answers, reviewer-calibration cases, and public source evidence used to assess frontend/backend prompt synchronization. No production data, credentials, or identifiable user records are included.

The changes after the pinned repository state are designed scenarios. They are not presented as upstream issues, pull requests, or historical requirements.

## Releases

| Release | Scope | Role in the study |
| --- | --- | --- |
| `inputs/monoplanner-new-data-v1.json` | 10 chains, 30 consecutive changes | Original requirement-direct dataset. Chains 1-2 are development data; chains 3-10 are held-out test data. |
| `inputs/monoplanner-contract-v2-pilot.json` | 2 development chains, 6 changes | Refined contract-fact input used by the v2, v2.1, and v2.2 pilots. |
| `answers/monoplanner-contract-v2-pilot.json` | Expected facts and review metadata for the six v2 steps | Separate scoring reference; generation code does not accept this path. |
| `calibration/requirement-review-v2.json` | 25 labeled examples | Reviewer calibration only. These examples are not model-effectiveness observations. |
| `inputs/benchmark.json`, `answers/benchmark.json` | Earlier full-orchestration templates | Draft templates, not completed benchmark data and not used for reported results. |

The v1 release contains ten chains covering item validation, pagination, permissions, field renaming, null and clear behavior, errors, filtering and sorting, deletion and restoration, user profiles, and scope clarification. Each chain starts independently and contains three stateful changes.

## v2 contract facts

The refined protocol separates two concepts:

- `change_facts` describe what the current requirement adds, modifies, removes, or rolls back.
- `active_contract_facts` describe the contract that is active after the change, including inherited rules needed as context.

Each contract fact records a stable ID, a complete statement, operation, state, category, applicable sides, coverage policy, change type, source type, superseded facts, and sources. `must_be_explicit` facts must appear in every applicable prompt. `derivable` facts remain available to generation but do not become omissions merely because they are not repeated verbatim.

`required_sides` is fact-specific. Shared API behavior can require both prompts, while interface-only or backend-only responsibilities require one side. This prevents a local implementation detail from being scored as a cross-stack omission.

## Source provenance

The starting system is the MIT-licensed FastAPI full-stack template at commit `1762adac607a1b29cfc4da129557780beea71616`. `sources/manifest.json` records selected upstream files and immutable source URLs; `sources/LICENSE` preserves the upstream license. The checked-in excerpts support offline inspection without copying the entire repository.

Existing repository facts cite the pinned source. Hypothetical changes cite their requirement step, for example `requirement:c02-s1`.

## Separation and leakage controls

- Input and answer files are separate.
- Generation commands load inputs but have no answer-file argument.
- Review export shuffles units and withholds method identities until reporting.
- Whole chains stay within one split; steps from the same chain never cross development and test sets.
- Each run writes to a new directory and refuses to overwrite history.
- Model requests, responses, parsed packs, usage, failures, and retries are retained under the matching run.

The v2 generator receives contract statements, applicable sides, and coverage requirements because these are necessary task inputs. Expected values and review judgments remain in the answer and review files.

## Dataset limitations

The source context comes from one public repository. The changes are authored scenarios rather than observed production requests. The v2 schema currently covers only the two development chains. The dataset does not include complete old/new asset snapshots and change sets for all ten chains, so it cannot support a valid full database-backed orchestration experiment without adding new authored data.

## Validation

Run from the backend repository root:

```bash
uv run python -m evals.requirement_eval_v2 report \
  results/v2.1-dev-pilot-20261004 \
  /tmp/monoplanner-v2.1-report.json \
  --reviews results/v2.1-dev-pilot-20261004/review/reviews.json

uv run pytest evals/tests --confcutdir=evals -q
```

Choose fresh output paths because the evaluation writer intentionally prevents overwriting prior artifacts.
