# Received Requirement-Label Dataset

`Monoplanner_New_Data_ZH.md` is the immutable source document used by the
`requirement-direct-v1` protocol. SHA-256: 
`10733be498330e8d023cb25542fd3f925310fb76206bc85fe8833fee17d8f6ba`.

`../inputs/monoplanner-new-data-v1.json` is a lossless structured extraction of
the following fields: chain identifier, topic, split, requirement origin, step
identifier, required sides, requirement text, preserved constraints, target
labels and source references. The generator never reads `labels`; it receives
only `raw_requirement` and `preserved_constraints`.

This release has 10 chains and 30 ordered steps: 6 development steps and 24
test steps. It does not contain layer-by-layer `old_versions`/`new_versions` or
`change_sets`; therefore it supports the direct prompt-pack protocol only, not
the complete orchestration protocol. The received target labels are reference
data. Semantic adjudication of generated packs is a separate, blinded review
activity and is not performed by the extraction step.
