"""Reproducible CLI; generation never opens the answer file."""

import argparse
import json
from pathlib import Path

from evals.dataset import freeze, validate_pair
from evals.reports import export_reviews, report
from evals.runner import METHODS, configured_database, run
from evals.storage import ROOT


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("validate", "freeze", "generate", "review-export", "report", "replay"):
        sub = commands.add_parser(name)
        if name in {"validate", "freeze", "generate"}:
            sub.add_argument("--inputs", type=Path, default=ROOT / "data/inputs/benchmark.json")
        if name != "generate":
            sub.add_argument("--answers", type=Path, default=ROOT / "data/answers/benchmark.json")
        if name == "freeze":
            sub.add_argument("--stage", choices=("pilot", "formal"), required=True)
            sub.add_argument("--pilot-run", type=Path)
        if name == "generate":
            sub.add_argument("--lock", type=Path, required=True)
            sub.add_argument("--split", choices=("dev", "test"), required=True)
            sub.add_argument("--methods", nargs="+", choices=METHODS, default=list(METHODS))
            sub.add_argument("--repeats", type=int, default=3)
        if name in {"review-export", "report", "replay"}:
            sub.add_argument("--run", type=Path, required=True)
        if name in {"report", "replay"}:
            sub.add_argument("--reviews", type=Path)
        if name != "validate":
            sub.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        if args.command == "validate":
            data, _ = validate_pair(args.inputs, args.answers)
            print(json.dumps({"valid": True, "chains": len(data.chains), "steps": 30}))
        elif args.command == "freeze":
            freeze(args.inputs, args.answers, args.output, args.stage, args.pilot_run)
        elif args.command == "generate":
            run(
                args.inputs,
                args.lock,
                args.output,
                args.split,
                args.methods,
                args.repeats,
                configured_database(),
            )
        elif args.command == "review-export":
            export_reviews(args.run, args.answers, args.output)
        else:
            result = report(args.run, args.answers, args.reviews, args.output)
            print(json.dumps(result["overall"], indent=2))
    except (ValueError, OSError, KeyError) as exc:
        parser.exit(2, f"Evaluation stopped: {exc}\n")


if __name__ == "__main__":
    main()
