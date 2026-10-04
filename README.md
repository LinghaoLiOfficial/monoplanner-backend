# Monoplanner

Monoplanner turns an evolving product requirement into versioned design assets and a synchronized frontend and backend prompt pack. It is intended for a technical lead who already uses coding agents and needs both sides of a full-stack change to receive the same current contract.

This repository is the canonical submission repository. It contains the FastAPI service, worker, prompt orchestration, dataset, evaluation code, raw evaluation artifacts, final report, demo script, and product documentation. The user interface is maintained in the separate [monoplanner-frontend](https://github.com/LinghaoLiOfficial/monoplanner-frontend) repository.

## Submission guide

| Deliverable | Location |
| --- | --- |
| Final report | `REPORT.docx` |
| Demo narration and screen plan | `DEMO_SCRIPT.md` |
| Persona, architecture, inputs, outputs, and metrics | `PRODUCT_DOCUMENTATION.md` |
| Dataset and provenance | `data/README.md` |
| Evaluation protocol and commands | `evals/README.md` |
| Canonical results and evidence boundaries | `results/README.md` |

The final evaluated claim is deliberately narrow: Monoplanner is assessed on whether one requirement change produces a prompt pack with complete and mutually compatible frontend and backend implementation instructions. The project does not claim measured improvements in generated code quality or developer productivity.

## Architecture

The browser calls a FastAPI API. Long-running generation requests are stored in PostgreSQL and claimed by a background worker. The worker invokes an OpenAI-compatible LLM, validates structured responses, and persists versioned requirements, change sets, design assets, and prompt packs. The evaluation CLI calls the database-free prompt-pack core so methods can be compared without cache or project-state leakage.

See `PRODUCT_DOCUMENTATION.md` for the architecture diagram, module map, persona, and measured results.

## Prerequisites

- Python 3.12 or later
- `uv`
- PostgreSQL 14 or later
- Node.js and `pnpm` for the separate frontend
- An OpenAI-compatible API key only when running new LLM generation

## Backend setup

```bash
uv sync --group dev
cp .env.example .env
```

Create separate development and test databases:

```bash
createdb context_orchestrator
createdb context_orchestrator_test
```

Set local values in `.env`. Never commit a real key:

```env
DATABASE_URL=postgresql+psycopg://USER@localhost:5432/context_orchestrator
TEST_DATABASE_URL=postgresql+psycopg://USER@localhost:5432/context_orchestrator_test
LLM_BASE_URL=https://your-openai-compatible-host/v1
LLM_API_KEY=replace-locally
LLM_MODEL=your-model
LLM_TASK_CONFIG_PATH=config/llm-task-mapping.local.json
```

Apply migrations, then start the API and worker in separate terminals:

```bash
uv run python -m alembic upgrade head
uv run python -m uvicorn app.main:app --reload
```

```bash
uv run python -m app.workers.generation_worker
```

The API is available at `http://127.0.0.1:8000`; OpenAPI documentation is at `http://127.0.0.1:8000/docs`. `make dev-all` applies migrations and starts both backend processes.

## Frontend setup

Clone the frontend as a sibling directory, then run:

```bash
cd ../monoplanner-frontend
pnpm install
cp .env.example .env
pnpm dev
```

The frontend expects `NEXT_PUBLIC_API_BASE_URL=http://localhost:8000/api/v1` and is available at `http://localhost:3000`.

## Prepared demo flow

Use a project whose assets and prompt pack have already completed so the recording does not depend on network latency.

1. Open a project and show its configuration and requirement history.
2. Open the business story and change set for one requirement change.
3. Show the resulting API, database, frontend, and backend assets.
4. Open the prompt-pack page and compare the frontend and backend instructions.
5. Show `data/README.md`, `evals/README.md`, and the final evidence indexed by `results/README.md`.

The exact timing and narration are in `DEMO_SCRIPT.md`.

## Evaluation reproduction

The checked-in reports can be recomputed without a database or paid API call:

```bash
uv run python -m evals.requirement_eval_v2 report \
  results/v2.1-dev-pilot-20261004 \
  /tmp/monoplanner-v2.1-report.json \
  --reviews results/v2.1-dev-pilot-20261004/review/reviews.json
```

This command refuses to overwrite an existing output path. Choose a fresh path when repeating it. See `evals/README.md` for the v1 protocol, review rules, metric definitions, and new-run commands.

## Verification

Run the evaluation tests without loading the database-mutating application fixtures:

```bash
uv run pytest evals/tests --confcutdir=evals -q
uv run ruff check evals app/services/prompt_pack_core.py app/services/prompt_pack_generation_service.py
```

Frontend checks run in the sibling repository:

```bash
pnpm lint
pnpm exec tsc --noEmit
pnpm build
```

The full backend test suite creates and drops tables. Run it only with `TEST_DATABASE_URL` pointing to a disposable database whose name ends in `_test`:

```bash
uv run pytest
```

## Troubleshooting

- A generation endpoint returns `503` when no recent worker heartbeat exists. Start `app.workers.generation_worker` and retry.
- A queued run does not complete when the worker cannot reach PostgreSQL or the configured model provider. Inspect the API and worker logs and verify `.env` locally.
- The evaluation runner rejects configuration drift from its recorded protocol. Use the checked-in configuration for reproduction instead of changing model or retry settings.
- A report command fails when its destination exists because evaluation artifacts are intentionally immutable. Select a new output path.
- Do not use the application development database for evaluation or tests. The full-orchestration runner requires a separately provisioned database ending in `_eval`.

## Evidence boundary

The repository contains a 10-chain, 30-step requirement dataset and an eight-chain v1 test run, plus a refined two-chain v2 development pilot. The v2.1 human review is the final semantic evidence. The v2.2 run is an automatic regression check only. A full database-backed orchestration experiment was not completed because the supplied dataset does not contain the required old and new asset snapshots and change sets.
