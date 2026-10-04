# Prompt Synchronization Evaluations

## Evaluated question

The evaluation asks whether one requirement change produces a frontend prompt and a backend prompt that state a complete, mutually compatible implementation contract. It does not grade the coding agent, generated application code, build success, or developer productivity.

The evaluation code records generation inputs and outputs, exports blind review packets, validates evidence, calculates metrics, and recomputes reports offline. It does not automatically repair contradictions or use a model as final ground truth.

## Compared methods

The final experiments compare two methods:

- `rule`: a deterministic baseline that copies the same explicit contract facts to every applicable side.
- `joint`: Monoplanner generates the frontend and backend prompts together through the database-free prompt-pack core and the production structured-output validator.

Both methods receive the same visible requirement and contract input. The rule method makes no model call. The joint method used `openai/gpt-5-mini`, temperature `0.2`, and at most two structured-output retries through an OpenAI-compatible endpoint.

Earlier code also supports an independent two-call method and a database-backed full-chain method. They are not part of the final two-method result. The full-chain method was not run because the completed dataset lacks the necessary asset snapshots and change sets.

## Metric definitions

| Metric | Definition |
| --- | --- |
| Structural validity | Completed packs with both required sides and valid schema divided by all planned packs |
| Marker coverage | Required prompt-side occurrences containing the expected stable fact marker divided by all required occurrences |
| Exact statement coverage | Required prompt-side occurrences containing the full expected statement divided by all required occurrences |
| Explicit semantic coverage | Facts judged consistent divided by all reviewed `must_be_explicit` facts |
| Evaluable rate | Packs with no omission and no uncertain fact divided by all planned packs |
| `C_evaluable` | Deduplicated contradiction facts found in fully evaluable packs |
| `C_observed` | Deduplicated contradiction facts found anywhere in the reviewed set |
| Strict success rate | Structurally valid, evaluable packs with zero contradictions and zero common errors divided by all planned packs |
| Omission, uncertainty, common-error rates | Each fact label count divided by all reviewed facts |

`C_evaluable = 0` does not mean the system succeeded when packs are incomplete or uncertain. Reports must show evaluability, strict success, observed contradictions, and coverage together.

## Human review rules

Each required fact receives one label:

- `consistent`: every applicable side expresses the expected meaning.
- `contradiction`: the frontend and backend prompts contain two facts that cannot both be true for the same operation and state. Evidence from both prompts is required.
- `omission`: at least one required side does not express a `must_be_explicit` fact.
- `uncertain`: the wording cannot be classified reliably.
- `common_error`: both sides agree with each other but disagree with the expected contract.

Repeated wording of the same semantic fact counts once. A derivable fact is not an omission merely because it is not repeated. Review files require named human attestation and quoted evidence; otherwise semantic metrics remain `null`.

## Recompute checked-in results

Recompute the v2.1 report without a model call or database:

```bash
uv run python -m evals.requirement_eval_v2 report \
  results/v2.1-dev-pilot-20261004 \
  /tmp/monoplanner-v2.1-report.json \
  --reviews results/v2.1-dev-pilot-20261004/review/reviews.json
```

Recompute the v1 diagnostic report:

```bash
uv run python -m evals.requirement_eval report \
  results/test-run-20261003-two-methods \
  /tmp/monoplanner-v1-report.json \
  --reviews results/test-run-20261003-two-methods/review/reviews.json
```

Output files are immutable; remove neither historical results nor failed units to improve a denominator.

## Run a new v2 pilot

A new run requires a configured model API and creates new recorded artifacts:

```bash
uv run python -m evals.requirement_eval_v2 run \
  data/inputs/monoplanner-contract-v2-pilot.json \
  results/<new-run-directory> \
  --workers 6

uv run python -m evals.requirement_eval_v2 report \
  results/<new-run-directory> \
  results/<new-run-directory>/report.json

uv run python -m evals.requirement_eval_v2 review-export \
  results/<new-run-directory> \
  results/<new-run-directory>/review
```

Do not use the separate answer file during generation. Do not copy prior labels onto changed outputs.

## Recorded execution

Every model unit stores redacted request messages, schema, raw response, parsed output, retry records, usage, and failure state. Transport attempts are bounded. Structural retries request schema correction only and do not ask the model to repair semantic contradictions. Missing usage or cost remains unknown rather than becoming zero.

Each repeated model run must use an independent unit directory. The application service cache is bypassed by the database-free prompt-pack core, so a prior pack cannot satisfy a new experimental unit.

## Database safety

The reported v1 and v2 prompt-pack experiments do not require a database. The separate full-chain runner accepts only an explicit PostgreSQL URL whose database name ends in `_eval`, uses an isolated schema, and never accepts the application database. The ordinary backend test suite can create and drop tables; do not run it against development or production data.

## Software verification

```bash
uv run pytest evals/tests --confcutdir=evals -q
uv run ruff check evals app/services/prompt_pack_core.py app/services/prompt_pack_generation_service.py
```

The tests use synthetic fixtures to verify scoring categories, deduplication, omission handling, common errors, ambiguity, rollback, failed-unit retention, cache isolation, answer-file separation, immutable output, bounded retries, blinding, and deterministic replay. Passing tests demonstrate evaluation-software behavior, not model effectiveness.
