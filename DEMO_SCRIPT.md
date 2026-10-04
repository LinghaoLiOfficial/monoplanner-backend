# Monoplanner Demo Script

## Recording setup

- Target duration: 5 minutes 30 seconds. Keep the final recording below 8 minutes.
- Keep the webcam visible throughout without covering navigation, prompts, or result values.
- Use a prepared project with completed requirements, assets, and prompt packs. Do not wait for a live model call.
- Set browser zoom so the requirement, frontend prompt, and backend prompt are readable.
- Open these tabs before recording: Monoplanner project, `PRODUCT_DOCUMENTATION.md`, `data/README.md`, `evals/README.md`, and `results/README.md`.
- Disable notifications and hide terminals or files that could expose credentials.

## 0:00 to 0:35 Problem and contribution

**Screen:** Show the Monoplanner project page with the webcam overlay visible.

**Narration:**

Hello, I am Li Linghao. Monoplanner addresses a specific failure mode in AI-assisted full-stack development. When a requirement changes, teams often rewrite frontend and backend prompts separately. Shared rules such as field types, validation limits, permissions, pagination, and errors can then diverge. Monoplanner stores the evolving project context and generates a versioned frontend and backend prompt pack from the same change. My final evaluation measures that synchronization directly rather than using code quality or build success as a proxy.

## 0:35 to 1:15 Product architecture

**Screen:** Open the architecture diagram in `PRODUCT_DOCUMENTATION.md` and point to each box as it is mentioned.

**Narration:**

The Next.js interface sends requests to a FastAPI service. Generation work is recorded in PostgreSQL and claimed by a background worker, so long model calls do not block the API. The worker sends structured prompts to an OpenAI-compatible model, validates the response, and stores versioned requirements, change sets, design assets, and prompt packs. I own this orchestration, persistence, validation, queue, and evaluation code. I rent only model inference. The evaluation runner calls the same prompt-pack core without database cache lookup, which keeps experimental units isolated.

## 1:15 to 3:15 Requirement to prompt pack

**Screen:** Return to the prepared project. Open the requirement history, then the selected business story.

**Narration:**

This project keeps the original requirement and later revisions instead of replacing the history. I select the business story that represents the change and inspect its scope before execution.

**Screen:** Open the associated change set and scroll through the affected layers.

**Narration:**

The change set identifies which product layers must change. This separates the requested change from the generated asset versions and makes the transition reviewable.

**Screen:** Open one API or database asset, then the frontend and backend implementation assets. Show the current version indicator and history briefly.

**Narration:**

Each affected layer becomes a versioned asset. The previous version remains available, while the current version becomes context for the next change. This prevents the prompt generator from relying only on the latest sentence from the user.

**Screen:** Open the prompt-pack page. Place the frontend and backend instructions in view and highlight one shared contract fact.

**Narration:**

The final prompt pack contains separate implementation instructions for frontend and backend coding agents. Both prompts receive the same current contract, but each prompt can also include responsibilities specific to its side. The key review question is simple: for the same operation and state, do the two prompts state facts that cannot both be true, and have they explicitly covered every required shared fact?

## 3:15 to 4:45 Data evaluation and results

**Screen:** Open `data/README.md`, show the dataset table, then open `evals/README.md` and its metric definitions.

**Narration:**

The repository checks in the data, evaluation code, model requests, raw responses, review evidence, and reports. The dataset contains ten requirement chains with three consecutive changes each, grounded in a pinned public full-stack repository. The first evaluation used eight held-out chains, two methods, and 48 prompt packs. Human review covered 688 fact judgments. Strict success was only 27.08 percent, with a 39.68 percent omission rate and two observed contradictions.

That result exposed a problem in my measurement design. The scorer expected historical contract facts that were not always present in the model input. I revised the data model to separate facts changed now from the active contract, and I assigned applicability and coverage requirements to each fact.

**Screen:** Open `results/README.md` and point to the v2.1 row and then the v2.2 row.

**Narration:**

The refined v2.1 pilot evaluated 12 packs and 82 facts. Structural, marker, and exact-statement coverage were 100 percent. Human semantic coverage reached 98.78 percent, and overall strict success reached 91.67 percent. The joint model method reached only 83.33 percent because one optional HTML validation suggestion could count Unicode text differently from the stated contract. I then removed semantically unsafe optional suggestions. The v2.2 automatic regression reached 100 percent on structural and exact coverage checks, but I did not perform another human review, so I do not claim a v2.2 semantic success rate.

## 4:45 to 5:30 Critique and future work

**Screen:** Return to the limitations and future-path sections in `PRODUCT_DOCUMENTATION.md`.

**Narration:**

The strongest outcome is the evaluation discipline rather than evidence that an LLM beats a rule template. In v2.1, the deterministic rule baseline passed every pack, while the joint method did not. The study also uses one source repository, two refined development chains, one reviewer, and one model repetition. The complete database-backed workflow was not evaluated because the dataset does not yet contain authored asset snapshots and change sets.

The next step is to extend the refined protocol to the eight held-out chains, use sampled or two-stage review, add a second reviewer, and run repeated paired trials. Monoplanner now provides a working versioned workflow and transparent evidence, but its broader productivity value remains a hypothesis for future testing. Thank you.

## No network fallback

If the application or model provider is unavailable during recording, do not retry on camera. Show the prepared screenshots or completed project pages, then use the checked-in `PRODUCT_DOCUMENTATION.md`, `results/README.md`, v2.1 report JSON, and recorded prompt-pack outputs. State that the demo uses recorded evidence from the completed run.

## Final recording check

- Face and screen are both visible.
- No API key, `.env`, user email, or database credential appears.
- The audio is clear and the pointer follows the narration.
- The video demonstrates one requirement change and both prompt sides.
- Metric claims match the checked-in reports.
- The recording is between 4 and 8 minutes.
