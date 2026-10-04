from __future__ import annotations

import json
from typing import Any

from app.prompts.templates.prompt_pack.output_schema import PromptPackSection
from app.services.prompt_pack_core import generate_prompt_pack_content
from evals.dataset import PackInput


def rule_pack(value: PackInput) -> dict[str, Any]:
    scope = (value.selected_story or {}).get("implementation_scope", "fullstack")
    context = json.dumps(value.model_dump(), ensure_ascii=False, indent=2)
    output: dict[str, Any] = {
        "batch_summary": "Rule baseline: explicit shared context, no semantic transformation",
        "implementation_scope": scope,
        "diff_summary": {},
        "execution_order": [],
        "acceptance_checklist": [],
        "rollback_notes": [],
    }
    for side in ("frontend", "backend"):
        needed = scope in {"fullstack", f"{side}_only"}
        output[f"{side}_prompt"] = {
            "needed": needed,
            "title": f"{side} instructions",
            "prompt": (
                f"Implement only the {side} responsibilities from the following context. "
                "Old versions are historical, not the target. Preserve unchanged constraints.\n"
                + context
            )
            if needed
            else "No changes required on this side.",
            "affected_files": [],
            "do_not_modify": [],
            "verification_steps": [],
        }
        if needed:
            output["execution_order"].append(f"{side}_prompt")
    return output


def independent_pack(value: PackInput, generate_json) -> dict[str, Any]:
    output = rule_pack(value)
    for side in ("frontend", "backend"):
        output[f"{side}_prompt"] = generate_json(
            f"You generate {side} coding instructions only, not code. "
            "Decide whether this side needs changes; set needed=false with a reason if not. "
            "Use the target snapshot and changes; do not implement historical superseded rules. "
            "Do not invent unresolved contract decisions.",
            json.dumps(value.model_dump(), ensure_ascii=False, indent=2),
            response_model=PromptPackSection,
            task_key="prompt_pack",
        )
    output["execution_order"] = [
        f"{s}_prompt" for s in ("backend", "frontend") if output[f"{s}_prompt"]["needed"]
    ]
    return output


def joint_pack(value: PackInput, generate_json) -> dict[str, Any]:
    return generate_prompt_pack_content(**value.model_dump(), generate_json=generate_json)
