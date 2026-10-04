# Received specification and scenario intake

`Monoplanner_Data_Specification_ZH_v2.md` is a byte-for-byte copy of the
received specification (SHA-256
`a92983e73c9a9fc627dccf47124609343c284a02fb9b282efd323fd90947f55b`).
It contains a completed protocol draft and thirty scenario descriptions, **not**
a frozen, reviewed ground-truth dataset. The document itself explicitly records
that no complete JSON release, independent answer review, pilot or formal run
exists.

`scenario-candidates.json` extracts the requirement and boundary cells in section
17, preserving their source line numbers. Its `candidate_unreviewed` status is
intentional; the generation runner does not accept this file as benchmark input.
Re-extract into a *new* path using:

```sh
.venv/bin/python -m evals.intake \
  data/intake/Monoplanner_Data_Specification_ZH_v2.md \
  data/intake/scenario-candidates-next.json
```

The received document includes AI-assisted scenario authorship and explicitly
states that independent human review has not happened. It must not be relabeled
`human_handwritten` or supplied with a fabricated attestation to satisfy the
existing `evals.dataset` model. Adapting that provenance model requires an
explicitly revised protocol and transparent reporting.

See `results/intake-audit.md` for experiment readiness and actual test results.
