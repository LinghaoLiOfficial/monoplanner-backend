"""Extract scenario rows from a specification without promoting them to gold data."""

import argparse
import hashlib
import json
import re
from pathlib import Path

from evals.dataset import PIN, TOPICS

HEADING = re.compile(r"^### 17\.\d+ chain-(\d{2})：([a-z_]+)（(dev|test)）$")
ROW = re.compile(r"^\| `(c\d{2}-s[123])` \| (.+) \| (.+) \|$")


def extract(source: Path) -> dict:
    raw = source.read_bytes()
    lines = raw.decode("utf-8").splitlines()
    chains = []
    current = None
    in_scenarios = False
    for number, line in enumerate(lines, 1):
        if line == "## 17. 十条需求链的填写内容":
            in_scenarios = True
        elif in_scenarios and line.startswith("## "):
            break
        if not in_scenarios:
            continue
        heading = HEADING.fullmatch(line)
        if heading:
            chain_number, topic, split = heading.groups()
            current = {
                "chain_id": f"chain-{chain_number}",
                "topic": topic,
                "split": split,
                "steps": [],
            }
            chains.append(current)
            continue
        row = ROW.fullmatch(line)
        if row:
            if current is None:
                raise ValueError(f"Step without chain at line {number}")
            step_id, requirement, boundary = row.groups()
            current["steps"].append(
                {
                    "step_id": step_id,
                    "requirement_text": requirement,
                    "boundary_text": boundary,
                    "source_line": number,
                }
            )
    if len(chains) != 10 or tuple(c["topic"] for c in chains) != TOPICS:
        raise ValueError("Expected ten preregistered topics in order")
    for index, chain in enumerate(chains, 1):
        expected = [f"c{index:02d}-s{step}" for step in range(1, 4)]
        if [step["step_id"] for step in chain["steps"]] != expected:
            raise ValueError(f"Incomplete or misordered steps in {chain['chain_id']}")
        if chain["split"] != ("dev" if index <= 2 else "test"):
            raise ValueError(f"Unexpected split in {chain['chain_id']}")
    return {
        "status": "candidate_unreviewed",
        "source_document": source.name,
        "source_sha256": hashlib.sha256(raw).hexdigest(),
        "source_commit": PIN,
        "chains": chains,
        "limitations": [
            "No independently reviewed atomic gold labels",
            "No complete old/new asset snapshots or change sets",
            "Not accepted by the generation or freeze CLI",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    candidate = extract(args.source)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8") as stream:
        json.dump(candidate, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
    print(f"Extracted {sum(len(c['steps']) for c in candidate['chains'])} draft steps")


if __name__ == "__main__":
    main()
